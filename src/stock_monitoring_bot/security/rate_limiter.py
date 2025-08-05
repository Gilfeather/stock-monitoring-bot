"""
セキュリティ: レート制限機能
スパム攻撃・DDoS攻撃対策
"""
import time
import logging
from typing import Dict, Optional
from decimal import Decimal
from datetime import datetime, UTC, timedelta

logger = logging.getLogger(__name__)

class RateLimiter:
    """ユーザー別レート制限"""
    
    def __init__(self):
        self.user_requests: Dict[str, list] = {}
        self.blocked_users: Dict[str, datetime] = {}
        
        # 制限設定
        self.max_requests_per_minute = 10
        self.max_requests_per_hour = 100
        self.block_duration_minutes = 30
        self.suspicious_threshold = 20  # 1分間にこれを超えたら疑わしい
        
    def check_rate_limit(self, user_id: str) -> tuple[bool, str]:
        """
        レート制限チェック
        
        Returns:
            tuple: (許可するか, エラーメッセージ)
        """
        now = datetime.now(UTC)
        
        # ブロック中のユーザーチェック
        if user_id in self.blocked_users:
            block_until = self.blocked_users[user_id]
            if now < block_until:
                remaining = (block_until - now).total_seconds() / 60
                return False, f"🚫 一時的にブロックされています。残り時間: {remaining:.0f}分"
            else:
                # ブロック期間終了
                del self.blocked_users[user_id]
        
        # ユーザーのリクエスト履歴を初期化
        if user_id not in self.user_requests:
            self.user_requests[user_id] = []
        
        # 古いリクエストを削除（1時間より古い）
        hour_ago = now - timedelta(hours=1)
        self.user_requests[user_id] = [
            req_time for req_time in self.user_requests[user_id] 
            if req_time > hour_ago
        ]
        
        # 現在のリクエスト数をチェック
        minute_ago = now - timedelta(minutes=1)
        requests_last_minute = len([
            req_time for req_time in self.user_requests[user_id]
            if req_time > minute_ago
        ])
        requests_last_hour = len(self.user_requests[user_id])
        
        # 疑わしい活動の検出
        if requests_last_minute >= self.suspicious_threshold:
            # 即座にブロック
            self.blocked_users[user_id] = now + timedelta(minutes=self.block_duration_minutes)
            logger.warning(f"SECURITY: User {user_id} blocked for suspicious activity: {requests_last_minute} requests/min")
            return False, "🚫 疑わしい活動が検出されました。一時的にブロックされました。"
        
        # 通常のレート制限チェック
        if requests_last_minute >= self.max_requests_per_minute:
            return False, f"🐌 レート制限: 1分間に{self.max_requests_per_minute}回まで。少し待ってからお試しください。"
        
        if requests_last_hour >= self.max_requests_per_hour:
            return False, f"🐌 レート制限: 1時間に{self.max_requests_per_hour}回まで。時間をおいてからお試しください。"
        
        # リクエストを記録
        self.user_requests[user_id].append(now)
        
        return True, ""

class SecurityValidator:
    """セキュリティ検証"""
    
    @staticmethod
    def validate_user_input(text: str) -> tuple[bool, str]:
        """
        ユーザー入力の検証
        
        Args:
            text: 検証するテキスト
            
        Returns:
            tuple: (有効か, エラーメッセージ)
        """
        if not text:
            return False, "入力が空です"
        
        # 長さ制限
        if len(text) > 1000:
            return False, "入力が長すぎます（1000文字以内）"
        
        # 危険な文字列パターン
        dangerous_patterns = [
            'javascript:', 'data:', 'vbscript:',
            '<script', '</script>', 'onclick=', 'onerror=',
            'eval(', 'alert(', 'document.cookie',
            'DROP TABLE', 'DELETE FROM', 'UPDATE SET',
            '../', '..\\', '/etc/passwd', 'cmd.exe'
        ]
        
        text_lower = text.lower()
        for pattern in dangerous_patterns:
            if pattern in text_lower:
                logger.warning(f"SECURITY: Dangerous pattern detected: {pattern}")
                return False, "🚫 不正な文字列が検出されました"
        
        # スパム検出（同じ文字の連続）
        if len(set(text)) < len(text) * 0.1 and len(text) > 10:
            return False, "🚫 スパムの可能性があります"
        
        return True, ""
    
    @staticmethod
    def validate_symbol(symbol: str) -> tuple[bool, str]:
        """
        株式シンボルの検証
        
        Args:
            symbol: 株式シンボル
            
        Returns:
            tuple: (有効か, エラーメッセージ)
        """
        if not symbol:
            return False, "シンボルが空です"
        
        # 基本的な形式チェック
        symbol = symbol.upper().strip()
        
        # 長さ制限
        if len(symbol) > 10:
            return False, "シンボルが長すぎます（10文字以内）"
        
        # 英数字のみ許可
        if not symbol.replace('.', '').replace('-', '').isalnum():
            return False, "シンボルは英数字、ピリオド、ハイフンのみ使用可能です"
        
        return True, ""
    
    @staticmethod
    def validate_quantity(quantity: int) -> tuple[bool, str]:
        """
        株数の検証
        
        Args:
            quantity: 株数
            
        Returns:
            tuple: (有効か, エラーメッセージ)
        """
        if quantity <= 0:
            return False, "株数は1以上である必要があります"
        
        if quantity > 1000000:  # 100万株制限
            return False, "株数が大きすぎます（100万株以内）"
        
        return True, ""
    
    @staticmethod
    def validate_price(price: Decimal) -> tuple[bool, str]:
        """
        価格の検証
        
        Args:
            price: 価格
            
        Returns:
            tuple: (有効か, エラーメッセージ)
        """
        if price <= 0:
            return False, "価格は0より大きい値である必要があります"
        
        if price > Decimal('1000000'):  # 100万円制限
            return False, "価格が大きすぎます（100万円以内）"
        
        # 小数点以下の桁数チェック
        if price.as_tuple().exponent < -2:  # 小数点以下2桁まで
            return False, "価格は小数点以下2桁までです"
        
        return True, ""

# グローバルインスタンス
rate_limiter = RateLimiter()