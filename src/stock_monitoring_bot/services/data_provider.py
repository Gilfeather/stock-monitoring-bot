"""
株価データプロバイダー
Yahoo Finance APIとAlpha Vantage APIを使用して株価データを取得
"""
import asyncio
import logging
from datetime import datetime, UTC
from decimal import Decimal
from typing import List, Optional, Dict, Any
import aiohttp
import yfinance as yf
import pandas as pd
from ..models.stock import StockPrice


logger = logging.getLogger(__name__)


class StockDataProviderError(Exception):
    """データプロバイダーエラー"""
    pass


class StockDataProvider:
    """株価データプロバイダー"""
    
    def __init__(self, alpha_vantage_api_key: Optional[str] = None):
        """
        初期化
        
        Args:
            alpha_vantage_api_key: Alpha Vantage APIキー（フォールバック用）
        """
        self.alpha_vantage_api_key = alpha_vantage_api_key
        self.session: Optional[aiohttp.ClientSession] = None
        
    async def __aenter__(self):
        """非同期コンテキストマネージャー開始"""
        self.session = aiohttp.ClientSession()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """非同期コンテキストマネージャー終了"""
        if self.session:
            await self.session.close()
    
    def validate_symbol(self, symbol: str) -> bool:
        """
        銘柄コードの妥当性を検証
        
        Args:
            symbol: 銘柄コード
            
        Returns:
            bool: 妥当性
        """
        if not symbol or not isinstance(symbol, str):
            return False
            
        symbol = symbol.strip().upper()
        
        # 空文字チェック
        if not symbol:
            return False
            
        # 基本的な文字チェック（英数字、ピリオド、ハイフンのみ許可）
        if not all(c.isalnum() or c in '.-' for c in symbol):
            return False
            
        # 長さチェック（1-10文字）
        if len(symbol) < 1 or len(symbol) > 10:
            return False
            
        return True
    
    def _normalize_symbol_for_yahoo(self, symbol: str) -> str:
        """
        Yahoo Finance API用に銘柄コードを正規化
        
        Args:
            symbol: 銘柄コード
            
        Returns:
            str: 正規化された銘柄コード
        """
        symbol = symbol.strip().upper()
        
        # 既に.Tが付いている場合はそのまま
        if symbol.endswith('.T'):
            return symbol
        
        # 日本株の判定パターン
        # 1. 4桁の数字（例：2433, 7203）
        # 2. 3-4桁の数字 + 1文字のアルファベット（例：142A, 8697A）
        # 3. REITなど特殊な形式
        if self._is_japanese_stock_symbol(symbol):
            return f"{symbol}.T"
            
        # その他の場合（米国株など）はそのまま
        return symbol
    
    def _is_japanese_stock_symbol(self, symbol: str) -> bool:
        """
        日本株の銘柄コードかどうかを判定
        
        Args:
            symbol: 銘柄コード
            
        Returns:
            bool: 日本株の場合True
        """
        # 4桁の数字（例：2433, 7203）
        if symbol.isdigit() and len(symbol) == 4:
            return True
        
        # 3-4桁の数字 + 1文字のアルファベット（例：142A, 8697A）
        if len(symbol) in [4, 5] and symbol[:-1].isdigit() and symbol[-1].isalpha():
            return True
        
        # その他の日本株パターンがあれば追加
        # 例：REITの特殊コードなど
        
        return False
    
    async def get_current_price(self, symbol: str) -> StockPrice:
        """
        現在の株価を取得
        
        Args:
            symbol: 銘柄コード
            
        Returns:
            StockPrice: 株価データ
            
        Raises:
            StockDataProviderError: データ取得エラー
        """
        if not self.validate_symbol(symbol):
            raise StockDataProviderError(f"無効な銘柄コード: {symbol}")
        
        symbol = symbol.strip().upper()
        
        try:
            # まずYahoo Finance APIを試行
            return await self._get_price_from_yahoo(symbol)
        except Exception as e:
            logger.warning(f"Yahoo Finance APIでの取得に失敗: {symbol}, エラー: {e}")
            
            # フォールバックとしてAlpha Vantage APIを試行
            if self.alpha_vantage_api_key:
                try:
                    return await self._get_price_from_alpha_vantage(symbol)
                except Exception as fallback_error:
                    logger.error(f"Alpha Vantage APIでの取得も失敗: {symbol}, エラー: {fallback_error}")
                    raise StockDataProviderError(f"全てのデータソースで取得失敗: {symbol}")
            else:
                raise StockDataProviderError(f"Yahoo Finance APIでの取得失敗: {symbol}, エラー: {e}")
    
    async def get_historical_data(self, symbol: str, period: str = "1d") -> List[StockPrice]:
        """
        過去の株価データを取得
        
        Args:
            symbol: 銘柄コード
            period: 期間（1d, 5d, 1mo, 3mo, 6mo, 1y, 2y, 5y, 10y, ytd, max）
            
        Returns:
            List[StockPrice]: 株価データのリスト
            
        Raises:
            StockDataProviderError: データ取得エラー
        """
        if not self.validate_symbol(symbol):
            raise StockDataProviderError(f"無効な銘柄コード: {symbol}")
        
        symbol = symbol.strip().upper()
        
        try:
            return await self._get_historical_from_yahoo(symbol, period)
        except Exception as e:
            logger.error(f"過去データ取得失敗: {symbol}, 期間: {period}, エラー: {e}")
            raise StockDataProviderError(f"過去データ取得失敗: {symbol}, エラー: {e}")
    
    async def _get_price_from_yahoo(self, symbol: str) -> StockPrice:
        """
        Yahoo Finance APIから株価を取得
        
        Args:
            symbol: 銘柄コード
            
        Returns:
            StockPrice: 株価データ
        """
        # Yahoo Finance用に銘柄コードを正規化
        yahoo_symbol = self._normalize_symbol_for_yahoo(symbol)
        
        # yfinanceは同期APIなので、別スレッドで実行
        loop = asyncio.get_event_loop()
        ticker_data = await loop.run_in_executor(None, self._fetch_yahoo_data, yahoo_symbol)
        
        if not ticker_data:
            raise StockDataProviderError(f"Yahoo Financeからデータを取得できませんでした: {symbol}")
        
        return self._parse_yahoo_data(symbol, ticker_data)
    
    def _fetch_yahoo_data(self, symbol: str) -> Dict[str, Any]:
        """
        Yahoo Financeからデータを同期取得（エグゼキューター用）
        
        Args:
            symbol: 銘柄コード
            
        Returns:
            Dict[str, Any]: 取得データ
        """
        try:
            logger.info(f"Yahoo Financeからデータ取得開始: {symbol}")
            ticker = yf.Ticker(symbol)
            info = ticker.info
            
            logger.debug(f"Yahoo Finance info取得結果: {symbol}, keys: {list(info.keys()) if info else 'None'}")
            
            # 基本的な株価情報が取得できているかチェック
            if not info or 'regularMarketPrice' not in info:
                logger.info(f"infoから価格取得失敗、historyを試行: {symbol}")
                # infoが空の場合、historyから最新データを取得
                hist = ticker.history(period="1d")
                if hist.empty:
                    logger.warning(f"historyも空でした: {symbol}")
                    return {}
                
                logger.info(f"historyから最新データを取得: {symbol}")
                latest = hist.iloc[-1]
                return {
                    'regularMarketPrice': float(latest['Close']),
                    'regularMarketOpen': float(latest['Open']),
                    'regularMarketDayHigh': float(latest['High']),
                    'regularMarketDayLow': float(latest['Low']),
                    'regularMarketVolume': int(latest['Volume']),
                    'regularMarketPreviousClose': float(latest['Close']),  # 暫定値
                    'symbol': symbol
                }
            
            logger.info(f"Yahoo Finance info取得成功: {symbol}")
            return info
        except Exception as e:
            logger.error(f"Yahoo Financeデータ取得エラー: {symbol}, {e}")
            return {}
    
    def _parse_yahoo_data(self, symbol: str, data: Dict[str, Any]) -> StockPrice:
        """
        Yahoo Financeのデータを解析してStockPriceオブジェクトを作成
        
        Args:
            symbol: 銘柄コード
            data: Yahoo Financeからの生データ
            
        Returns:
            StockPrice: 株価データ
        """
        try:
            current_price = Decimal(str(data.get('regularMarketPrice', 0)))
            if current_price <= 0:
                raise ValueError("無効な価格データ")
            
            open_price = data.get('regularMarketOpen')
            high_price = data.get('regularMarketDayHigh')
            low_price = data.get('regularMarketDayLow')
            volume = data.get('regularMarketVolume')
            previous_close = data.get('regularMarketPreviousClose')
            
            stock_price = StockPrice(
                symbol=symbol,
                timestamp=datetime.now(UTC),
                price=current_price,
                open_price=Decimal(str(open_price)) if open_price else None,
                high_price=Decimal(str(high_price)) if high_price else None,
                low_price=Decimal(str(low_price)) if low_price else None,
                volume=int(volume) if volume else None,
                previous_close=Decimal(str(previous_close)) if previous_close else None
            )
            
            # 変動額と変動率を計算
            stock_price.calculate_change()
            
            return stock_price
            
        except (ValueError, KeyError, TypeError) as e:
            raise StockDataProviderError(f"Yahoo Financeデータの解析に失敗: {symbol}, エラー: {e}")
    
    async def _get_historical_from_yahoo(self, symbol: str, period: str) -> List[StockPrice]:
        """
        Yahoo Finance APIから過去データを取得
        
        Args:
            symbol: 銘柄コード
            period: 期間
            
        Returns:
            List[StockPrice]: 株価データのリスト
        """
        # Yahoo Finance用に銘柄コードを正規化
        yahoo_symbol = self._normalize_symbol_for_yahoo(symbol)
        
        loop = asyncio.get_event_loop()
        hist_data = await loop.run_in_executor(None, self._fetch_yahoo_history, yahoo_symbol, period)
        
        if hist_data is None or hist_data.empty:
            raise StockDataProviderError(f"Yahoo Financeから過去データを取得できませんでした: {symbol}")
        
        return self._parse_yahoo_history(symbol, hist_data)
    
    def _fetch_yahoo_history(self, symbol: str, period: str):
        """
        Yahoo Financeから過去データを同期取得（エグゼキューター用）
        
        Args:
            symbol: 銘柄コード
            period: 期間
            
        Returns:
            pandas.DataFrame: 過去データ
        """
        try:
            ticker = yf.Ticker(symbol)
            return ticker.history(period=period)
        except Exception as e:
            logger.error(f"Yahoo Finance過去データ取得エラー: {symbol}, {e}")
            return None
    
    def _parse_yahoo_history(self, symbol: str, hist_data) -> List[StockPrice]:
        """
        Yahoo Financeの過去データを解析
        
        Args:
            symbol: 銘柄コード
            hist_data: pandas.DataFrame
            
        Returns:
            List[StockPrice]: 株価データのリスト
        """
        stock_prices = []
        
        for index, row in hist_data.iterrows():
            try:
                # 前日終値を計算（前の行のCloseを使用）
                previous_close = None
                if len(stock_prices) > 0:
                    previous_close = stock_prices[-1].price
                
                stock_price = StockPrice(
                    symbol=symbol,
                    timestamp=index.to_pydatetime().replace(tzinfo=UTC),
                    price=Decimal(str(row['Close'])),
                    open_price=Decimal(str(row['Open'])),
                    high_price=Decimal(str(row['High'])),
                    low_price=Decimal(str(row['Low'])),
                    volume=int(row['Volume']) if not pd.isna(row['Volume']) else None,
                    previous_close=previous_close
                )
                
                # 変動額と変動率を計算
                stock_price.calculate_change()
                
                stock_prices.append(stock_price)
                
            except (ValueError, KeyError, TypeError) as e:
                logger.warning(f"過去データの行をスキップ: {symbol}, {index}, エラー: {e}")
                continue
        
        return stock_prices
    
    async def _get_historical_from_alpha_vantage(self, symbol: str, period: str) -> List[StockPrice]:
        """
        Alpha Vantage APIから過去データを取得
        
        Args:
            symbol: 銘柄コード
            period: 期間（Alpha Vantageでは使用しない、1日分のみ取得）
            
        Returns:
            List[StockPrice]: 株価データのリスト
        """
        if not self.session:
            raise StockDataProviderError("HTTPセッションが初期化されていません")
        
        url = "https://www.alphavantage.co/query"
        params = {
            "function": "TIME_SERIES_DAILY",
            "symbol": symbol,
            "apikey": self.alpha_vantage_api_key
        }
        
        try:
            async with self.session.get(url, params=params) as response:
                if response.status != 200:
                    raise StockDataProviderError(f"Alpha Vantage API HTTPエラー: {response.status}")
                
                data = await response.json()
                return self._parse_alpha_vantage_historical(symbol, data)
                
        except aiohttp.ClientError as e:
            raise StockDataProviderError(f"Alpha Vantage API接続エラー: {e}")
    
    def _parse_alpha_vantage_historical(self, symbol: str, data: Dict[str, Any]) -> List[StockPrice]:
        """
        Alpha Vantageの過去データを解析
        
        Args:
            symbol: 銘柄コード
            data: Alpha Vantageからの生データ
            
        Returns:
            List[StockPrice]: 株価データのリスト
        """
        try:
            if "Error Message" in data:
                raise StockDataProviderError(f"Alpha Vantage APIエラー: {data['Error Message']}")
            
            if "Note" in data:
                raise StockDataProviderError("Alpha Vantage API呼び出し制限に達しました")
            
            time_series = data.get("Time Series (Daily)", {})
            if not time_series:
                raise StockDataProviderError("Alpha VantageからTime Seriesデータを取得できませんでした")
            
            stock_prices = []
            previous_close = None
            
            # 日付順に並び替え（古い順）
            sorted_dates = sorted(time_series.keys())
            
            for date_str in sorted_dates:
                day_data = time_series[date_str]
                try:
                    stock_price = StockPrice(
                        symbol=symbol,
                        timestamp=datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=UTC),
                        price=Decimal(day_data.get("4. close", "0")),
                        open_price=Decimal(day_data.get("1. open", "0")),
                        high_price=Decimal(day_data.get("2. high", "0")),
                        low_price=Decimal(day_data.get("3. low", "0")),
                        volume=int(day_data.get("5. volume", "0")),
                        previous_close=previous_close
                    )
                    
                    # 変動額と変動率を計算
                    stock_price.calculate_change()
                    
                    stock_prices.append(stock_price)
                    previous_close = stock_price.price
                    
                except (ValueError, KeyError, TypeError) as e:
                    logger.warning(f"過去データの日付をスキップ: {symbol}, {date_str}, エラー: {e}")
                    continue
            
            return stock_prices
            
        except (ValueError, KeyError, TypeError) as e:
            raise StockDataProviderError(f"Alpha Vantage過去データの解析に失敗: {symbol}, エラー: {e}")
    
    async def _get_price_from_alpha_vantage(self, symbol: str) -> StockPrice:
        """
        Alpha Vantage APIから株価を取得（フォールバック）
        
        Args:
            symbol: 銘柄コード
            
        Returns:
            StockPrice: 株価データ
        """
        if not self.session:
            raise StockDataProviderError("HTTPセッションが初期化されていません")
        
        url = "https://www.alphavantage.co/query"
        params = {
            "function": "GLOBAL_QUOTE",
            "symbol": symbol,
            "apikey": self.alpha_vantage_api_key
        }
        
        try:
            async with self.session.get(url, params=params) as response:
                if response.status != 200:
                    raise StockDataProviderError(f"Alpha Vantage API HTTPエラー: {response.status}")
                
                data = await response.json()
                return self._parse_alpha_vantage_data(symbol, data)
                
        except aiohttp.ClientError as e:
            raise StockDataProviderError(f"Alpha Vantage API接続エラー: {e}")
    
    def _parse_alpha_vantage_data(self, symbol: str, data: Dict[str, Any]) -> StockPrice:
        """
        Alpha Vantageのデータを解析してStockPriceオブジェクトを作成
        
        Args:
            symbol: 銘柄コード
            data: Alpha Vantageからの生データ
            
        Returns:
            StockPrice: 株価データ
        """
        try:
            if "Error Message" in data:
                raise StockDataProviderError(f"Alpha Vantage APIエラー: {data['Error Message']}")
            
            if "Note" in data:
                raise StockDataProviderError("Alpha Vantage API呼び出し制限に達しました")
            
            quote_data = data.get("Global Quote", {})
            if not quote_data:
                raise StockDataProviderError("Alpha VantageからGlobal Quoteデータを取得できませんでした")
            
            current_price = Decimal(quote_data.get("05. price", "0"))
            if current_price <= 0:
                raise ValueError("無効な価格データ")
            
            open_price = quote_data.get("02. open")
            high_price = quote_data.get("03. high")
            low_price = quote_data.get("04. low")
            volume = quote_data.get("06. volume")
            previous_close = quote_data.get("08. previous close")
            
            stock_price = StockPrice(
                symbol=symbol,
                timestamp=datetime.now(UTC),
                price=current_price,
                open_price=Decimal(open_price) if open_price else None,
                high_price=Decimal(high_price) if high_price else None,
                low_price=Decimal(low_price) if low_price else None,
                volume=int(volume) if volume else None,
                previous_close=Decimal(previous_close) if previous_close else None
            )
            
            # 変動額と変動率を計算
            stock_price.calculate_change()
            
            return stock_price
            
        except (ValueError, KeyError, TypeError) as e:
            raise StockDataProviderError(f"Alpha Vantageデータの解析に失敗: {symbol}, エラー: {e}")