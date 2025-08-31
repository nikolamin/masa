#!/usr/bin/env bash
set -euo pipefail

# Configurable via env vars
: "${PYTHON:=python3}"
: "${START_DATE:=2013-09-01}"
: "${END_DATE:=$(date +%Y-%m-%d)}"
: "${EPOCHS:=5}"
: "${BENCHMARK_ALGO:=MASA-dc}"
: "${MARKET_NAME:=EURUSD}"
: "${TOPK:=1}"
: "${FREQ:=1d}"
: "${FINEFREQ:=60m}"

echo "Installing dependencies (falling back to user install if needed)..."
if ! ${PYTHON} -m pip install --user -r requirements.txt --break-system-packages 2>/dev/null | cat; then
  ${PYTHON} -m pip install --user -r requirements.txt | cat || true
fi

echo "Fetching EURUSD data..."
${PYTHON} data/fetch_eurusd.py --start "${START_DATE}" --end "${END_DATE}" --fine | cat

echo "Starting training..."
BENCHMARK_ALGO="${BENCHMARK_ALGO}" \
MARKET_NAME="${MARKET_NAME}" \
TOPK="${TOPK}" \
EPOCHS="${EPOCHS}" \
FREQ="${FREQ}" \
FINEFREQ="${FINEFREQ}" \
${PYTHON} entrance.py | cat

