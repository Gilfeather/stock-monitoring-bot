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


class PortfolioService:
    """ポートフォリオ管理サービス"""
    
    def __init__(self, data_provider: StockDataProvider):
        self.data_provider = data_provider
        self.logger = logging.getLogger(__name__)
        
        # TODO: 実際のデータベース接続に置き換える
        # 現在はメモリ内ストレージを使用
        self._portfolios: Dict[str, Portfolio] = {}
        self._holdings: Dict[str, List[PortfolioHolding]] = {}
    
    async def create_portfolio(self, user_id: str, name: str, description: Optional[str] = None) -> Portfolio:
        """ポートフォリオを作成"""
        portfolio_id = str(uuid.uuid4())
        portfolio = Portfolio(
            portfolio_id=portfolio_id,
            user_id=user_id,
            name=name,
            description=description
        )
        
        self._portfolios[portfolio_id] = portfolio
        self._holdings[portfolio_id] = []
        
        self.logger.info(f"ポートフォリオ作成: {portfolio_id} - {name}")
        return portfolio
    
    async def get_portfolio(self, portfolio_id: str) -> Optional[Portfolio]:
        """ポートフォリオを取得"""
        return self._portfolios.get(portfolio_id)
    
    async def get_user_portfolios(self, user_id: str) -> List[Portfolio]:
        """ユーザーのポートフォリオ一覧を取得"""
        return [p for p in self._portfolios.values() if p.user_id == user_id and p.is_active]
    
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
        if portfolio_id not in self._portfolios:
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
        
        if portfolio_id not in self._holdings:
            self._holdings[portfolio_id] = []
        
        self._holdings[portfolio_id].append(holding)
        
        self.logger.info(f"保有銘柄追加: {symbol} x{quantity} @ ¥{purchase_price}")
        return holding
    
    async def remove_holding(self, holding_id: str) -> bool:
        """保有銘柄を削除"""
        for portfolio_id, holdings in self._holdings.items():
            for i, holding in enumerate(holdings):
                if holding.holding_id == holding_id:
                    holding.is_active = False
                    self.logger.info(f"保有銘柄削除: {holding.symbol}")
                    return True
        return False
    
    async def get_portfolio_holdings(self, portfolio_id: str) -> List[PortfolioHolding]:
        """ポートフォリオの保有銘柄一覧を取得"""
        holdings = self._holdings.get(portfolio_id, [])
        return [h for h in holdings if h.is_active]
    
    async def update_holding(
        self, 
        holding_id: str, 
        quantity: Optional[int] = None,
        purchase_price: Optional[Decimal] = None,
        notes: Optional[str] = None
    ) -> Optional[PortfolioHolding]:
        """保有銘柄を更新"""
        for holdings in self._holdings.values():
            for holding in holdings:
                if holding.holding_id == holding_id and holding.is_active:
                    if quantity is not None:
                        holding.quantity = quantity
                    if purchase_price is not None:
                        holding.purchase_price = purchase_price
                    if notes is not None:
                        holding.notes = notes
                    holding.updated_at = datetime.now(UTC)
                    
                    self.logger.info(f"保有銘柄更新: {holding.symbol}")
                    return holding
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
            portfolios = await self.portfolio_service.get_user_portfolios(user_id)
            if not portfolios:
                return "❌ ポートフォリオが見つかりません"
            
            # 指定銘柄の保有を削除
            removed = False
            for portfolio in portfolios:
                holdings = await self.portfolio_service.get_portfolio_holdings(portfolio.portfolio_id)
                for holding in holdings:
                    if holding.symbol.upper() == symbol.upper():
                        await self.portfolio_service.remove_holding(holding.holding_id)
                        removed = True
                        break
                if removed:
                    break
            
            if removed:
                return f"✅ {symbol} をポートフォリオから削除しました"
            else:
                return f"❌ 銘柄 {symbol} が見つかりませんでした"
                
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
