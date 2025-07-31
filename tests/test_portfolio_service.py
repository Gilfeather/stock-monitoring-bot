"""
ポートフォリオサービスのテスト
"""
import pytest
from datetime import datetime, UTC
from decimal import Decimal
from unittest.mock import AsyncMock

from src.stock_monitoring_bot.services.portfolio_service import (
    PortfolioService, PortfolioCommandHandler
)
from src.stock_monitoring_bot.models.stock import (
    PortfolioHolding, ProfitLossCalculation, 
    StockPrice
)


class TestPortfolioService:
    """PortfolioServiceのテスト"""
    
    def setup_method(self):
        """テストセットアップ"""
        self.mock_data_provider = AsyncMock()
        self.service = PortfolioService(self.mock_data_provider)
        self.user_id = "test_user_123"
    
    @pytest.mark.asyncio
    async def test_create_portfolio(self):
        """ポートフォリオ作成テスト"""
        name = "テストポートフォリオ"
        description = "テスト用"
        
        portfolio = await self.service.create_portfolio(self.user_id, name, description)
        
        assert portfolio.user_id == self.user_id
        assert portfolio.name == name
        assert portfolio.description == description
        assert portfolio.is_active is True
        assert portfolio.portfolio_id in self.service._portfolios
    
    @pytest.mark.asyncio
    async def test_get_portfolio(self):
        """ポートフォリオ取得テスト"""
        portfolio = await self.service.create_portfolio(self.user_id, "テスト")
        
        retrieved = await self.service.get_portfolio(portfolio.portfolio_id)
        
        assert retrieved is not None
        assert retrieved.portfolio_id == portfolio.portfolio_id
        assert retrieved.user_id == self.user_id
    
    @pytest.mark.asyncio
    async def test_get_user_portfolios(self):
        """ユーザーポートフォリオ一覧取得テスト"""
        portfolio1 = await self.service.create_portfolio(self.user_id, "ポートフォリオ1")
        portfolio2 = await self.service.create_portfolio(self.user_id, "ポートフォリオ2")
        portfolio3 = await self.service.create_portfolio("other_user", "他のユーザー")
        
        user_portfolios = await self.service.get_user_portfolios(self.user_id)
        
        assert len(user_portfolios) == 2
        portfolio_ids = [p.portfolio_id for p in user_portfolios]
        assert portfolio1.portfolio_id in portfolio_ids
        assert portfolio2.portfolio_id in portfolio_ids
        assert portfolio3.portfolio_id not in portfolio_ids
    
    @pytest.mark.asyncio
    async def test_add_holding(self):
        """保有銘柄追加テスト"""
        portfolio = await self.service.create_portfolio(self.user_id, "テスト")
        
        symbol = "7203"
        quantity = 100
        purchase_price = Decimal("2500.00")
        
        holding = await self.service.add_holding(
            portfolio.portfolio_id, symbol, quantity, purchase_price
        )
        
        assert holding.portfolio_id == portfolio.portfolio_id
        assert holding.symbol == symbol
        assert holding.quantity == quantity
        assert holding.purchase_price == purchase_price
        assert holding.is_active is True
    
    @pytest.mark.asyncio
    async def test_add_holding_invalid_portfolio(self):
        """無効なポートフォリオへの保有銘柄追加テスト"""
        with pytest.raises(ValueError, match="ポートフォリオが見つかりません"):
            await self.service.add_holding(
                "invalid_id", "7203", 100, Decimal("2500")
            )
    
    @pytest.mark.asyncio
    async def test_remove_holding(self):
        """保有銘柄削除テスト"""
        portfolio = await self.service.create_portfolio(self.user_id, "テスト")
        holding = await self.service.add_holding(
            portfolio.portfolio_id, "7203", 100, Decimal("2500")
        )
        
        result = await self.service.remove_holding(holding.holding_id)
        
        assert result is True
        assert holding.is_active is False
    
    @pytest.mark.asyncio
    async def test_get_portfolio_holdings(self):
        """ポートフォリオ保有銘柄取得テスト"""
        portfolio = await self.service.create_portfolio(self.user_id, "テスト")
        
        holding1 = await self.service.add_holding(
            portfolio.portfolio_id, "7203", 100, Decimal("2500")
        )
        holding2 = await self.service.add_holding(
            portfolio.portfolio_id, "AAPL", 50, Decimal("150.00")
        )
        
        # 1つを削除
        await self.service.remove_holding(holding2.holding_id)
        
        holdings = await self.service.get_portfolio_holdings(portfolio.portfolio_id)
        
        assert len(holdings) == 1
        assert holdings[0].holding_id == holding1.holding_id
    
    @pytest.mark.asyncio
    async def test_update_holding(self):
        """保有銘柄更新テスト"""
        portfolio = await self.service.create_portfolio(self.user_id, "テスト")
        holding = await self.service.add_holding(
            portfolio.portfolio_id, "7203", 100, Decimal("2500")
        )
        
        new_quantity = 200
        new_price = Decimal("2600")
        new_notes = "更新テスト"
        
        updated = await self.service.update_holding(
            holding.holding_id, new_quantity, new_price, new_notes
        )
        
        assert updated is not None
        assert updated.quantity == new_quantity
        assert updated.purchase_price == new_price
        assert updated.notes == new_notes
    
    @pytest.mark.asyncio
    async def test_calculate_portfolio_pnl(self):
        """ポートフォリオ損益計算テスト"""
        # モックデータ設定
        self.mock_data_provider.get_current_price.return_value = StockPrice(
            symbol="7203",
            timestamp=datetime.now(UTC),
            price=Decimal("3000.00")  # 取得価格2500から+500の利益
        )
        
        portfolio = await self.service.create_portfolio(self.user_id, "テスト")
        await self.service.add_holding(
            portfolio.portfolio_id, "7203", 100, Decimal("2500.00")
        )
        
        report = await self.service.calculate_portfolio_pnl(portfolio.portfolio_id)
        
        assert report is not None
        assert report.portfolio_id == portfolio.portfolio_id
        assert len(report.holdings) == 1
        
        holding_pnl = report.holdings[0]
        assert holding_pnl.symbol == "7203"
        assert holding_pnl.purchase_price == Decimal("2500.00")
        assert holding_pnl.current_price == Decimal("3000.00")
        assert holding_pnl.unrealized_pnl == Decimal("50000.00")  # (3000-2500) * 100
        assert holding_pnl.unrealized_pnl_percent == Decimal("20.00")  # 20%の利益
        
        assert report.total_purchase_value == Decimal("250000.00")
        assert report.total_current_value == Decimal("300000.00")
        assert report.total_unrealized_pnl == Decimal("50000.00")
        assert report.total_unrealized_pnl_percent == Decimal("20.00")
    
    @pytest.mark.asyncio
    async def test_calculate_portfolio_pnl_with_error(self):
        """価格取得エラー時の損益計算テスト"""
        # 価格取得でエラーが発生する場合
        self.mock_data_provider.get_current_price.side_effect = Exception("API Error")
        
        portfolio = await self.service.create_portfolio(self.user_id, "テスト")
        await self.service.add_holding(
            portfolio.portfolio_id, "7203", 100, Decimal("2500.00")
        )
        
        report = await self.service.calculate_portfolio_pnl(portfolio.portfolio_id)
        
        assert report is not None
        assert len(report.holdings) == 1
        
        # エラー時は取得価格を現在価格として使用
        holding_pnl = report.holdings[0]
        assert holding_pnl.current_price == Decimal("2500.00")
        assert holding_pnl.unrealized_pnl == Decimal("0.00")
    
    @pytest.mark.asyncio
    async def test_get_portfolio_summary(self):
        """ポートフォリオサマリー取得テスト"""
        self.mock_data_provider.get_current_price.return_value = StockPrice(
            symbol="7203",
            timestamp=datetime.now(UTC),
            price=Decimal("3000.00")
        )
        
        portfolio = await self.service.create_portfolio(self.user_id, "テスト")
        await self.service.add_holding(
            portfolio.portfolio_id, "7203", 100, Decimal("2500.00")
        )
        await self.service.add_holding(
            portfolio.portfolio_id, "7203", 50, Decimal("2600.00")  # 同じ銘柄の追加購入
        )
        
        summary = await self.service.get_portfolio_summary(portfolio.portfolio_id)
        
        assert summary is not None
        assert summary["holdings_count"] == 2
        assert summary["unique_symbols"] == 1  # 7203のみ
        assert summary["total_purchase_value"] == Decimal("380000.00")  # 250000 + 130000


class TestProfitLossCalculation:
    """ProfitLossCalculationのテスト"""
    
    def test_calculate_profit(self):
        """利益計算テスト"""
        holding = PortfolioHolding(
            holding_id="test",
            portfolio_id="test",
            symbol="7203",
            quantity=100,
            purchase_price=Decimal("2500.00"),
            purchase_date=datetime.now(UTC)
        )
        
        current_price = Decimal("3000.00")
        pnl = ProfitLossCalculation.calculate(holding, current_price)
        
        assert pnl.symbol == "7203"
        assert pnl.quantity == 100
        assert pnl.purchase_price == Decimal("2500.00")
        assert pnl.current_price == Decimal("3000.00")
        assert pnl.purchase_value == Decimal("250000.00")
        assert pnl.current_value == Decimal("300000.00")
        assert pnl.unrealized_pnl == Decimal("50000.00")
        assert pnl.unrealized_pnl_percent == Decimal("20.00")
    
    def test_calculate_loss(self):
        """損失計算テスト"""
        holding = PortfolioHolding(
            holding_id="test",
            portfolio_id="test",
            symbol="7203",
            quantity=100,
            purchase_price=Decimal("3000.00"),
            purchase_date=datetime.now(UTC)
        )
        
        current_price = Decimal("2500.00")
        pnl = ProfitLossCalculation.calculate(holding, current_price)
        
        assert pnl.unrealized_pnl == Decimal("-50000.00")
        # 計算精度の許容範囲を設定
        expected_percent = Decimal("-16.67")
        actual_percent = pnl.unrealized_pnl_percent.quantize(Decimal("0.01"))
        assert actual_percent == expected_percent


class TestPortfolioCommandHandler:
    """PortfolioCommandHandlerのテスト"""
    
    def setup_method(self):
        """テストセットアップ"""
        self.mock_data_provider = AsyncMock()
        self.portfolio_service = PortfolioService(self.mock_data_provider)
        self.handler = PortfolioCommandHandler(self.portfolio_service)
        self.user_id = "test_user_123"
    
    @pytest.mark.asyncio
    async def test_handle_portfolio_add_command(self):
        """ポートフォリオ追加コマンドテスト"""
        result = await self.handler.handle_portfolio_add_command(
            self.user_id, "7203", 100, Decimal("2500.00")
        )
        
        assert "追加しました" in result
        assert "7203" in result
        assert "100" in result
        assert "2,500.00" in result
    
    @pytest.mark.asyncio
    async def test_handle_portfolio_list_command_empty(self):
        """空のポートフォリオ一覧コマンドテスト"""
        result = await self.handler.handle_portfolio_list_command(self.user_id)
        
        assert "ポートフォリオが見つかりません" in result
        assert "!portfolio add" in result
    
    @pytest.mark.asyncio
    async def test_handle_portfolio_list_command_with_holdings(self):
        """保有銘柄ありのポートフォリオ一覧コマンドテスト"""
        # 事前にポートフォリオと保有銘柄を作成
        await self.handler.handle_portfolio_add_command(
            self.user_id, "7203", 100, Decimal("2500.00")
        )
        
        result = await self.handler.handle_portfolio_list_command(self.user_id)
        
        assert "ポートフォリオ一覧" in result
        assert "7203" in result
        assert "100" in result
    
    @pytest.mark.asyncio
    async def test_handle_portfolio_remove_command(self):
        """ポートフォリオ削除コマンドテスト"""
        # 事前に保有銘柄を追加
        await self.handler.handle_portfolio_add_command(
            self.user_id, "7203", 100, Decimal("2500.00")
        )
        
        result = await self.handler.handle_portfolio_remove_command(self.user_id, "7203")
        
        assert "削除しました" in result
        assert "7203" in result
    
    @pytest.mark.asyncio
    async def test_handle_portfolio_pnl_command(self):
        """ポートフォリオ損益コマンドテスト"""
        # モック設定
        self.mock_data_provider.get_current_price.return_value = StockPrice(
            symbol="7203",
            timestamp=datetime.now(UTC),
            price=Decimal("3000.00")
        )
        
        # 事前に保有銘柄を追加
        await self.handler.handle_portfolio_add_command(
            self.user_id, "7203", 100, Decimal("2500.00")
        )
        
        result = await self.handler.handle_portfolio_pnl_command(self.user_id)
        
        assert "含み損益レポート" in result
        assert "ポートフォリオ" in result
        assert "取得価格合計" in result
        assert "現在価格合計" in result
        assert "含み損益" in result


@pytest.mark.asyncio
async def test_integration_portfolio_workflow():
    """ポートフォリオ機能の統合テスト"""
    mock_data_provider = AsyncMock()
    mock_data_provider.get_current_price.return_value = StockPrice(
        symbol="7203",
        timestamp=datetime.now(UTC),
        price=Decimal("3000.00")
    )
    
    service = PortfolioService(mock_data_provider)
    handler = PortfolioCommandHandler(service)
    user_id = "integration_test_user"
    
    # 1. ポートフォリオに銘柄追加
    add_result = await handler.handle_portfolio_add_command(
        user_id, "7203", 100, Decimal("2500.00")
    )
    assert "追加しました" in add_result
    
    # 2. ポートフォリオ一覧確認
    list_result = await handler.handle_portfolio_list_command(user_id)
    assert "7203" in list_result
    assert "100" in list_result
    
    # 3. 損益レポート確認
    pnl_result = await handler.handle_portfolio_pnl_command(user_id)
    assert "含み損益レポート" in pnl_result
    assert "¥50,000.00" in pnl_result  # 利益額確認
    
    # 4. 銘柄削除
    remove_result = await handler.handle_portfolio_remove_command(user_id, "7203")
    assert "削除しました" in remove_result
    
    # 5. 削除後の一覧確認
    final_list = await handler.handle_portfolio_list_command(user_id)
    assert "保有銘柄なし" in final_list