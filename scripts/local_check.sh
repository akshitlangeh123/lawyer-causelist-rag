#!/usr/bin/env bash
set -e

echo "Running backend tests..."
pytest -q

echo "Checking frontend build..."
docker run --rm \
  -v "$PWD/frontend":/app \
  -w /app \
  node:22-bookworm \
  sh -lc "npm ci && npm run build"

echo "Checking Docker build..."
docker compose build

echo "Local checks passed."
