use anyhow::Result;
use aws_sdk_dynamodb::Client as DynamoDbClient;
use aws_sdk_dynamodb::types::AttributeValue;
use chrono::Utc;
use crate::models::WatchlistItem;

pub struct DynamoClient {
    client: DynamoDbClient,
    stocks_table: String,
    alerts_table: String,
}

impl DynamoClient {
    pub async fn new() -> Result<Self> {
        let aws_config = aws_config::load_from_env().await;
        let client = DynamoDbClient::new(&aws_config);
        
        Ok(Self {
            client,
            stocks_table: "stock-monitoring-bot-stocks-dev".to_string(),
            alerts_table: "stock-monitoring-bot-alerts-dev".to_string(),
        })
    }

    pub async fn get_user_watchlist(&self, user_id: &str) -> Result<Vec<WatchlistItem>> {
        let response = self.client
            .scan()
            .table_name(&self.stocks_table)
            .filter_expression("user_id = :user_id")
            .expression_attribute_values(
                ":user_id", 
                AttributeValue::S(user_id.to_string())
            )
            .send()
            .await?;

        let mut watchlist = Vec::new();
        if let Some(items) = response.items {
            for item in items {
                if let Some(watchlist_item) = self.parse_watchlist_item(item)? {
                    watchlist.push(watchlist_item);
                }
            }
        }

        Ok(watchlist)
    }

    pub async fn add_to_watchlist(&self, user_id: &str, symbol: &str) -> Result<()> {
        let now = Utc::now();
        
        self.client
            .put_item()
            .table_name(&self.stocks_table)
            .item("user_id", AttributeValue::S(user_id.to_string()))
            .item("symbol", AttributeValue::S(symbol.to_string()))
            .item("added_at", AttributeValue::S(now.to_rfc3339()))
            .item("is_active", AttributeValue::Bool(true))
            .send()
            .await?;

        Ok(())
    }

    pub async fn remove_from_watchlist(&self, user_id: &str, symbol: &str) -> Result<bool> {
        let response = self.client
            .delete_item()
            .table_name(&self.stocks_table)
            .key("user_id", AttributeValue::S(user_id.to_string()))
            .key("symbol", AttributeValue::S(symbol.to_string()))
            .return_values(aws_sdk_dynamodb::types::ReturnValue::AllOld)
            .send()
            .await?;

        Ok(response.attributes.is_some())
    }

    pub async fn set_alert_threshold(&self, user_id: &str, symbol: &str, threshold: f64) -> Result<()> {
        // まず監視リストに銘柄があるかチェック
        let existing = self.client
            .get_item()
            .table_name(&self.stocks_table)
            .key("user_id", AttributeValue::S(user_id.to_string()))
            .key("symbol", AttributeValue::S(symbol.to_string()))
            .send()
            .await?;

        if existing.item.is_none() {
            // 監視リストに無い場合は追加
            self.add_to_watchlist(user_id, symbol).await?;
        }

        // アラート閾値を更新
        self.client
            .update_item()
            .table_name(&self.stocks_table)
            .key("user_id", AttributeValue::S(user_id.to_string()))
            .key("symbol", AttributeValue::S(symbol.to_string()))
            .update_expression("SET alert_threshold = :threshold")
            .expression_attribute_values(
                ":threshold", 
                AttributeValue::N(threshold.to_string())
            )
            .send()
            .await?;

        Ok(())
    }

    fn parse_watchlist_item(&self, item: std::collections::HashMap<String, AttributeValue>) -> Result<Option<WatchlistItem>> {
        let user_id = match item.get("user_id") {
            Some(AttributeValue::S(s)) => s.clone(),
            _ => return Ok(None),
        };

        let symbol = match item.get("symbol") {
            Some(AttributeValue::S(s)) => s.clone(),
            _ => return Ok(None),
        };

        let added_at = match item.get("added_at") {
            Some(AttributeValue::S(s)) => chrono::DateTime::parse_from_rfc3339(s)?.with_timezone(&Utc),
            _ => Utc::now(),
        };

        let alert_threshold = match item.get("alert_threshold") {
            Some(AttributeValue::N(n)) => n.parse::<f64>().ok(),
            _ => None,
        };

        Ok(Some(WatchlistItem {
            user_id,
            symbol,
            added_at,
            alert_threshold,
        }))
    }
}