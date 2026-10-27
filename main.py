 import os
import time
import logging
from datetime import datetime, timezone
import ccxt
import numpy as np
import pandas as pd
import requests

TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
TIMEFRAME = "1m"
CANDLE_LIMIT = 150
MIN_SCORE = 80

logging.basicConfig(level=logging.INFO)

exchange = ccxt.binance({"enableRateLimit": True})

def send_telegram(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    try:
        requests.post(url, json={"chat_id": TELEGRAM_CHAT_ID, "text": message}, timeout=15)
    except Exception as e:
        logging.error(e)

def indicators(df):
    close = df["close"]; high = df["high"]; low = df["low"]
    df["ema9"] = close.ewm(span=9).mean()
    df["ema21"] = close.ewm(span=21).mean()
    df["ema50"] = close.ewm(span=50).mean()
    delta = close.diff()
    gain = delta.clip(lower=0); loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1/14).mean()
    avg_loss = loss.ewm(alpha=1/14).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    df["rsi"] = 100 - (100 / (1 + rs))
    tr = pd.concat([high - low, (high - close.shift(1)).abs(), (low - close.shift(1)).abs()], axis=1).max(axis=1)
    df["atr"] = tr.ewm(alpha=1/14).mean()
    return df

def analyze(symbol):
    try:
        candles = exchange.fetch_ohlcv(symbol, timeframe=TIMEFRAME, limit=CANDLE_LIMIT)
    except: return None
    if len(candles) < 100: return None
    df = pd.DataFrame(candles, columns=["timestamp","open","high","low","close","volume"])
    df = df.iloc[:-1].copy()
    df = indicators(df).dropna()
    cur = df.iloc[-1]
    if cur["close"] > cur["ema9"] > cur["ema21"]:
        side = "CALL 🟢"
        score = 85
    elif cur["close"] < cur["ema9"] < cur["ema21"]:
        side = "PUT 🔴"
        score = 85
    else:
        return None
    return {"symbol": symbol, "side": side, "score": score, "price": cur["close"], "rsi": cur["rsi"], "candle_ts": cur["timestamp"]}

def main():
    symbols = ['BTC/USDT','ETH/USDT','SOL/USDT','BNB/USDT','XRP/USDT','ADA/USDT','DOGE/USDT','SHIB/USDT','DOT/USDT','AVAX/USDT']
    for symbol in symbols:
        result = analyze(symbol)
        if result:
            candle_time = datetime.fromtimestamp(result["candle_ts"]/1000, tz=timezone.utc).strftime("%H:%M UTC")
            message = f"📊 SIGNAL TECHNIQUE — 1 MIN\n\nMarché : {result['symbol']}\nDirection : {result['side']}\nScore : {result['score']}/100\nPrix : {result['price']}\nRSI : {result['rsi']:.1f}\nBougie : {candle_time}"
            send_telegram(message)
            time.sleep(0.3)
    logging.info("Scan fini")

if __name__ == "__main__":
    main()
