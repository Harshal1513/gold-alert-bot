#!/usr/bin/env python3
"""
XAU/USD 5-min Supertrend + ADX Zone Alert Bot
-----------------------------------------------
Replicates the logic of the "Supertrend + ADX Zone Tag" Pine Script indicator
and sends a mobile push notification (Telegram and/or ntfy.sh) whenever a
LONG or SHORT signal fires on a closed 5-minute XAU/USD candle.

Data source : Twelve Data (free tier: 800 calls/day, 8 calls/min)
Notification: Telegram bot and/or ntfy.sh (both free)

Run this script on a schedule (cron) every 5 minutes, ~30-60 sec after each
5-min candle close (e.g. */5 * * * * with a short sleep, or 1,6,11,16... etc).

------------------------------------------------------------------------------
REQUIRED ENVIRONMENT VARIABLES
------------------------------------------------------------------------------
TWELVE_DATA_API_KEY     (required)  - from https://twelvedata.com/apikey
TELEGRAM_BOT_TOKEN      (optional)  - from @BotFather on Telegram
TELEGRAM_CHAT_ID        (optional)  - your numeric chat id
NTFY_TOPIC              (optional)  - any secret topic name, e.g. "xauusd-alerts-9f3k2"

Set at least one of (TELEGRAM_BOT_TOKEN + TELEGRAM_CHAT_ID) or NTFY_TOPIC.
------------------------------------------------------------------------------
"""

import os
import json
import sys
import requests
import pandas as pd
import numpy as np

# ================= SETTINGS (mirrors the Pine Script inputs) =================
SYMBOL = "XAU/USD"
INTERVAL = "5min"
OUTPUT_SIZE = 200          # candles fetched each run (plenty for indicator warmup)

ST_FACTOR = 3.0
ST_ATR_PERIOD = 10

ADX_LENGTH = 14
ADX_SMOOTHING = 14
ADX_MIN_FLOOR = 12
ADX_OVEREXTENDED = 35

COOLDOWN_BARS = 1

STATE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "state.json")

# ================= ENV VARS =================
TD_API_KEY = os.environ.get("TWELVE_DATA_API_KEY")
TG_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TG_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
NTFY_TOPIC = os.environ.get("NTFY_TOPIC")


def fail(msg):
    print(f"[ERROR] {msg}", file=sys.stderr)
    sys.exit(1)


# ================= DATA FETCH =================
def fetch_candles():
    url = "https://api.twelvedata.com/time_series"
    params = {
        "symbol": SYMBOL,
        "interval": INTERVAL,
        "outputsize": OUTPUT_SIZE,
        "apikey": TD_API_KEY,
        "order": "ASC",
        "timezone": "UTC",
    }
    r = requests.get(url, params=params, timeout=20)
    data = r.json()
    if "values" not in data:
        fail(f"Twelve Data error: {data}")

    df = pd.DataFrame(data["values"])
    df["datetime"] = pd.to_datetime(df["datetime"])
    for col in ["open", "high", "low", "close"]:
        df[col] = df[col].astype(float)
    df = df.sort_values("datetime").reset_index(drop=True)
    return df


# ================= INDICATOR MATH =================
def wilder_rma(series, period):
    """Wilder's smoothing (used by Pine's ta.atr / ta.rma / ta.dmi)."""
    return series.ewm(alpha=1 / period, adjust=False).mean()


def compute_atr(df, period):
    high, low, close = df["high"], df["low"], df["close"]
    prev_close = close.shift(1)
    tr = pd.concat([
        high - low,
        (high - prev_close).abs(),
        (low - prev_close).abs(),
    ], axis=1).max(axis=1)
    return wilder_rma(tr, period)


def compute_supertrend(df, factor, period):
    atr = compute_atr(df, period)
    hl2 = (df["high"] + df["low"]) / 2

    basic_upper = hl2 + factor * atr
    basic_lower = hl2 - factor * atr

    final_upper = basic_upper.copy()
    final_lower = basic_lower.copy()
    close = df["close"]

    for i in range(1, len(df)):
        if basic_upper.iloc[i] < final_upper.iloc[i - 1] or close.iloc[i - 1] > final_upper.iloc[i - 1]:
            final_upper.iloc[i] = basic_upper.iloc[i]
        else:
            final_upper.iloc[i] = final_upper.iloc[i - 1]

        if basic_lower.iloc[i] > final_lower.iloc[i - 1] or close.iloc[i - 1] < final_lower.iloc[i - 1]:
            final_lower.iloc[i] = basic_lower.iloc[i]
        else:
            final_lower.iloc[i] = final_lower.iloc[i - 1]

    supertrend = pd.Series(index=df.index, dtype=float)
    direction = pd.Series(index=df.index, dtype=int)

    supertrend.iloc[0] = final_upper.iloc[0]
    direction.iloc[0] = 1  # start as downtrend, arbitrary seed

    for i in range(1, len(df)):
        if supertrend.iloc[i - 1] == final_upper.iloc[i - 1]:
            if close.iloc[i] <= final_upper.iloc[i]:
                supertrend.iloc[i] = final_upper.iloc[i]
                direction.iloc[i] = 1
            else:
                supertrend.iloc[i] = final_lower.iloc[i]
                direction.iloc[i] = -1
        else:
            if close.iloc[i] >= final_lower.iloc[i]:
                supertrend.iloc[i] = final_lower.iloc[i]
                direction.iloc[i] = -1
            else:
                supertrend.iloc[i] = final_upper.iloc[i]
                direction.iloc[i] = 1

    return supertrend, direction


def compute_dmi_adx(df, length, smoothing):
    high, low, close = df["high"], df["low"], df["close"]
    up_move = high.diff()
    down_move = -low.diff()

    plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0.0)
    minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0.0)

    plus_dm = pd.Series(plus_dm, index=df.index)
    minus_dm = pd.Series(minus_dm, index=df.index)

    prev_close = close.shift(1)
    tr = pd.concat([
        high - low,
        (high - prev_close).abs(),
        (low - prev_close).abs(),
    ], axis=1).max(axis=1)

    atr = wilder_rma(tr, length)
    plus_di = 100 * wilder_rma(plus_dm, length) / atr
    minus_di = 100 * wilder_rma(minus_dm, length) / atr

    dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di)
    adx = wilder_rma(dx, smoothing)

    return plus_di, minus_di, adx


def adx_tag(adx_value, adx_rising):
    if adx_value < ADX_MIN_FLOOR:
        return "WEAK"
    elif adx_value > ADX_OVEREXTENDED:
        return "LATE"
    elif adx_rising:
        return "BEST"
    return "MID"


# ================= STATE (prevents duplicate alerts across cron runs) =================
def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE) as f:
            return json.load(f)
    return {"last_alerted_bar": None}


def save_state(state):
    with open(STATE_FILE, "w") as f:
        json.dump(state, f)


# ================= NOTIFICATIONS =================
def send_telegram(text):
    if not (TG_TOKEN and TG_CHAT_ID):
        return
    url = f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage"
    try:
        r = requests.post(url, data={"chat_id": TG_CHAT_ID, "text": text}, timeout=15)
        if not r.ok:
            print(f"[WARN] Telegram send failed: {r.text}")
    except Exception as e:
        print(f"[WARN] Telegram send exception: {e}")


def send_ntfy(text):
    if not NTFY_TOPIC:
        return
    url = f"https://ntfy.sh/{NTFY_TOPIC}"
    try:
        r = requests.post(url, data=text.encode("utf-8"), headers={"Title": "XAU/USD Signal"}, timeout=15)
        if not r.ok:
            print(f"[WARN] ntfy send failed: {r.text}")
    except Exception as e:
        print(f"[WARN] ntfy send exception: {e}")


def notify(text):
    print(text)
    send_telegram(text)
    send_ntfy(text)


# ================= MAIN =================
def main():
    if not TD_API_KEY:
        fail("TWELVE_DATA_API_KEY environment variable not set.")
    if not (TG_TOKEN and TG_CHAT_ID) and not NTFY_TOPIC:
        fail("Set TELEGRAM_BOT_TOKEN + TELEGRAM_CHAT_ID and/or NTFY_TOPIC.")

    df = fetch_candles()

    # Drop the very last row: it may still be an in-progress (unclosed) candle.
    # We evaluate signals on the last fully closed bar instead.
    if len(df) < 60:
        fail("Not enough candles returned to compute indicators reliably.")
    df = df.iloc[:-1].reset_index(drop=True)

    supertrend, direction = compute_supertrend(df, ST_FACTOR, ST_ATR_PERIOD)
    plus_di, minus_di, adx = compute_dmi_adx(df, ADX_LENGTH, ADX_SMOOTHING)

    df["direction"] = direction
    df["adx"] = adx

    i = len(df) - 1  # index of the latest CLOSED bar
    prev_dir = df["direction"].iloc[i - 1]
    curr_dir = df["direction"].iloc[i]

    bull_flip = curr_dir == -1 and prev_dir == 1
    bear_flip = curr_dir == 1 and prev_dir == -1

    bar_time = str(df["datetime"].iloc[i])
    state = load_state()

    cooldown_ok = True
    if state.get("last_alerted_bar") is not None:
        last_ts = pd.to_datetime(state["last_alerted_bar"])
        bars_since = (df["datetime"].iloc[i] - last_ts) / pd.Timedelta(minutes=5)
        cooldown_ok = bars_since >= COOLDOWN_BARS

    if (bull_flip or bear_flip) and cooldown_ok and state.get("last_alerted_bar") != bar_time:
        adx_value = df["adx"].iloc[i]
        adx_rising = df["adx"].iloc[i] > df["adx"].iloc[i - 2] if i >= 2 else False
        tag = adx_tag(adx_value, adx_rising)
        price = df["close"].iloc[i]

        side = "LONG 🟢" if bull_flip else "SHORT 🔴"
        msg = (
            f"XAU/USD 5m {side}\n"
            f"Time (UTC): {bar_time}\n"
            f"Price: {price:.2f}\n"
            f"ADX: {adx_value:.1f} [{tag}]"
        )
        notify(msg)

        state["last_alerted_bar"] = bar_time
        save_state(state)
    else:
        print(f"No new signal. Bar {bar_time} | dir={curr_dir} | adx={df['adx'].iloc[i]:.1f}")


if __name__ == "__main__":
    main()
