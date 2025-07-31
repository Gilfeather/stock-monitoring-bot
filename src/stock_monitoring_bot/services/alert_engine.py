"""
アラートエンジン
価格閾値チェック、取引量変動アラート、重複防止機能を提供
"""
import asyncio
import uuid
from datetime import datetime, UTC, timedelta
from decimal import Decimal
from typing import List, Dict
from dataclasses import dataclass, field

from ..models.stock import MonitoredStock, StockPrice, Alert
from ..handlers.discord_handler import DiscordHandler


@dataclass
class VolumeData:
    """取引量データ"""
    symbol: str
    current_volume: int
    average_volume: int
    timestamp: datetime
    
    @property
    def volume_ratio(self) -> float:
        """現在取引量の平均に対する倍率"""
        if self.average_volume <= 0:
            return 0.0
        return float(self.current_volume / self.average_volume)


@dataclass
class AlertHistory:
    """アラート履歴管理"""
    recent_alerts: Dict[str, datetime] = field(default_factory=dict)
    duplicate_prevention_minutes: int = 30
    
    def should_send_alert(self, alert_key: str) -> bool:
        """重複防止チェック"""
        if alert_key not in self.recent_alerts:
            return True
        
        last_sent = self.recent_alerts[alert_key]
        time_diff = datetime.now(UTC) - last_sent
        return time_diff.total_seconds() > (self.duplicate_prevention_minutes * 60)
    
    def record_alert(self, alert_key: str) -> None:
        """アラート送信記録"""
        self.recent_alerts[alert_key] = datetime.now(UTC)
    
    def cleanup_old_records(self) -> None:
        """古い記録をクリーンアップ"""
        cutoff_time = datetime.now(UTC) - timedelta(hours=24)
        keys_to_remove = [
            key for key, timestamp in self.recent_alerts.items()
            if timestamp < cutoff_time
        ]
        for key in keys_to_remove:
            del self.recent_alerts[key]


class AlertEngine:
    """アラートエンジン"""
    
    def __init__(self, discord_handler: DiscordHandler):
        self.discord_handler = discord_handler
        self.alert_history = AlertHistory()
        self._volume_history: Dict[str, List[int]] = {}
        self._lock = asyncio.Lock()
    
    async def check_price_alerts(
        self, 
        stock: MonitoredStock, 
        current_price: StockPrice
    ) -> List[Alert]:
        """価格閾値アラートをチェック"""
        alerts = []
        
        # 上限閾値チェック
        if (stock.price_threshold_upper and 
            current_price.price >= stock.price_threshold_upper):
            
            alert = Alert(
                alert_id=str(uuid.uuid4()),
                symbol=stock.symbol,
                alert_type="price_upper",
                message=self._format_price_alert_message(
                    stock, current_price, "上限", stock.price_threshold_upper
                ),
                price_at_trigger=current_price.price,
                threshold_value=stock.price_threshold_upper
            )
            alerts.append(alert)
        
        # 下限閾値チェック
        if (stock.price_threshold_lower and 
            current_price.price <= stock.price_threshold_lower):
            
            alert = Alert(
                alert_id=str(uuid.uuid4()),
                symbol=stock.symbol,
                alert_type="price_lower",
                message=self._format_price_alert_message(
                    stock, current_price, "下限", stock.price_threshold_lower
                ),
                price_at_trigger=current_price.price,
                threshold_value=stock.price_threshold_lower
            )
            alerts.append(alert)
        
        return alerts
    
    async def check_volume_alerts(
        self, 
        stock: MonitoredStock, 
        volume_data: VolumeData
    ) -> List[Alert]:
        """取引量変動アラートをチェック"""
        alerts = []
        
        # 取引時間外は取引量監視を停止
        if not self._is_trading_hours():
            return alerts
        
        # 取引量急増チェック
        if volume_data.volume_ratio >= float(stock.volume_threshold_multiplier):
            alert = Alert(
                alert_id=str(uuid.uuid4()),
                symbol=stock.symbol,
                alert_type="volume",
                message=self._format_volume_alert_message(
                    stock, volume_data, "急増"
                ),
                volume_at_trigger=volume_data.current_volume,
                threshold_value=Decimal(str(volume_data.average_volume * float(stock.volume_threshold_multiplier)))
            )
            alerts.append(alert)
        
        # 取引量急減チェック（平均の50%以下）
        volume_decrease_threshold = 0.5
        if volume_data.volume_ratio <= volume_decrease_threshold:
            alert = Alert(
                alert_id=str(uuid.uuid4()),
                symbol=stock.symbol,
                alert_type="volume",
                message=self._format_volume_alert_message(
                    stock, volume_data, "急減"
                ),
                volume_at_trigger=volume_data.current_volume,
                threshold_value=Decimal(str(volume_data.average_volume * volume_decrease_threshold))
            )
            alerts.append(alert)
        
        return alerts
    
    async def process_alerts(self, alerts: List[Alert]) -> List[Alert]:
        """アラートを処理し、重複防止チェックを適用"""
        async with self._lock:
            processed_alerts = []
            
            for alert in alerts:
                alert_key = f"{alert.symbol}_{alert.alert_type}_{alert.threshold_value}"
                
                if self.alert_history.should_send_alert(alert_key):
                    try:
                        await self.discord_handler.send_alert(alert)
                        alert.is_sent = True
                        alert.sent_at = datetime.now(UTC)
                        self.alert_history.record_alert(alert_key)
                        processed_alerts.append(alert)
                    except Exception as e:
                        # Discord送信失敗時もアラートは記録するが、送信フラグは立てない
                        alert.is_sent = False
                        processed_alerts.append(alert)
                        # ログ出力（実際の実装では適切なロガーを使用）
                        print(f"Discord alert send failed: {e}")
            
            # 古い記録をクリーンアップ
            self.alert_history.cleanup_old_records()
            
            return processed_alerts
    
    def update_volume_history(self, symbol: str, volume: int) -> None:
        """取引量履歴を更新"""
        if symbol not in self._volume_history:
            self._volume_history[symbol] = []
        
        self._volume_history[symbol].append(volume)
        
        # 過去20日分のデータのみ保持
        if len(self._volume_history[symbol]) > 20:
            self._volume_history[symbol] = self._volume_history[symbol][-20:]
    
    def calculate_average_volume(self, symbol: str) -> int:
        """平均取引量を計算"""
        if symbol not in self._volume_history or not self._volume_history[symbol]:
            return 0
        
        volumes = self._volume_history[symbol]
        return sum(volumes) // len(volumes)
    
    def create_volume_data(self, symbol: str, current_volume: int) -> VolumeData:
        """VolumeDataオブジェクトを作成"""
        average_volume = self.calculate_average_volume(symbol)
        
        return VolumeData(
            symbol=symbol,
            current_volume=current_volume,
            average_volume=average_volume,
            timestamp=datetime.now(UTC)
        )
    
    def _format_price_alert_message(
        self, 
        stock: MonitoredStock, 
        price: StockPrice, 
        threshold_type: str,
        threshold_value: Decimal
    ) -> str:
        """価格アラートメッセージをフォーマット"""
        change_indicator = ""
        if price.change_percent:
            change_indicator = f" ({price.change_percent:+.2f}%)"
        
        return (
            f"🚨 **価格アラート** 🚨\n"
            f"**銘柄**: {stock.symbol} ({stock.name})\n"
            f"**現在価格**: ¥{price.price:,.2f}{change_indicator}\n"
            f"**{threshold_type}閾値**: ¥{threshold_value:,.2f}\n"
            f"**時刻**: {price.timestamp.strftime('%Y-%m-%d %H:%M:%S')}"
        )
    
    def _format_volume_alert_message(
        self, 
        stock: MonitoredStock, 
        volume_data: VolumeData,
        change_type: str
    ) -> str:
        """取引量アラートメッセージをフォーマット"""
        return (
            f"📊 **取引量アラート** 📊\n"
            f"**銘柄**: {stock.symbol} ({stock.name})\n"
            f"**現在取引量**: {volume_data.current_volume:,}株\n"
            f"**平均取引量**: {volume_data.average_volume:,}株\n"
            f"**倍率**: {volume_data.volume_ratio:.2f}倍\n"
            f"**状況**: 取引量{change_type}\n"
            f"**時刻**: {volume_data.timestamp.strftime('%Y-%m-%d %H:%M:%S')}"
        )
    
    def _is_trading_hours(self) -> bool:
        """取引時間内かどうかをチェック"""
        now = datetime.now(UTC)
        # 日本時間に変換（UTC+9）
        jst_now = now.replace(tzinfo=None) + timedelta(hours=9)
        
        # 平日かチェック
        if jst_now.weekday() >= 5:  # 土日
            return False
        
        # 取引時間チェック（9:00-11:30, 12:30-15:00）
        time_now = jst_now.time()
        morning_start = datetime.strptime("09:00", "%H:%M").time()
        morning_end = datetime.strptime("11:30", "%H:%M").time()
        afternoon_start = datetime.strptime("12:30", "%H:%M").time()
        afternoon_end = datetime.strptime("15:00", "%H:%M").time()
        
        return ((morning_start <= time_now <= morning_end) or 
                (afternoon_start <= time_now <= afternoon_end))