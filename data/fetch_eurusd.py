#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import argparse
import pandas as pd
import numpy as np
import yfinance as yf
from datetime import datetime


def fetch_eurusd_daily(start: str, end: str) -> pd.DataFrame:
    # Yahoo Finance EURUSD daily: 'EURUSD=X'
    ticker = 'EURUSD=X'
    df = yf.download(ticker, start=start, end=end, interval='1d', auto_adjust=False, progress=False)
    if df.empty:
        raise RuntimeError('No EURUSD data returned from Yahoo Finance.')
    df = df.rename(columns={'Open': 'open', 'High': 'high', 'Low': 'low', 'Close': 'close', 'Volume': 'volume'})
    df = df.reset_index()
    df['date'] = pd.to_datetime(df['Date']).dt.strftime('%Y-%m-%d %H:%M:%S')
    df = df.drop(columns=['Date'])
    # Duplicate as single-asset universe with stock id 1
    df['stock'] = 1
    df = df[['date', 'stock', 'open', 'high', 'low', 'close', 'volume']]
    return df


def fetch_eurusd_intraday(start: str, end: str, interval: str = '60m') -> pd.DataFrame:
    ticker = 'EURUSD=X'
    df = yf.download(ticker, start=start, end=end, interval=interval, auto_adjust=False, progress=False)
    if df.empty:
        return pd.DataFrame()
    df = df.rename(columns={'Open': 'open', 'High': 'high', 'Low': 'low', 'Close': 'close', 'Volume': 'volume'})
    df = df.reset_index()
    # yfinance intraday index has timezone; normalize
    if 'Datetime' in df.columns:
        ts_col = 'Datetime'
    elif 'Date' in df.columns:
        ts_col = 'Date'
    else:
        ts_col = df.columns[0]
    df['date'] = pd.to_datetime(df[ts_col]).dt.tz_localize(None)
    df['date'] = df['date'].dt.strftime('%Y-%m-%d %H:%M:%S')
    df = df.drop(columns=[ts_col])
    df['stock'] = 1
    df = df[['date', 'stock', 'open', 'high', 'low', 'close', 'volume']]
    return df


def main():
    parser = argparse.ArgumentParser(description='Fetch EURUSD data and save to MASA format.')
    parser.add_argument('--start', type=str, default=os.environ.get('START_DATE', '2013-09-01'))
    parser.add_argument('--end', type=str, default=os.environ.get('END_DATE', datetime.now().strftime('%Y-%m-%d')))
    parser.add_argument('--data_dir', type=str, default=os.environ.get('DATA_DIR', './data'))
    parser.add_argument('--topk', type=int, default=int(os.environ.get('TOPK', '1')))
    parser.add_argument('--fine', action='store_true', help='Also fetch intraday 60m data for market observer.')
    args = parser.parse_args()

    os.makedirs(args.data_dir, exist_ok=True)

    # Daily universe file: MARKET_TOPK_FREQ.csv -> EURUSD_1_1d.csv
    daily = fetch_eurusd_daily(start=args.start, end=args.end)
    # Ensure topK=1 naming convention
    market = 'EURUSD'
    topk = args.topk if args.topk >= 1 else 1
    daily_path = os.path.join(args.data_dir, f'{market}_{topk}_1d.csv')
    daily.to_csv(daily_path, index=False)

    # Daily index file: MARKET_1d_index.csv with market-level OHLCV (mean over assets; single asset -> copy)
    index_df = daily.copy()
    # Collapse stocks per date (single stock -> no change)
    index_df = index_df.groupby(['date']).agg({'open': 'mean', 'high': 'mean', 'low': 'mean', 'close': 'mean', 'volume': 'sum'}).reset_index()
    index_path = os.path.join(args.data_dir, f'{market}_1d_index.csv')
    index_df.to_csv(index_path, index=False)

    if args.fine:
        intra = fetch_eurusd_intraday(start=args.start, end=args.end, interval='60m')
        if not intra.empty:
            intra_path = os.path.join(args.data_dir, f'{market}_{topk}_60m.csv')
            intra.to_csv(intra_path, index=False)
            # For market observer fine market index, follow same pattern as daily index
            intra_idx = intra.copy()
            intra_idx = intra_idx.groupby(['date']).agg({'open': 'mean', 'high': 'mean', 'low': 'mean', 'close': 'mean', 'volume': 'sum'}).reset_index()
            intra_idx_path = os.path.join(args.data_dir, f'{market}_60m_index.csv')
            intra_idx.to_csv(intra_idx_path, index=False)

    print('Saved:')
    print(daily_path)
    print(index_path)


if __name__ == '__main__':
    sys.exit(main())

