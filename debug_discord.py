#!/usr/bin/env python3
"""
実際のDiscordリクエストをシミュレートしてデバッグ
"""
import requests
import json
import time
import sys

def test_discord_request():
    """Discordリクエストの形式でテスト"""
    
    url = "https://80ru5yrvb3.execute-api.ap-northeast-1.amazonaws.com/dev/interactions"
    
    # Discord PING形式
    payload = {
        "type": 1,
        "id": "123456789012345678",
        "application_id": "1399877333527171215",
        "version": 1
    }
    
    body = json.dumps(payload, separators=(',', ':'))
    timestamp = str(int(time.time()))
    
    # Discordが送信するヘッダー形式
    headers = {
        "Content-Type": "application/json",
        "User-Agent": "Discord-Interactions/1.0 (+https://discord.com/developers/docs/interactions/receiving-and-responding)",
        "X-Signature-Ed25519": "a" * 128,  # ダミー署名（128文字）
        "X-Signature-Timestamp": timestamp,
        "Accept": "*/*",
        "Accept-Encoding": "gzip, deflate",
        "Connection": "keep-alive",
    }
    
    print("=== Discord形式リクエストテスト ===")
    print(f"URL: {url}")
    print(f"Payload: {body}")
    print(f"Headers: {json.dumps({k: v for k, v in headers.items() if not k.startswith('X-Signature')}, indent=2)}")
    print(f"Signature length: {len(headers['X-Signature-Ed25519'])}")
    print(f"Timestamp: {timestamp}")
    print("")
    
    start_time = time.time()
    
    try:
        response = requests.post(
            url,
            headers=headers,
            data=body,
            timeout=10
        )
        
        end_time = time.time()
        response_time = end_time - start_time
        
        print(f"✅ レスポンス時間: {response_time:.3f}秒")
        print(f"ステータスコード: {response.status_code}")
        print(f"レスポンス: {response.text}")
        
        if response_time < 3.0:
            print("🎉 3秒以内に応答しました！")
        else:
            print("❌ 3秒を超えました - Discordタイムアウトが発生します")
            
    except requests.exceptions.Timeout:
        print("❌ リクエストタイムアウト（10秒以上）")
    except Exception as e:
        print(f"❌ エラー: {e}")

if __name__ == "__main__":
    test_discord_request()