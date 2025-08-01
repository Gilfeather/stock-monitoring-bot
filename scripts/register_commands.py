#!/usr/bin/env python3
"""
Discord Slash Commands登録スクリプト
"""
import requests
import json
import os
import time

# Discord設定（環境変数から取得）
APPLICATION_ID = os.getenv("DISCORD_APPLICATION_ID", "1399877333527171215")
BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")

if not BOT_TOKEN:
    print("❌ DISCORD_BOT_TOKEN環境変数を設定してください")
    exit(1)

# APIエンドポイント
DISCORD_API_URL = f"https://discord.com/api/v10/applications/{APPLICATION_ID}/commands"

# ヘッダー
headers = {
    "Authorization": f"Bot {BOT_TOKEN}",
    "Content-Type": "application/json"
}

# コマンド定義（実装済みのもののみ）
commands = [
    {
        "name": "status",
        "description": "システムの動作状況を確認"
    },
    {
        "name": "list",
        "description": "監視中の株式一覧を表示"
    },
    {
        "name": "add",
        "description": "株式を監視リストに追加",
        "options": [
            {
                "name": "symbol",
                "description": "株式シンボル（例：AAPL, TSLA）",
                "type": 3,  # STRING
                "required": True
            }
        ]
    },
    {
        "name": "remove",
        "description": "株式を監視リストから削除",
        "options": [
            {
                "name": "symbol",
                "description": "株式シンボル",
                "type": 3,  # STRING
                "required": True
            }
        ]
    },
    {
        "name": "price",
        "description": "株式の現在価格を取得",
        "options": [
            {
                "name": "symbol",
                "description": "株式シンボル",
                "type": 3,  # STRING
                "required": True
            }
        ]
    },
    {
        "name": "alert",
        "description": "価格アラートを設定",
        "options": [
            {
                "name": "symbol",
                "description": "株式シンボル",
                "type": 3,  # STRING
                "required": True
            },
            {
                "name": "threshold",
                "description": "アラート閾値",
                "type": 10,  # NUMBER
                "required": False
            }
        ]
    },
    {
        "name": "chart",
        "description": "株価チャート情報を表示",
        "options": [
            {
                "name": "symbol",
                "description": "株式シンボル",
                "type": 3,  # STRING
                "required": True
            },
            {
                "name": "period",
                "description": "期間（デフォルト：1mo）",
                "type": 3,  # STRING
                "required": False,
                "choices": [
                    {"name": "1日", "value": "1d"},
                    {"name": "5日", "value": "5d"},
                    {"name": "1ヶ月", "value": "1mo"},
                    {"name": "3ヶ月", "value": "3mo"},
                    {"name": "6ヶ月", "value": "6mo"},
                    {"name": "1年", "value": "1y"}
                ]
            }
        ]
    },
    {
        "name": "help",
        "description": "使用可能なコマンドの一覧とヘルプを表示"
    },
    {
        "name": "portfolio",
        "description": "ポートフォリオ管理",
        "options": [
            {
                "name": "action",
                "description": "実行するアクション",
                "type": 3,  # STRING
                "required": True,
                "choices": [
                    {"name": "add", "value": "add"},
                    {"name": "remove", "value": "remove"},
                    {"name": "list", "value": "list"},
                    {"name": "pnl", "value": "pnl"}
                ]
            },
            {
                "name": "symbol",
                "description": "株式シンボル（add/remove時に必要）",
                "type": 3,  # STRING
                "required": False
            },
            {
                "name": "quantity",
                "description": "株数（add時に必要）",
                "type": 4,  # INTEGER
                "required": False
            },
            {
                "name": "price",
                "description": "取得価格（add時に必要）",
                "type": 10,  # NUMBER
                "required": False
            }
        ]
    }
]

def register_commands():
    """Slash Commandsを登録（レートリミット対応）"""
    print(f"Discordに{len(commands)}個のコマンドを登録中...")
    print("レートリミット対策のため、各コマンド間で1秒待機します\n")
    
    success_count = 0
    failed_count = 0
    
    for i, command in enumerate(commands, 1):
        print(f"[{i}/{len(commands)}] 登録中: /{command['name']}")
        
        try:
            response = requests.post(
                DISCORD_API_URL,
                headers=headers,
                data=json.dumps(command),
                timeout=10
            )
            
            if response.status_code in [200, 201]:
                status_text = "登録成功" if response.status_code == 201 else "更新成功"
                print(f"✅ /{command['name']} {status_text}")
                success_count += 1
            elif response.status_code == 429:
                # レートリミット発生
                retry_after = response.json().get('retry_after', 5)
                print(f"⏳ レートリミット発生。{retry_after}秒待機...")
                time.sleep(retry_after)
                
                # リトライ
                response = requests.post(
                    DISCORD_API_URL,
                    headers=headers,
                    data=json.dumps(command),
                    timeout=10
                )
                
                if response.status_code in [200, 201]:
                    status_text = "登録成功" if response.status_code == 201 else "更新成功"
                    print(f"✅ /{command['name']} {status_text}（リトライ後）")
                    success_count += 1
                else:
                    print(f"❌ /{command['name']} 登録失敗（リトライ後）: {response.status_code}")
                    print(f"   エラー詳細: {response.text}")
                    failed_count += 1
            else:
                print(f"❌ /{command['name']} 登録失敗: {response.status_code}")
                print(f"   エラー詳細: {response.text}")
                failed_count += 1
                
        except requests.exceptions.RequestException as e:
            print(f"❌ /{command['name']} 登録失敗: ネットワークエラー - {e}")
            failed_count += 1
        
        # レートリミット対策：各コマンド間で1秒待機（最後のコマンド以外）
        if i < len(commands):
            time.sleep(1)
    
    print(f"\n📊 登録結果:")
    print(f"✅ 成功: {success_count}個")
    print(f"❌ 失敗: {failed_count}個")
    print(f"📝 合計: {len(commands)}個")
    
    if failed_count == 0:
        print("\n🎉 すべてのコマンドが正常に登録されました！")
    else:
        print(f"\n⚠️  {failed_count}個のコマンドで登録に失敗しました。")

def list_existing_commands():
    """既存のコマンド一覧を取得"""
    print("既存のコマンドを取得中...")
    
    try:
        response = requests.get(DISCORD_API_URL, headers=headers, timeout=10)
        
        if response.status_code == 200:
            existing_commands = response.json()
            print(f"\n📋 既存のコマンド ({len(existing_commands)}個):")
            for cmd in existing_commands:
                print(f"  - /{cmd['name']}: {cmd.get('description', 'No description')}")
            return existing_commands
        else:
            print(f"❌ 既存コマンドの取得に失敗: {response.status_code}")
            return []
            
    except requests.exceptions.RequestException as e:
        print(f"❌ 既存コマンドの取得に失敗: {e}")
        return []

def delete_all_commands():
    """すべてのコマンドを削除"""
    existing_commands = list_existing_commands()
    
    if not existing_commands:
        print("削除するコマンドがありません。")
        return
    
    confirm = input(f"\n⚠️  {len(existing_commands)}個のコマンドを削除しますか？ (y/N): ")
    if confirm.lower() != 'y':
        print("削除をキャンセルしました。")
        return
    
    print(f"\n{len(existing_commands)}個のコマンドを削除中...")
    
    for i, cmd in enumerate(existing_commands, 1):
        print(f"[{i}/{len(existing_commands)}] 削除中: /{cmd['name']}")
        
        try:
            response = requests.delete(
                f"{DISCORD_API_URL}/{cmd['id']}",
                headers=headers,
                timeout=10
            )
            
            if response.status_code == 204:
                print(f"✅ /{cmd['name']} 削除成功")
            else:
                print(f"❌ /{cmd['name']} 削除失敗: {response.status_code}")
                
        except requests.exceptions.RequestException as e:
            print(f"❌ /{cmd['name']} 削除失敗: {e}")
        
        # レートリミット対策
        if i < len(existing_commands):
            time.sleep(1)
    
    print("\nコマンド削除完了！")

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        if sys.argv[1] == "list":
            list_existing_commands()
        elif sys.argv[1] == "delete":
            delete_all_commands()
        elif sys.argv[1] == "register":
            register_commands()
        else:
            print("使用方法:")
            print("  python register_commands.py register  # コマンドを登録")
            print("  python register_commands.py list      # 既存コマンドを一覧表示")
            print("  python register_commands.py delete    # すべてのコマンドを削除")
    else:
        register_commands()