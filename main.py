import os
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

# TOUS LES ACTIFS POCKET OPTION
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

# Mapping vers Binance car Binance n'a pas l'OTC
SYMBOL_MAP = {
    "EUR/USD": "EUR/USDT", "EUR/USD OTC": "EUR/USDT",
    "GBP/USD": "GBP/USDT", "GBP/USD OTC": "GBP/USDT",
    "USD/JPY": "JPY/USDT", "USD/JPY OTC": "JPY/USDT",
    "AUD/USD": "AUD/USDT", "AUD/USD OTC": "AUD/USDT",
    "USD/CAD": "CAD/USDT", "USD/CAD OTC": "CAD/USDT",
    "EUR/JPY": "EUR/JPY", "EUR/GBP": "EUR/GBP",
    "GBP/JPY": "GBP/JPY", "GBP/JPY OTC": "GBP/JPY",
    "EUR/CHF": "EUR/CHF", "USD/CHF": "CHF/USDT",
    "AUD/JPY": "AUD/JPY", "AUD/JPY OTC": "AUD/JPY",
    "NZD/USD": "NZD/USDT", "EUR/AUD": "EUR/AUD",
    "EUR/CAD": "EUR/CAD", "GBP/AUD": "GBP/AUD",
    "GBP/CAD": "GBP/CAD", "CHF/JPY": "CHF/JPY",
    "AUD/CAD": "AUD/CAD", "AUD/CHF": "AUD/CHF",
    "CAD/JPY": "CAD/JPY", "CAD/CHF": "CAD/CHF",
    "BTC/USD": "BTC/USDT", "ETH/USD": "ETH/USDT",
    "BTC/USD OTC": "BTC/USDT"
}

logging.basicConfig(level=logging.INFO)
exchange = ccxt.binance({"enableRateLimit": True})

def send_telegram(msg):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        logging.warning("Secrets missing")
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
        try:
            ohlcv = exchange.fetch_ohlcv(binance_symbol, TIMEFRAME, limit=CANDLE_LIMIT)
        except:
            ohlcv = exchange.fetch_ohlcv("BTC/USDT", TIMEFRAME, limit=CANDLE_LIMIT)
        
        df = pd.DataFrame(ohlcv, columns=["timestamp", "open", "high", "low", "close", "volume"])
        df["ema9"] = df["close"].ewm(span=9).mean()
        df["ema21"] = df["close"].ewm(span=21).mean()
        df["ema50"] = df["close"].ewm(span=50).mean()
        df["rsi"] = calc_rsi(df["close"])

        last = df.iloc[-1]
        prev = df.iloc[-2]

        score = 0
        signal = None

        # CROSS EMA9/21
        if last["ema9"] > last["ema21"] and prev["ema9"] <= prev["ema21"]:
            signal = "CALL"
            score += 40
        elif last["ema9"] < last["ema21"] and prev["ema9"] >= prev["ema21"]:
            signal = "PUT"
            score += 40

        # FILTRES PUISSANTS
        if signal == "CALL" and last["rsi"] < 70 and last["rsi"] > 35:
            score += 20
        if signal == "PUT" and last["rsi"] > 30 and last["rsi"] < 65:
            score += 20
        if last["close"] > last["ema50"] and signal == "CALL":
            score += 15
        if last["close"] < last["ema50"] and signal == "PUT":
            score += 15
        if abs(last["ema9"] - last["ema21"]) / last["close"] > 0.0003:
            score += 10

        return signal, score, last["close"], last["rsi"]
    except Exception as e:
        logging.error(f"{pocket_name}: {e}")
        return None, 0, 0, 0

def main():
    now = datetime.now().strftime("%H:%M:%S")
    logging.info(f"=== SCAN ALL {now} ===")
    found = 0
    for asset in POCKET_ASSETS:
        sig, score, price, rsi = analyze(asset)
        if sig and score >= MIN_SCORE:
            emoji = "🟢" if sig == "CALL" else "🔴"
            msg = f"{emoji} *SIGNAL POCKET* {emoji}\n\nActif: {asset}\nSignal: {sig} {emoji}\nScore: {score}/100\nRSI: {round(float(rsi),1)}\nHeure: {now} UTC\n\n⏱️ Expiration: 2 min\n📊 Confiance: {'HAUTE' if score>=85 else 'MOYENNE'}"
            send_telegram(msg)
            logging.info(f"ALERT {asset} {sig} {score}")
            found += 1
        time_sleep = 0.3
        import time
        time.sleep(time_sleep)
    
    if found == 0:
        logging.info("Aucun signal >75, attente prochain scan")
        # Optionnel: envoie un message toutes les heures pour dire que le bot vit
        # send_telegram(f"Bot OK {now} - 0 signal sur 31 actifs scannés")

if __name__ == "__main__":
    main()
