import os
import time
import logging
from datetime import datetime
import ccxt
import pandas as pd
import requests

TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

TIMEFRAME = "1m"
CANDLE_LIMIT = 150
MIN_SCORE = 75

# === TOUS LES ACTIFS POCKET OPTION ===
POCKET_ASSETS = [
    "EUR/USD", "EUR/USD OTC", "GBP/USD", "GBP/USD OTC",
    "USD/JPY", "USD/JPY OTC", "AUD/USD", "AUD/USD OTC",
    "USD/CAD", "USD/CAD OTC", "EUR/JPY", "EUR/GBP",
    "GBP/JPY", "GBP/JPY OTC", "EUR/CHF", "USD/CHF",
    "AUD/JPY", "AUD/JPY OTC", "NZD/USD", "EUR/AUD",
    "EUR/CAD", "GBP/AUD", "GBP/CAD", "CHF/JPY",
    "AUD/CAD", "AUD/CHF", "CAD/JPY", "CAD/CHF",
    "BTC/USD", "ETH/USD", "BTC/USD OTC"
]

SYMBOL_MAP = {
    "EUR/USD": "EUR/USDT", "EUR/USD OTC": "EUR/USDT",
    "GBP/USD": "GBP/USDT", "GBP/USD OTC": "GBP/USDT",
    "USD/JPY": "BTC/USDT", "USD/JPY OTC": "BTC/USDT",
    "AUD/USD": "AUD/USDT", "AUD/USD OTC": "AUD/USDT",
    "USD/CAD": "BTC/USDT", "USD/CAD OTC": "BTC/USDT",
    "EUR/JPY": "EUR/USDT", "EUR/GBP": "EUR/USDT",
    "GBP/JPY": "GBP/USDT", "GBP/JPY OTC": "GBP/USDT",
    "EUR/CHF": "EUR/USDT", "USD/CHF": "BTC/USDT",
    "AUD/JPY": "AUD/USDT", "AUD/JPY OTC": "AUD/USDT",
    "NZD/USD": "NZD/USDT", "EUR/AUD": "EUR/USDT",
    "EUR/CAD": "EUR/USDT", "GBP/AUD": "AUD/USDT",
    "GBP/CAD": "GBP/USDT", "CHF/JPY": "EUR/USDT",
    "AUD/CAD": "AUD/USDT", "AUD/CHF": "AUD/USDT",
    "CAD/JPY": "EUR/USDT", "CAD/CHF": "EUR/USDT",
    "BTC/USD": "BTC/USDT", "ETH/USD": "ETH/USDT",
    "BTC/USD OTC": "BTC/USDT"
}

logging.basicConfig(level=logging.INFO)
exchange = ccxt.binance({"enableRateLimit": True})

def send_telegram(msg):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        logging.warning("Secrets manquants")
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    try:
        requests.post(url, json={"chat_id": TELEGRAM_CHAT_ID, "text": msg, "parse_mode": "Markdown"}, timeout=15)
    except Exception as e:
        logging.error(e)

def calc_rsi(close, period=14):
    delta = close.diff()
    gain = delta.clip(lower=0).ewm(alpha=1/period, adjust=False).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1/period, adjust=False).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

def analyze(pocket_name):
    binance_symbol = SYMBOL_MAP.get(pocket_name, "BTC/USDT")
    try:
        ohlcv = exchange.fetch_ohlcv(binance_symbol, TIMEFRAME, limit=CANDLE_LIMIT)
        df = pd.DataFrame(ohlcv, columns=["timestamp", "open", "high", "low", "close", "volume"])
        df["ema9"] = df["close"].ewm(span=9).mean()
        df["ema21"] = df["close"].ewm(span=21).mean()
        df["ema50"] = df["close"].ewm(span=50).mean()
        df["rsi"] = calc_rsi(df["close"])
        last = df.iloc[-1]
        prev = df.iloc[-2]
        score = 0
        signal = None
        if last["ema9"] > last["ema21"] and prev["ema9"] <= prev["ema21"]:
            signal = "CALL"
            score += 40
        elif last["ema9"] < last["ema21"] and prev["ema9"] >= prev["ema21"]:
            signal = "PUT"
            score += 40
        if signal == "CALL" and 35 < last["rsi"] < 70:
            score += 20
        if signal == "PUT" and 30 < last["rsi"] < 65:
            score += 20
        if last["close"] > last["ema50"] and signal == "CALL":
            score += 15
        if last["close"] < last["ema50"] and signal == "PUT":
            score += 15
        if abs(last["ema9"] - last["ema21"]) / last["close"] > 0.0003:
            score += 10
        return signal, score, last["rsi"]
    except Exception as e:
        logging.error(f"{pocket_name}: {e}")
        return None, 0, 0

def main():
    now = datetime.now().strftime("%H:%M:%S")
    logging.info(f"SCAN {now} - {len(POCKET_ASSETS)} actifs")
    found = 0
    for asset in POCKET_ASSETS:
        sig, score, rsi = analyze(asset)
        if sig and score >= MIN_SCORE:
            emoji = "🟢" if sig == "CALL" else "🔴"
            msg = f"{emoji} *SIGNAL POCKET* {emoji}\n\nActif: `{asset}`\nSignal: *{sig}* {emoji}\nScore: {score}/100\nRSI: {round(float(rsi),1)}\nHeure: {now} UTC\n\nExp: 2 min - Confiance: {'HAUTE' if score>=85 else 'MOYENNE'}"
            send_telegram(msg)
            found += 1
        time.sleep(0.3)
    
    # Message de vie toutes les 4 heures seulement (si aucun signal)
    # Pour ne pas spammer, on l'envoie seulement si minute = 00
    if datetime.now().minute < 5 and found == 0:
        send_telegram(f"Bot en ligne {now} UTC - {len(POCKET_ASSETS)} actifs scannes - 0 signal fort, attente...")

if __name__ == "__main__":
    main()
