"""
ポートフォリオ用DynamoDBリポジトリ
"""
import logging
import os
from datetime import datetime, UTC
from decimal import Decimal
from typing import List, Optional
import boto3
from botocore.exceptions import ClientError

from ..models.stock import Portfolio, PortfolioHolding


class PortfolioRepository:
    """ポートフォリオ用DynamoDBリポジトリ"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.dynamodb = boto3.resource('dynamodb')
        
        # テーブル名を環境変数から取得
        self.portfolios_table_name = os.environ.get('DYNAMODB_TABLE_PORTFOLIOS', 'stock-monitoring-bot-portfolios-dev')
        self.holdings_table_name = os.environ.get('DYNAMODB_TABLE_HOLDINGS', 'stock-monitoring-bot-holdings-dev')
        
        self.portfolios_table = self.dynamodb.Table(self.portfolios_table_name)
        self.holdings_table = self.dynamodb.Table(self.holdings_table_name)
    
    async def create_portfolio(self, portfolio: Portfolio) -> bool:
        """ポートフォリオを作成"""
        try:
            item = {
                'portfolio_id': portfolio.portfolio_id,
                'user_id': portfolio.user_id,
                'name': portfolio.name,
                'description': portfolio.description or '',
                'is_active': portfolio.is_active,
                'created_at': portfolio.created_at.isoformat(),
                'updated_at': portfolio.updated_at.isoformat()
            }
            
            self.portfolios_table.put_item(Item=item)
            self.logger.info(f"ポートフォリオ作成成功: {portfolio.portfolio_id}")
            return True
            
        except ClientError as e:
            self.logger.error(f"ポートフォリオ作成エラー: {e}")
            return False
    
    async def get_portfolio(self, portfolio_id: str) -> Optional[Portfolio]:
        """ポートフォリオを取得"""
        try:
            response = self.portfolios_table.get_item(
                Key={'portfolio_id': portfolio_id}
            )
            
            if 'Item' not in response:
                return None
            
            item = response['Item']
            return Portfolio(
                portfolio_id=item['portfolio_id'],
                user_id=item['user_id'],
                name=item['name'],
                description=item.get('description', ''),
                is_active=item.get('is_active', True),
                created_at=datetime.fromisoformat(item['created_at']),
                updated_at=datetime.fromisoformat(item['updated_at'])
            )
            
        except ClientError as e:
            self.logger.error(f"ポートフォリオ取得エラー: {e}")
            return None
    
    async def get_user_portfolios(self, user_id: str) -> List[Portfolio]:
        """ユーザーのポートフォリオ一覧を取得"""
        try:
            response = self.portfolios_table.query(
                IndexName='user_id-index',
                KeyConditionExpression='user_id = :user_id',
                FilterExpression='is_active = :active',
                ExpressionAttributeValues={
                    ':user_id': user_id,
                    ':active': True
                }
            )
            
            portfolios = []
            for item in response['Items']:
                portfolio = Portfolio(
                    portfolio_id=item['portfolio_id'],
                    user_id=item['user_id'],
                    name=item['name'],
                    description=item.get('description', ''),
                    is_active=item.get('is_active', True),
                    created_at=datetime.fromisoformat(item['created_at']),
                    updated_at=datetime.fromisoformat(item['updated_at'])
                )
                portfolios.append(portfolio)
            
            return portfolios
            
        except ClientError as e:
            self.logger.error(f"ユーザーポートフォリオ取得エラー: {e}")
            return []
    
    async def add_holding(self, holding: PortfolioHolding) -> bool:
        """保有銘柄を追加"""
        try:
            item = {
                'holding_id': holding.holding_id,
                'portfolio_id': holding.portfolio_id,
                'symbol': holding.symbol,
                'quantity': int(holding.quantity),
                'purchase_price': str(holding.purchase_price),
                'purchase_date': holding.purchase_date.isoformat(),
                'notes': holding.notes or '',
                'is_active': holding.is_active,
                'created_at': holding.created_at.isoformat(),
                'updated_at': holding.updated_at.isoformat()
            }
            
            self.holdings_table.put_item(Item=item)
            self.logger.info(f"保有銘柄追加成功: {holding.symbol}")
            return True
            
        except ClientError as e:
            self.logger.error(f"保有銘柄追加エラー: {e}")
            return False
    
    async def get_portfolio_holdings(self, portfolio_id: str) -> List[PortfolioHolding]:
        """ポートフォリオの保有銘柄一覧を取得"""
        try:
            response = self.holdings_table.query(
                IndexName='portfolio_id-index',
                KeyConditionExpression='portfolio_id = :portfolio_id',
                FilterExpression='is_active = :active',
                ExpressionAttributeValues={
                    ':portfolio_id': portfolio_id,
                    ':active': True
                }
            )
            
            holdings = []
            for item in response['Items']:
                holding = PortfolioHolding(
                    holding_id=item['holding_id'],
                    portfolio_id=item['portfolio_id'],
                    symbol=item['symbol'],
                    quantity=int(item['quantity']),
                    purchase_price=Decimal(item['purchase_price']),
                    purchase_date=datetime.fromisoformat(item['purchase_date']),
                    notes=item.get('notes', ''),
                    is_active=item.get('is_active', True),
                    created_at=datetime.fromisoformat(item['created_at']),
                    updated_at=datetime.fromisoformat(item['updated_at'])
                )
                holdings.append(holding)
            
            return holdings
            
        except ClientError as e:
            self.logger.error(f"保有銘柄取得エラー: {e}")
            return []
    
    async def remove_holding(self, holding_id: str) -> bool:
        """保有銘柄を削除（論理削除）"""
        try:
            self.holdings_table.update_item(
                Key={'holding_id': holding_id},
                UpdateExpression='SET is_active = :active, updated_at = :updated_at',
                ExpressionAttributeValues={
                    ':active': False,
                    ':updated_at': datetime.now(UTC).isoformat()
                }
            )
            
            self.logger.info(f"保有銘柄削除成功: {holding_id}")
            return True
            
        except ClientError as e:
            self.logger.error(f"保有銘柄削除エラー: {e}")
            return False
    
    async def get_user_holdings_by_symbol(self, user_id: str, symbol: str) -> List[PortfolioHolding]:
        """ユーザーの特定銘柄の保有一覧を取得"""
        try:
            # まずユーザーのポートフォリオを取得
            portfolios = await self.get_user_portfolios(user_id)
            
            all_holdings = []
            for portfolio in portfolios:
                holdings = await self.get_portfolio_holdings(portfolio.portfolio_id)
                symbol_holdings = [h for h in holdings if h.symbol.upper() == symbol.upper()]
                all_holdings.extend(symbol_holdings)
            
            return all_holdings
            
        except Exception as e:
            self.logger.error(f"銘柄別保有取得エラー: {e}")
            return []