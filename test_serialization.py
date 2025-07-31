#!/usr/bin/env python3
"""
DynamoDBシリアライゼーションのテスト
"""
import sys
sys.path.append('src')

from stock_monitoring_bot.repositories.base import BaseRepository

# テスト用のBaseRepositoryサブクラス
class TestRepository(BaseRepository):
    def get_table_name(self) -> str:
        return "test-table"

def test_boolean_serialization():
    """Boolean値のシリアライゼーションをテスト"""
    repo = TestRepository()
    
    # テストデータ
    test_item = {
        'symbol': 'AAPL',
        'name': 'Apple Inc.',
        'is_active': True,
        'count': 123,
        'price': 150.5
    }
    
    print("=== Boolean Serialization Test ===")
    print(f"Original item: {test_item}")
    print(f"is_active type: {type(test_item['is_active'])}")
    print(f"isinstance(True, bool): {isinstance(True, bool)}")
    print(f"isinstance(True, int): {isinstance(True, int)}")
    print(f"isinstance(True, (int, float)): {isinstance(True, (int, float))}")
    
    # シリアライズ
    serialized = repo._serialize_item(test_item)
    print(f"Serialized item: {serialized}")
    
    # 各フィールドの確認
    for key, value in serialized.items():
        print(f"  {key}: {value}")
    
    # Boolean値が正しくシリアライズされているかチェック
    if 'is_active' in serialized:
        if serialized['is_active'].get('BOOL') is not None:
            print("✅ Boolean値が正しくシリアライズされています")
        else:
            print("❌ Boolean値が正しくシリアライズされていません")
            print(f"   実際の値: {serialized['is_active']}")
    
if __name__ == "__main__":
    test_boolean_serialization()