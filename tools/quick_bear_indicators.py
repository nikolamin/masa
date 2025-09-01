#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import csv
import urllib.request
import io
from datetime import datetime, timedelta


def fetch_stooq_eurusd():
    # Stooq daily data for EURUSD - no API key required
    url = 'https://stooq.com/q/d/l/?s=eurusd&i=d'
    with urllib.request.urlopen(url, timeout=30) as resp:
        content = resp.read().decode('utf-8')
    return content


def parse_csv(content):
    f = io.StringIO(content)
    reader = csv.DictReader(f)
    rows = []
    for row in reader:
        try:
            date = datetime.strptime(row['Date'], '%Y-%m-%d')
            close = float(row['Close'])
            open_ = float(row['Open'])
            high = float(row['High'])
            low = float(row['Low'])
            rows.append({'date': date, 'open': open_, 'high': high, 'low': low, 'close': close})
        except Exception:
            continue
    rows.sort(key=lambda r: r['date'])
    return rows


def sma(values, window):
    out = [None] * len(values)
    s = 0.0
    for i, v in enumerate(values):
        s += v
        if i >= window:
            s -= values[i - window]
        if i >= window - 1:
            out[i] = s / window
    return out


def ema(values, span):
    out = [None] * len(values)
    k = 2.0 / (span + 1.0)
    ema_val = None
    for i, v in enumerate(values):
        if ema_val is None:
            ema_val = v
        else:
            ema_val = v * k + ema_val * (1 - k)
        out[i] = ema_val
    return out


def rsi(values, period=14):
    gains = [0.0]
    losses = [0.0]
    for i in range(1, len(values)):
        delta = values[i] - values[i - 1]
        gains.append(max(delta, 0.0))
        losses.append(max(-delta, 0.0))
    # Wilder's smoothing
    avg_gain = []
    avg_loss = []
    g = sum(gains[1:period + 1]) / period if len(gains) > period else 0.0
    l = sum(losses[1:period + 1]) / period if len(losses) > period else 0.0
    avg_gain = [None] * len(values)
    avg_loss = [None] * len(values)
    if len(values) > period:
        avg_gain[period] = g
        avg_loss[period] = l
        for i in range(period + 1, len(values)):
            g = (g * (period - 1) + gains[i]) / period
            l = (l * (period - 1) + losses[i]) / period
            avg_gain[i] = g
            avg_loss[i] = l
    rsi_vals = [None] * len(values)
    for i in range(len(values)):
        if avg_gain[i] is None or avg_loss[i] is None:
            rsi_vals[i] = None
        else:
            if avg_loss[i] == 0:
                rsi_vals[i] = 100.0
            else:
                rs = avg_gain[i] / avg_loss[i]
                rsi_vals[i] = 100.0 - (100.0 / (1.0 + rs))
    return rsi_vals


def macd(values, fast=12, slow=26, signal=9):
    ema_fast = ema(values, fast)
    ema_slow = ema(values, slow)
    macd_line = [None if (a is None or b is None) else (a - b) for a, b in zip(ema_fast, ema_slow)]
    # Build list without None for signal EMA computation, then align
    cleaned = [v for v in macd_line if v is not None]
    sig_clean = ema(cleaned, signal) if cleaned else []
    signal_line = [None] * len(values)
    # Align signal to macd_line length
    offset = len(macd_line) - len(sig_clean)
    for i in range(len(sig_clean)):
        signal_line[i + offset] = sig_clean[i]
    hist = [None if (m is None or s is None) else (m - s) for m, s in zip(macd_line, signal_line)]
    return macd_line, signal_line, hist


def summarize(rows):
    closes = [r['close'] for r in rows]
    dates = [r['date'] for r in rows]
    sma50 = sma(closes, 50)
    sma200 = sma(closes, 200)
    rsi14 = rsi(closes, 14)
    macd_line, signal_line, hist = macd(closes, 12, 26, 9)

    last_idx = len(closes) - 1
    last_close = closes[last_idx]
    last_sma50 = sma50[last_idx]
    last_sma200 = sma200[last_idx]
    last_rsi = rsi14[last_idx]
    last_macd = macd_line[last_idx]
    last_signal = signal_line[last_idx]
    last_hist = hist[last_idx]

    # Recent momentum
    lookback = 20
    if last_idx >= lookback:
        ret20 = (closes[last_idx] / closes[last_idx - lookback]) - 1.0
    else:
        ret20 = None

    # Bearish conditions
    cond_price_below_200 = (last_sma200 is not None) and (last_close < last_sma200)
    cond_sma50_below_200 = (last_sma50 is not None and last_sma200 is not None) and (last_sma50 < last_sma200)
    cond_macd_below_signal = (last_macd is not None and last_signal is not None) and (last_macd < last_signal)
    cond_macd_negative = (last_macd is not None) and (last_macd < 0)
    cond_rsi_below_50 = (last_rsi is not None) and (last_rsi < 50)

    # Probability proxy: share of last 30 days with close below SMA50 and MACD < 0
    window = 30
    bear_count = 0
    denom = 0
    for i in range(max(0, len(closes) - window), len(closes)):
        if sma50[i] is None or macd_line[i] is None:
            continue
        denom += 1
        if (closes[i] < sma50[i]) and (macd_line[i] < 0):
            bear_count += 1
    bear_share = (bear_count / denom) if denom > 0 else None

    out = {
        'date': dates[last_idx].strftime('%Y-%m-%d'),
        'close': last_close,
        'sma50': last_sma50,
        'sma200': last_sma200,
        'rsi14': last_rsi,
        'macd': last_macd,
        'macd_signal': last_signal,
        'macd_hist': last_hist,
        'ret20': ret20,
        'bear_price_below_200': cond_price_below_200,
        'bear_sma50_below_200': cond_sma50_below_200,
        'bear_macd_below_signal': cond_macd_below_signal,
        'bear_macd_negative': cond_macd_negative,
        'bear_rsi_below_50': cond_rsi_below_50,
        'bear_share_30d': bear_share,
    }
    return out


def main():
    try:
        csv_text = fetch_stooq_eurusd()
        rows = parse_csv(csv_text)
        # Keep last 3 years
        cutoff = datetime.now() - timedelta(days=3 * 365)
        rows = [r for r in rows if r['date'] >= cutoff]
        if len(rows) < 210:
            print('Not enough data to compute SMA200.')
            return 1
        summary = summarize(rows)
        print('EURUSD Daily Bearish Indicators (last close):')
        print(f"Date: {summary['date']}")
        print(f"Close: {summary['close']:.6f}")
        print(f"SMA50: {summary['sma50']:.6f} | SMA200: {summary['sma200']:.6f}")
        print(f"RSI14: {summary['rsi14']:.2f}")
        print(f"MACD: {summary['macd']:.6f} | Signal: {summary['macd_signal']:.6f} | Hist: {summary['macd_hist']:.6f}")
        if summary['ret20'] is not None:
            print(f"20D Return: {summary['ret20']*100:.2f}%")
        print('Bearish conditions:')
        print(f"- Price below SMA200: {summary['bear_price_below_200']}")
        print(f"- SMA50 below SMA200 (death-cross state): {summary['bear_sma50_below_200']}")
        print(f"- MACD below signal: {summary['bear_macd_below_signal']} (MACD<0: {summary['bear_macd_negative']})")
        print(f"- RSI<50: {summary['bear_rsi_below_50']}")
        if summary['bear_share_30d'] is not None:
            print(f"- Bear share last 30d (close<SMA50 and MACD<0): {summary['bear_share_30d']*100:.1f}%")
        return 0
    except Exception as e:
        print(f'Error: {e}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())

