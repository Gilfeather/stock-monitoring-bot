use anyhow::Result;
use aws_sdk_ssm::Client as SsmClient;

pub struct Config {
    pub ssm_client: SsmClient,
    pub project_name: String,
    pub environment: String,
}

impl Config {
    pub async fn new() -> Result<Self> {
        let aws_config = aws_config::load_from_env().await;
        let ssm_client = SsmClient::new(&aws_config);
        
        Ok(Self {
            ssm_client,
            project_name: "stock-monitoring-bot".to_string(),
            environment: "dev".to_string(),
        })
    }

    pub async fn get_parameter(&self, key: &str) -> Result<String> {
        let param_name = format!("/{}/{}/{}", self.project_name, self.environment, key);
        
        let response = self.ssm_client
            .get_parameter()
            .name(&param_name)
            .send()
            .await?;
        
        Ok(response
            .parameter()
            .and_then(|p| p.value())
            .unwrap_or("")
            .to_string())
    }

    pub async fn get_discord_public_key(&self) -> Result<String> {
        self.get_parameter("discord-public-key").await
    }

    pub async fn get_discord_webhook_url(&self) -> Result<String> {
        self.get_parameter("discord-webhook-url").await
    }

    pub async fn get_alpha_vantage_api_key(&self) -> Result<String> {
        self.get_parameter("alpha-vantage-api-key").await
    }
}