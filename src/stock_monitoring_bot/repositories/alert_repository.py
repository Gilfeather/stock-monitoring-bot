"""
アラートリポジトリ
"""
import os
from datetime import datetime, timedelta
from typing import List, Optional
from decimal import Decimal
from botocore.exceptions import ClientError
from aws_lambda_powertools import Logger

from .base import BaseRepository
from ..models.stock import Alert

logger = Logger()


class AlertRepository(BaseRepository):
    """アラートリポジトリ"""
    
    def get_table_name(self) -> str:
        table_name = os.getenv('DYNAMODB_TABLE_ALERTS', 'stock-monitoring-bot-alerts-dev')
        if not table_name:
            raise ValueError("DYNAMODB_TABLE_ALERTS環境変数が設定されていません")
        return table_name
    
    async def create_alert(self, alert: Alert) -> bool:
        """アラートを作成"""
        try:
            async with self._get_async_client() as client:
                item = {
                    'alert_id': alert.alert_id,
                    'symbol': alert.symbol,
                    'timestamp': alert.triggered_at.isoformat(),
                    'alert_type': alert.alert_type,
                    'message': alert.message,
                    'triggered_at': alert.triggered_at.isoformat(),
                    'price_at_trigger': float(alert.price_at_trigger) if alert.price_at_trigger else None,
                    'volume_at_trigger': alert.volume_at_trigger,
                    'threshold_value': float(alert.threshold_value) if alert.threshold_value else None,
                    'is_sent': alert.is_sent,
                    'sent_at': alert.sent_at.isoformat() if alert.sent_at else None
                }
                
                # Noneの値を除外
                item = {k: v for k, v in item.items() if v is not None}
                
                # 入力値の検証
                if not alert.alert_id or not alert.symbol:
                    raise ValueError("必須フィールドが不足しています")
                if len(alert.symbol) > 10:
                    raise ValueError("銘柄コードが無効です")
                
                await client.put_item(
                    TableName=self.get_table_name(),
                    Item=self._serialize_item(item)
                )
                
                logger.info(f"アラートを作成しました: {alert.alert_id}")
                return True
                
        except ClientError as e:
            self._handle_client_error(e, "create_alert")
            return False
    
    async def get_alert(self, alert_id: str, timestamp: datetime) -> Optional[Alert]:
        """アラートを取得"""
        try:
            async with self._get_async_client() as client:
                # 入力値の検証
                if not alert_id or not isinstance(timestamp, datetime):
                    raise ValueError("無効なパラメータです")
                
                response = await client.get_item(
                    TableName=self.get_table_name(),
                    Key={
                        'alert_id': {'S': alert_id},
                        'timestamp': {'S': timestamp.isoformat()}
                    }
                )
                
                if 'Item' not in response:
                    return None
                
                item = self._deserialize_item(response['Item'])
                return self._item_to_alert(item)
                
        except ClientError as e:
            self._handle_client_error(e, "get_alert")
            return None
    
    async def update_alert_sent_status(self, alert_id: str, timestamp: datetime, sent_at: datetime) -> bool:
        """アラートの送信状態を更新"""
        try:
            async with self._get_async_client() as client:
                # 入力値の検証
                if not alert_id or not isinstance(timestamp, datetime) or not isinstance(sent_at, datetime):
                    raise ValueError("無効なパラメータです")
                
                await client.update_item(
                    TableName=self.get_table_name(),
                    Key={
                        'alert_id': {'S': alert_id},
                        'timestamp': {'S': timestamp.isoformat()}
                    },
                    UpdateExpression='SET is_sent = :sent, sent_at = :sent_at',
                    ExpressionAttributeValues={
                        ':sent': {'BOOL': True},
                        ':sent_at': {'S': sent_at.isoformat()}
                    },
                    ConditionExpression='attribute_exists(alert_id)'
                )
                
                logger.info(f"アラート送信状態を更新しました: {alert_id}")
                return True
                
        except ClientError as e:
            if e.response['Error']['Code'] == 'ConditionalCheckFailedException':
                logger.warning(f"更新対象のアラートが見つかりません: {alert_id}")
                return False
            else:
                self._handle_client_error(e, "update_alert_sent_status")
                return False
    
    async def get_recent_alerts_by_symbol(self, symbol: str, hours: int = 1) -> List[Alert]:
        """指定銘柄の最近のアラートを取得"""
        try:
            async with self._get_async_client() as client:
                # GSIを使用してsymbolで検索
                cutoff_time = datetime.utcnow() - timedelta(hours=hours)
                
                response = await client.query(
                    TableName=self.get_table_name(),
                    IndexName='symbol-timestamp-index',
                    KeyConditionExpression='symbol = :symbol AND #ts >= :cutoff',
                    ExpressionAttributeNames={'#ts': 'timestamp'},
                    ExpressionAttributeValues={
                        ':symbol': {'S': symbol},
                        ':cutoff': {'S': cutoff_time.isoformat()}
                    },
                    ScanIndexForward=False  # 降順（最新から）
                )
                
                alerts = []
                for item in response.get('Items', []):
                    deserialized = self._deserialize_item(item)
                    alerts.append(self._item_to_alert(deserialized))
                
                return alerts
                
        except ClientError as e:
            self._handle_client_error(e, "get_recent_alerts_by_symbol")
            return []
    
    async def get_unsent_alerts(self, limit: int = 100) -> List[Alert]:
        """未送信のアラートを取得"""
        try:
            async with self._get_async_client() as client:
                response = await client.scan(
                    TableName=self.get_table_name(),
                    FilterExpression='is_sent = :sent',
                    ExpressionAttributeValues={':sent': {'BOOL': False}},
                    Limit=limit
                )
                
                alerts = []
                for item in response.get('Items', []):
                    deserialized = self._deserialize_item(item)
                    alerts.append(self._item_to_alert(deserialized))
                
                # 発生時刻でソート（古いものから）
                alerts.sort(key=lambda x: x.triggered_at)
                
                logger.info(f"未送信アラートを {len(alerts)} 件取得しました")
                return alerts
                
        except ClientError as e:
            self._handle_client_error(e, "get_unsent_alerts")
            return []
    
    async def check_duplicate_alert(self, symbol: str, alert_type: str, cooldown_minutes: int = 30) -> bool:
        """重複アラートをチェック"""
        try:
            cutoff_time = datetime.utcnow() - timedelta(minutes=cooldown_minutes)
            recent_alerts = await self.get_recent_alerts_by_symbol(symbol, hours=1)
            
            # 同じ種類のアラートがクールダウン時間内にあるかチェック
            for alert in recent_alerts:
                if (alert.alert_type == alert_type and 
                    alert.triggered_at > cutoff_time):
                    logger.info(f"重複アラートを検出: {symbol} - {alert_type}")
                    return True
            
            return False
            
        except Exception as e:
            logger.error(f"重複アラートチェックでエラー: {e}")
            return False  # エラー時は重複なしとして処理
    
    async def cleanup_old_alerts(self, days: int = 30) -> int:
        """古いアラートを削除"""
        try:
            async with self._get_async_client() as client:
                cutoff_time = datetime.utcnow() - timedelta(days=days)
                
                # 古いアラートを検索
                response = await client.scan(
                    TableName=self.get_table_name(),
                    FilterExpression='triggered_at < :cutoff',
                    ExpressionAttributeValues={
                        ':cutoff': {'S': cutoff_time.isoformat()}
                    },
                    ProjectionExpression='alert_id, #ts',
                    ExpressionAttributeNames={'#ts': 'timestamp'}
                )
                
                deleted_count = 0
                for item in response.get('Items', []):
                    try:
                        await client.delete_item(
                            TableName=self.get_table_name(),
                            Key={
                                'alert_id': item['alert_id'],
                                'timestamp': item['timestamp']
                            }
                        )
                        deleted_count += 1
                    except ClientError as e:
                        logger.warning(f"アラート削除に失敗: {e}")
                
                logger.info(f"古いアラートを {deleted_count} 件削除しました")
                return deleted_count
                
        except ClientError as e:
            self._handle_client_error(e, "cleanup_old_alerts")
            return 0
    
    def _item_to_alert(self, item: dict) -> Alert:
        """DynamoDBアイテムをAlertに変換"""
        return Alert(
            alert_id=item['alert_id'],
            symbol=item['symbol'],
            alert_type=item['alert_type'],
            message=item['message'],
            triggered_at=datetime.fromisoformat(item['triggered_at']),
            price_at_trigger=Decimal(str(item['price_at_trigger'])) if item.get('price_at_trigger') else None,
            volume_at_trigger=item.get('volume_at_trigger'),
            threshold_value=Decimal(str(item['threshold_value'])) if item.get('threshold_value') else None,
            is_sent=item['is_sent'],
            sent_at=datetime.fromisoformat(item['sent_at']) if item.get('sent_at') else None
        )