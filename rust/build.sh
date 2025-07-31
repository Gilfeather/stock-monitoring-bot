#!/bin/bash
set -e

echo "Building Rust Lambda functions..."

# Install cargo-lambda if not present
if ! command -v cargo-lambda &> /dev/null; then
    echo "Installing cargo-lambda..."
    pip install cargo-lambda
fi

# Clean previous builds
rm -rf target/lambda/

# Build Discord handler
echo "Building discord_handler..."
cargo lambda build --release --bin discord_handler

# Build stock monitor
echo "Building stock_monitor..."
cargo lambda build --release --bin stock_monitor

# Build PnL report
echo "Building pnl_report..."
cargo lambda build --release --bin pnl_report

echo "✅ Rust Lambda functions built successfully!"
echo "Discord handler: target/lambda/discord_handler/bootstrap.zip"
echo "Stock monitor: target/lambda/stock_monitor/bootstrap.zip"
echo "PnL report: target/lambda/pnl_report/bootstrap.zip"

# Copy to deployment directory
mkdir -p ../deployment/rust/
cp target/lambda/discord_handler/discord_handler.zip ../deployment/rust/discord_handler.zip
cp target/lambda/stock_monitor/stock_monitor.zip ../deployment/rust/stock_monitor.zip || echo "stock_monitor not ready yet"
cp target/lambda/pnl_report/pnl_report.zip ../deployment/rust/pnl_report.zip || echo "pnl_report not ready yet"

echo "✅ Deployment packages ready!"