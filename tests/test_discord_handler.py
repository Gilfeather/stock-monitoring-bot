"""
Discord Handler テスト
"""
import asyncio
from datetime import datetime, UTC
from decimal import Decimal
from unittest.mock import AsyncMock, patch
import pytest
import aiohttp

from src.stock_monitoring_bot.handlers.discord_handler import (
    DiscordHandler, 
    RateLimiter, 
    DuplicateFilter,
    DiscordMessage
)
from src.stock_monitoring_bot.models.stock import Alert, MonitoredStock, StockPrice


class TestRateLimiter:
    """レート制限テスト"""
    
    @pytest.mark.asyncio
    async def test_can_send_within_limit(self):
        """制限内での送信可能テスト"""
        limiter = RateLimiter(max_requests=3, time_window=60)
        
        # 制限内なので送信可能
        assert await limiter.can_send() is True
        await limiter.record_request()
        
        assert await limiter.can_send() is True
        await limiter.record_request()
        
        assert await limiter.can_send() is True
        await limiter.record_request()
        
        # 制限に達したので送信不可
        assert await limiter.can_send() is False
    
    @pytest.mark.asyncio
    async def test_rate_limit_reset_after_time_window(self):
        """時間窓経過後のリセットテスト"""
        limiter = RateLimiter(max_requests=1, time_window=1)  # 1秒窓
        
        # 制限まで送信
        assert await limiter.can_send() is True
        await limiter.record_request()
        assert await limiter.can_send() is False
        
        # 時間経過後にリセット
        await asyncio.sleep(1.1)
        assert await limiter.can_send() is True


class TestDuplicateFilter:
    """重複防止フィルターテスト"""
    
    @pytest.mark.asyncio
    async def test_should_send_first_alert(self):
        """初回アラート送信テスト"""
        filter = DuplicateFilter(cooldown_minutes=15)
        alert = Alert(
            alert_id="test1",
            symbol="7203",
            alert_type="price_upper",
            message="テストアラート",
            threshold_value=Decimal("1000")
        )
        
        assert await filter.should_send_alert(alert) is True
    
    @pytest.mark.asyncio
    async def test_should_not_send_duplicate_alert(self):
        """重複アラート防止テスト"""
        filter = DuplicateFilter(cooldown_minutes=15)
        alert = Alert(
            alert_id="test1",
            symbol="7203",
            alert_type="price_upper",
            message="テストアラート",
            threshold_value=Decimal("1000")
        )
        
        # 初回は送信
        assert await filter.should_send_alert(alert) is True
        
        # 同じアラートは送信しない
        duplicate_alert = Alert(
            alert_id="test2",  # IDは違うが内容は同じ
            symbol="7203",
            alert_type="price_upper",
            message="テストアラート2",
            threshold_value=Decimal("1000")
        )
        assert await filter.should_send_alert(duplicate_alert) is False
    
    @pytest.mark.asyncio
    async def test_should_send_after_cooldown(self):
        """クールダウン後の送信テスト"""
        filter = DuplicateFilter(cooldown_minutes=0.01)  # 0.6秒クールダウン
        alert = Alert(
            alert_id="test1",
            symbol="7203",
            alert_type="price_upper",
            message="テストアラート",
            threshold_value=Decimal("1000")
        )
        
        # 初回送信
        assert await filter.should_send_alert(alert) is True
        
        # クールダウン経過後は送信可能
        await asyncio.sleep(0.7)
        assert await filter.should_send_alert(alert) is True


class TestDiscordHandler:
    """Discord Handler テスト"""
    
    @pytest.fixture
    def mock_webhook_url(self):
        return "https://discord.com/api/webhooks/123/test"
    
    @pytest.fixture
    def sample_alert(self):
        return Alert(
            alert_id="test_alert_1",
            symbol="7203",
            alert_type="price_upper",
            message="価格が上限を超えました",
            price_at_trigger=Decimal("1500"),
            threshold_value=Decimal("1400")
        )
    
    @pytest.fixture
    def sample_stock_price(self):
        return StockPrice(
            symbol="7203",
            timestamp=datetime.now(UTC),
            price=Decimal("1500"),
            open_price=Decimal("1450"),
            high_price=Decimal("1520"),
            low_price=Decimal("1440"),
            volume=1000000,
            previous_close=Decimal("1450"),
            change_amount=Decimal("50"),
            change_percent=Decimal("3.45")
        )
    
    @pytest.fixture
    def sample_monitored_stocks(self):
        return [
            MonitoredStock(
                symbol="7203",
                name="トヨタ自動車",
                market="TSE",
                price_threshold_upper=Decimal("1500"),
                price_threshold_lower=Decimal("1300")
            ),
            MonitoredStock(
                symbol="6758",
                name="ソニーグループ",
                market="TSE",
                price_threshold_upper=Decimal("12000"),
                price_threshold_lower=Decimal("10000")
            )
        ]
    
    @pytest.mark.asyncio
    async def test_format_price(self, mock_webhook_url):
        """価格フォーマットテスト"""
        handler = DiscordHandler(mock_webhook_url)
        
        assert handler._format_price(Decimal("1234.56")) == "¥1,234.56"
        assert handler._format_price(None) == "N/A"
        assert handler._format_price(Decimal("1000000")) == "¥1,000,000.00"
    
    @pytest.mark.asyncio
    async def test_format_volume(self, mock_webhook_url):
        """取引量フォーマットテスト"""
        handler = DiscordHandler(mock_webhook_url)
        
        assert handler._format_volume(1500000) == "1.5M"
        assert handler._format_volume(1500) == "1.5K"
        assert handler._format_volume(500) == "500"
        assert handler._format_volume(None) == "N/A"
    
    @pytest.mark.asyncio
    async def test_format_change_percent(self, mock_webhook_url):
        """変動率フォーマットテスト"""
        handler = DiscordHandler(mock_webhook_url)
        
        assert handler._format_change_percent(Decimal("3.45")) == "+3.45%"
        assert handler._format_change_percent(Decimal("-2.10")) == "-2.10%"
        assert handler._format_change_percent(None) == "N/A"
    
    @pytest.mark.asyncio
    async def test_get_alert_color(self, mock_webhook_url):
        """アラート色取得テスト"""
        handler = DiscordHandler(mock_webhook_url)
        
        assert handler._get_alert_color("price_upper") == 0x00FF00
        assert handler._get_alert_color("price_lower") == 0xFF0000
        assert handler._get_alert_color("volume") == 0xFFFF00
        assert handler._get_alert_color("system") == 0x808080
        assert handler._get_alert_color("unknown") == 0x0099FF
    
    @pytest.mark.asyncio
    async def test_create_price_alert_embed(self, mock_webhook_url, sample_alert, sample_stock_price):
        """価格アラートEmbed作成テスト"""
        handler = DiscordHandler(mock_webhook_url)
        
        embed = handler._create_price_alert_embed(sample_alert, sample_stock_price)
        
        assert embed["title"] == "🚨 価格アラート: 7203"
        assert embed["color"] == 0x00FF00
        assert embed["description"] == "価格が上限を超えました"
        
        # フィールドチェック
        fields = {field["name"]: field["value"] for field in embed["fields"]}
        assert fields["現在価格"] == "¥1,500.00"
        assert fields["閾値"] == "¥1,400.00"
        assert fields["変動率"] == "+3.45%"
        assert fields["取引量"] == "1.0M"
    
    @pytest.mark.asyncio
    async def test_create_volume_alert_embed(self, mock_webhook_url):
        """取引量アラートEmbed作成テスト"""
        handler = DiscordHandler(mock_webhook_url)
        
        alert = Alert(
            alert_id="vol_test",
            symbol="7203",
            alert_type="volume",
            message="取引量が急増しました",
            volume_at_trigger=5000000,
            price_at_trigger=Decimal("1500")
        )
        
        embed = handler._create_volume_alert_embed(alert)
        
        assert embed["title"] == "📊 取引量アラート: 7203"
        assert embed["color"] == 0xFFFF00
        assert embed["description"] == "取引量が急増しました"
        
        fields = {field["name"]: field["value"] for field in embed["fields"]}
        assert fields["現在取引量"] == "5.0M"
        assert fields["現在価格"] == "¥1,500.00"
    
    @pytest.mark.asyncio
    async def test_create_system_alert_embed(self, mock_webhook_url):
        """システムアラートEmbed作成テスト"""
        handler = DiscordHandler(mock_webhook_url)
        
        alert = Alert(
            alert_id="sys_test",
            symbol="SYSTEM",
            alert_type="system",
            message="システムが正常に起動しました"
        )
        
        embed = handler._create_system_alert_embed(alert)
        
        assert embed["title"] == "⚙️ システム通知"
        assert embed["description"] == "システムが正常に起動しました"
        assert embed["color"] == 0x808080
    
    @pytest.mark.asyncio
    async def test_create_status_report_embed(self, mock_webhook_url, sample_monitored_stocks):
        """ステータスレポートEmbed作成テスト"""
        handler = DiscordHandler(mock_webhook_url)
        
        embed = handler._create_status_report_embed(sample_monitored_stocks, "正常")
        
        assert embed["title"] == "📈 株価監視システム - 日次レポート"
        assert embed["color"] == 0x0099FF
        
        fields = {field["name"]: field["value"] for field in embed["fields"]}
        assert fields["システム状態"] == "正常"
        assert fields["監視銘柄数"] == "2"
        assert fields["アクティブ銘柄数"] == "2"
        assert "7203 (トヨタ自動車)" in fields["監視銘柄"]
        assert "6758 (ソニーグループ)" in fields["監視銘柄"]
    
    @pytest.mark.asyncio
    async def test_send_alert_success(self, mock_webhook_url, sample_alert):
        """アラート送信成功テスト"""
        with patch('aiohttp.ClientSession.post') as mock_post:
            # モックレスポンス設定
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_post.return_value.__aenter__.return_value = mock_response
            
            async with DiscordHandler(mock_webhook_url) as handler:
                result = await handler.send_alert(sample_alert)
                
                assert result is True
                mock_post.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_send_alert_rate_limited(self, mock_webhook_url, sample_alert):
        """レート制限によるアラート送信スキップテスト"""
        handler = DiscordHandler(mock_webhook_url, rate_limit_requests=0)  # 即座に制限
        
        async with handler:
            result = await handler.send_alert(sample_alert)
            assert result is False
    
    @pytest.mark.asyncio
    async def test_send_alert_duplicate_prevention(self, mock_webhook_url, sample_alert):
        """重複防止テスト"""
        with patch('aiohttp.ClientSession.post') as mock_post:
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_post.return_value.__aenter__.return_value = mock_response
            
            async with DiscordHandler(mock_webhook_url) as handler:
                # 初回送信成功
                result1 = await handler.send_alert(sample_alert)
                assert result1 is True
                
                # 重複送信は防止される
                result2 = await handler.send_alert(sample_alert)
                assert result2 is False
                
                # 1回だけ呼ばれる
                assert mock_post.call_count == 1
    
    @pytest.mark.asyncio
    async def test_send_alert_http_error(self, mock_webhook_url, sample_alert):
        """HTTP エラー時のテスト"""
        with patch('aiohttp.ClientSession.post') as mock_post:
            mock_response = AsyncMock()
            mock_response.status = 400
            mock_response.text.return_value = "Bad Request"
            mock_post.return_value.__aenter__.return_value = mock_response
            
            async with DiscordHandler(mock_webhook_url) as handler:
                result = await handler.send_alert(sample_alert)
                assert result is False
    
    @pytest.mark.asyncio
    async def test_send_alert_discord_rate_limit(self, mock_webhook_url, sample_alert):
        """Discord API レート制限テスト"""
        with patch('aiohttp.ClientSession.post') as mock_post:
            mock_response = AsyncMock()
            mock_response.status = 429  # Too Many Requests
            mock_post.return_value.__aenter__.return_value = mock_response
            
            async with DiscordHandler(mock_webhook_url) as handler:
                result = await handler.send_alert(sample_alert)
                assert result is False
    
    @pytest.mark.asyncio
    async def test_send_status_report_success(self, mock_webhook_url, sample_monitored_stocks):
        """ステータスレポート送信成功テスト"""
        with patch('aiohttp.ClientSession.post') as mock_post:
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_post.return_value.__aenter__.return_value = mock_response
            
            async with DiscordHandler(mock_webhook_url) as handler:
                result = await handler.send_status_report(sample_monitored_stocks)
                
                assert result is True
                mock_post.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_send_chart_success(self, mock_webhook_url):
        """チャート送信成功テスト"""
        with patch('aiohttp.ClientSession.post') as mock_post:
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_post.return_value.__aenter__.return_value = mock_response
            
            chart_data = b"fake_chart_data"
            
            async with DiscordHandler(mock_webhook_url) as handler:
                result = await handler.send_chart("7203", chart_data, "テストチャート")
                
                assert result is True
                mock_post.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_test_connection_success(self, mock_webhook_url):
        """接続テスト成功"""
        with patch('aiohttp.ClientSession.post') as mock_post:
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_post.return_value.__aenter__.return_value = mock_response
            
            async with DiscordHandler(mock_webhook_url) as handler:
                result = await handler.test_connection()
                
                assert result is True
                mock_post.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_test_connection_failure(self, mock_webhook_url):
        """接続テスト失敗"""
        with patch('aiohttp.ClientSession.post') as mock_post:
            mock_response = AsyncMock()
            mock_response.status = 404
            mock_response.text.return_value = "Not Found"
            mock_post.return_value.__aenter__.return_value = mock_response
            
            async with DiscordHandler(mock_webhook_url) as handler:
                result = await handler.test_connection()
                
                assert result is False
    
    @pytest.mark.asyncio
    async def test_timeout_handling(self, mock_webhook_url, sample_alert):
        """タイムアウト処理テスト"""
        with patch('aiohttp.ClientSession.post') as mock_post:
            mock_post.side_effect = asyncio.TimeoutError()
            
            async with DiscordHandler(mock_webhook_url, timeout=1) as handler:
                result = await handler.send_alert(sample_alert)
                assert result is False
    
    @pytest.mark.asyncio
    async def test_context_manager(self, mock_webhook_url):
        """コンテキストマネージャーテスト"""
        handler = DiscordHandler(mock_webhook_url)
        
        # 初期状態ではセッションなし
        assert handler._session is None
        
        async with handler:
            # コンテキスト内ではセッション存在
            assert handler._session is not None
            assert isinstance(handler._session, aiohttp.ClientSession)
        
        # コンテキスト終了後はセッションクローズ
        assert handler._session.closed is True


class TestDiscordMessage:
    """Discord メッセージモデルテスト"""
    
    def test_discord_message_creation(self):
        """Discord メッセージ作成テスト"""
        message = DiscordMessage(
            content="テストメッセージ",
            username="TestBot"
        )
        
        assert message.content == "テストメッセージ"
        assert message.username == "TestBot"
        assert message.embeds is None
        assert message.avatar_url is None
    
    def test_discord_message_with_embeds(self):
        """Embed付きメッセージテスト"""
        embed = {
            "title": "テストEmbed",
            "description": "テスト説明",
            "color": 0x00FF00
        }
        
        message = DiscordMessage(embeds=[embed])
        
        assert message.embeds == [embed]
        assert message.content is None
    
    def test_discord_message_model_dump(self):
        """モデルダンプテスト"""
        message = DiscordMessage(
            content="テスト",
            username="Bot"
        )
        
        data = message.model_dump(exclude_none=True)
        
        assert data == {
            "content": "テスト",
            "username": "Bot"
        }
        # None値は除外される
        assert "embeds" not in data
        assert "avatar_url" not in data