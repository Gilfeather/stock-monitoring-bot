# 技術スタック

## 言語・ランタイム
- **Python 3.13+** (requires-python = ">=3.13")
- **AWS Lambda** (runtime: python3.13)

## 主要ライブラリ
- **aiohttp**: 非同期HTTP通信
- **pydantic**: データ検証とモデル定義
- **yfinance**: Yahoo Finance API
- **boto3/aioboto3**: AWS SDK
- **requests**: HTTP通信
- **aws-lambda-powertools**: Lambda開発ツール
- **PyNaCl**: Discord署名検証

## インフラストラクチャ
- **AWS Lambda**: サーバーレス実行環境
- **AWS DynamoDB**: データストレージ
- **AWS SQS FIFO**: メッセージキュー
- **AWS EventBridge**: スケジュール実行
- **AWS Parameter Store**: 機密情報管理
- **Cloudflare Workers**: Discord Webhook処理
- **Terraform**: インフラ管理

## 開発ツール
- **uv**: Python依存関係管理
- **pytest**: テストフレームワーク
- **black**: コードフォーマッター
- **isort**: インポート整理
- **mypy**: 型チェック
- **ruff**: リンター