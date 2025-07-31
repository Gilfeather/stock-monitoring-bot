#!/bin/bash

# Discord Lambda function build script
set -e

echo "Building Discord Lambda function..."

# Create deployment directory
mkdir -p deployment

# Clean previous builds
rm -rf deployment/discord-lambda-function.zip
rm -rf deployment/discord-temp/

# Create temporary directory
mkdir -p deployment/discord-temp

# Copy source code
cp -r src/ deployment/discord-temp/
cp src/discord_processor.py deployment/discord-temp/

# Install dependencies (if needed)
# pip install -r requirements.txt -t deployment/discord-temp/

# Create zip file
cd deployment/discord-temp
zip -r ../discord-lambda-function.zip .
cd ../..

# Clean up
rm -rf deployment/discord-temp/

echo "Discord Lambda function built successfully: deployment/discord-lambda-function.zip"