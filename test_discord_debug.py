#!/usr/bin/env python3
"""
Discord署名検証のデバッグ
"""
import sys
import asyncio
import os
sys.path.append('src')

from stock_monitoring_bot.handlers.interactions_handler import InteractionsHandler
import json
import logging

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

async def test_discord_signature():
    """Discord署名検証をテスト"""
    print("=== Discord 署名検証デバッグ ===")
    
    # dev.tfvarsから実際のDiscord公開鍵を使用
    discord_public_key = "1b1ba15d2d17765c2d6bc06642f98901128c12978bd4b43de8008d8435082bd1"
    
    print(f"Discord公開鍵: {discord_public_key[:16]}...")
    
    try:
        # InteractionsHandlerを初期化
        handler = InteractionsHandler(public_key=discord_public_key)
        print("✅ InteractionsHandler初期化成功")
        
        # テストイベントを作成（実際のDiscordリクエスト形式）
        test_event = {
            'headers': {
                'x-signature-ed25519': '0' * 128,  # 正確に128文字のダミー署名
                'x-signature-timestamp': '1234567890'
            },
            'body': json.dumps({
                'type': 1,  # PING
                'id': 'test_id',
                'application_id': 'test_app_id',
                'token': 'test_token'
            })
        }
        
        print(f"テストイベント: {json.dumps(test_event, indent=2)}")
        
        # インタラクション処理をテスト
        result = await handler.handle_interaction(test_event)
        print(f"処理結果: {result}")
        
    except Exception as e:
        print(f"❌ エラー: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_discord_signature())