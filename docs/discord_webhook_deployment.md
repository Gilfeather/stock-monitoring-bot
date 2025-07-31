# Discord Webhook サーバーレス構成デプロイ手順

## 概要

Discord WebhookをCloudflare Workers + AWS SQS + AWS Lambdaで処理するサーバーレス構成のデプロイ手順です。

## アーキテクチャ

```
Discord Webhook → Cloudflare Workers → SQS FIFO → Lambda
                      ↓ (即座に204)
```

## 1. AWS インフラのデプロイ

### 1.1 Discord Lambda関数をビルド

```bash
# Discord処理用Lambda関数をビルド
make build-discord
```

### 1.2 Terraformでインフラをデプロイ

```bash
cd terraform

# 初期化
terraform init

# プランを確認
terraform plan -var-file="environments/dev.tfvars"

# デプロイ
terraform apply -var-file="environments/dev.tfvars"
```

### 1.3 SQS情報を取得

```bash
# SQS Queue URLを取得
terraform output -raw sqs_queue_url

# Cloudflare Workers用のAWSクレデンシャルを取得
terraform output -raw cloudflare_access_key_id
terraform output -raw cloudflare_secret_access_key
```

## 2. Cloudflare Workers のデプロイ

### 2.1 依存関係をインストール

```bash
cd cloudflare-worker
npm install
```

### 2.2 環境変数を設定

```bash
# Discord Public Key
wrangler secret put DISCORD_PUBLIC_KEY

# AWS認証情報
wrangler secret put AWS_ACCESS_KEY_ID
wrangler secret put AWS_SECRET_ACCESS_KEY

# SQS Queue URL
wrangler secret put SQS_QUEUE_URL
```

### 2.3 デプロイ

```bash
# 開発環境
wrangler deploy

# 本番環境
wrangler deploy --env production
```

## 3. Discord Developer Portal 設定

### 3.1 Interactions Endpoint URL を設定

1. [Discord Developer Portal](https://discord.com/developers/applications) にアクセス
2. アプリケーションを選択
3. "General Information" → "Interactions Endpoint URL" に Cloudflare Workers の URL を設定

例: `https://discord-webhook-handler.your-subdomain.workers.dev`

### 3.2 Bot Permissions を設定

必要な権限:
- `applications.commands` (Slash Commands)
- `bot` (基本的なBot機能)

## 4. テスト

### 4.1 PING テスト

Discord Developer Portal の "Interactions Endpoint URL" で "Save Changes" をクリックすると、自動的にPINGテストが実行されます。

### 4.2 Slash Command テスト

Discordサーバーで以下のコマンドをテスト:

```
/status
/list
/price 2433
```

## 5. モニタリング

### 5.1 Cloudflare Workers ログ

```bash
# リアルタイムログを確認
wrangler tail
```

### 5.2 AWS CloudWatch ログ

- Lambda関数: `/aws/lambda/stock-monitoring-bot-discord-processor-dev`
- SQS メトリクス: CloudWatch → SQS

### 5.3 SQS キューの状態確認

```bash
# キューの状態を確認
aws sqs get-queue-attributes \
  --queue-url "YOUR_SQS_QUEUE_URL" \
  --attribute-names All \
  --profile polarmap \
  --region ap-northeast-1
```

## 6. トラブルシューティング

### 6.1 署名検証エラー

- Discord Public Key が正しく設定されているか確認
- Cloudflare Workers の環境変数を確認

### 6.2 SQS 送信エラー

- AWS認証情報が正しく設定されているか確認
- SQS Queue URL が正しいか確認
- IAM権限を確認

### 6.3 Lambda 処理エラー

- CloudWatch Logs でエラー詳細を確認
- DynamoDB テーブルが存在するか確認
- Parameter Store の値が設定されているか確認

## 7. セキュリティ考慮事項

- Discord Public Key は環境変数として安全に管理
- AWS認証情報は最小権限の原則に従って設定
- SQS FIFO キューで重複処理を防止
- CloudWatch Logs で監査ログを保持

## 8. パフォーマンス最適化

- Cloudflare Workers: エッジで高速処理
- SQS FIFO: 順序保証と重複排除
- Lambda: 必要時のみ起動（コールドスタート回避）
- DynamoDB: オンデマンド課金で柔軟なスケーリング