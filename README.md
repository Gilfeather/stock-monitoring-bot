# 株価監視ボット

リアルタイムで株価を監視し、設定した条件に基づいてDiscordに通知を送信するボットです。ポートフォリオ管理機能により、保有銘柄の含み損益も定期的にレポートします。

## 主な機能

### 📈 株価監視
- 指定した銘柄の価格変動を監視
- 設定した閾値を超えた場合にDiscordに通知
- 取引量の異常な変動も検知

### 💰 ポートフォリオ管理
- 保有銘柄の登録・管理
- 含み損益の自動計算
- 定期的な損益レポートの送信（1時間に1回）

### 🤖 Discordコマンド
- `!add <銘柄コード>` - 監視銘柄を追加
- `!remove <銘柄コード>` - 監視銘柄を削除
- `!list` - 監視銘柄一覧を表示
- `!alert <銘柄コード> <上限> [下限]` - アラート閾値を設定
- `!portfolio add <銘柄> <株数> <取得価格>` - 保有銘柄を追加
- `!portfolio remove <銘柄>` - 保有銘柄を削除
- `!portfolio list` - 保有銘柄一覧を表示
- `!portfolio pnl` - 含み損益レポートを表示

## アーキテクチャ

### メインアーキテクチャ
```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Discord Bot   │    │  Stock Monitor  │    │  Stock Data API │
│   (Commands)    │◄──►│     Core        │◄──►│  (Yahoo/Alpha)  │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       
         ▼                       ▼                       
┌─────────────────┐    ┌─────────────────┐              
│ Discord Webhook │    │   DynamoDB      │              
│   (Notifications)│    │  (Data Store)   │              
└─────────────────┘    └─────────────────┘              
```

### Discord Webhook処理アーキテクチャ（サーバーレス）
```
Discord Webhook
       │
       ▼
┌─────────────────┐
│ Cloudflare      │ ◄── Ed25519署名検証
│ Workers         │ ◄── 即座に204レスポンス
└─────────────────┘
       │ (非同期POST)
       ▼
┌─────────────────┐
│ AWS SQS FIFO    │ ◄── 冪等性保証
│ Queue           │ ◄── メッセージ重複排除
└─────────────────┘
       │ (トリガー)
       ▼
┌─────────────────┐
│ AWS Lambda      │ ◄── 重い処理
│ (Discord処理)   │ ◄── ビジネスロジック
└─────────────────┘
```

## セットアップ

### 1. 環境変数の設定

#### Terraformを使用する場合（推奨）

`terraform/environments/dev.tfvars.template`をコピーして`dev.tfvars`ファイルを作成し、必要な値を設定してください。

```bash
cp terraform/environments/dev.tfvars.template terraform/environments/dev.tfvars
```

主要な設定項目：
- `discord_webhook_url`: Discord WebhookのURL
- `alpha_vantage_api_key`: Alpha Vantage APIキー（フォールバック用）
- `discord_public_key`: Discord Public Key
- `user_ids`: P&L通知対象ユーザーID（カンマ区切り）

#### 従来の.envファイルを使用する場合

`.env.template`をコピーして`.env`ファイルを作成し、必要な値を設定してください。

```bash
cp .env.template .env
```

主要な設定項目：
- `DISCORD_WEBHOOK_URL`: Discord WebhookのURL
- `TARGET_USERS`: 損益レポートの送信対象ユーザーID（カンマ区切り）
- `ADMIN_USERS`: 管理者権限を持つユーザーID（カンマ区切り）
- `ALLOWED_CHANNELS`: コマンド実行を許可するチャンネルID（カンマ区切り）

### 2. 依存関係のインストール

```bash
# uvを使用する場合
uv sync

# pipを使用する場合
pip install -r requirements.txt
```

### 3. インフラストラクチャのデプロイ

#### Terraformを使用したデプロイ（推奨）

```bash
# Terraformディレクトリに移動
cd terraform

# Terraformを初期化
terraform init

# 設定を確認
terraform plan -var-file="environments/dev.tfvars"

# インフラをデプロイ
terraform apply -var-file="environments/dev.tfvars"
```

#### 手動でのAWS Lambda関数デプロイ

```bash
# パッケージをビルド
make build

# Lambda関数をデプロイ
make deploy
```

または手動でデプロイ：

```bash
# 依存関係をパッケージ化
pip install -r requirements.txt -t deployment/package/

# Lambda関数用のzipファイルを作成
cd deployment/package/
zip -r ../lambda-function.zip .
cd ../..
zip -g deployment/lambda-function.zip lambda_pnl_report.py

# AWS CLIでデプロイ
aws lambda create-function \
  --function-name stock-monitoring-pnl-report \
  --runtime python3.11 \
  --role arn:aws:iam::YOUR_ACCOUNT:role/lambda-execution-role \
  --handler lambda_pnl_report.handler \
  --zip-file fileb://deployment/lambda-function.zip \
  --timeout 300 \
  --memory-size 512
```

### 4. CloudWatch Eventsでスケジュール設定

Terraformを使用した場合は自動で設定されます。手動の場合：

```bash
# EventBridge ルールを作成
aws events put-rule \
  --name stock-monitoring-pnl-schedule \
  --schedule-expression "rate(1 hour)"

# Lambda関数をターゲットに追加
aws events put-targets \
  --rule stock-monitoring-pnl-schedule \
  --targets "Id"="1","Arn"="arn:aws:lambda:REGION:ACCOUNT:function:stock-monitoring-pnl-report"
```

## 使用方法

### ポートフォリオ管理

1. **保有銘柄の追加**
   ```
   !portfolio add 7203 100 2500
   ```
   トヨタ自動車（7203）を100株、取得価格2500円で追加

2. **保有銘柄の確認**
   ```
   !portfolio list
   ```

3. **含み損益の確認**
   ```
   !portfolio pnl
   ```

4. **保有銘柄の削除**
   ```
   !portfolio remove 7203
   ```

### 株価監視

1. **監視銘柄の追加**
   ```
   !add 7203 トヨタ自動車
   ```

2. **アラート設定**
   ```
   !alert 7203 3000 2000
   ```
   上限3000円、下限2000円でアラート設定

3. **監視銘柄一覧**
   ```
   !list
   ```

## 定期レポート

システムは1時間に1回、設定されたユーザーに対して含み損益レポートを自動送信します。

レポートには以下の情報が含まれます：
- 総取得金額
- 現在評価額
- 含み損益（金額・パーセンテージ）
- 銘柄別詳細
- 主要銘柄の損益ランキング

## 開発

### テストの実行

```bash
# 全テストを実行
python -m pytest

# 特定のテストファイルを実行
python -m pytest tests/test_portfolio_service.py -v

# カバレッジレポート付きで実行
python -m pytest --cov=src --cov-report=html
```

### ローカル開発

```bash
# 開発サーバーを起動
python main.py

# Lambda関数をローカルでテスト
python lambda_pnl_report.py
```

## 技術スタック

- **Python 3.11+**
- **aiohttp**: 非同期HTTP通信
- **pydantic**: データ検証
- **pandas**: データ分析
- **yfinance**: Yahoo Finance API
- **boto3**: AWS SDK
- **pytest**: テストフレームワーク

## ライセンス

MIT License

## 貢献

プルリクエストやイシューの報告を歓迎します。

## サポート

質問や問題がある場合は、GitHubのIssuesページでお知らせください。