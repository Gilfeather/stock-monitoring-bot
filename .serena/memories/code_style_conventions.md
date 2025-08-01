# コードスタイルと規約

## フォーマット設定
- **Black**: line-length = 88, target-version = py313
- **isort**: profile = "black", line_length = 88
- **MyPy**: python_version = "3.13", disallow_untyped_defs = true

## ディレクトリ構造
```
src/stock_monitoring_bot/
├── config.py                 # 設定管理
├── models/                   # データモデル（Pydantic）
├── repositories/             # データアクセス層
├── services/                 # ビジネスロジック
└── handlers/                 # Lambda ハンドラー
```

## 命名規約
- **クラス**: PascalCase (例: `StockRepository`, `AlertEngine`)
- **関数・変数**: snake_case (例: `process_discord_interaction`)
- **定数**: UPPER_SNAKE_CASE (例: `DISCORD_WEBHOOK_URL`)
- **ファイル名**: snake_case (例: `portfolio_service.py`)

## 型ヒント
- すべての関数に型ヒントを必須
- Pydanticモデルを使用したデータ検証
- `disallow_untyped_defs = true`設定

## ログ設定
- AWS Lambda Powertoolsを使用
- 構造化ログ出力