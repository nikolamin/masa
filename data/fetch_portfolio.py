#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import argparse
import pandas as pd
import numpy as np
from datetime import datetime
import urllib.request
import io

def require(module_name):
    try:
        return __import__(module_name)
    except Exception as e:
        print(f'Please install {module_name}: {e}', file=sys.stderr)
        sys.exit(1)


def _as_multiindex(df, ticker):
    # Ensure a MultiIndex column structure like yfinance(group_by='ticker')
    if df is None or df.empty:
        return None
    # Standardize index name for downstream logic
    if 'Datetime' in df.columns:
        # Some intervals return a column rather than index; unify as index
        df = df.set_index('Datetime')
    if df.index.name is None:
        df.index.name = 'Date'
    elif df.index.name not in ('Date', 'Datetime'):
        df.index.name = 'Date'
    cols = list(df.columns)
    return pd.concat({ticker: df[cols]}, axis=1)


def fetch_yahoo(tickers, start, end, interval='1d'):
    yf = require('yfinance')
    # Try a single batched request first
    try:
        df = yf.download(tickers, start=start, end=end, interval=interval, auto_adjust=False, progress=False, group_by='ticker', threads=False)
        # yfinance may return a single-level columns for one ticker; normalize
        if not isinstance(df.columns, pd.MultiIndex):
            # Attempt to infer the sole ticker
            t0 = tickers[0] if isinstance(tickers, (list, tuple)) and len(tickers) > 0 else (tickers if isinstance(tickers, str) else 'T')
            df = _as_multiindex(df, str(t0).upper())
        return df
    except Exception:
        pass

    # Fallback: download per-ticker and merge
    frames = []
    for t in tickers:
        try:
            df_t = yf.download(t, start=start, end=end, interval=interval, auto_adjust=False, progress=False, threads=False)
            mi = _as_multiindex(df_t, t)
            if mi is not None:
                frames.append(mi)
        except Exception:
            continue
    if frames:
        return pd.concat(frames, axis=1)
    return pd.DataFrame()


# --- Stooq fallback (daily only) ---
def _stooq_symbol(ticker: str) -> str:
    t = ticker.strip().lower()
    mapping = {
        'goog': 'goog.us',
        'googl': 'googl.us',
        'msft': 'msft.us',
        'aapl': 'aapl.us',
        'spy': 'spy.us',
    }
    return mapping.get(t, f'{t}.us')


def _stooq_download_daily_df(ticker: str, start: str, end: str) -> pd.DataFrame:
    sym = _stooq_symbol(ticker)
    url = f'https://stooq.com/q/d/l/?s={sym}&i=d'
    with urllib.request.urlopen(url, timeout=30) as resp:
        content = resp.read().decode('utf-8')
    # Parse CSV
    f = io.StringIO(content)
    df = pd.read_csv(f)
    if df.empty:
        return pd.DataFrame()
    # Filter range
    df['Date'] = pd.to_datetime(df['Date'])
    df = df[(df['Date'] >= pd.to_datetime(start)) & (df['Date'] <= pd.to_datetime(end))]
    # Align columns with Yahoo
    df = df.rename(columns={'Open': 'Open', 'High': 'High', 'Low': 'Low', 'Close': 'Close', 'Volume': 'Volume'})
    df = df.set_index('Date')
    df.index.name = 'Date'
    return df[['Open', 'High', 'Low', 'Close', 'Volume']]


def fetch_stooq_multi(tickers, start, end) -> pd.DataFrame:
    frames = []
    for t in tickers:
        try:
            df_t = _stooq_download_daily_df(t, start, end)
            if not df_t.empty:
                frames.append(pd.concat({t: df_t}, axis=1))
        except Exception:
            continue
    if frames:
        return pd.concat(frames, axis=1)
    return pd.DataFrame()


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
    # If Yahoo failed or missing most tickers, fallback to Stooq daily
    missing = []
    if isinstance(df, pd.DataFrame) and isinstance(df.columns, pd.MultiIndex):
        have = set(df.columns.get_level_values(0))
        missing = [t for t in tickers if t not in have]
    if df is None or df.empty or (len(missing) == len(tickers)):
        df = fetch_stooq_multi(tickers, args.start, args.end)
    uni = to_universe(df, tickers)
    idx = to_index(uni)

    topk = len(tickers)
    uni_path = os.path.join(args.data_dir, f'{args.market}_{topk}_1d.csv')
    idx_path = os.path.join(args.data_dir, f'{args.market}_1d_index.csv')
    uni.to_csv(uni_path, index=False)
    idx.to_csv(idx_path, index=False)

    if args.fine:
        # yfinance intraday data (<= 60m) is limited to last ~730 days
        # Clamp the fine range and only persist 60m data if it fully covers daily dates
        try:
            end_dt = pd.to_datetime(args.end)
        except Exception:
            end_dt = pd.to_datetime(datetime.now().strftime('%Y-%m-%d'))
        start_dt = pd.to_datetime(args.start)
        lower_bound = end_dt - pd.Timedelta(days=728)
        fine_start = max(start_dt, lower_bound)
        fine_start_str = fine_start.strftime('%Y-%m-%d')
        fine_end_str = end_dt.strftime('%Y-%m-%d')
        df60 = fetch_yahoo(tickers, fine_start_str, fine_end_str, interval='60m')
        if not df60.empty:
            uni60 = to_universe(df60, tickers)
            # Compare coverage by day
            daily_days = set(pd.to_datetime(uni['date']).dt.date.unique())
            fine_days = set(pd.to_datetime(uni60['date']).dt.date.unique())
            if daily_days.issubset(fine_days):
                idx60 = to_index(uni60)
                uni60_path = os.path.join(args.data_dir, f'{args.market}_{topk}_60m.csv')
                idx60_path = os.path.join(args.data_dir, f'{args.market}_60m_index.csv')
                uni60.to_csv(uni60_path, index=False)
                idx60.to_csv(idx60_path, index=False)
            else:
                # Insufficient intraday coverage for the requested daily range; skip writing 60m files
                pass

    print('Saved:')
    print(uni_path)
    print(idx_path)
    return 0


if __name__ == '__main__':
    sys.exit(main())

