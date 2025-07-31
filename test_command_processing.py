#!/usr/bin/env python3
"""
コマンド処理部分のデバッグ（署名検証をスキップ）
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

async def test_command_processing():
    """署名検証をスキップしてコマンド処理をテスト"""
    print("=== コマンド処理デバッグ ===")
    
    # Discord公開鍵（署名検証には使わない）
    discord_public_key = "1b1ba15d2d17765c2d6bc06642f98901128c12978bd4b43de8008d8435082bd1"
    
    try:
        # InteractionsHandlerを初期化
        handler = InteractionsHandler(public_key=discord_public_key)
        print("✅ InteractionsHandler初期化成功")
        
        # 直接コマンド処理をテスト（署名検証をスキップ）
        print("\n=== /list コマンドテスト ===")
        result = await handler._process_slash_command('list', [], 'test_user_123')
        print(f"結果: {result}")
        
        print("\n=== /add コマンドテスト ===")
        options = [{'name': 'symbol', 'value': 'AAPL'}]
        result = await handler._process_slash_command('add', options, 'test_user_123')
        print(f"結果: {result}")
        
        print("\n=== /price コマンドテスト ===")
        options = [{'name': 'symbol', 'value': 'AAPL'}]
        result = await handler._process_slash_command('price', options, 'test_user_123')
        print(f"結果: {result}")
        
    except Exception as e:
        print(f"❌ エラー: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_command_processing())