"""
株価データプロバイダーのテスト
"""
import pytest
from unittest.mock import patch
from decimal import Decimal
from datetime import datetime, UTC
import pandas as pd
import aiohttp

from src.stock_monitoring_bot.services.data_provider import (
    StockDataProvider, 
    StockDataProviderError
)
from src.stock_monitoring_bot.models.stock import StockPrice


class TestStockDataProvider:
    """StockDataProviderのテストクラス"""
    
    @pytest.fixture
    def provider(self):
        """テスト用プロバイダーインスタンス"""
        return StockDataProvider(alpha_vantage_api_key="test_api_key")
    
    @pytest.fixture
    def provider_no_alpha(self):
        """Alpha Vantage APIキーなしのプロバイダー"""
        return StockDataProvider()
    
    def test_validate_symbol_valid_cases(self, provider):
        """有効な銘柄コードのテスト"""
        valid_symbols = [
            "AAPL",
            "MSFT", 
            "GOOGL",
            "7203",  # トヨタ
            "BRK.A",  # バークシャー・ハサウェイ
            "BRK-A",  # ハイフン付き
            "A",      # 1文字
            "ABCDEFGHIJ"  # 10文字
        ]
        
        for symbol in valid_symbols:
            assert provider.validate_symbol(symbol), f"'{symbol}' should be valid"
    
    def test_validate_symbol_invalid_cases(self, provider):
        """無効な銘柄コードのテスト"""
        invalid_symbols = [
            "",           # 空文字
            "   ",        # 空白のみ
            None,         # None
            123,          # 数値
            "ABCDEFGHIJK", # 11文字（長すぎる）
            "AA@PL",      # 無効文字
            "AA PL",      # スペース
            "AA/PL",      # スラッシュ
        ]
        
        for symbol in invalid_symbols:
            assert not provider.validate_symbol(symbol), f"'{symbol}' should be invalid"
    
    @pytest.mark.asyncio
    async def test_get_current_price_invalid_symbol(self, provider):
        """無効な銘柄コードでのエラーテスト"""
        with pytest.raises(StockDataProviderError, match="無効な銘柄コード"):
            await provider.get_current_price("INVALID@SYMBOL")
    
    @pytest.mark.asyncio
    async def test_get_current_price_yahoo_success(self, provider):
        """Yahoo Finance API成功時のテスト"""
        mock_data = {
            'regularMarketPrice': 150.0,
            'regularMarketOpen': 148.0,
            'regularMarketDayHigh': 152.0,
            'regularMarketDayLow': 147.0,
            'regularMarketVolume': 1000000,
            'regularMarketPreviousClose': 149.0,
            'symbol': 'AAPL'
        }
        
        with patch.object(provider, '_fetch_yahoo_data', return_value=mock_data):
            result = await provider.get_current_price("AAPL")
            
            assert isinstance(result, StockPrice)
            assert result.symbol == "AAPL"
            assert result.price == Decimal("150.0")
            assert result.open_price == Decimal("148.0")
            assert result.high_price == Decimal("152.0")
            assert result.low_price == Decimal("147.0")
            assert result.volume == 1000000
            assert result.previous_close == Decimal("149.0")
            assert result.change_amount == Decimal("1.0")  # 150 - 149
            assert result.change_percent == Decimal("0.6711409395973154362416107383")  # (1/149)*100
    
    @pytest.mark.asyncio
    async def test_get_current_price_yahoo_fallback_to_alpha(self, provider):
        """Yahoo Finance失敗時のAlpha Vantageフォールバックテスト"""
        # Yahoo Financeを失敗させる
        with patch.object(provider, '_fetch_yahoo_data', side_effect=Exception("Yahoo API Error")):
            # Alpha Vantage APIを直接モック
            with patch.object(provider, '_get_price_from_alpha_vantage') as mock_alpha:
                mock_stock_price = StockPrice(
                    symbol="AAPL",
                    timestamp=datetime.now(UTC),
                    price=Decimal("150.0000"),
                    open_price=Decimal("148.0000"),
                    high_price=Decimal("152.0000"),
                    low_price=Decimal("147.0000"),
                    volume=1000000,
                    previous_close=Decimal("149.0000")
                )
                mock_alpha.return_value = mock_stock_price
                
                result = await provider.get_current_price("AAPL")
                
                assert isinstance(result, StockPrice)
                assert result.symbol == "AAPL"
                assert result.price == Decimal("150.0000")
                mock_alpha.assert_called_once_with("AAPL")
    
    @pytest.mark.asyncio
    async def test_get_current_price_all_apis_fail(self, provider):
        """全てのAPI失敗時のテスト"""
        with patch.object(provider, '_fetch_yahoo_data', side_effect=Exception("Yahoo API Error")):
            # Alpha Vantageも失敗させる
            with patch.object(provider, '_get_price_from_alpha_vantage', side_effect=Exception("Alpha API Error")):
                with pytest.raises(StockDataProviderError, match="全てのデータソースで取得失敗"):
                    await provider.get_current_price("AAPL")
    
    @pytest.mark.asyncio
    async def test_get_current_price_no_alpha_key(self, provider_no_alpha):
        """Alpha Vantage APIキーなしでYahoo失敗時のテスト"""
        with patch.object(provider_no_alpha, '_fetch_yahoo_data', side_effect=Exception("Yahoo API Error")):
            with pytest.raises(StockDataProviderError, match="Yahoo Finance APIでの取得失敗"):
                await provider_no_alpha.get_current_price("AAPL")
    
    @pytest.mark.asyncio
    async def test_get_historical_data_success(self, provider):
        """過去データ取得成功時のテスト"""
        # モックのDataFrame作成
        dates = pd.date_range('2024-01-01', periods=3, freq='D')
        mock_hist_data = pd.DataFrame({
            'Open': [100.0, 101.0, 102.0],
            'High': [105.0, 106.0, 107.0],
            'Low': [99.0, 100.0, 101.0],
            'Close': [104.0, 105.0, 106.0],
            'Volume': [1000000, 1100000, 1200000]
        }, index=dates)
        
        with patch.object(provider, '_fetch_yahoo_history', return_value=mock_hist_data):
            result = await provider.get_historical_data("AAPL", "3d")
            
            assert len(result) == 3
            assert all(isinstance(price, StockPrice) for price in result)
            assert result[0].symbol == "AAPL"
            assert result[0].price == Decimal("104.0")
            assert result[1].price == Decimal("105.0")
            assert result[2].price == Decimal("106.0")
    
    @pytest.mark.asyncio
    async def test_get_historical_data_invalid_symbol(self, provider):
        """過去データ取得で無効な銘柄コードのテスト"""
        with pytest.raises(StockDataProviderError, match="無効な銘柄コード"):
            await provider.get_historical_data("INVALID@SYMBOL")
    
    @pytest.mark.asyncio
    async def test_get_historical_data_no_data(self, provider):
        """過去データが取得できない場合のテスト"""
        with patch.object(provider, '_fetch_yahoo_history', return_value=None):
            with pytest.raises(StockDataProviderError, match="Yahoo Financeから過去データを取得できませんでした"):
                await provider.get_historical_data("AAPL")
    
    def test_parse_yahoo_data_success(self, provider):
        """Yahoo Financeデータ解析成功時のテスト"""
        mock_data = {
            'regularMarketPrice': 150.0,
            'regularMarketOpen': 148.0,
            'regularMarketDayHigh': 152.0,
            'regularMarketDayLow': 147.0,
            'regularMarketVolume': 1000000,
            'regularMarketPreviousClose': 149.0
        }
        
        result = provider._parse_yahoo_data("AAPL", mock_data)
        
        assert isinstance(result, StockPrice)
        assert result.symbol == "AAPL"
        assert result.price == Decimal("150.0")
        assert result.change_amount == Decimal("1.0")
    
    def test_parse_yahoo_data_invalid_price(self, provider):
        """Yahoo Financeデータで無効な価格のテスト"""
        mock_data = {
            'regularMarketPrice': 0,  # 無効な価格
        }
        
        with pytest.raises(StockDataProviderError, match="Yahoo Financeデータの解析に失敗"):
            provider._parse_yahoo_data("AAPL", mock_data)
    
    def test_parse_alpha_vantage_data_success(self, provider):
        """Alpha Vantageデータ解析成功時のテスト"""
        mock_data = {
            "Global Quote": {
                "01. symbol": "AAPL",
                "02. open": "148.0000",
                "03. high": "152.0000",
                "04. low": "147.0000", 
                "05. price": "150.0000",
                "06. volume": "1000000",
                "08. previous close": "149.0000"
            }
        }
        
        result = provider._parse_alpha_vantage_data("AAPL", mock_data)
        
        assert isinstance(result, StockPrice)
        assert result.symbol == "AAPL"
        assert result.price == Decimal("150.0000")
        assert result.change_amount == Decimal("1.0000")
    
    def test_parse_alpha_vantage_data_error_message(self, provider):
        """Alpha Vantageのエラーメッセージテスト"""
        mock_data = {
            "Error Message": "Invalid API call"
        }
        
        with pytest.raises(StockDataProviderError, match="Alpha Vantage APIエラー"):
            provider._parse_alpha_vantage_data("AAPL", mock_data)
    
    def test_parse_alpha_vantage_data_rate_limit(self, provider):
        """Alpha Vantageのレート制限テスト"""
        mock_data = {
            "Note": "Thank you for using Alpha Vantage! Our standard API call frequency is 5 calls per minute"
        }
        
        with pytest.raises(StockDataProviderError, match="Alpha Vantage API呼び出し制限に達しました"):
            provider._parse_alpha_vantage_data("AAPL", mock_data)
    
    def test_parse_alpha_vantage_data_no_quote(self, provider):
        """Alpha VantageでGlobal Quoteがない場合のテスト"""
        mock_data = {}
        
        with pytest.raises(StockDataProviderError, match="Alpha VantageからGlobal Quoteデータを取得できませんでした"):
            provider._parse_alpha_vantage_data("AAPL", mock_data)
    
    @pytest.mark.asyncio
    async def test_context_manager(self):
        """非同期コンテキストマネージャーのテスト"""
        async with StockDataProvider() as provider:
            assert provider.session is not None
            assert isinstance(provider.session, aiohttp.ClientSession)
        
        # コンテキスト終了後はセッションがクローズされている
        assert provider.session.closed


@pytest.mark.integration
class TestStockDataProviderIntegration:
    """統合テスト（実際のAPIを使用）"""
    
    @pytest.mark.asyncio
    async def test_real_yahoo_finance_api(self):
        """実際のYahoo Finance APIテスト（ネットワーク接続が必要）"""
        async with StockDataProvider() as provider:
            try:
                # 有名な銘柄で実際にテスト
                result = await provider.get_current_price("AAPL")
                
                assert isinstance(result, StockPrice)
                assert result.symbol == "AAPL"
                assert result.price > 0
                assert result.timestamp is not None
                
            except StockDataProviderError:
                # ネットワークエラーやAPI制限の場合はスキップ
                pytest.skip("Yahoo Finance APIにアクセスできません")
    
    @pytest.mark.asyncio
    async def test_real_historical_data(self):
        """実際の過去データ取得テスト"""
        async with StockDataProvider() as provider:
            try:
                result = await provider.get_historical_data("AAPL", "5d")
                
                assert len(result) > 0
                assert all(isinstance(price, StockPrice) for price in result)
                assert all(price.symbol == "AAPL" for price in result)
                
            except StockDataProviderError:
                pytest.skip("Yahoo Finance APIにアクセスできません")