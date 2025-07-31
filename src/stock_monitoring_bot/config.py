"""Configuration management for stock monitoring bot."""

import os
import logging
import boto3
from typing import Optional, Dict
from functools import lru_cache


class Config:
    """Configuration class for managing environment variables and AWS Parameter Store."""
    
    def __init__(self):
        self.environment = os.getenv('ENVIRONMENT', 'dev')
        self.project_name = 'stock-monitoring-bot'
        self._ssm_client = None
        self.logger = logging.getLogger(__name__)
        self._validate_environment()
    
    @property
    def ssm_client(self):
        """Lazy initialization of SSM client."""
        if self._ssm_client is None:
            self._ssm_client = boto3.client('ssm')
        return self._ssm_client
    
    @lru_cache(maxsize=128)
    def get_parameter(self, parameter_name: str, decrypt: bool = True, default: Optional[str] = None) -> Optional[str]:
        """
        Get parameter from AWS Systems Manager Parameter Store.
        
        Args:
            parameter_name: The name of the parameter
            decrypt: Whether to decrypt SecureString parameters
            
        Returns:
            The parameter value or None if not found
        """
        # パラメータ名の検証
        if not parameter_name or not isinstance(parameter_name, str):
            self.logger.error("Invalid parameter name provided")
            return None
            
        try:
            response = self.ssm_client.get_parameter(
                Name=parameter_name,
                WithDecryption=decrypt
            )
            return response['Parameter']['Value']
        except Exception:
            # セキュリティ上、詳細なエラー情報はログに記録しない
            self.logger.error(f"Parameter retrieval failed for {parameter_name[:10]}***")
            return default
    
    @property
    def discord_webhook_url(self) -> Optional[str]:
        """Get Discord webhook URL from Parameter Store."""
        parameter_name = os.getenv('DISCORD_WEBHOOK_PARAMETER')
        if parameter_name:
            webhook_url = self.get_parameter(parameter_name)
            if webhook_url and self._validate_webhook_url(webhook_url):
                return webhook_url
        
        env_webhook_url = os.getenv('DISCORD_WEBHOOK_URL')
        if env_webhook_url and self._validate_webhook_url(env_webhook_url):
            return env_webhook_url
            
        return None
    
    @property
    def alpha_vantage_api_key(self) -> Optional[str]:
        """Get Alpha Vantage API key from Parameter Store."""
        parameter_name = os.getenv('ALPHA_VANTAGE_API_KEY_PARAMETER')
        if parameter_name:
            api_key = self.get_parameter(parameter_name)
            if api_key and len(api_key) >= 10:  # 最小長チェック
                return api_key
        
        env_api_key = os.getenv('ALPHA_VANTAGE_API_KEY')
        if env_api_key and len(env_api_key) >= 10:
            return env_api_key
            
        return None
    
    @property
    def admin_users(self) -> list[str]:
        """管理者ユーザーID一覧を取得"""
        admin_users_str = os.getenv('ADMIN_USERS', '')
        if not admin_users_str:
            return []
        
        # カンマ区切りで分割し、空文字を除去
        users = [user.strip() for user in admin_users_str.split(',') if user.strip()]
        # 英数字のみのユーザーIDをフィルタリング
        return [user for user in users if user.isalnum() and len(user) <= 20]
    
    @property
    def allowed_channels(self) -> list[str]:
        """許可されたチャンネルID一覧を取得"""
        channels_str = os.getenv('ALLOWED_CHANNELS', '')
        if not channels_str:
            return []
        
        # カンマ区切りで分割し、空文字を除去
        channels = [channel.strip() for channel in channels_str.split(',') if channel.strip()]
        # 英数字のみのチャンネルIDをフィルタリング
        return [channel for channel in channels if channel.isalnum() and len(channel) <= 20]
    
    @property
    def dynamodb_table_stocks(self) -> str:
        """Get DynamoDB stocks table name."""
        return os.getenv('DYNAMODB_TABLE_STOCKS', f'stock-monitoring-bot-stocks-{self.environment}')
    
    @property
    def dynamodb_table_alerts(self) -> str:
        """Get DynamoDB alerts table name."""
        return os.getenv('DYNAMODB_TABLE_ALERTS', f'stock-monitoring-bot-alerts-{self.environment}')
    
    @property
    def dynamodb_table_history(self) -> str:
        """Get DynamoDB history table name."""
        return os.getenv('DYNAMODB_TABLE_HISTORY', f'stock-monitoring-bot-history-{self.environment}')


    def _validate_environment(self) -> None:
        """環境設定の検証"""
        valid_environments = {'dev', 'staging', 'prod'}
        if self.environment not in valid_environments:
            raise ValueError(f"Invalid environment: {self.environment}. Must be one of {valid_environments}")
    
    def validate_config(self) -> Dict[str, bool]:
        """設定値の検証"""
        validation_results = {}
        
        # 環境検証
        validation_results['environment_valid'] = self.environment in {'dev', 'staging', 'prod'}
        
        # 必須パラメータの検証
        required_params = {
            'discord_webhook_url': self.discord_webhook_url,
            'alpha_vantage_api_key': self.alpha_vantage_api_key,
        }
        
        # 管理者設定の検証
        validation_results['admin_users_configured'] = len(self.admin_users) > 0
        validation_results['allowed_channels_configured'] = len(self.allowed_channels) > 0
        
        for param_name, param_value in required_params.items():
            validation_results[param_name] = param_value is not None and len(param_value) > 0
            
        # DynamoDBテーブル名の検証
        table_names = {
            'stocks_table': self.dynamodb_table_stocks,
            'alerts_table': self.dynamodb_table_alerts,
            'history_table': self.dynamodb_table_history,
        }
        
        for table_key, table_name in table_names.items():
            validation_results[table_key] = bool(table_name and len(table_name) > 0)
            
        return validation_results
    
    @property
    def rate_limit_requests(self) -> int:
        """Discord API レート制限 - リクエスト数"""
        try:
            return int(os.getenv('RATE_LIMIT_REQUESTS', '5'))
        except ValueError:
            return 5
    
    @property
    def rate_limit_window(self) -> int:
        """Discord API レート制限 - 時間窓（秒）"""
        try:
            return int(os.getenv('RATE_LIMIT_WINDOW', '60'))
        except ValueError:
            return 60
    
    @property
    def request_timeout(self) -> int:
        """HTTPリクエストタイムアウト（秒）"""
        try:
            return int(os.getenv('REQUEST_TIMEOUT', '30'))
        except ValueError:
            return 30
    
    @property
    def max_message_length(self) -> int:
        """最大メッセージ長"""
        try:
            return int(os.getenv('MAX_MESSAGE_LENGTH', '2000'))
        except ValueError:
            return 2000
    
    def _validate_webhook_url(self, webhook_url: str) -> bool:
        """Webhook URLの検証"""
        try:
            from urllib.parse import urlparse
            parsed = urlparse(webhook_url)
            # Discord webhook URLのフォーマット検証
            if parsed.hostname not in ("discord.com", "discordapp.com"):
                return False
            if not parsed.path.startswith("/api/webhooks/"):
                return False
            return True
        except Exception:
            return False


# Global config instance
config = Config()