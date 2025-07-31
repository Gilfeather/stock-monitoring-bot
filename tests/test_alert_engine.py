"""
アラートエンジンのテスト
"""
import pytest
from datetime import datetime, UTC, timedelta
from decimal import Decimal
from unittest.mock import AsyncMock, patch

from src.stock_monitoring_bot.models.stock import MonitoredStock, StockPrice, Alert
from src.stock_monitoring_bot.services.alert_engine import AlertEngine, VolumeData, AlertHistory
from src.stock_monitoring_bot.handlers.discord_handler import DiscordHandler


class TestVolumeData:
    """VolumeDataクラスのテスト"""
    
    def test_volume_ratio_calculation(self):
        """取引量倍率の計算テスト"""
        volume_data = VolumeData(
            symbol="7203",
            current_volume=200000,
            average_volume=100000,
            timestamp=datetime.now(UTC)
        )
        assert volume_data.volume_ratio == 2.0
    
    def test_volume_ratio_zero_average(self):
        """平均取引量が0の場合のテスト"""
        volume_data = VolumeData(
            symbol="7203",
            current_volume=100000,
            average_volume=0,
            timestamp=datetime.now(UTC)
        )
        assert volume_data.volume_ratio == 0.0


class TestAlertHistory:
    """AlertHistoryクラスのテスト"""
    
    def test_should_send_alert_new_key(self):
        """新しいアラートキーの場合のテスト"""
        history = AlertHistory()
        assert history.should_send_alert("test_key") is True
    
    def test_should_send_alert_within_prevention_period(self):
        """重複防止期間内のテスト"""
        history = AlertHistory(duplicate_prevention_minutes=30)
        history.record_alert("test_key")
        assert history.should_send_alert("test_key") is False
    
    def test_should_send_alert_after_prevention_period(self):
        """重複防止期間経過後のテスト"""
        history = AlertHistory(duplicate_prevention_minutes=30)
        # 過去の時刻を設定
        past_time = datetime.now(UTC) - timedelta(minutes=31)
        history.recent_alerts["test_key"] = past_time
        assert history.should_send_alert("test_key") is True
    
    def test_record_alert(self):
        """アラート記録のテスト"""
        history = AlertHistory()
        history.record_alert("test_key")
        assert "test_key" in history.recent_alerts
        assert isinstance(history.recent_alerts["test_key"], datetime)
    
    def test_cleanup_old_records(self):
        """古い記録のクリーンアップテスト"""
        history = AlertHistory()
        # 古い記録を追加
        old_time = datetime.now(UTC) - timedelta(hours=25)
        recent_time = datetime.now(UTC) - timedelta(minutes=10)
        
        history.recent_alerts["old_key"] = old_time
        history.recent_alerts["recent_key"] = recent_time
        
        history.cleanup_old_records()
        
        assert "old_key" not in history.recent_alerts
        assert "recent_key" in history.recent_alerts


class TestAlertEngine:
    """AlertEngineクラスのテスト"""
    
    @pytest.fixture
    def mock_discord_handler(self):
        """モックDiscordハンドラー"""
        handler = AsyncMock(spec=DiscordHandler)
        handler.send_alert = AsyncMock()
        return handler
    
    @pytest.fixture
    def alert_engine(self, mock_discord_handler):
        """AlertEngineインスタンス"""
        return AlertEngine(mock_discord_handler)
    
    @pytest.fixture
    def sample_stock(self):
        """サンプル監視株式"""
        return MonitoredStock(
            symbol="7203",
            name="トヨタ自動車",
            market="TSE",
            price_threshold_upper=Decimal("3000"),
            price_threshold_lower=Decimal("2500"),
            volume_threshold_multiplier=Decimal("2.0")
        )
    
    @pytest.fixture
    def sample_price(self):
        """サンプル株価データ"""
        return StockPrice(
            symbol="7203",
            timestamp=datetime.now(UTC),
            price=Decimal("2800"),
            volume=150000,
            change_percent=Decimal("1.5")
        )
    
    @pytest.mark.asyncio
    async def test_check_price_alerts_upper_threshold(self, alert_engine, sample_stock):
        """価格上限閾値アラートのテスト"""
        high_price = StockPrice(
            symbol="7203",
            timestamp=datetime.now(UTC),
            price=Decimal("3100"),  # 上限閾値3000を超過
            volume=150000
        )
        
        alerts = await alert_engine.check_price_alerts(sample_stock, high_price)
        
        assert len(alerts) == 1
        assert alerts[0].alert_type == "price_upper"
        assert alerts[0].symbol == "7203"
        assert alerts[0].price_at_trigger == Decimal("3100")
        assert alerts[0].threshold_value == Decimal("3000")
    
    @pytest.mark.asyncio
    async def test_check_price_alerts_lower_threshold(self, alert_engine, sample_stock):
        """価格下限閾値アラートのテスト"""
        low_price = StockPrice(
            symbol="7203",
            timestamp=datetime.now(UTC),
            price=Decimal("2400"),  # 下限閾値2500を下回る
            volume=150000
        )
        
        alerts = await alert_engine.check_price_alerts(sample_stock, low_price)
        
        assert len(alerts) == 1
        assert alerts[0].alert_type == "price_lower"
        assert alerts[0].symbol == "7203"
        assert alerts[0].price_at_trigger == Decimal("2400")
        assert alerts[0].threshold_value == Decimal("2500")
    
    @pytest.mark.asyncio
    async def test_check_price_alerts_no_threshold(self, alert_engine, sample_price):
        """閾値が設定されていない場合のテスト"""
        stock_no_threshold = MonitoredStock(
            symbol="7203",
            name="トヨタ自動車",
            market="TSE"
        )
        
        alerts = await alert_engine.check_price_alerts(stock_no_threshold, sample_price)
        
        assert len(alerts) == 0
    
    @pytest.mark.asyncio
    async def test_check_price_alerts_within_threshold(self, alert_engine, sample_stock, sample_price):
        """閾値内の価格の場合のテスト"""
        alerts = await alert_engine.check_price_alerts(sample_stock, sample_price)
        
        assert len(alerts) == 0
    
    @pytest.mark.asyncio
    async def test_check_volume_alerts_high_volume(self, alert_engine, sample_stock):
        """取引量急増アラートのテスト"""
        volume_data = VolumeData(
            symbol="7203",
            current_volume=300000,  # 平均100000の3倍
            average_volume=100000,
            timestamp=datetime.now(UTC)
        )
        
        with patch.object(alert_engine, '_is_trading_hours', return_value=True):
            alerts = await alert_engine.check_volume_alerts(sample_stock, volume_data)
        
        assert len(alerts) == 1
        assert alerts[0].alert_type == "volume"
        assert alerts[0].volume_at_trigger == 300000
        assert "急増" in alerts[0].message
    
    @pytest.mark.asyncio
    async def test_check_volume_alerts_low_volume(self, alert_engine, sample_stock):
        """取引量急減アラートのテスト"""
        volume_data = VolumeData(
            symbol="7203",
            current_volume=40000,  # 平均100000の40%
            average_volume=100000,
            timestamp=datetime.now(UTC)
        )
        
        with patch.object(alert_engine, '_is_trading_hours', return_value=True):
            alerts = await alert_engine.check_volume_alerts(sample_stock, volume_data)
        
        assert len(alerts) == 1
        assert alerts[0].alert_type == "volume"
        assert alerts[0].volume_at_trigger == 40000
        assert "急減" in alerts[0].message
    
    @pytest.mark.asyncio
    async def test_check_volume_alerts_outside_trading_hours(self, alert_engine, sample_stock):
        """取引時間外の取引量チェックテスト"""
        volume_data = VolumeData(
            symbol="7203",
            current_volume=300000,
            average_volume=100000,
            timestamp=datetime.now(UTC)
        )
        
        with patch.object(alert_engine, '_is_trading_hours', return_value=False):
            alerts = await alert_engine.check_volume_alerts(sample_stock, volume_data)
        
        assert len(alerts) == 0
    
    @pytest.mark.asyncio
    async def test_process_alerts_success(self, alert_engine, mock_discord_handler):
        """アラート処理成功のテスト"""
        alert = Alert(
            alert_id="test-id",
            symbol="7203",
            alert_type="price_upper",
            message="Test alert",
            threshold_value=Decimal("3000")
        )
        
        processed = await alert_engine.process_alerts([alert])
        
        assert len(processed) == 1
        assert processed[0].is_sent is True
        assert processed[0].sent_at is not None
        mock_discord_handler.send_alert.assert_called_once_with(alert)
    
    @pytest.mark.asyncio
    async def test_process_alerts_duplicate_prevention(self, alert_engine, mock_discord_handler):
        """重複防止機能のテスト"""
        alert1 = Alert(
            alert_id="test-id-1",
            symbol="7203",
            alert_type="price_upper",
            message="Test alert 1",
            threshold_value=Decimal("3000")
        )
        alert2 = Alert(
            alert_id="test-id-2",
            symbol="7203",
            alert_type="price_upper",
            message="Test alert 2",
            threshold_value=Decimal("3000")
        )
        
        # 最初のアラートを処理
        await alert_engine.process_alerts([alert1])
        
        # 同じ条件の2番目のアラートを処理（重複防止で送信されない）
        processed = await alert_engine.process_alerts([alert2])
        
        assert len(processed) == 0
        assert mock_discord_handler.send_alert.call_count == 1
    
    @pytest.mark.asyncio
    async def test_process_alerts_discord_failure(self, alert_engine, mock_discord_handler):
        """Discord送信失敗時のテスト"""
        mock_discord_handler.send_alert.side_effect = Exception("Discord error")
        
        alert = Alert(
            alert_id="test-id",
            symbol="7203",
            alert_type="price_upper",
            message="Test alert",
            threshold_value=Decimal("3000")
        )
        
        processed = await alert_engine.process_alerts([alert])
        
        assert len(processed) == 1
        assert processed[0].is_sent is False
        assert processed[0].sent_at is None
    
    def test_update_volume_history(self, alert_engine):
        """取引量履歴更新のテスト"""
        symbol = "7203"
        
        # 複数の取引量データを追加
        for volume in [100000, 120000, 110000]:
            alert_engine.update_volume_history(symbol, volume)
        
        assert len(alert_engine._volume_history[symbol]) == 3
        assert alert_engine._volume_history[symbol] == [100000, 120000, 110000]
    
    def test_update_volume_history_limit(self, alert_engine):
        """取引量履歴の上限テスト"""
        symbol = "7203"
        
        # 21個のデータを追加（上限20を超える）
        for i in range(21):
            alert_engine.update_volume_history(symbol, 100000 + i)
        
        assert len(alert_engine._volume_history[symbol]) == 20
        assert alert_engine._volume_history[symbol][0] == 100001  # 最初のデータは削除される
    
    def test_calculate_average_volume(self, alert_engine):
        """平均取引量計算のテスト"""
        symbol = "7203"
        volumes = [100000, 120000, 110000]
        
        for volume in volumes:
            alert_engine.update_volume_history(symbol, volume)
        
        average = alert_engine.calculate_average_volume(symbol)
        expected_average = sum(volumes) // len(volumes)
        
        assert average == expected_average
    
    def test_calculate_average_volume_no_history(self, alert_engine):
        """履歴がない場合の平均取引量計算テスト"""
        average = alert_engine.calculate_average_volume("UNKNOWN")
        assert average == 0
    
    def test_create_volume_data(self, alert_engine):
        """VolumeDataオブジェクト作成のテスト"""
        symbol = "7203"
        alert_engine.update_volume_history(symbol, 100000)
        alert_engine.update_volume_history(symbol, 120000)
        
        volume_data = alert_engine.create_volume_data(symbol, 150000)
        
        assert volume_data.symbol == symbol
        assert volume_data.current_volume == 150000
        assert volume_data.average_volume == 110000  # (100000 + 120000) // 2
        assert isinstance(volume_data.timestamp, datetime)
    
    def test_format_price_alert_message(self, alert_engine, sample_stock, sample_price):
        """価格アラートメッセージフォーマットのテスト"""
        message = alert_engine._format_price_alert_message(
            sample_stock, sample_price, "上限", Decimal("3000")
        )
        
        assert "🚨 **価格アラート** 🚨" in message
        assert "7203" in message
        assert "トヨタ自動車" in message
        assert "¥2,800.00" in message
        assert "上限閾値" in message
        assert "¥3,000.00" in message
    
    def test_format_volume_alert_message(self, alert_engine, sample_stock):
        """取引量アラートメッセージフォーマットのテスト"""
        volume_data = VolumeData(
            symbol="7203",
            current_volume=200000,
            average_volume=100000,
            timestamp=datetime.now(UTC)
        )
        
        message = alert_engine._format_volume_alert_message(
            sample_stock, volume_data, "急増"
        )
        
        assert "📊 **取引量アラート** 📊" in message
        assert "7203" in message
        assert "トヨタ自動車" in message
        assert "200,000株" in message
        assert "100,000株" in message
        assert "2.00倍" in message
        assert "取引量急増" in message
    
    @patch('src.stock_monitoring_bot.services.alert_engine.datetime')
    def test_is_trading_hours_weekday_morning(self, mock_datetime, alert_engine):
        """平日午前の取引時間テスト"""
        # 平日の10:00 JST (01:00 UTC)
        mock_datetime.now.return_value = datetime(2024, 1, 15, 1, 0, 0, tzinfo=UTC)  # 月曜日
        mock_datetime.strptime = datetime.strptime
        
        assert alert_engine._is_trading_hours() is True
    
    @patch('src.stock_monitoring_bot.services.alert_engine.datetime')
    def test_is_trading_hours_weekday_afternoon(self, mock_datetime, alert_engine):
        """平日午後の取引時間テスト"""
        # 平日の14:00 JST (05:00 UTC)
        mock_datetime.now.return_value = datetime(2024, 1, 15, 5, 0, 0, tzinfo=UTC)  # 月曜日
        mock_datetime.strptime = datetime.strptime
        
        assert alert_engine._is_trading_hours() is True
    
    @patch('src.stock_monitoring_bot.services.alert_engine.datetime')
    def test_is_trading_hours_lunch_break(self, mock_datetime, alert_engine):
        """昼休み時間のテスト"""
        # 平日の12:00 JST (03:00 UTC)
        mock_datetime.now.return_value = datetime(2024, 1, 15, 3, 0, 0, tzinfo=UTC)  # 月曜日
        mock_datetime.strptime = datetime.strptime
        
        assert alert_engine._is_trading_hours() is False
    
    @patch('src.stock_monitoring_bot.services.alert_engine.datetime')
    def test_is_trading_hours_weekend(self, mock_datetime, alert_engine):
        """週末のテスト"""
        # 土曜日の10:00 JST (01:00 UTC)
        mock_datetime.now.return_value = datetime(2024, 1, 13, 1, 0, 0, tzinfo=UTC)  # 土曜日
        mock_datetime.strptime = datetime.strptime
        
        assert alert_engine._is_trading_hours() is False
    
    @patch('src.stock_monitoring_bot.services.alert_engine.datetime')
    def test_is_trading_hours_after_close(self, mock_datetime, alert_engine):
        """取引終了後のテスト"""
        # 平日の16:00 JST (07:00 UTC)
        mock_datetime.now.return_value = datetime(2024, 1, 15, 7, 0, 0, tzinfo=UTC)  # 月曜日
        mock_datetime.strptime = datetime.strptime
        
        assert alert_engine._is_trading_hours() is False


if __name__ == "__main__":
    pytest.main([__file__])