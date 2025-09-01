#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import argparse
import pandas as pd
import numpy as np
from datetime import datetime

def require(module_name):
    try:
        return __import__(module_name)
    except Exception as e:
        print(f'Please install {module_name}: {e}', file=sys.stderr)
        sys.exit(1)


def fetch_yahoo(tickers, start, end, interval='1d'):
    yf = require('yfinance')
    # yfinance supports multi-ticker download
    df = yf.download(tickers, start=start, end=end, interval=interval, auto_adjust=False, progress=False, group_by='ticker')
    return df


def to_universe(df_multi, tickers):
    rows = []
    for t in tickers:
        if t not in df_multi.columns.get_level_values(0):
            # yfinance returns lowercase? try fallback
            continue
        sub = df_multi[t].reset_index()
        # Normalize columns
        sub = sub.rename(columns={'Date': 'date', 'Open': 'open', 'High': 'high', 'Low': 'low', 'Close': 'close', 'Volume': 'volume'})
        # unify timestamp
        sub['date'] = pd.to_datetime(sub['date']).dt.strftime('%Y-%m-%d %H:%M:%S')
        sub['stock'] = t
        rows.append(sub[['date', 'stock', 'open', 'high', 'low', 'close', 'volume']])
    if not rows:
        raise RuntimeError('No ticker data downloaded.')
    df = pd.concat(rows, axis=0)
    # Map stock to rank index required by MASA format
    # Keep ordering of input tickers
    mapping = {t: i + 1 for i, t in enumerate(tickers)}
    df['stock'] = df['stock'].map(mapping)
    df = df.dropna(subset=['close'])
    return df


def to_index(universe_df):
    # Average OHLC across components, sum volume
    idx = universe_df.copy()
    idx = idx.drop(columns=['stock'])
    idx = idx.groupby('date').agg({'open': 'mean', 'high': 'mean', 'low': 'mean', 'close': 'mean', 'volume': 'sum'}).reset_index()
    return idx


def main():
    parser = argparse.ArgumentParser(description='Fetch multi-ticker portfolio data for MASA')
    parser.add_argument('--tickers', type=str, required=True, help='Comma-separated tickers')
    parser.add_argument('--market', type=str, default=os.environ.get('MARKET_NAME', 'CUSTOM'))
    parser.add_argument('--start', type=str, default=os.environ.get('START_DATE', '2016-01-01'))
    parser.add_argument('--end', type=str, default=os.environ.get('END_DATE', datetime.now().strftime('%Y-%m-%d')))
    parser.add_argument('--data_dir', type=str, default=os.environ.get('DATA_DIR', './data'))
    parser.add_argument('--freq', type=str, default=os.environ.get('FREQ', '1d'))
    parser.add_argument('--fine', action='store_true', help='Also fetch 60m intraday for market observer')
    args = parser.parse_args()

    tickers = [t.strip().upper() for t in args.tickers.split(',') if t.strip()]
    if len(tickers) == 0:
        raise ValueError('No tickers provided')

    os.makedirs(args.data_dir, exist_ok=True)
    df = fetch_yahoo(tickers, args.start, args.end, interval='1d')
    uni = to_universe(df, tickers)
    idx = to_index(uni)

    topk = len(tickers)
    uni_path = os.path.join(args.data_dir, f'{args.market}_{topk}_1d.csv')
    idx_path = os.path.join(args.data_dir, f'{args.market}_1d_index.csv')
    uni.to_csv(uni_path, index=False)
    idx.to_csv(idx_path, index=False)

    if args.fine:
        df60 = fetch_yahoo(tickers, args.start, args.end, interval='60m')
        if not df60.empty:
            uni60 = to_universe(df60, tickers)
            idx60 = to_index(uni60)
            uni60_path = os.path.join(args.data_dir, f'{args.market}_{topk}_60m.csv')
            idx60_path = os.path.join(args.data_dir, f'{args.market}_60m_index.csv')
            uni60.to_csv(uni60_path, index=False)
            idx60.to_csv(idx60_path, index=False)

    print('Saved:')
    print(uni_path)
    print(idx_path)
    return 0


if __name__ == '__main__':
    sys.exit(main())

