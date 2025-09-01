#!/usr/bin/env bash
set -euo pipefail

# Input tickers
TICKERS=${TICKERS:-"GOOGL,AMD,SOFI,COIN,ELF,AVGO,TSM,FUBO,TSLA,NVDA"}
MARKET_NAME=${MARKET_NAME:-CUSTOM}
TOPK=${TOPK:-10}
START_DATE=${START_DATE:-2016-01-01}
END_DATE=${END_DATE:-$(date +%Y-%m-%d)}
EPOCHS=${EPOCHS:-5}
BENCHMARK_ALGO=${BENCHMARK_ALGO:-MASA-dc}
FREQ=${FREQ:-1d}
FINEFREQ=${FINEFREQ:-60m}

PY=${PY:-python3}

if [ "${IN_DOCKER:-}" != "1" ]; then
  echo "Installing minimal runtime deps first..."
  ${PY} -m pip install --user --upgrade pip || true
  ${PY} -m pip install --user yfinance pandas numpy matplotlib || true

  echo "Installing project dependencies (may partially fail, continuing)..."
  ${PY} -m pip install --user -r requirements.txt || true
else
  echo "Running inside Docker; dependencies already installed in image. Skipping pip installs."
fi

echo "Fetching portfolio data for: ${TICKERS}"
${PY} data/fetch_portfolio.py --tickers "${TICKERS}" --market "${MARKET_NAME}" --start "${START_DATE}" --end "${END_DATE}" --fine | cat

echo "Training MASA..."
BENCHMARK_ALGO="${BENCHMARK_ALGO}" \
MARKET_NAME="${MARKET_NAME}" \
TOPK="${TOPK}" \
EPOCHS="${EPOCHS}" \
FREQ="${FREQ}" \
FINEFREQ="${FINEFREQ}" \
${PY} entrance.py | cat

RES_BASE="res/RLcontroller/TD3/${MARKET_NAME}-${TOPK}"
LAST_RUN_DIR=$(ls -dt ${RES_BASE}/* 2>/dev/null | head -n1 || true)
if [ -z "${LAST_RUN_DIR}" ]; then
  echo "No results found in ${RES_BASE}" >&2
  exit 1
fi

echo "Evaluating bull/bear regimes..."
${PY} evaluate/regime_eval.py --res_dir "${LAST_RUN_DIR}" --data_file "data/${MARKET_NAME}_${TOPK}_1d.csv" --split test --out evaluation | cat

echo "Done. Results in: ${LAST_RUN_DIR} and evaluation/"

