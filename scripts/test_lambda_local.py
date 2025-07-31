#!/usr/bin/env python3
"""
Lambda関数のローカルテスト
"""
import sys
import os
import json
import asyncio

# プロジェクトルートをPATHに追加
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from stock_monitoring_bot.handlers.main import lambda_handler

async def test_interactions_handler():
    """Discord Interactions handlerのテスト"""
    
    # テスト用のAPI Gateway イベント
    test_event = {
        "httpMethod": "POST",
        "path": "/interactions",
        "headers": {
            "Content-Type": "application/json",
            "X-Signature-Ed25519": "dummy_signature",
            "X-Signature-Timestamp": "1234567890"
        },
        "body": json.dumps({
            "type": 1,  # PING
            "id": "123456789",
            "application_id": "1399877333527171215"
        }),
        "requestContext": {
            "requestId": "test-request-id",
            "stage": "dev"
        }
    }
    
    print("テスト用イベント:")
    print(json.dumps(test_event, indent=2))
    print("\n" + "="*50)
    
    try:
        # Lambda関数を実行
        result = await lambda_handler(test_event, None)
        
        print("Lambda実行結果:")
        print(f"Status Code: {result.get('statusCode')}")
        print(f"Body: {result.get('body')}")
        print(f"Headers: {result.get('headers', {})}")
        
        return result
        
    except Exception as e:
        print(f"❌ Lambda実行エラー: {e}")
        import traceback
        traceback.print_exc()
        return None

if __name__ == "__main__":
    print("Lambda関数ローカルテスト")
    print("=" * 50)
    
    # 環境変数設定（テスト用）
    os.environ.setdefault('ENVIRONMENT', 'dev')
    
    # テスト実行
    result = asyncio.run(test_interactions_handler())
    
    if result:
        print("\n✅ テスト完了")
    else:
        print("\n❌ テスト失敗")