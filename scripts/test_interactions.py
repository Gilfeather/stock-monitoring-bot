#!/usr/bin/env python3
"""
Discord Interactions Endpoint テストスクリプト
"""
import requests
import json
import time
from nacl.signing import SigningKey

# Discord設定
PUBLIC_KEY = "1b1ba15d2d17765c2d6bc06642f98901128c12978bd4b43de8008d8435082bd1"
ENDPOINT_URL = "https://80ru5yrvb3.execute-api.ap-northeast-1.amazonaws.com/dev/interactions"

def create_test_ping():
    """PINGリクエストを作成してテスト"""
    
    # PINGペイロード
    ping_payload = {
        "type": 1,  # PING
        "id": "123456789",
        "application_id": "1399877333527171215"
    }
    
    body = json.dumps(ping_payload)
    timestamp = str(int(time.time()))
    
    print("注意: Discord公開鍵に対応する秘密鍵はDiscordのみが保持しています")
    print("開発者はこの秘密鍵を入手することはできません")
    print("そのため、このテストでは必ず401エラーが返されます")
    print("")
    print("実際のテストには以下の方法があります:")
    print("1. Discord Developer Portalでエンドポイント設定")
    print("2. 実際のDiscordボットコマンドを実行")
    print("3. 署名検証をスキップするテストモード（開発時のみ）")
    print("")
    
    # ダミー署名（実際には無効）
    signature = "0" * 128  # 128文字の無効な署名
    
    headers = {
        "Content-Type": "application/json",
        "X-Signature-Ed25519": signature,
        "X-Signature-Timestamp": timestamp,
        "User-Agent": "Discord-Interactions/1.0"
    }
    
    print(f"テストリクエスト送信中...")
    print(f"URL: {ENDPOINT_URL}")
    print(f"Signature: {signature}")
    print(f"Timestamp: {timestamp}")
    
    try:
        response = requests.post(ENDPOINT_URL, headers=headers, data=body, timeout=10)
        print(f"ステータスコード: {response.status_code}")
        print(f"レスポンス: {response.text}")
        
        if response.status_code == 401:
            print("✅ 署名検証が動作しています（401 Unauthorized）")
        elif response.status_code == 200:
            print("✅ エンドポイントが応答しています")
        else:
            print(f"⚠️  予期しないレスポンス: {response.status_code}")
            
    except Exception as e:
        print(f"❌ リクエストエラー: {e}")

def test_endpoint_availability():
    """エンドポイントの可用性をテスト"""
    try:
        # 無効なリクエストでテスト
        response = requests.post(ENDPOINT_URL, json={}, timeout=5)
        print(f"エンドポイント可用性テスト: {response.status_code}")
        
        if response.status_code in [400, 401, 403]:
            print("✅ エンドポイントは稼働中です")
            return True
        else:
            print(f"⚠️  予期しないレスポンス: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ エンドポイント接続エラー: {e}")
        return False

if __name__ == "__main__":
    print("Discord Interactions Endpoint テスト")
    print("=" * 50)
    
    # エンドポイント可用性テスト
    if test_endpoint_availability():
        print("\n署名検証テスト実行中...")
        create_test_ping()
    else:
        print("\n❌ エンドポイントに接続できません")