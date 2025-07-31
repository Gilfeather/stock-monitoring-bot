"""
株式データモデル
"""
from datetime import datetime, UTC
from decimal import Decimal
from typing import Optional, List
from pydantic import BaseModel, Field, field_validator


class MonitoredStock(BaseModel):
    """監視対象株式"""
    symbol: str = Field(..., description="銘柄コード")
    name: str = Field(..., description="銘柄名")
    market: str = Field(..., description="市場（TSE, NASDAQ等）")
    price_threshold_upper: Optional[Decimal] = Field(None, description="価格上限閾値")
    price_threshold_lower: Optional[Decimal] = Field(None, description="価格下限閾値")
    volume_threshold_multiplier: Decimal = Field(default=Decimal("2.0"), description="取引量閾値倍率")
    is_active: bool = Field(default=True, description="監視有効フラグ")
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC), description="作成日時")
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC), description="更新日時")
    
    @field_validator('symbol')
    @classmethod
    def validate_symbol(cls, v):
        if not v or len(v.strip()) == 0:
            raise ValueError('銘柄コードは必須です')
        return v.upper().strip()
    
    @field_validator('price_threshold_upper', 'price_threshold_lower')
    @classmethod
    def validate_price_thresholds(cls, v):
        if v is not None and v <= 0:
            raise ValueError('価格閾値は正の値である必要があります')
        return v
    
    @field_validator('volume_threshold_multiplier')
    @classmethod
    def validate_volume_multiplier(cls, v):
        if v <= 0:
            raise ValueError('取引量閾値倍率は正の値である必要があります')
        return v


class StockPrice(BaseModel):
    """株価データ"""
    symbol: str = Field(..., description="銘柄コード")
    timestamp: datetime = Field(..., description="データ取得時刻")
    price: Decimal = Field(..., description="現在価格")
    open_price: Optional[Decimal] = Field(None, description="始値")
    high_price: Optional[Decimal] = Field(None, description="高値")
    low_price: Optional[Decimal] = Field(None, description="安値")
    volume: Optional[int] = Field(None, description="取引量")
    previous_close: Optional[Decimal] = Field(None, description="前日終値")
    change_amount: Optional[Decimal] = Field(None, description="変動額")
    change_percent: Optional[Decimal] = Field(None, description="変動率（%）")
    
    @field_validator('price', 'open_price', 'high_price', 'low_price', 'previous_close')
    @classmethod
    def validate_prices(cls, v):
        if v is not None and v <= 0:
            raise ValueError('価格は正の値である必要があります')
        return v
    
    @field_validator('volume')
    @classmethod
    def validate_volume(cls, v):
        if v is not None and v < 0:
            raise ValueError('取引量は非負の値である必要があります')
        return v
    
    def calculate_change(self) -> None:
        """変動額と変動率を計算"""
        if self.previous_close and self.previous_close > 0:
            self.change_amount = self.price - self.previous_close
            self.change_percent = (self.change_amount / self.previous_close) * 100


class Alert(BaseModel):
    """アラート"""
    alert_id: str = Field(..., description="アラートID")
    symbol: str = Field(..., description="銘柄コード")
    alert_type: str = Field(..., description="アラート種別（price_upper, price_lower, volume）")
    message: str = Field(..., description="アラートメッセージ")
    triggered_at: datetime = Field(default_factory=lambda: datetime.now(UTC), description="発生日時")
    price_at_trigger: Optional[Decimal] = Field(None, description="発生時価格")
    volume_at_trigger: Optional[int] = Field(None, description="発生時取引量")
    threshold_value: Optional[Decimal] = Field(None, description="閾値")
    is_sent: bool = Field(default=False, description="送信済みフラグ")
    sent_at: Optional[datetime] = Field(None, description="送信日時")
    
    @field_validator('alert_type')
    @classmethod
    def validate_alert_type(cls, v):
        valid_types = ['price_upper', 'price_lower', 'volume', 'system']
        if v not in valid_types:
            raise ValueError(f'アラート種別は {valid_types} のいずれかである必要があります')
        return v


class Command(BaseModel):
    """Discordコマンド"""
    command_id: str = Field(..., description="コマンドID")
    user_id: str = Field(..., description="実行ユーザーID")
    channel_id: str = Field(..., description="チャンネルID")
    command_type: str = Field(..., description="コマンド種別")
    parameters: dict = Field(default_factory=dict, description="コマンドパラメータ")
    executed_at: datetime = Field(default_factory=lambda: datetime.now(UTC), description="実行日時")
    status: str = Field(default="pending", description="実行状態")
    result: Optional[str] = Field(None, description="実行結果")
    error_message: Optional[str] = Field(None, description="エラーメッセージ")
    
    @field_validator('command_type')
    @classmethod
    def validate_command_type(cls, v):
        valid_commands = ['add', 'remove', 'list', 'alert', 'chart', 'stats', 'portfolio', 'help', 'error']
        if v not in valid_commands:
            raise ValueError(f'コマンド種別は {valid_commands} のいずれかである必要があります')
        return v
    
    @field_validator('status')
    @classmethod
    def validate_status(cls, v):
        valid_statuses = ['pending', 'processing', 'completed', 'failed']
        if v not in valid_statuses:
            raise ValueError(f'実行状態は {valid_statuses} のいずれかである必要があります')
        return v





class SystemLog(BaseModel):
    """システムログ"""
    log_id: str = Field(..., description="ログID")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC), description="ログ出力時刻")
    level: str = Field(..., description="ログレベル")
    component: str = Field(..., description="コンポーネント名")
    message: str = Field(..., description="ログメッセージ")
    details: Optional[dict] = Field(None, description="詳細情報")
    
    @field_validator('level')
    @classmethod
    def validate_level(cls, v):
        valid_levels = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']
        v_upper = v.upper()
        if v_upper not in valid_levels:
            raise ValueError(f'ログレベルは {valid_levels} のいずれかである必要があります')
        return v_upper


class Portfolio(BaseModel):
    """ポートフォリオ"""
    portfolio_id: str = Field(..., description="ポートフォリオID")
    user_id: str = Field(..., description="ユーザーID")
    name: str = Field(..., description="ポートフォリオ名")
    description: Optional[str] = Field(None, description="説明")
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC), description="作成日時")
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC), description="更新日時")
    is_active: bool = Field(default=True, description="有効フラグ")


class PortfolioHolding(BaseModel):
    """ポートフォリオ保有銘柄"""
    holding_id: str = Field(..., description="保有ID")
    portfolio_id: str = Field(..., description="ポートフォリオID")
    symbol: str = Field(..., description="銘柄コード")
    quantity: int = Field(..., description="保有株数")
    purchase_price: Decimal = Field(..., description="取得価格")
    purchase_date: datetime = Field(..., description="取得日")
    notes: Optional[str] = Field(None, description="メモ")
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC), description="作成日時")
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC), description="更新日時")
    is_active: bool = Field(default=True, description="有効フラグ")
    
    @field_validator('symbol')
    @classmethod
    def validate_symbol(cls, v):
        if not v or len(v.strip()) == 0:
            raise ValueError('銘柄コードは必須です')
        return v.upper().strip()
    
    @field_validator('quantity')
    @classmethod
    def validate_quantity(cls, v):
        if v <= 0:
            raise ValueError('保有株数は正の値である必要があります')
        return v
    
    @field_validator('purchase_price')
    @classmethod
    def validate_purchase_price(cls, v):
        if v <= 0:
            raise ValueError('取得価格は正の値である必要があります')
        return v


class ProfitLossCalculation(BaseModel):
    """損益計算結果"""
    holding_id: str = Field(..., description="保有ID")
    symbol: str = Field(..., description="銘柄コード")
    quantity: int = Field(..., description="保有株数")
    purchase_price: Decimal = Field(..., description="取得価格")
    current_price: Decimal = Field(..., description="現在価格")
    purchase_value: Decimal = Field(..., description="取得金額")
    current_value: Decimal = Field(..., description="現在評価額")
    unrealized_pnl: Decimal = Field(..., description="含み損益（金額）")
    unrealized_pnl_percent: Decimal = Field(..., description="含み損益（%）")
    calculated_at: datetime = Field(default_factory=lambda: datetime.now(UTC), description="計算日時")
    
    @classmethod
    def calculate(cls, holding: PortfolioHolding, current_price: Decimal) -> 'ProfitLossCalculation':
        """損益を計算"""
        purchase_value = holding.purchase_price * holding.quantity
        current_value = current_price * holding.quantity
        unrealized_pnl = current_value - purchase_value
        unrealized_pnl_percent = (unrealized_pnl / purchase_value) * 100
        
        return cls(
            holding_id=holding.holding_id,
            symbol=holding.symbol,
            quantity=holding.quantity,
            purchase_price=holding.purchase_price,
            current_price=current_price,
            purchase_value=purchase_value,
            current_value=current_value,
            unrealized_pnl=unrealized_pnl,
            unrealized_pnl_percent=unrealized_pnl_percent
        )


class PortfolioProfitLossReport(BaseModel):
    """ポートフォリオ損益レポート"""
    portfolio_id: str = Field(..., description="ポートフォリオID")
    user_id: str = Field(..., description="ユーザーID")
    portfolio_name: str = Field(..., description="ポートフォリオ名")
    holdings: List[ProfitLossCalculation] = Field(..., description="保有銘柄損益")
    total_purchase_value: Decimal = Field(..., description="総取得金額")
    total_current_value: Decimal = Field(..., description="総現在評価額")
    total_unrealized_pnl: Decimal = Field(..., description="総含み損益（金額）")
    total_unrealized_pnl_percent: Decimal = Field(..., description="総含み損益（%）")
    generated_at: datetime = Field(default_factory=lambda: datetime.now(UTC), description="生成日時")
    
    @classmethod
    def create_report(cls, portfolio: Portfolio, holdings_pnl: List[ProfitLossCalculation]) -> 'PortfolioProfitLossReport':
        """レポートを作成"""
        total_purchase_value = sum(h.purchase_value for h in holdings_pnl)
        total_current_value = sum(h.current_value for h in holdings_pnl)
        total_unrealized_pnl = total_current_value - total_purchase_value
        total_unrealized_pnl_percent = (total_unrealized_pnl / total_purchase_value * 100) if total_purchase_value > 0 else Decimal('0')
        
        return cls(
            portfolio_id=portfolio.portfolio_id,
            user_id=portfolio.user_id,
            portfolio_name=portfolio.name,
            holdings=holdings_pnl,
            total_purchase_value=total_purchase_value,
            total_current_value=total_current_value,
            total_unrealized_pnl=total_unrealized_pnl,
            total_unrealized_pnl_percent=total_unrealized_pnl_percent
        )