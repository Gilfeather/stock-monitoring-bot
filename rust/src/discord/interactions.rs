use anyhow::Result;
use crate::models::{DiscordInteraction, InteractionResponse};
use crate::database::DynamoClient;
use crate::stocks::StockClient;

pub struct InteractionHandler {
    pub dynamo_client: DynamoClient,
    pub stock_client: StockClient,
}

impl InteractionHandler {
    pub fn new(dynamo_client: DynamoClient, stock_client: StockClient) -> Self {
        Self {
            dynamo_client,
            stock_client,
        }
    }

    pub async fn handle_interaction(&self, interaction: DiscordInteraction) -> Result<InteractionResponse> {
        // PING応答
        if interaction.interaction_type == 1 {
            return Ok(InteractionResponse::pong());
        }

        // アプリケーションコマンド
        if interaction.interaction_type == 2 {
            return self.handle_application_command(interaction).await;
        }

        Ok(InteractionResponse::ephemeral_message(
            "❌ 未対応の操作タイプです".to_string()
        ))
    }

    async fn handle_application_command(&self, interaction: DiscordInteraction) -> Result<InteractionResponse> {
        let data = interaction.data.ok_or_else(|| anyhow::anyhow!("Missing interaction data"))?;
        let user_id = self.get_user_id(&interaction)?;

        match data.name.as_str() {
            "list" => self.handle_list_command(&user_id).await,
            "add" => self.handle_add_command(&data, &user_id).await,
            "remove" => self.handle_remove_command(&data, &user_id).await,
            "price" => self.handle_price_command(&data).await,
            "alert" => self.handle_alert_command(&data, &user_id).await,
            "chart" => self.handle_chart_command(&data).await,
            _ => Ok(InteractionResponse::ephemeral_message(
                format!("❌ 未知のコマンド: {}", data.name)
            )),
        }
    }

    fn get_user_id(&self, interaction: &DiscordInteraction) -> Result<String> {
        if let Some(member) = &interaction.member {
            if let Some(user) = &member.user {
                return Ok(user.id.clone());
            }
        }
        
        if let Some(user) = &interaction.user {
            return Ok(user.id.clone());
        }

        Err(anyhow::anyhow!("User ID not found"))
    }

    fn get_option_value(&self, data: &crate::models::InteractionData, name: &str) -> Option<String> {
        data.options.as_ref()?
            .iter()
            .find(|opt| opt.name == name)?
            .value
            .as_ref()?
            .as_str()
            .map(|s| s.to_string())
    }

    async fn handle_list_command(&self, user_id: &str) -> Result<InteractionResponse> {
        match self.dynamo_client.get_user_watchlist(user_id).await {
            Ok(watchlist) => {
                if watchlist.is_empty() {
                    Ok(InteractionResponse::ephemeral_message(
                        "📊 監視銘柄はありません。\n`/add` コマンドで銘柄を追加してください。".to_string()
                    ))
                } else {
                    let mut content = "📊 あなたの監視銘柄:\n".to_string();
                    for item in watchlist {
                        content.push_str(&format!("• {} ", item.symbol));
                        if let Some(threshold) = item.alert_threshold {
                            content.push_str(&format!("(アラート: ${:.2})", threshold));
                        }
                        content.push('\n');
                    }
                    Ok(InteractionResponse::message(content))
                }
            }
            Err(e) => {
                tracing::error!("Failed to get watchlist: {}", e);
                Ok(InteractionResponse::ephemeral_message(
                    "❌ 監視リストの取得に失敗しました".to_string()
                ))
            }
        }
    }

    async fn handle_add_command(&self, data: &crate::models::InteractionData, user_id: &str) -> Result<InteractionResponse> {
        let symbol = match self.get_option_value(data, "symbol") {
            Some(s) => s.to_uppercase().trim().to_string(),
            None => return Ok(InteractionResponse::ephemeral_message(
                "❌ 銘柄コードを指定してください".to_string()
            )),
        };

        if symbol.is_empty() {
            return Ok(InteractionResponse::ephemeral_message(
                "❌ 有効な銘柄コードを入力してください".to_string()
            ));
        }

        // 銘柄の存在確認（Yahoo Financeで検証）
        match self.stock_client.validate_symbol(&symbol).await {
            Ok(true) => {
                match self.dynamo_client.add_to_watchlist(user_id, &symbol).await {
                    Ok(()) => Ok(InteractionResponse::message(
                        format!("✅ 銘柄 {} を監視リストに追加しました", symbol)
                    )),
                    Err(e) => {
                        tracing::error!("Failed to add to watchlist: {}", e);
                        Ok(InteractionResponse::ephemeral_message(
                            format!("❌ 銘柄 {} の追加に失敗しました", symbol)
                        ))
                    }
                }
            }
            Ok(false) => Ok(InteractionResponse::ephemeral_message(
                format!("❌ 銘柄コード {} が見つかりません", symbol)
            )),
            Err(e) => {
                tracing::error!("Failed to validate symbol: {}", e);
                Ok(InteractionResponse::ephemeral_message(
                    "❌ 銘柄の検証中にエラーが発生しました".to_string()
                ))
            }
        }
    }

    async fn handle_remove_command(&self, data: &crate::models::InteractionData, user_id: &str) -> Result<InteractionResponse> {
        let symbol = match self.get_option_value(data, "symbol") {
            Some(s) => s.to_uppercase().trim().to_string(),
            None => return Ok(InteractionResponse::ephemeral_message(
                "❌ 銘柄コードを指定してください".to_string()
            )),
        };

        match self.dynamo_client.remove_from_watchlist(user_id, &symbol).await {
            Ok(true) => Ok(InteractionResponse::message(
                format!("✅ 銘柄 {} を監視リストから削除しました", symbol)
            )),
            Ok(false) => Ok(InteractionResponse::ephemeral_message(
                format!("❌ 銘柄 {} は監視リストにありません", symbol)
            )),
            Err(e) => {
                tracing::error!("Failed to remove from watchlist: {}", e);
                Ok(InteractionResponse::ephemeral_message(
                    format!("❌ 銘柄 {} の削除に失敗しました", symbol)
                ))
            }
        }
    }

    async fn handle_price_command(&self, data: &crate::models::InteractionData) -> Result<InteractionResponse> {
        let symbol = match self.get_option_value(data, "symbol") {
            Some(s) => s.to_uppercase().trim().to_string(),
            None => return Ok(InteractionResponse::ephemeral_message(
                "❌ 銘柄コードを指定してください".to_string()
            )),
        };

        match self.stock_client.get_current_price(&symbol).await {
            Ok(stock_price) => {
                let mut content = format!("📈 **{}** の現在価格\n", symbol);
                content.push_str(&format!("💰 **${:.2}**\n", stock_price.price));
                
                if let (Some(change), Some(change_percent)) = (stock_price.change, stock_price.change_percent) {
                    let emoji = if change >= 0.0 { "📈" } else { "📉" };
                    content.push_str(&format!("{} ${:.2} ({:.2}%)\n", emoji, change, change_percent));
                }

                if let Some(volume) = stock_price.volume {
                    content.push_str(&format!("📊 出来高: {:,}\n", volume));
                }

                content.push_str(&format!("🕐 {}", stock_price.timestamp.format("%Y-%m-%d %H:%M:%S UTC")));

                Ok(InteractionResponse::message(content))
            }
            Err(e) => {
                tracing::error!("Failed to get stock price: {}", e);
                Ok(InteractionResponse::ephemeral_message(
                    format!("❌ 銘柄 {} の価格取得に失敗しました", symbol)
                ))
            }
        }
    }

    async fn handle_alert_command(&self, data: &crate::models::InteractionData, user_id: &str) -> Result<InteractionResponse> {
        let symbol = match self.get_option_value(data, "symbol") {
            Some(s) => s.to_uppercase().trim().to_string(),
            None => return Ok(InteractionResponse::ephemeral_message(
                "❌ 銘柄コードを指定してください".to_string()
            )),
        };

        let threshold = match self.get_option_value(data, "price") {
            Some(price_str) => match price_str.parse::<f64>() {
                Ok(price) => price,
                Err(_) => return Ok(InteractionResponse::ephemeral_message(
                    "❌ 有効な価格を入力してください".to_string()
                )),
            },
            None => return Ok(InteractionResponse::ephemeral_message(
                "❌ アラート価格を指定してください".to_string()
            )),
        };

        match self.dynamo_client.set_alert_threshold(user_id, &symbol, threshold).await {
            Ok(()) => Ok(InteractionResponse::message(
                format!("🔔 銘柄 {} のアラートを ${:.2} に設定しました", symbol, threshold)
            )),
            Err(e) => {
                tracing::error!("Failed to set alert: {}", e);
                Ok(InteractionResponse::ephemeral_message(
                    "❌ アラートの設定に失敗しました".to_string()
                ))
            }
        }
    }

    async fn handle_chart_command(&self, _data: &crate::models::InteractionData) -> Result<InteractionResponse> {
        Ok(InteractionResponse::ephemeral_message(
            "📈 チャート機能は準備中です。しばらくお待ちください。".to_string()
        ))
    }
}