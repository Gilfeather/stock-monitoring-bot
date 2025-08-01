"""
株式データリポジトリ
"""
import os
from datetime import datetime
from typing import List, Optional
from decimal import Decimal
from botocore.exceptions import ClientError
from aws_lambda_powertools import Logger

from .base import BaseRepository
from ..models.stock import MonitoredStock, StockPrice

logger = Logger()


class StockRepository(BaseRepository):
    """株式データリポジトリ"""
    
    def get_table_name(self) -> str:
        table_name = os.getenv('DYNAMODB_TABLE_STOCKS', 'stock-monitoring-bot-stocks-dev')
        if not table_name:
            raise ValueError("DYNAMODB_TABLE_STOCKS環境変数が設定されていません")
        return table_name
    
    async def create_monitored_stock(self, stock: MonitoredStock) -> bool:
        """監視対象株式を作成"""
        try:
            async with self._get_async_client() as client:
                # デバッグ用ログ
                logger.error("=== DEBUG CREATE STOCK ===")
                logger.error(f"Symbol: {stock.symbol}")
                logger.error(f"is_active type: {type(stock.is_active)}, value: {stock.is_active}")
                
                item = {
                    'symbol': stock.symbol,
                    'name': stock.name,
                    'market': stock.market,
                    'price_threshold_upper': float(stock.price_threshold_upper) if stock.price_threshold_upper else None,
                    'price_threshold_lower': float(stock.price_threshold_lower) if stock.price_threshold_lower else None,
                    'volume_threshold_multiplier': float(stock.volume_threshold_multiplier),
                    'is_active': stock.is_active,
                    'created_at': stock.created_at.isoformat(),
                    'updated_at': stock.updated_at.isoformat()
                }
                
                # Noneの値を除外
                item = {k: v for k, v in item.items() if v is not None}
                
                logger.error(f"Item before serialization: {item}")
                
                # 入力値の検証
                if not stock.symbol or len(stock.symbol) > 10:
                    raise ValueError("無効な銘柄コードです")
                
                serialized_item = self._serialize_item(item)
                logger.error(f"Serialized item: {serialized_item}")
                
                await client.put_item(
                    TableName=self.get_table_name(),
                    Item=serialized_item,
                    ConditionExpression='attribute_not_exists(symbol)'  # 重複防止
                )
                
                logger.info(f"監視対象株式を作成しました: {stock.symbol}")
                return True
                
        except ClientError as e:
            if e.response['Error']['Code'] == 'ConditionalCheckFailedException':
                logger.warning(f"株式は既に監視対象です: {stock.symbol}")
                return False
            else:
                self._handle_client_error(e, "create_monitored_stock")
                return False
    
    async def get_monitored_stock(self, symbol: str) -> Optional[MonitoredStock]:
        """監視対象株式を取得"""
        try:
            async with self._get_async_client() as client:
                # 入力値の検証
                if not symbol or len(symbol) > 10:
                    raise ValueError("無効な銘柄コードです")
                
                response = await client.get_item(
                    TableName=self.get_table_name(),
                    Key={'symbol': {'S': symbol}}
                )
                
                if 'Item' not in response:
                    return None
                
                item = self._deserialize_item(response['Item'])
                return self._item_to_monitored_stock(item)
                
        except ClientError as e:
            self._handle_client_error(e, "get_monitored_stock")
            return None
    
    async def update_monitored_stock(self, stock: MonitoredStock) -> bool:
        """監視対象株式を更新"""
        try:
            async with self._get_async_client() as client:
                stock.updated_at = datetime.utcnow()
                
                update_expression = "SET #name = :name, market = :market, is_active = :is_active, updated_at = :updated_at, volume_threshold_multiplier = :volume_multiplier"
                expression_attribute_names = {'#name': 'name'}  # nameは予約語のため
                expression_attribute_values = {
                    ':name': {'S': stock.name},
                    ':market': {'S': stock.market},
                    ':is_active': {'BOOL': stock.is_active},
                    ':updated_at': {'S': stock.updated_at.isoformat()},
                    ':volume_multiplier': {'N': str(float(stock.volume_threshold_multiplier))}
                }
                
                # 価格閾値の更新（Noneの場合は削除）
                if stock.price_threshold_upper is not None:
                    update_expression += ", price_threshold_upper = :upper"
                    expression_attribute_values[':upper'] = {'N': str(float(stock.price_threshold_upper))}
                else:
                    update_expression += " REMOVE price_threshold_upper"
                
                if stock.price_threshold_lower is not None:
                    update_expression += ", price_threshold_lower = :lower"
                    expression_attribute_values[':lower'] = {'N': str(float(stock.price_threshold_lower))}
                else:
                    update_expression += " REMOVE price_threshold_lower"
                
                await client.update_item(
                    TableName=self.get_table_name(),
                    Key={'symbol': {'S': stock.symbol}},
                    UpdateExpression=update_expression,
                    ExpressionAttributeNames=expression_attribute_names,
                    ExpressionAttributeValues=expression_attribute_values,
                    ConditionExpression='attribute_exists(symbol)'
                )
                
                logger.info(f"監視対象株式を更新しました: {stock.symbol}")
                return True
                
        except ClientError as e:
            if e.response['Error']['Code'] == 'ConditionalCheckFailedException':
                logger.warning(f"更新対象の株式が見つかりません: {stock.symbol}")
                return False
            else:
                self._handle_client_error(e, "update_monitored_stock")
                return False
    
    async def delete_monitored_stock(self, symbol: str) -> bool:
        """監視対象株式を削除"""
        try:
            async with self._get_async_client() as client:
                # 入力値の検証
                if not symbol or len(symbol) > 10:
                    raise ValueError("無効な銘柄コードです")
                
                await client.delete_item(
                    TableName=self.get_table_name(),
                    Key={'symbol': {'S': symbol}},
                    ConditionExpression='attribute_exists(symbol)'
                )
                
                logger.info(f"監視対象株式を削除しました: {symbol}")
                return True
                
        except ClientError as e:
            if e.response['Error']['Code'] == 'ConditionalCheckFailedException':
                logger.warning(f"削除対象の株式が見つかりません: {symbol}")
                return False
            else:
                self._handle_client_error(e, "delete_monitored_stock")
                return False
    
    async def list_monitored_stocks(self, active_only: bool = True) -> List[MonitoredStock]:
        """監視対象株式一覧を取得"""
        try:
            async with self._get_async_client() as client:
                if active_only:
                    response = await client.scan(
                        TableName=self.get_table_name(),
                        FilterExpression='is_active = :active',
                        ExpressionAttributeValues={':active': {'BOOL': True}}
                    )
                else:
                    response = await client.scan(TableName=self.get_table_name())
                
                stocks = []
                for item in response.get('Items', []):
                    deserialized = self._deserialize_item(item)
                    stocks.append(self._item_to_monitored_stock(deserialized))
                
                logger.info(f"監視対象株式を {len(stocks)} 件取得しました")
                return stocks
                
        except ClientError as e:
            self._handle_client_error(e, "list_monitored_stocks")
            return []
    
    def _item_to_monitored_stock(self, item: dict) -> MonitoredStock:
        """DynamoDBアイテムをMonitoredStockに変換"""
        return MonitoredStock(
            symbol=item['symbol'],
            name=item['name'],
            market=item['market'],
            price_threshold_upper=Decimal(str(item['price_threshold_upper'])) if item.get('price_threshold_upper') else None,
            price_threshold_lower=Decimal(str(item['price_threshold_lower'])) if item.get('price_threshold_lower') else None,
            volume_threshold_multiplier=Decimal(str(item['volume_threshold_multiplier'])),
            is_active=item['is_active'],
            created_at=datetime.fromisoformat(item['created_at']),
            updated_at=datetime.fromisoformat(item['updated_at'])
        )


class StockPriceRepository(BaseRepository):
    """株価履歴リポジトリ"""
    
    def get_table_name(self) -> str:
        table_name = os.getenv('DYNAMODB_TABLE_HISTORY', 'stock-monitoring-bot-history-dev')
        if not table_name:
            raise ValueError("DYNAMODB_TABLE_HISTORY環境変数が設定されていません")
        return table_name
    
    async def save_stock_price(self, price: StockPrice) -> bool:
        """株価データを保存"""
        try:
            async with self._get_async_client() as client:
                # TTL設定（30日後に自動削除）
                ttl = int((price.timestamp.timestamp() + 30 * 24 * 3600))
                
                item = {
                    'symbol': price.symbol,
                    'timestamp': price.timestamp.isoformat(),
                    'price': float(price.price),
                    'open_price': float(price.open_price) if price.open_price else None,
                    'high_price': float(price.high_price) if price.high_price else None,
                    'low_price': float(price.low_price) if price.low_price else None,
                    'volume': price.volume,
                    'previous_close': float(price.previous_close) if price.previous_close else None,
                    'change_amount': float(price.change_amount) if price.change_amount else None,
                    'change_percent': float(price.change_percent) if price.change_percent else None,
                    'ttl': ttl
                }
                
                # Noneの値を除外
                item = {k: v for k, v in item.items() if v is not None}
                
                await client.put_item(
                    TableName=self.get_table_name(),
                    Item=self._serialize_item(item)
                )
                
                logger.debug(f"株価データを保存しました: {price.symbol} @ {price.timestamp}")
                return True
                
        except ClientError as e:
            self._handle_client_error(e, "save_stock_price")
            return False
    
    async def get_latest_price(self, symbol: str) -> Optional[StockPrice]:
        """最新の株価データを取得"""
        try:
            async with self._get_async_client() as client:
                response = await client.query(
                    TableName=self.get_table_name(),
                    KeyConditionExpression='symbol = :symbol',
                    ExpressionAttributeValues={':symbol': {'S': symbol}},
                    ScanIndexForward=False,  # 降順（最新から）
                    Limit=1
                )
                
                if not response.get('Items'):
                    return None
                
                item = self._deserialize_item(response['Items'][0])
                return self._item_to_stock_price(item)
                
        except ClientError as e:
            self._handle_client_error(e, "get_latest_price")
            return None
    
    async def get_price_history(self, symbol: str, limit: int = 100) -> List[StockPrice]:
        """株価履歴を取得"""
        try:
            async with self._get_async_client() as client:
                response = await client.query(
                    TableName=self.get_table_name(),
                    KeyConditionExpression='symbol = :symbol',
                    ExpressionAttributeValues={':symbol': {'S': symbol}},
                    ScanIndexForward=False,  # 降順（最新から）
                    Limit=limit
                )
                
                prices = []
                for item in response.get('Items', []):
                    deserialized = self._deserialize_item(item)
                    prices.append(self._item_to_stock_price(deserialized))
                
                return prices
                
        except ClientError as e:
            self._handle_client_error(e, "get_price_history")
            return []
    
    def _item_to_stock_price(self, item: dict) -> StockPrice:
        """DynamoDBアイテムをStockPriceに変換"""
        return StockPrice(
            symbol=item['symbol'],
            timestamp=datetime.fromisoformat(item['timestamp']),
            price=Decimal(str(item['price'])),
            open_price=Decimal(str(item['open_price'])) if item.get('open_price') else None,
            high_price=Decimal(str(item['high_price'])) if item.get('high_price') else None,
            low_price=Decimal(str(item['low_price'])) if item.get('low_price') else None,
            volume=item.get('volume'),
            previous_close=Decimal(str(item['previous_close'])) if item.get('previous_close') else None,
            change_amount=Decimal(str(item['change_amount'])) if item.get('change_amount') else None,
            change_percent=Decimal(str(item['change_percent'])) if item.get('change_percent') else None
        )