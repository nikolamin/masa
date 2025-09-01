#!/usr/bin/env bash
set -euo pipefail

IMAGE_NAME=${IMAGE_NAME:-masa:latest}
TICKERS=${TICKERS:-"GOOGL,AMD,SOFI,COIN,ELF,AVGO,TSM,FUBO,TSLA,NVDA"}
MARKET_NAME=${MARKET_NAME:-CUSTOM}
TOPK=${TOPK:-10}
START_DATE=${START_DATE:-2018-01-01}
END_DATE=${END_DATE:-2019-12-31}
EPOCHS=${EPOCHS:-10}
FREQ=${FREQ:-1d}
FINEFREQ=${FINEFREQ:-60m}

echo "Building Docker image ${IMAGE_NAME}..."
docker build -t "${IMAGE_NAME}" . | cat

echo "Running training + evaluation in Docker..."
docker run --rm -v "$PWD:/mnt/out" -w /app \
  -e TICKERS="${TICKERS}" \
  -e MARKET_NAME="${MARKET_NAME}" \
  -e TOPK="${TOPK}" \
  -e START_DATE="${START_DATE}" \
  -e END_DATE="${END_DATE}" \
  -e EPOCHS="${EPOCHS}" \
  -e FREQ="${FREQ}" \
  -e FINEFREQ="${FINEFREQ}" \
  bash -lc 'chmod +x run_portfolio.sh && bash run_portfolio.sh && cp -r res /mnt/out/ && cp -r evaluation /mnt/out/' | cat

echo "Done. Results copied to ./res and ./evaluation"

