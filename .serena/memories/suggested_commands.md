# 推奨コマンド

## 依存関係管理
```bash
# 依存関係のインストール
uv sync --extra dev

# 新しい依存関係の追加
uv add <package-name>
```

## 開発・テスト
```bash
# テスト実行
uv run pytest
make test

# 特定のテストファイル実行
uv run pytest tests/test_portfolio_service.py -v

# カバレッジ付きテスト
uv run pytest --cov=src --cov-report=html
```

## コード品質
```bash
# リンティング
make lint
uv run black --check .
uv run isort --check-only .
uv run mypy src/

# フォーマット
make format
uv run black .
uv run isort .
```

## ビルド・デプロイ
```bash
# Lambda パッケージビルド
make build
make build-discord
make build-cloudflare

# Terraform
make terraform-init
make terraform-plan-dev
terraform apply -var-file="environments/dev.tfvars"

# デプロイ
make deploy-dev
make deploy-cloudflare-dev
```

## ローカル開発
```bash
# 開発サーバー起動
python main.py

# Lambda関数ローカルテスト
python lambda_pnl_report.py
```