use serde::{Deserialize, Serialize};
use chrono::{DateTime, Utc};

#[derive(Debug, Serialize, Deserialize)]
pub struct DiscordInteraction {
    #[serde(rename = "type")]
    pub interaction_type: u8,
    pub id: Option<String>,
    pub application_id: Option<String>,
    pub data: Option<InteractionData>,
    pub member: Option<Member>,
    pub user: Option<User>,
}

#[derive(Debug, Serialize, Deserialize)]
pub struct InteractionData {
    pub name: String,
    pub options: Option<Vec<CommandOption>>,
}

#[derive(Debug, Serialize, Deserialize)]
pub struct CommandOption {
    pub name: String,
    pub value: Option<serde_json::Value>,
}

#[derive(Debug, Serialize, Deserialize)]
pub struct Member {
    pub user: Option<User>,
}

#[derive(Debug, Serialize, Deserialize)]
pub struct User {
    pub id: String,
}

#[derive(Debug, Serialize, Deserialize)]
pub struct InteractionResponse {
    #[serde(rename = "type")]
    pub response_type: u8,
    pub data: Option<InteractionResponseData>,
}

#[derive(Debug, Serialize, Deserialize)]
pub struct InteractionResponseData {
    pub content: String,
    pub flags: Option<u64>,
}

#[derive(Debug, Serialize, Deserialize)]
pub struct StockPrice {
    pub symbol: String,
    pub timestamp: DateTime<Utc>,
    pub price: f64,
    pub open_price: Option<f64>,
    pub high_price: Option<f64>,
    pub low_price: Option<f64>,
    pub volume: Option<u64>,
    pub previous_close: Option<f64>,
    pub change: Option<f64>,
    pub change_percent: Option<f64>,
}

#[derive(Debug, Serialize, Deserialize)]
pub struct WatchlistItem {
    pub user_id: String,
    pub symbol: String,
    pub added_at: DateTime<Utc>,
    pub alert_threshold: Option<f64>,
}

impl InteractionResponse {
    pub fn pong() -> Self {
        Self {
            response_type: 1, // PONG
            data: None,
        }
    }

    pub fn message(content: String) -> Self {
        Self {
            response_type: 4, // CHANNEL_MESSAGE_WITH_SOURCE
            data: Some(InteractionResponseData {
                content,
                flags: None,
            }),
        }
    }

    pub fn ephemeral_message(content: String) -> Self {
        Self {
            response_type: 4, // CHANNEL_MESSAGE_WITH_SOURCE
            data: Some(InteractionResponseData {
                content,
                flags: Some(64), // EPHEMERAL
            }),
        }
    }
}