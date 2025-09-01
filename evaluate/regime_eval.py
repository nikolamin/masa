#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import argparse
import pandas as pd
import numpy as np
from datetime import datetime


def moving_regime(close, fast=50, slow=200):
    sma_fast = close.rolling(fast).mean()
    sma_slow = close.rolling(slow).mean()
    # Bull when fast > slow, Bear when fast < slow
    regime = np.where(sma_fast > sma_slow, 1, np.where(sma_fast < sma_slow, -1, 0))
    return regime, sma_fast, sma_slow


def read_profile(res_dir, split='test'):
    prof_path = os.path.join(res_dir, f'{split}_profile.csv')
    if not os.path.exists(prof_path):
        raise FileNotFoundError(f'Missing {prof_path}')
    df = pd.read_csv(prof_path)
    return df


def main():
    parser = argparse.ArgumentParser(description='Evaluate bull/bear regime performance and plot candlesticks')
    parser.add_argument('--res_dir', type=str, required=True, help='Result directory (e.g., res/RLcontroller/TD3/CUSTOM-10/DATE)')
    parser.add_argument('--data_file', type=str, required=True, help='Universe CSV (e.g., data/CUSTOM_10_1d.csv)')
    parser.add_argument('--split', type=str, default='test', choices=['train', 'valid', 'test'])
    parser.add_argument('--out', type=str, default='evaluation')
    args = parser.parse_args()

    os.makedirs(args.out, exist_ok=True)
    prof = read_profile(args.res_dir, split=args.split)
    # Extract capital and date length
    capital = prof['final_capital'].values[-1]
    # Load data for regime detection
    df = pd.read_csv(args.data_file)
    df['date'] = pd.to_datetime(df['date'])
    pivot_close = df.pivot_table(index='date', columns='stock', values='close').sort_index()
    mkt_close = pivot_close.mean(axis=1)

    regime, sma50, sma200 = moving_regime(mkt_close)
    # Align with test length heuristically (last N days)
    N = len(prof['daily_return_lst'].iloc[-1].strip('[]').split(',')) if 'daily_return_lst' in prof.columns else len(mkt_close)

    regime_series = pd.Series(regime[-N:], index=mkt_close.index[-N:])
    returns_series = pd.Series(np.array(prof['daily_return_lst'].iloc[-1].strip('[]').split(','), dtype=float)) if 'daily_return_lst' in prof.columns else mkt_close.pct_change().fillna(0).iloc[-N:]

    bull_mask = (regime_series.values == 1)
    bear_mask = (regime_series.values == -1)
    bull_ret = (1 + returns_series[bull_mask]).prod() - 1 if bull_mask.any() else 0.0
    bear_ret = (1 + returns_series[bear_mask]).prod() - 1 if bear_mask.any() else 0.0

    print('Regime performance:')
    print(f'- Bull regime cumulative return: {bull_ret*100:.2f}%')
    print(f'- Bear regime cumulative return: {bear_ret*100:.2f}%')
    print(f'- Final capital: {capital:.2f}')

    # Optional: generate a simple candlestick-like CSV
    candle_df = df.groupby('date').agg({'open':'mean','high':'mean','low':'mean','close':'mean','volume':'sum'}).reset_index()
    candle_path = os.path.join(args.out, 'market_candles.csv')
    candle_df.to_csv(candle_path, index=False)
    print(f'Saved candlestick data: {candle_path}')

    # Try plotting candlestick with volume and MAs
    try:
        import mplfinance as mpf
        cdf = candle_df.copy()
        cdf = cdf.rename(columns={'date': 'Date', 'open': 'Open', 'high': 'High', 'low': 'Low', 'close': 'Close', 'volume': 'Volume'})
        cdf['Date'] = pd.to_datetime(cdf['Date'])
        cdf = cdf.set_index('Date')
        fig_path = os.path.join(args.out, 'market_candles.png')
        mpf.plot(cdf, type='candle', volume=True, style='yahoo', mav=(50, 200), savefig=fig_path)
        print(f'Saved candlestick chart: {fig_path}')
    except Exception as e:
        print(f'Candlestick plot skipped: {e}')
    return 0


if __name__ == '__main__':
    sys.exit(main())

