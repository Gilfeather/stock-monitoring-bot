# Lambda関数の構造（更新版）

## 単一のLambda関数構成
このプロジェクトは単一のLambda関数で構成される：

### Discord処理Lambda関数 (`discord_processor`)
- **ファイル**: `src/discord_processor.py`  
- **ハンドラー**: `discord_processor.handler`
- **機能**: 
  - SQSキューからのDiscord Webhookメッセージ処理
  - EventBridgeスケジュールによる株価監視 (平日9:00-15:00 JST)
  - EventBridgeスケジュールによる含み損益レポート (毎時間)
- **トリガー**: 
  - SQS FIFO Queue (Cloudflare Workerから送信)
  - EventBridge スケジュール (2つのルール)

## アーキテクチャフロー
```
Discord Webhook → Cloudflare Worker → SQS → Discord処理Lambda
EventBridge Schedule (株価監視) → Discord処理Lambda
EventBridge Schedule (P&Lレポート) → Discord処理Lambda
```

## 削除されたコンポーネント
- **メインLambda関数** (`stock_monitoring`): 削除済み
- **API Gateway**: 削除済み（Cloudflare Workerに置き換え）
- **lambda_pnl_report.py**: 削除済み（不要ファイル）

## Lambda Layers
- 基本依存関係Layer (`dependencies_basic`)
- データ処理Layer (`dependencies_data`) 
両方ともdiscord_lambdaモジュール内で管理