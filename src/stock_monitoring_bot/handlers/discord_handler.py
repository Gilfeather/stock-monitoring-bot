"""
Discord Webhook通知ハンドラー
"""
import asyncio
import json
import logging
import re
from datetime import datetime, UTC, timedelta
from typing import Dict, List, Optional
from decimal import Decimal
from urllib.parse import urlparse

import aiohttp
from pydantic import BaseModel

from ..models.stock import Alert, MonitoredStock, StockPrice, Command
from .command_processor import CommandProcessor


class DiscordMessage(BaseModel):
    """Discord メッセージ構造"""
    content: Optional[str] = None
    embeds: Optional[List[Dict]] = None
    username: Optional[str] = None
    avatar_url: Optional[str] = None


class RateLimiter:
    """レート制限管理クラス"""
    
    def __init__(self, max_requests: int = 5, time_window: int = 60):
        self.max_requests = max_requests
        self.time_window = time_window
        self.requests: List[datetime] = []
        self._lock = asyncio.Lock()
    
    async def can_send(self) -> bool:
        """送信可能かチェック"""
        async with self._lock:
            now = datetime.now(UTC)
            # 時間窓外の古いリクエストを削除
            self.requests = [req_time for req_time in self.requests 
                           if now - req_time < timedelta(seconds=self.time_window)]
            
            return len(self.requests) < self.max_requests
    
    async def record_request(self) -> None:
        """リクエスト記録"""
        async with self._lock:
            self.requests.append(datetime.now(UTC))


class DuplicateFilter:
    """重複通知防止フィルター"""
    
    def __init__(self, cooldown_minutes: int = 15):
        self.cooldown_minutes = cooldown_minutes
        self.sent_alerts: Dict[str, datetime] = {}
        self._lock = asyncio.Lock()
    
    def _generate_alert_key(self, alert: Alert) -> str:
        """アラートの一意キーを生成"""
        return f"{alert.symbol}:{alert.alert_type}:{alert.threshold_value}"
    
    async def should_send_alert(self, alert: Alert) -> bool:
        """アラート送信すべきかチェック"""
        async with self._lock:
            alert_key = self._generate_alert_key(alert)
            now = datetime.now(UTC)
            
            # 古いアラート記録をクリーンアップ
            expired_keys = [
                key for key, sent_time in self.sent_alerts.items()
                if now - sent_time > timedelta(minutes=self.cooldown_minutes)
            ]
            for key in expired_keys:
                del self.sent_alerts[key]
            
            # 重複チェック
            if alert_key in self.sent_alerts:
                return False
            
            # 送信記録
            self.sent_alerts[alert_key] = now
            return True


class DiscordHandler:
    """Discord Webhook通知ハンドラー"""
    
    def __init__(
        self, 
        webhook_url: str,
        rate_limit_requests: int = 5,
        rate_limit_window: int = 60,
        duplicate_cooldown_minutes: int = 15,
        timeout: int = 30,
        admin_users: Optional[List[str]] = None,
        allowed_channels: Optional[List[str]] = None
    ):
        # Validate webhook URL
        if not self._validate_webhook_url(webhook_url):
            raise ValueError("Invalid Discord webhook URL")
        
        self.webhook_url = webhook_url
        self.timeout = timeout
        self.logger = logging.getLogger(__name__)
        
        # レート制限と重複防止
        self.rate_limiter = RateLimiter(rate_limit_requests, rate_limit_window)
        self.duplicate_filter = DuplicateFilter(duplicate_cooldown_minutes)
        
        # コマンド処理システム
        self.command_processor = CommandProcessor(admin_users, allowed_channels)
        
        # HTTPセッション
        self._session: Optional[aiohttp.ClientSession] = None
    
    async def __aenter__(self):
        """非同期コンテキストマネージャー開始"""
        self._session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=self.timeout)
        )
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """非同期コンテキストマネージャー終了"""
        if self._session:
            await self._session.close()
    
    def _format_price(self, price: Optional[Decimal]) -> str:
        """価格フォーマット"""
        if price is None:
            return "N/A"
        return f"¥{price:,.2f}"
    
    def _format_volume(self, volume: Optional[int]) -> str:
        """取引量フォーマット"""
        if volume is None:
            return "N/A"
        if volume >= 1_000_000:
            return f"{volume / 1_000_000:.1f}M"
        elif volume >= 1_000:
            return f"{volume / 1_000:.1f}K"
        return str(volume)
    
    def _format_change_percent(self, change_percent: Optional[Decimal]) -> str:
        """変動率フォーマット"""
        if change_percent is None:
            return "N/A"
        
        sign = "+" if change_percent > 0 else ""
        return f"{sign}{change_percent:.2f}%"
    
    def _get_alert_color(self, alert_type: str) -> int:
        """アラート種別に応じた色を取得"""
        color_map = {
            "price_upper": 0x00FF00,  # 緑（価格上昇）
            "price_lower": 0xFF0000,  # 赤（価格下落）
            "volume": 0xFFFF00,       # 黄（取引量異常）
            "system": 0x808080        # グレー（システム）
        }
        return color_map.get(alert_type, 0x0099FF)  # デフォルト青
    
    def _create_price_alert_embed(self, alert: Alert, stock_price: Optional[StockPrice] = None) -> Dict:
        """価格アラート用Embed作成"""
        embed = {
            "title": f"🚨 価格アラート: {alert.symbol}",
            "color": self._get_alert_color(alert.alert_type),
            "timestamp": alert.triggered_at.isoformat(),
            "fields": [
                {
                    "name": "現在価格",
                    "value": self._format_price(alert.price_at_trigger),
                    "inline": True
                },
                {
                    "name": "閾値",
                    "value": self._format_price(alert.threshold_value),
                    "inline": True
                },
                {
                    "name": "アラート種別",
                    "value": "価格上昇" if alert.alert_type == "price_upper" else "価格下落",
                    "inline": True
                }
            ]
        }
        
        # 株価データがある場合は追加情報を含める
        if stock_price:
            embed["fields"].extend([
                {
                    "name": "変動率",
                    "value": self._format_change_percent(stock_price.change_percent),
                    "inline": True
                },
                {
                    "name": "取引量",
                    "value": self._format_volume(stock_price.volume),
                    "inline": True
                },
                {
                    "name": "高値/安値",
                    "value": f"{self._format_price(stock_price.high_price)} / {self._format_price(stock_price.low_price)}",
                    "inline": True
                }
            ])
        
        embed["description"] = alert.message
        return embed
    
    def _create_volume_alert_embed(self, alert: Alert, stock_price: Optional[StockPrice] = None) -> Dict:
        """取引量アラート用Embed作成"""
        embed = {
            "title": f"📊 取引量アラート: {alert.symbol}",
            "color": self._get_alert_color(alert.alert_type),
            "timestamp": alert.triggered_at.isoformat(),
            "fields": [
                {
                    "name": "現在取引量",
                    "value": self._format_volume(alert.volume_at_trigger),
                    "inline": True
                },
                {
                    "name": "現在価格",
                    "value": self._format_price(alert.price_at_trigger),
                    "inline": True
                }
            ]
        }
        
        if stock_price and stock_price.change_percent:
            embed["fields"].append({
                "name": "変動率",
                "value": self._format_change_percent(stock_price.change_percent),
                "inline": True
            })
        
        embed["description"] = alert.message
        return embed
    
    def _create_system_alert_embed(self, alert: Alert) -> Dict:
        """システムアラート用Embed作成"""
        return {
            "title": "⚙️ システム通知",
            "description": alert.message,
            "color": self._get_alert_color(alert.alert_type),
            "timestamp": alert.triggered_at.isoformat()
        }
    
    def _create_status_report_embed(self, monitored_stocks: List[MonitoredStock], system_status: str) -> Dict:
        """ステータスレポート用Embed作成"""
        embed = {
            "title": "📈 株価監視システム - 日次レポート",
            "color": 0x0099FF,
            "timestamp": datetime.now(UTC).isoformat(),
            "fields": [
                {
                    "name": "システム状態",
                    "value": system_status,
                    "inline": False
                },
                {
                    "name": "監視銘柄数",
                    "value": str(len(monitored_stocks)),
                    "inline": True
                },
                {
                    "name": "アクティブ銘柄数",
                    "value": str(len([s for s in monitored_stocks if s.is_active])),
                    "inline": True
                }
            ]
        }
        
        if monitored_stocks:
            stock_list = "\n".join([
                f"• {stock.symbol} ({stock.name})" 
                for stock in monitored_stocks[:10]  # 最大10銘柄表示
            ])
            if len(monitored_stocks) > 10:
                stock_list += f"\n... 他{len(monitored_stocks) - 10}銘柄"
            
            embed["fields"].append({
                "name": "監視銘柄",
                "value": stock_list,
                "inline": False
            })
        
        return embed
    
    async def send_alert(self, alert: Alert, stock_price: Optional[StockPrice] = None) -> bool:
        """アラート送信"""
        try:
            # 重複チェック
            if not await self.duplicate_filter.should_send_alert(alert):
                self.logger.info(f"重複アラートをスキップ: {alert.symbol} - {alert.alert_type}")
                return False
            
            # レート制限チェック
            if not await self.rate_limiter.can_send():
                self.logger.warning("レート制限により送信をスキップ")
                return False
            
            # Embed作成
            if alert.alert_type in ["price_upper", "price_lower"]:
                embed = self._create_price_alert_embed(alert, stock_price)
            elif alert.alert_type == "volume":
                embed = self._create_volume_alert_embed(alert, stock_price)
            else:
                embed = self._create_system_alert_embed(alert)
            
            message = DiscordMessage(embeds=[embed])
            
            # 送信実行
            success = await self._send_webhook(message)
            
            if success:
                await self.rate_limiter.record_request()
                self.logger.info(f"アラート送信成功: {alert.symbol} - {alert.alert_type}")
            
            return success
            
        except Exception as e:
            self.logger.error(f"アラート送信エラー: {e}")
            return False
    
    async def send_status_report(self, monitored_stocks: List[MonitoredStock], system_status: str = "正常") -> bool:
        """ステータスレポート送信"""
        try:
            # レート制限チェック
            if not await self.rate_limiter.can_send():
                self.logger.warning("レート制限によりステータスレポート送信をスキップ")
                return False
            
            embed = self._create_status_report_embed(monitored_stocks, system_status)
            message = DiscordMessage(embeds=[embed])
            
            success = await self._send_webhook(message)
            
            if success:
                await self.rate_limiter.record_request()
                self.logger.info("ステータスレポート送信成功")
            
            return success
            
        except Exception as e:
            self.logger.error(f"ステータスレポート送信エラー: {e}")
            return False
    
    async def send_chart(self, symbol: str, chart_data: bytes, caption: str = "") -> bool:
        """チャート画像送信"""
        try:
            # レート制限チェック
            if not await self.rate_limiter.can_send():
                self.logger.warning("レート制限によりチャート送信をスキップ")
                return False
            
            # マルチパートフォームデータでファイル送信
            data = aiohttp.FormData()
            data.add_field('file', chart_data, filename=f'{symbol}_chart.png', content_type='image/png')
            
            if caption:
                payload = {"content": caption}
                data.add_field('payload_json', json.dumps(payload))
            
            if not self._session:
                raise RuntimeError("HTTPセッションが初期化されていません")
            
            async with self._session.post(self.webhook_url, data=data) as response:
                if response.status == 200:
                    await self.rate_limiter.record_request()
                    self.logger.info(f"チャート送信成功: {symbol}")
                    return True
                else:
                    error_text = await response.text()
                    self.logger.error(f"チャート送信失敗: {response.status} - {error_text}")
                    return False
                    
        except Exception as e:
            self.logger.error(f"チャート送信エラー: {e}")
            return False
    
    async def _send_webhook(self, message: DiscordMessage) -> bool:
        """Webhook送信実行"""
        try:
            if not self._session:
                raise RuntimeError("HTTPセッションが初期化されていません")
            
            payload = message.model_dump(exclude_none=True)
            
            async with self._session.post(
                self.webhook_url,
                json=payload,
                headers={"Content-Type": "application/json"}
            ) as response:
                if response.status == 200:
                    return True
                elif response.status == 429:  # Rate limited
                    self.logger.warning("Discord API レート制限に達しました")
                    return False
                else:
                    error_text = await response.text()
                    self.logger.error(f"Webhook送信失敗: {response.status} - {error_text}")
                    return False
                    
        except asyncio.TimeoutError:
            self.logger.error("Webhook送信タイムアウト")
            return False
        except Exception:
            # セキュリティ上、詳細なエラー情報はログに記録しない
            self.logger.error("Webhook送信でエラーが発生しました")
            return False
    
    async def process_command_message(self, message: str, user_id: str, channel_id: str) -> bool:
        """コマンドメッセージを処理"""
        try:
            # コマンド処理
            command = await self.command_processor.process_message(message, user_id, channel_id)
            
            if command is None:
                # コマンドではない場合は何もしない
                return False
            
            # 結果をDiscordに送信
            await self._send_command_response(command)
            return True
            
        except Exception as e:
            self.logger.error(f"コマンドメッセージ処理エラー: {e}")
            return False
    
    async def _send_command_response(self, command: Command) -> bool:
        """コマンド実行結果をDiscordに送信"""
        try:
            # レート制限チェック
            if not await self.rate_limiter.can_send():
                self.logger.warning("レート制限によりコマンド応答送信をスキップ")
                return False
            
            # 応答メッセージ作成
            if command.status == "completed":
                embed = self._create_command_success_embed(command)
            elif command.status == "failed":
                embed = self._create_command_error_embed(command)
            else:
                embed = self._create_command_processing_embed(command)
            
            message = DiscordMessage(embeds=[embed])
            success = await self._send_webhook(message)
            
            if success:
                await self.rate_limiter.record_request()
                self.logger.info(f"コマンド応答送信成功: {command.command_type}")
            
            return success
            
        except Exception as e:
            self.logger.error(f"コマンド応答送信エラー: {e}")
            return False
    
    def _create_command_success_embed(self, command: Command) -> Dict:
        """コマンド成功時のEmbed作成"""
        return {
            "title": "✅ コマンド実行完了",
            "description": self._sanitize_text(command.result or "コマンドが正常に実行されました"),
            "color": 0x00FF00,
            "timestamp": datetime.now(UTC).isoformat(),
            "footer": {
                "text": f"コマンド: !{self._sanitize_text(command.command_type)} | 実行者: {self._sanitize_user_id(command.user_id)}"
            }
        }
    
    def _create_command_error_embed(self, command: Command) -> Dict:
        """コマンドエラー時のEmbed作成"""
        return {
            "title": "❌ コマンド実行エラー",
            "description": self._sanitize_text(command.error_message or "コマンドの実行中にエラーが発生しました"),
            "color": 0xFF0000,
            "timestamp": datetime.now(UTC).isoformat(),
            "footer": {
                "text": f"コマンド: !{self._sanitize_text(command.command_type)} | 実行者: {self._sanitize_user_id(command.user_id)}"
            }
        }
    
    def _create_command_processing_embed(self, command: Command) -> Dict:
        """コマンド処理中のEmbed作成"""
        return {
            "title": "⏳ コマンド処理中",
            "description": f"コマンド `!{self._sanitize_text(command.command_type)}` を処理しています...",
            "color": 0xFFFF00,
            "timestamp": datetime.now(UTC).isoformat(),
            "footer": {
                "text": f"実行者: {self._sanitize_user_id(command.user_id)}"
            }
        }
    
    async def test_connection(self) -> bool:
        """接続テスト"""
        try:
            test_message = DiscordMessage(
                content="🤖 株価監視システム接続テスト",
                embeds=[{
                    "title": "システム起動",
                    "description": "Discord通知システムが正常に動作しています",
                    "color": 0x00FF00,
                    "timestamp": datetime.now(UTC).isoformat()
                }]
            )
            
            return await self._send_webhook(test_message)
            
        except Exception as e:
            self.logger.error(f"接続テストエラー: {e}")
            return False
    
    def _validate_webhook_url(self, webhook_url: str) -> bool:
        """Webhook URLの検証"""
        try:
            parsed = urlparse(webhook_url)
            # Discord webhook URLのフォーマット検証
            if parsed.hostname != "discord.com" and parsed.hostname != "discordapp.com":
                return False
            if not parsed.path.startswith("/api/webhooks/"):
                return False
            return True
        except Exception:
            return False
    
    def _sanitize_text(self, text: str) -> str:
        """テキストのサニタイズ（Discord markdown injection対策）"""
        if not text:
            return ""
        # Discord特殊文字をエスケープ
        sanitized = re.sub(r'[*_`~|\\]', r'\\\g<0>', text)
        # 長さ制限
        return sanitized[:100]
    
    def _sanitize_user_id(self, user_id: str) -> str:
        """ユーザーIDのサニタイズ"""
        if not user_id:
            return "unknown"
        # 英数字のみ許可
        sanitized = re.sub(r'[^a-zA-Z0-9]', '', user_id)
        return sanitized[:20] if sanitized else "unknown"