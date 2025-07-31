#!/bin/bash

# Lambda関数とLayer用パッケージをビルド
set -e

echo "Building Lambda packages..."

# 一時ディレクトリを作成
rm -rf deployment/layer* deployment/function
mkdir -p deployment/layer-basic/python deployment/layer-data/python deployment/function

# uvを使って依存関係をインストール（Linux向けビルド、dev依存関係除外）
echo "Installing dependencies with uv for Lambda (Linux x86_64)..."
uv export --format requirements-txt --no-header --no-dev --no-hashes > deployment/requirements.txt

# 基本依存関係（重いパッケージ除外）
echo "Creating basic dependencies layer..."
cat > deployment/requirements-basic.txt << 'EOF'
aioboto3==15.0.0
aiohttp==3.12.15
pydantic==2.11.7
pydantic-core==2.33.2
PyNaCl==1.5.0
python-dotenv==1.1.1
aws-lambda-powertools==3.18.0
requests==2.32.4
EOF

# Install dependencies ensuring proper platform compatibility
uv pip install --target deployment/layer-basic/python --python-platform x86_64-unknown-linux-gnu --python-version 3.13 --only-binary=:all: -r deployment/requirements-basic.txt

# Verify pydantic-core is properly installed
if [ ! -d "deployment/layer-basic/python/pydantic_core" ]; then
    echo "Warning: pydantic_core not found, installing separately..."
    uv pip install --target deployment/layer-basic/python --python-platform x86_64-unknown-linux-gnu --python-version 3.13 --only-binary=:all: pydantic-core==2.33.2
fi

# データ処理依存関係（pandas, numpy, yfinance + その依存関係）
echo "Creating data processing dependencies layer..."
uv pip install --target deployment/layer-data/python --python-platform x86_64-unknown-linux-gnu --python-version 3.13 pandas numpy yfinance curl-cffi cffi beautifulsoup4 frozendict multitasking peewee platformdirs protobuf pytz websockets

# Layer用の依存関係は既にインストール済み
echo "Lambda Layers created:"
echo "- Basic layer: deployment/layer-basic/python/"
echo "- Data layer: deployment/layer-data/python/"

# パッケージメタデータを保持（curl_cffi等で必要）
echo "Preserving package metadata and only removing compiled files..."

# 基本Layerの軽微なクリーンアップ
echo "Cleaning basic layer..."
find deployment/layer-basic -name "*.pyc" -delete 2>/dev/null || true
find deployment/layer-basic -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true

# データLayerの軽微なクリーンアップ
echo "Cleaning data layer..."
find deployment/layer-data -name "*.pyc" -delete 2>/dev/null || true
find deployment/layer-data -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true

# Function用：ソースコードのみをコピー
echo "Creating Lambda Function (source code only)..."
cp -r src/stock_monitoring_bot deployment/function/

# 基本Layerパッケージを作成
echo "Creating basic Lambda Layer package..."
cd deployment/layer-basic
zip -r ../lambda-layer-basic.zip . -q
cd ../..

# データLayerパッケージを作成
echo "Creating data Lambda Layer package..."
cd deployment/layer-data
zip -r ../lambda-layer-data.zip . -q
cd ../..

# Functionパッケージを作成
echo "Creating Lambda Function package..."
cd deployment/function
zip -r ../lambda-function.zip . -q
cd ../..

echo "Basic Lambda Layer created: deployment/lambda-layer-basic.zip"
echo "Basic layer size: $(du -h deployment/lambda-layer-basic.zip | cut -f1)"
echo "Data Lambda Layer created: deployment/lambda-layer-data.zip"
echo "Data layer size: $(du -h deployment/lambda-layer-data.zip | cut -f1)"
echo "Lambda Function created: deployment/lambda-function.zip"
echo "Function size: $(du -h deployment/lambda-function.zip | cut -f1)"