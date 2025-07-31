#!/bin/bash

# Cloudflare Worker build script
set -e

echo "Building Cloudflare Worker..."

# Navigate to cloudflare-worker directory
cd cloudflare-worker

# Install dependencies if node_modules doesn't exist
if [ ! -d "node_modules" ]; then
    echo "Installing dependencies..."
    npm install
fi

# Create dist directory
mkdir -p dist

# Build the worker using esbuild with no module format (global scope)
echo "Building with esbuild (global scope for Cloudflare Workers)..."
npx esbuild src/index.ts --bundle --format=iife --outfile=dist/worker.js --platform=neutral --target=es2022 --global-name=workerModule

echo "Cloudflare Worker built successfully: cloudflare-worker/dist/worker.js"

# Post-process the built file to extract the default export as global handlers
echo "Post-processing for Cloudflare Workers compatibility..."
cat >> dist/worker.js << 'EOF'

// Extract the default export and make it globally available
if (typeof workerModule !== 'undefined' && workerModule.default) {
  addEventListener('fetch', workerModule.default.fetch);
}
EOF

# Go back to root directory
cd ..