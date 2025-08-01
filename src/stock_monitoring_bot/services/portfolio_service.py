"""
ポートフォリオ管理サービス
"""
import logging
import uuid
from datetime import datetime, UTC
from decimal import Decimal
from typing import List, Optional, Dict, Any

from ..models.stock import (
    Portfolio, PortfolioHolding, ProfitLossCalculation, 
    PortfolioProfitLossReport
)
from .data_provider import StockDataProvider
from ..repositories.portfolio_repository import PortfolioRepository


class PortfolioService:
    """ポートフォリオ管理サービス"""
    
    def __init__(self, data_provider: StockDataProvider):
        self.data_provider = data_provider
        self.logger = logging.getLogger(__name__)
        self.portfolio_repo = PortfolioRepository()
    
    async def create_portfolio(self, user_id: str, name: str, description: Optional[str] = None) -> Portfolio:
        """ポートフォリオを作成"""
        portfolio_id = str(uuid.uuid4())
        portfolio = Portfolio(
            portfolio_id=portfolio_id,
            user_id=user_id,
            name=name,
            description=description
        )
        
        success = await self.portfolio_repo.create_portfolio(portfolio)
        if success:
            self.logger.info(f"ポートフォリオ作成: {portfolio_id} - {name}")
            return portfolio
        else:
            raise Exception("ポートフォリオの作成に失敗しました")
    
    async def get_portfolio(self, portfolio_id: str) -> Optional[Portfolio]:
        """ポートフォリオを取得"""
        return await self.portfolio_repo.get_portfolio(portfolio_id)
    
    async def get_user_portfolios(self, user_id: str) -> List[Portfolio]:
        """ユーザーのポートフォリオ一覧を取得"""
        return await self.portfolio_repo.get_user_portfolios(user_id)
    
    async def add_holding(
        self, 
        portfolio_id: str, 
        symbol: str, 
        quantity: int, 
        purchase_price: Decimal,
        purchase_date: Optional[datetime] = None,
        notes: Optional[str] = None
    ) -> PortfolioHolding:
        """保有銘柄を追加"""
        portfolio = await self.portfolio_repo.get_portfolio(portfolio_id)
        if not portfolio:
            raise ValueError(f"ポートフォリオが見つかりません: {portfolio_id}")
        
        holding_id = str(uuid.uuid4())
        holding = PortfolioHolding(
            holding_id=holding_id,
            portfolio_id=portfolio_id,
            symbol=symbol,
            quantity=quantity,
            purchase_price=purchase_price,
            purchase_date=purchase_date or datetime.now(UTC),
            notes=notes
        )
        
        success = await self.portfolio_repo.add_holding(holding)
        if success:
            self.logger.info(f"保有銘柄追加: {symbol} x{quantity} @ ¥{purchase_price}")
            return holding
        else:
            raise Exception("保有銘柄の追加に失敗しました")
    
    async def remove_holding(self, holding_id: str) -> bool:
        """保有銘柄を削除"""
        return await self.portfolio_repo.remove_holding(holding_id)
    
    async def get_portfolio_holdings(self, portfolio_id: str) -> List[PortfolioHolding]:
        """ポートフォリオの保有銘柄一覧を取得"""
        return await self.portfolio_repo.get_portfolio_holdings(portfolio_id)
    
    async def update_holding(
        self, 
        holding_id: str, 
        quantity: Optional[int] = None,
        purchase_price: Optional[Decimal] = None,
        notes: Optional[str] = None
    ) -> Optional[PortfolioHolding]:
        """保有銘柄を更新"""
        # TODO: PortfolioRepositoryにupdate_holdingメソッドを追加
        self.logger.warning("update_holding is not implemented yet")
        return None
    
    async def calculate_portfolio_pnl(self, portfolio_id: str) -> Optional[PortfolioProfitLossReport]:
        """ポートフォリオの損益を計算"""
        portfolio = await self.get_portfolio(portfolio_id)
        if not portfolio:
            return None
        
        holdings = await self.get_portfolio_holdings(portfolio_id)
        if not holdings:
            return PortfolioProfitLossReport.create_report(portfolio, [])
        
        holdings_pnl = []
        
        for holding in holdings:
            try:
                # 現在価格を取得
                current_price_data = await self.data_provider.get_current_price(holding.symbol)
                current_price = current_price_data.price
                
                # 損益計算
                pnl = ProfitLossCalculation.calculate(holding, current_price)
                holdings_pnl.append(pnl)
                
            except Exception as e:
                self.logger.error(f"価格取得エラー {holding.symbol}: {e}")
                # エラーの場合は取得価格を現在価格として使用
                pnl = ProfitLossCalculation.calculate(holding, holding.purchase_price)
                holdings_pnl.append(pnl)
        
        return PortfolioProfitLossReport.create_report(portfolio, holdings_pnl)
    
    async def calculate_all_user_portfolios_pnl(self, user_id: str) -> List[PortfolioProfitLossReport]:
        """ユーザーの全ポートフォリオの損益を計算"""
        portfolios = await self.get_user_portfolios(user_id)
        reports = []
        
        for portfolio in portfolios:
            report = await self.calculate_portfolio_pnl(portfolio.portfolio_id)
            if report:
                reports.append(report)
        
        return reports
    
    async def get_portfolio_summary(self, portfolio_id: str) -> Optional[Dict[str, Any]]:
        """ポートフォリオサマリーを取得"""
        portfolio = await self.get_portfolio(portfolio_id)
        if not portfolio:
            return None
        
        holdings = await self.get_portfolio_holdings(portfolio_id)
        pnl_report = await self.calculate_portfolio_pnl(portfolio_id)
        
        return {
            "portfolio": portfolio,
            "holdings_count": len(holdings),
            "unique_symbols": len(set(h.symbol for h in holdings)),
            "total_purchase_value": pnl_report.total_purchase_value if pnl_report else Decimal('0'),
            "total_current_value": pnl_report.total_current_value if pnl_report else Decimal('0'),
            "total_unrealized_pnl": pnl_report.total_unrealized_pnl if pnl_report else Decimal('0'),
            "total_unrealized_pnl_percent": pnl_report.total_unrealized_pnl_percent if pnl_report else Decimal('0')
        }


class PortfolioCommandHandler:
    """ポートフォリオコマンドハンドラー"""
    
    def __init__(self, portfolio_service: PortfolioService):
        self.portfolio_service = portfolio_service
        self.logger = logging.getLogger(__name__)
    
    async def handle_portfolio_add_command(self, user_id: str, symbol: str, quantity: int, purchase_price: Decimal) -> str:
        """ポートフォリオに銘柄を追加"""
        try:
            # ユーザーのデフォルトポートフォリオを取得または作成
            portfolios = await self.portfolio_service.get_user_portfolios(user_id)
            if not portfolios:
                portfolio = await self.portfolio_service.create_portfolio(
                    user_id=user_id,
                    name=f"{user_id}のポートフォリオ",
                    description="デフォルトポートフォリオ"
                )
            else:
                portfolio = portfolios[0]
            
            # 銘柄を追加
            await self.portfolio_service.add_holding(
                portfolio_id=portfolio.portfolio_id,
                symbol=symbol,
                quantity=quantity,
                purchase_price=purchase_price
            )
            
            return f"✅ ポートフォリオに追加しました\n" \
                   f"銘柄: {symbol}\n" \
                   f"株数: {quantity:,}株\n" \
                   f"取得価格: ¥{purchase_price:,.2f}"
                   
        except ValueError as e:
            return f"❌ エラー: {str(e)}"
        except Exception as e:
            self.logger.error(f"ポートフォリオ追加エラー: {e}")
            return "❌ ポートフォリオへの追加に失敗しました"
    
    async def handle_portfolio_remove_command(self, user_id: str, symbol: str) -> str:
        """ポートフォリオから銘柄を削除"""
        try:
            # ユーザーの指定銘柄の保有を取得
            holdings = await self.portfolio_service.portfolio_repo.get_user_holdings_by_symbol(user_id, symbol)
            
            if not holdings:
                return f"❌ 銘柄 {symbol} が見つかりませんでした"
            
            # 全ての保有を削除
            removed_count = 0
            for holding in holdings:
                success = await self.portfolio_service.remove_holding(holding.holding_id)
                if success:
                    removed_count += 1
            
            if removed_count > 0:
                return f"✅ {symbol} をポートフォリオから削除しました（{removed_count}件）"
            else:
                return f"❌ 銘柄 {symbol} の削除に失敗しました"
                
        except Exception as e:
            self.logger.error(f"ポートフォリオ削除エラー: {e}")
            return "❌ ポートフォリオからの削除に失敗しました"
    
    async def handle_portfolio_list_command(self, user_id: str) -> str:
        """ポートフォリオ一覧を表示"""
        try:
            portfolios = await self.portfolio_service.get_user_portfolios(user_id)
            if not portfolios:
                return "📋 **ポートフォリオ一覧**\n\nポートフォリオが見つかりませんでした。\n`!portfolio add <銘柄> <株数> <取得価格>` で銘柄を追加してください。"
            
            result = "📋 **ポートフォリオ一覧**\n\n"
            
            for portfolio in portfolios:
                holdings = await self.portfolio_service.get_portfolio_holdings(portfolio.portfolio_id)
                if holdings:
                    result += f"**{portfolio.name}**\n"
                    for holding in holdings:
                        result += f"• {holding.symbol}: {holding.quantity:,}株 @ ¥{holding.purchase_price:,.2f}\n"
                    result += "\n"
                else:
                    result += f"**{portfolio.name}**: 保有銘柄なし\n\n"
            
            return result.strip()
            
        except Exception as e:
            self.logger.error(f"ポートフォリオ一覧エラー: {e}")
            return "❌ ポートフォリオ一覧の取得に失敗しました"
    
    async def handle_portfolio_pnl_command(self, user_id: str) -> str:
        """ポートフォリオ損益レポートを表示"""
        try:
            reports = await self.portfolio_service.calculate_all_user_portfolios_pnl(user_id)
            if not reports:
                return "📊 **含み損益レポート**\n\nポートフォリオが見つかりませんでした。"
            
            result = "📊 **含み損益レポート**\n\n"
            
            total_purchase = Decimal('0')
            total_current = Decimal('0')
            total_pnl = Decimal('0')
            
            for report in reports:
                result += f"**{report.portfolio_name}**\n"
                result += f"取得価格合計: ¥{report.total_purchase_value:,.2f}\n"
                result += f"現在価格合計: ¥{report.total_current_value:,.2f}\n"
                result += f"含み損益: ¥{report.total_unrealized_pnl:,.2f} ({report.total_unrealized_pnl_percent:.2f}%)\n\n"
                
                total_purchase += report.total_purchase_value
                total_current += report.total_current_value
                total_pnl += report.total_unrealized_pnl
            
            if len(reports) > 1:
                total_pnl_percent = (total_pnl / total_purchase * 100) if total_purchase > 0 else Decimal('0')
                result += "**全体合計**\n"
                result += f"取得価格合計: ¥{total_purchase:,.2f}\n"
                result += f"現在価格合計: ¥{total_current:,.2f}\n"
                result += f"含み損益: ¥{total_pnl:,.2f} ({total_pnl_percent:.2f}%)\n"
            
            return result.strip()
            
        except Exception as e:
            self.logger.error(f"損益レポートエラー: {e}")
            return "❌ 損益レポートの取得に失敗しました"
