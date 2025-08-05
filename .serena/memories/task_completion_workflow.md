# タスク完了時のワークフロー

## コード変更後の必須チェック
1. **リンティング実行**
   ```bash
   make lint
   # または個別に
   uv run black --check .
   uv run isort --check-only .
   uv run mypy src/
   ```

2. **フォーマット適用** (必要に応じて)
   ```bash
   make format
   ```

3. **テスト実行**
   ```bash
   make test
   # または
   uv run pytest
   ```

## Lambda関数変更時の追加手順
1. **パッケージビルド**
   ```bash
   make build        # メインLambda
   make build-discord # Discord処理Lambda
   ```

2. **デプロイ** (開発環境)
   ```bash
   make deploy-dev
   ```

## Terraformリソース変更時
```bash
make terraform-plan-dev  # 変更確認
terraform apply -var-file="environments/dev.tfvars"  # 適用
```

## 完了基準
- すべてのlintエラーが解消されている
- すべてのテストが通る
- 型チェックエラーがない
- ビルドが成功する