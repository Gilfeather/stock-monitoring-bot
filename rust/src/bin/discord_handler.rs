use lambda_runtime::{service_fn, Error, LambdaEvent};
// use lambda_web::{is_running_on_lambda, LambdaWeb, Request, RequestExt, Response, Body};
use serde_json::{json, Value};
use std::collections::HashMap;
use tracing::{info, error, debug};
use tracing_subscriber;

use stock_monitoring_bot::config::Config;
use stock_monitoring_bot::discord::{verify_signature, InteractionHandler};
use stock_monitoring_bot::database::DynamoClient;
use stock_monitoring_bot::stocks::StockClient;
use stock_monitoring_bot::models::{DiscordInteraction, InteractionResponse};

async fn handler(event: LambdaEvent<Value>) -> Result<Value, Error> {
    let (event, _context) = event.into_parts();
    
    info!("Discord Interactions処理開始");
    debug!("Event: {}", serde_json::to_string_pretty(&event)?);

    // HTTP リクエストの処理
    let headers = event.get("headers")
        .and_then(|h| h.as_object())
        .unwrap_or(&serde_json::Map::new());

    let body = event.get("body")
        .and_then(|b| b.as_str())
        .unwrap_or("");

    // Discord署名ヘッダーを取得
    let mut signature = String::new();
    let mut timestamp = String::new();

    for (key, value) in headers {
        let key_lower = key.to_lowercase();
        if let Some(val_str) = value.as_str() {
            match key_lower.as_str() {
                "x-signature-ed25519" => signature = val_str.to_string(),
                "x-signature-timestamp" => timestamp = val_str.to_string(),
                _ => {}
            }
        }
    }

    debug!("Signature length: {}, Timestamp: {}", signature.len(), timestamp);

    // 設定とクライアント初期化
    let config = Config::new().await?;
    let public_key = config.get_discord_public_key().await?;

    // 署名検証
    match verify_signature(&signature, &timestamp, body, &public_key) {
        Ok(true) => {
            debug!("署名検証成功");
        }
        Ok(false) => {
            error!("署名検証失敗");
            return Ok(json!({
                "statusCode": 401,
                "headers": {"Content-Type": "application/json"},
                "body": json!({"error": "Invalid signature"}).to_string()
            }));
        }
        Err(e) => {
            error!("署名検証エラー: {}", e);
            return Ok(json!({
                "statusCode": 401,
                "headers": {"Content-Type": "application/json"},
                "body": json!({"error": "Signature verification failed"}).to_string()
            }));
        }
    }

    // Discord Interactionをパース
    let interaction: DiscordInteraction = match serde_json::from_str(body) {
        Ok(interaction) => interaction,
        Err(e) => {
            error!("Interaction parse error: {}", e);
            return Ok(json!({
                "statusCode": 400,
                "headers": {"Content-Type": "application/json"},
                "body": json!({"error": "Invalid interaction data"}).to_string()
            }));
        }
    };

    debug!("Interaction type: {}", interaction.interaction_type);

    // PING応答（Discord検証用）
    if interaction.interaction_type == 1 {
        info!("PING応答");
        return Ok(json!({
            "statusCode": 200,
            "headers": {"Content-Type": "application/json"},
            "body": json!({"type": 1}).to_string()
        }));
    }

    // 他のInteractionを処理
    match process_interaction(interaction).await {
        Ok(response) => {
            let response_json = serde_json::to_string(&response)?;
            info!("Discord Interactions処理完了");
            
            Ok(json!({
                "statusCode": 200,
                "headers": {"Content-Type": "application/json"},
                "body": response_json
            }))
        }
        Err(e) => {
            error!("Interaction処理エラー: {}", e);
            let error_response = InteractionResponse::ephemeral_message(
                "❌ 処理中にエラーが発生しました".to_string()
            );
            let response_json = serde_json::to_string(&error_response)?;
            
            Ok(json!({
                "statusCode": 200,
                "headers": {"Content-Type": "application/json"},
                "body": response_json
            }))
        }
    }
}

async fn process_interaction(interaction: DiscordInteraction) -> Result<InteractionResponse, Box<dyn std::error::Error + Send + Sync>> {
    info!("Creating clients...");
    
    let dynamo_client = DynamoClient::new().await?;
    let stock_client = StockClient::new();
    let interaction_handler = InteractionHandler::new(dynamo_client, stock_client);

    info!("Processing interaction...");
    
    let response = interaction_handler.handle_interaction(interaction).await?;
    
    Ok(response)
}

#[tokio::main]
async fn main() -> Result<(), Error> {
    // ログ初期化
    tracing_subscriber::fmt()
        .with_max_level(tracing::Level::INFO)
        .with_target(false)
        .without_time()
        .init();

    info!("Discord Handler Lambda starting...");

    let func = service_fn(handler);
    lambda_runtime::run(func).await?;
    
    Ok(())
}