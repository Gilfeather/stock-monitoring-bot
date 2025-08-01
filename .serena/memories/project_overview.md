# 株価監視ボット - プロジェクト概要

## プロジェクトの目的
リアルタイムで株価を監視し、設定した条件に基づいてDiscordに通知を送信するボット。ポートフォリオ管理機能により、保有銘柄の含み損益も定期的にレポートする。

## 主な機能
- **株価監視**: 指定した銘柄の価格変動を監視、閾値を超えた場合にDiscordに通知
- **ポートフォリオ管理**: 保有銘柄の登録・管理、含み損益の自動計算
- **定期レポート**: 1時間に1回の損益レポート自動送信
- **Discordコマンド**: `!add`, `!remove`, `!list`, `!alert`, `!portfolio` コマンド群

## アーキテクチャ
- **Discord Webhook処理**: Cloudflare Workers → AWS SQS FIFO → AWS Lambda
- **メインアーキテクチャ**: Discord Bot ↔ Stock Monitor Core ↔ Stock Data API
- **データストア**: DynamoDB
- **通知**: Discord Webhook

## Lambda関数
1. **メインLambda関数** (`stock_monitoring`): 株価監視と含み損益レポート
2. **Discord処理Lambda関数** (`discord_processor`): Discord WebhookからのSQSメッセージ処理