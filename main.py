import os
import time
import logging
from datetime import datetime, timezone
import ccxt
import numpy as np
import pandas as pd
import requests

TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
TIMEFRAME = "1m"
CANDLE_LIMIT = 150
MIN_SCORE = 80

logging.basicConfig(level=logging.INFO)

exchange = ccxt.binance({"enableRateLimit": True})

def send_telegram(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    try:
        requests.post(url, json={"chat_id": TELEGRAM_CHAT_ID, "text": message})
    except Exception as e:
        logging.error(e)

def indicators(df):
    close = df["close"]
    high = df["high"]
    low = df["low"]
    df["ema9"] = close.ewm(span=9).mean()
    df["ema21"] = close.ewm(span=21).mean()
    df["rsi"] = 100 - (100 / (1 + close.diff().clip(lower=0).ewm(14).mean() / (-close.diff().clip(upper=0).ewm(14).mean())))
    return df

def main():
    logging.info("Bot started")
    # ton code de trading ici - exemple simple
    try:
        ohlcv = exchange.fetch_ohlcv("BTC/USDT", TIMEFRAME, limit=CANDLE_LIMIT)
        df = pd.DataFrame(ohlcv, columns=["timestamp", "open", "high", "low", "close", "volume"])
        df = indicators(df)
        logging.info(f"Last close: {df['close'].iloc[-1]}")
        # send_telegram(f"Signal BTC: {df['close'].iloc[-1]}")
    except Exception as e:
        logging.error(e)

if __name__ == "__main__":
    main()
