#!/usr/bin/env python3
"""
DynamoDBにテストデータを手動追加
"""
import sys
import asyncio
sys.path.append('src')

from stock_monitoring_bot.repositories.stock_repository import StockRepository
from stock_monitoring_bot.models.stock import MonitoredStock
from datetime import datetime, UTC
from decimal import Decimal

async def add_test_data():
    """テストデータを追加"""
    print("=== DynamoDB Test Data Insert ===")
    
    # テスト用の監視株式データ
    test_stock = MonitoredStock(
        symbol='AAPL',
        name='Apple Inc.',
        market='NASDAQ',
        price_threshold_upper=Decimal('200.0'),
        volume_threshold_multiplier=Decimal('1.5'),
        is_active=True,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC)
    )
    
    print(f"追加するデータ: {test_stock}")
    print(f"is_active type: {type(test_stock.is_active)}")
    
    try:
        repo = StockRepository()
        success = await repo.create_monitored_stock(test_stock)
        
        if success:
            print("✅ テストデータの追加に成功しました")
            
            # 追加されたデータを確認
            stocks = await repo.list_monitored_stocks()
            print(f"現在のデータ件数: {len(stocks)}")
            for stock in stocks:
                print(f"  - {stock.symbol}: {stock.name}")
        else:
            print("❌ テストデータの追加に失敗しました")
            
    except Exception as e:
        print(f"❌ エラー: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(add_test_data())