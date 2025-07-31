"""
データモデルのテスト
"""
import pytest
from datetime import datetime, UTC
from decimal import Decimal
from pydantic import ValidationError

from src.stock_monitoring_bot.models.stock import (
    MonitoredStock, StockPrice, Alert, Command, SystemLog
)


class TestMonitoredStock:
    """MonitoredStockモデルのテスト"""
    
    def test_valid_monitored_stock(self):
        """有効なMonitoredStockの作成"""
        stock = MonitoredStock(
            symbol="7203",
            name="トヨタ自動車",
            market="TSE",
            price_threshold_upper=Decimal("3000"),
            price_threshold_lower=Decimal("2500"),
            volume_threshold_multiplier=Decimal("2.0")
        )
        
        assert stock.symbol == "7203"
        assert stock.name == "トヨタ自動車"
        assert stock.market == "TSE"
        assert stock.price_threshold_upper == Decimal("3000")
        assert stock.price_threshold_lower == Decimal("2500")
        assert stock.volume_threshold_multiplier == Decimal("2.0")
        assert stock.is_active is True
        assert isinstance(stock.created_at, datetime)
        assert isinstance(stock.updated_at, datetime)
    
    def test_symbol_validation(self):
        """銘柄コードのバリデーション"""
        # 空文字列
        with pytest.raises(ValidationError):
            MonitoredStock(
                symbol="",
                name="テスト",
                market="TSE"
            )
        
        # 小文字は大文字に変換される
        stock = MonitoredStock(
            symbol="aapl",
            name="Apple",
            market="NASDAQ"
        )
        assert stock.symbol == "AAPL"
    
    def test_price_threshold_validation(self):
        """価格閾値のバリデーション"""
        # 負の値
        with pytest.raises(ValidationError):
            MonitoredStock(
                symbol="7203",
                name="トヨタ自動車",
                market="TSE",
                price_threshold_upper=Decimal("-100")
            )
        
        # ゼロ
        with pytest.raises(ValidationError):
            MonitoredStock(
                symbol="7203",
                name="トヨタ自動車",
                market="TSE",
                price_threshold_lower=Decimal("0")
            )
    
    def test_volume_multiplier_validation(self):
        """取引量倍率のバリデーション"""
        # 負の値
        with pytest.raises(ValidationError):
            MonitoredStock(
                symbol="7203",
                name="トヨタ自動車",
                market="TSE",
                volume_threshold_multiplier=Decimal("-1.0")
            )
        
        # ゼロ
        with pytest.raises(ValidationError):
            MonitoredStock(
                symbol="7203",
                name="トヨタ自動車",
                market="TSE",
                volume_threshold_multiplier=Decimal("0")
            )


class TestStockPrice:
    """StockPriceモデルのテスト"""
    
    def test_valid_stock_price(self):
        """有効なStockPriceの作成"""
        now = datetime.now(UTC)
        price = StockPrice(
            symbol="7203",
            timestamp=now,
            price=Decimal("2800"),
            open_price=Decimal("2750"),
            high_price=Decimal("2850"),
            low_price=Decimal("2740"),
            volume=1000000,
            previous_close=Decimal("2760")
        )
        
        assert price.symbol == "7203"
        assert price.timestamp == now
        assert price.price == Decimal("2800")
        assert price.volume == 1000000
    
    def test_calculate_change(self):
        """変動額・変動率の計算"""
        price = StockPrice(
            symbol="7203",
            timestamp=datetime.now(UTC),
            price=Decimal("2800"),
            previous_close=Decimal("2760")
        )
        
        price.calculate_change()
        
        assert price.change_amount == Decimal("40")
        assert abs(price.change_percent - Decimal("1.449275362318841")) < Decimal("0.001")
    
    def test_price_validation(self):
        """価格のバリデーション"""
        # 負の価格
        with pytest.raises(ValidationError):
            StockPrice(
                symbol="7203",
                timestamp=datetime.now(UTC),
                price=Decimal("-100")
            )
        
        # ゼロの価格
        with pytest.raises(ValidationError):
            StockPrice(
                symbol="7203",
                timestamp=datetime.now(UTC),
                price=Decimal("0")
            )
    
    def test_volume_validation(self):
        """取引量のバリデーション"""
        # 負の取引量
        with pytest.raises(ValidationError):
            StockPrice(
                symbol="7203",
                timestamp=datetime.now(UTC),
                price=Decimal("2800"),
                volume=-1000
            )


class TestAlert:
    """Alertモデルのテスト"""
    
    def test_valid_alert(self):
        """有効なAlertの作成"""
        alert = Alert(
            alert_id="alert_001",
            symbol="7203",
            alert_type="price_upper",
            message="価格が上限を超えました",
            price_at_trigger=Decimal("3100"),
            threshold_value=Decimal("3000")
        )
        
        assert alert.alert_id == "alert_001"
        assert alert.symbol == "7203"
        assert alert.alert_type == "price_upper"
        assert alert.is_sent is False
        assert alert.sent_at is None
    
    def test_alert_type_validation(self):
        """アラート種別のバリデーション"""
        # 無効なアラート種別
        with pytest.raises(ValidationError):
            Alert(
                alert_id="alert_001",
                symbol="7203",
                alert_type="invalid_type",
                message="テスト"
            )
        
        # 有効なアラート種別
        valid_types = ['price_upper', 'price_lower', 'volume', 'system']
        for alert_type in valid_types:
            alert = Alert(
                alert_id="alert_001",
                symbol="7203",
                alert_type=alert_type,
                message="テスト"
            )
            assert alert.alert_type == alert_type


class TestCommand:
    """Commandモデルのテスト"""
    
    def test_valid_command(self):
        """有効なCommandの作成"""
        command = Command(
            command_id="cmd_001",
            user_id="user123",
            channel_id="channel456",
            command_type="add",
            parameters={"symbol": "7203", "name": "トヨタ自動車"}
        )
        
        assert command.command_id == "cmd_001"
        assert command.user_id == "user123"
        assert command.command_type == "add"
        assert command.status == "pending"
        assert command.parameters["symbol"] == "7203"
    
    def test_command_type_validation(self):
        """コマンド種別のバリデーション"""
        # 無効なコマンド種別
        with pytest.raises(ValidationError):
            Command(
                command_id="cmd_001",
                user_id="user123",
                channel_id="channel456",
                command_type="invalid_command"
            )
    
    def test_status_validation(self):
        """ステータスのバリデーション"""
        # 無効なステータス
        with pytest.raises(ValidationError):
            Command(
                command_id="cmd_001",
                user_id="user123",
                channel_id="channel456",
                command_type="add",
                status="invalid_status"
            )


class TestSystemLog:
    """SystemLogモデルのテスト"""
    
    def test_valid_system_log(self):
        """有効なSystemLogの作成"""
        log = SystemLog(
            log_id="log_001",
            level="INFO",
            component="StockMonitor",
            message="監視を開始しました",
            details={"stocks_count": 5}
        )
        
        assert log.log_id == "log_001"
        assert log.level == "INFO"
        assert log.component == "StockMonitor"
        assert log.details["stocks_count"] == 5
    
    def test_level_validation(self):
        """ログレベルのバリデーション"""
        # 無効なレベル
        with pytest.raises(ValidationError):
            SystemLog(
                log_id="log_001",
                level="INVALID",
                component="Test",
                message="テスト"
            )
        
        # 小文字は大文字に変換される
        log = SystemLog(
            log_id="log_001",
            level="info",
            component="Test",
            message="テスト"
        )
        assert log.level == "INFO"