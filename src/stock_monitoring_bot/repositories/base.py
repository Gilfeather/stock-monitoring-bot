"""
ベースリポジトリクラス
"""
import os
from abc import ABC, abstractmethod
from typing import Any, Dict
import boto3
from botocore.exceptions import ClientError, NoCredentialsError, BotoCoreError
import aioboto3
from aws_lambda_powertools import Logger
from contextlib import asynccontextmanager

logger = Logger()


class BaseRepository(ABC):
    """ベースリポジトリクラス"""
    
    def __init__(self):
        self.region = os.getenv('AWS_REGION', 'ap-northeast-1')
        self.endpoint_url = os.getenv('DYNAMODB_ENDPOINT_URL')  # ローカル開発用
        
        # 設定値の検証
        if not self.region:
            raise ValueError("AWS_REGIONが設定されていません")
        
        # 接続プールサイズ制限
        self.max_pool_connections = 50
        self.max_retries = 3
        
    def _get_client(self):
        """DynamoDBクライアントを取得"""
        try:
            # リトライ設定
            from botocore.config import Config
            config = Config(
                retries={
                    'max_attempts': 3,
                    'mode': 'adaptive'
                },
                max_pool_connections=50
            )
            
            if self.endpoint_url:
                # ローカル開発環境
                return boto3.client(
                    'dynamodb',
                    region_name=self.region,
                    endpoint_url=self.endpoint_url,
                    config=config
                )
            else:
                # AWS環境
                return boto3.client(
                    'dynamodb',
                    region_name=self.region,
                    config=config
                )
        except Exception as e:
            logger.error(f"DynamoDBクライアント作成エラー: {type(e).__name__}")
            raise
    
    @asynccontextmanager
    async def _get_async_client(self):
        """非同期DynamoDBクライアントを取得（コンテキストマネージャー）"""
        session = aioboto3.Session()
        
        # botocore Configオブジェクトを使用
        from botocore.config import Config
        config = Config(
            retries={
                'max_attempts': 3,
                'mode': 'adaptive'
            },
            max_pool_connections=50
        )
        
        # aioboto3のclientメソッドの引数
        client_kwargs = {
            'service_name': 'dynamodb',
            'region_name': self.region,
            'config': config
        }
        
        if self.endpoint_url:
            client_kwargs['endpoint_url'] = self.endpoint_url
        
        client = session.client(**client_kwargs)
        
        try:
            async with client as dynamo_client:
                yield dynamo_client
        except Exception as e:
            logger.error(f"DynamoDBクライアントエラー: {type(e).__name__}: {str(e)}")
            raise
    
    def _handle_client_error(self, error: Exception, operation: str) -> None:
        """DynamoDBクライアントエラーをハンドリング"""
        if isinstance(error, ClientError):
            error_code = error.response['Error']['Code']
            error.response['Error']['Message']
            
            # セキュリティ上、詳細なエラーメッセージはログに記録しない
            logger.error(
                f"DynamoDB {operation} failed",
                extra={
                    "error_code": error_code,
                    "operation": operation
                }
            )
            
            if error_code == 'ResourceNotFoundException':
                raise ValueError("リソースが見つかりません")
            elif error_code == 'ValidationException':
                raise ValueError("バリデーションエラーが発生しました")
            elif error_code == 'ConditionalCheckFailedException':
                raise ValueError("条件チェックに失敗しました")
            elif error_code == 'ThrottlingException':
                raise RuntimeError("レート制限に達しました")
            elif error_code == 'ProvisionedThroughputExceededException':
                raise RuntimeError("スループット制限を超過しました")
            else:
                raise RuntimeError("データベース操作エラーが発生しました")
        elif isinstance(error, NoCredentialsError):
            logger.error(f"AWS認証エラー in {operation}")
            raise RuntimeError("認証エラーが発生しました")
        elif isinstance(error, BotoCoreError):
            logger.error(f"AWS接続エラー in {operation}")
            raise RuntimeError("接続エラーが発生しました")
        else:
            logger.error(f"予期しないエラー in {operation}: {type(error)}")
            raise RuntimeError("予期しないエラーが発生しました")
    
    @abstractmethod
    def get_table_name(self) -> str:
        """テーブル名を取得"""
        pass
    
    def _serialize_item(self, item: Dict[str, Any]) -> Dict[str, Any]:
        """PythonオブジェクトをDynamoDB形式にシリアライズ"""
        serialized = {}
        for key, value in item.items():
            if value is None:
                continue
            elif isinstance(value, bool):  # boolを先にチェック（intのサブクラスなので）
                serialized[key] = {'BOOL': value}
            elif isinstance(value, str):
                serialized[key] = {'S': value}
            elif isinstance(value, (int, float)):
                serialized[key] = {'N': str(value)}
            elif isinstance(value, dict):
                serialized[key] = {'M': self._serialize_item(value)}
            elif isinstance(value, list):
                serialized[key] = {'L': [self._serialize_value(v) for v in value]}
            else:
                # datetime等はISO文字列に変換
                serialized[key] = {'S': str(value)}
        return serialized
    
    def _serialize_value(self, value: Any) -> Dict[str, Any]:
        """単一値をDynamoDB形式にシリアライズ"""
        if isinstance(value, bool):  # boolを先にチェック（intのサブクラスなので）
            return {'BOOL': value}
        elif isinstance(value, str):
            return {'S': value}
        elif isinstance(value, (int, float)):
            return {'N': str(value)}
        elif isinstance(value, dict):
            return {'M': self._serialize_item(value)}
        elif isinstance(value, list):
            return {'L': [self._serialize_value(v) for v in value]}
        else:
            return {'S': str(value)}
    
    def _deserialize_item(self, item: Dict[str, Any]) -> Dict[str, Any]:
        """DynamoDB形式をPythonオブジェクトにデシリアライズ"""
        deserialized = {}
        for key, value in item.items():
            if 'S' in value:
                deserialized[key] = value['S']
            elif 'N' in value:
                # 数値は適切な型に変換
                num_str = value['N']
                if '.' in num_str:
                    deserialized[key] = float(num_str)
                else:
                    deserialized[key] = int(num_str)
            elif 'BOOL' in value:
                deserialized[key] = value['BOOL']
            elif 'M' in value:
                deserialized[key] = self._deserialize_item(value['M'])
            elif 'L' in value:
                deserialized[key] = [self._deserialize_value(v) for v in value['L']]
            elif 'NULL' in value:
                deserialized[key] = None
        return deserialized
    
    def _deserialize_value(self, value: Dict[str, Any]) -> Any:
        """単一値をデシリアライズ"""
        if 'S' in value:
            return value['S']
        elif 'N' in value:
            num_str = value['N']
            if '.' in num_str:
                return float(num_str)
            else:
                return int(num_str)
        elif 'BOOL' in value:
            return value['BOOL']
        elif 'M' in value:
            return self._deserialize_item(value['M'])
        elif 'L' in value:
            return [self._deserialize_value(v) for v in value['L']]
        elif 'NULL' in value:
            return None
        else:
            return None