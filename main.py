
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
╔══════════════════════════════════════════════════════════════════╗
║         AlphaBot Signal v11.4 — by leaderOdg                   ║
║  ⚡ Scan LIVE 3s | Entrée M1 | Tendance M15                    ║
║  📊 ICT/SMC | RR 1:3-5 | BTC + GOLD + 7 FOREX                 ║
║  🚫 Session Asiatique bloquée (00:00–07:00 UTC)                ║
║  📣 Multi-diffusion Telegram (plusieurs comptes/canaux)        ║
║  📋 Tracking TP/SL | Rapport quotidien 22h UTC                 ║
║  💾 Persistance JSON | Logs fichier | VPS-stable               ║
╚══════════════════════════════════════════════════════════════════╝

CHANGELOG v11.4 vs v11.3:
  - [FIX] Cache M15 (refresh toutes les 15 min) → moins d'appels Yahoo
  - [FIX] Log fichier alphabot.log (+ rotation 5 Mo) → logs persistants
  - [FIX] Handler SIGTERM/SIGINT → arrêt propre sur VPS
  - [NEW] Tracking signaux dans alphabot_signals.json (persistant)
  - [NEW] Monitoring TP/SL en temps réel (thread dédié, toutes les 60s)
  - [NEW] Notifications Telegram TP1/TP2/TP3/SL touchés
  - [NEW] Rapport quotidien automatique à 22h00 UTC
  - [NEW] Rapport hebdomadaire automatique dimanche 22h00 UTC
  - [NEW] Heartbeat Telegram toutes les 6h (preuve de vie)
  - [NEW] Test Telegram au démarrage
"""

import time
import json
import logging
import logging.handlers
import ssl
import hashlib
import hmac
import urllib.request
import urllib.parse
import signal
import threading
import os
from datetime import datetime, timezone, timedelta

# ════════════════════════════════════════════════════
#  CONFIGURATION
# ════════════════════════════════════════════════════

BOT_TOKEN          = "8665812395:AAFO4BMTIrBCQJYVL8UytO028TcB1sDfgbI"
BINANCE_API_KEY    = "VOTRE_API_KEY"
BINANCE_API_SECRET = "VOTRE_API_SECRET"
LIVE_TRADING       = False
RISK_PER_TRADE_PCT = 1.0
USE_LEVERAGE       = 10
MIN_SCORE_LIVE     = 65
POLL_INTERVAL_SEC  = 3
CANDLE_LIMIT       = 150
HTF_LIMIT          = 100
MIN_RR             = 3.0
TARGET_RR          = 4.0
MAX_RR             = 5.0
SIGNAL_COOLDOWN    = 300

# Fichiers persistants
SIGNALS_FILE       = "alphabot_signals.json"
LOG_FILE           = "alphabot.log"

# Timing rapports (heure UTC)
DAILY_REPORT_HOUR  = 22   # Rapport quotidien à 22h UTC
HEARTBEAT_EVERY_H  = 6    # Heartbeat toutes les 6h

# ─────────────────────────────────────────────────────
#  DESTINATAIRES TELEGRAM
# ─────────────────────────────────────────────────────
CHAT_IDS = [
    "-1002335466840",
    # "-1001234567890",
    # "123456789",
    # "@mon_canal_vip",
]

# ════════════════════════════════════════════════════
#  MARCHÉS : BTC + GOLD + 7 PAIRES FOREX
# ════════════════════════════════════════════════════
ALL_MARKETS = [
    {"symbol": "BTCUSDT",  "label": "BTC/USDT",         "pip": 0.1,    "priority": 1, "source": "binance", "min_score": 55, "category": "Crypto"},
    {"symbol": "XAUUSD",   "label": "XAU/USD (Gold)",    "pip": 0.01,   "priority": 2, "source": "yahoo",   "yahoo_sym": "GC=F",       "min_score": 45, "category": "Commodité"},
    {"symbol": "EURUSD",   "label": "EUR/USD",           "pip": 0.0001, "priority": 3, "source": "yahoo",   "yahoo_sym": "EURUSD=X",   "min_score": 45, "category": "Forex"},
    {"symbol": "GBPUSD",   "label": "GBP/USD",           "pip": 0.0001, "priority": 4, "source": "yahoo",   "yahoo_sym": "GBPUSD=X",   "min_score": 45, "category": "Forex"},
    {"symbol": "USDJPY",   "label": "USD/JPY",           "pip": 0.01,   "priority": 5, "source": "yahoo",   "yahoo_sym": "USDJPY=X",   "min_score": 45, "category": "Forex"},
    {"symbol": "USDCHF",   "label": "USD/CHF",           "pip": 0.0001, "priority": 6, "source": "yahoo",   "yahoo_sym": "USDCHF=X",   "min_score": 45, "category": "Forex"},
    {"symbol": "AUDUSD",   "label": "AUD/USD",           "pip": 0.0001, "priority": 7, "source": "yahoo",   "yahoo_sym": "AUDUSD=X",   "min_score": 45, "category": "Forex"},
    {"symbol": "USDCAD",   "label": "USD/CAD",           "pip": 0.0001, "priority": 8, "source": "yahoo",   "yahoo_sym": "USDCAD=X",   "min_score": 45, "category": "Forex"},
    {"symbol": "NZDUSD",   "label": "NZD/USD",           "pip": 0.0001, "priority": 9, "source": "yahoo",   "yahoo_sym": "NZDUSD=X",   "min_score": 45, "category": "Forex"},
]

WEEKEND_MARKETS = [m for m in ALL_MARKETS if m["category"] != "Forex"]

# Lookup rapide symbol → market
MARKET_BY_SYMBOL = {m["symbol"]: m for m in ALL_MARKETS}

# ════════════════════════════════════════════════════
#  LOGGING — Console + Fichier rotatif
# ════════════════════════════════════════════════════

def setup_logging():
    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
    root = logging.getLogger("AlphaBot")
    root.setLevel(logging.INFO)
    # Console
    ch = logging.StreamHandler()
    ch.setFormatter(fmt)
    root.addHandler(ch)
    # Fichier rotatif (5 Mo max, 3 backups)
    fh = logging.handlers.RotatingFileHandler(LOG_FILE, maxBytes=5*1024*1024, backupCount=3, encoding="utf-8")
    fh.setFormatter(fmt)
    root.addHandler(fh)
    return root

log = setup_logging()

# ════════════════════════════════════════════════════
#  SSL
# ════════════════════════════════════════════════════

ssl_ctx = ssl.create_default_context()
ssl_ctx.check_hostname = False
ssl_ctx.verify_mode    = ssl.CERT_NONE

# ════════════════════════════════════════════════════
#  ÉTAT GLOBAL
# ════════════════════════════════════════════════════

last_signal_time = {}
signal_count     = 0
symbol_state     = {}
_shutdown        = threading.Event()

# Cache M15 : symbol → {"trend": str, "ts": float}
_m15_cache = {}
M15_CACHE_TTL = 900  # 15 minutes en secondes

# Tracking rapports déjà envoyés
_last_daily_report_day  = None
_last_weekly_report_week = None
_last_heartbeat_h       = None

# Lock pour accès concurrent aux fichiers
_file_lock = threading.Lock()

# ════════════════════════════════════════════════════
#  SESSIONS
# ════════════════════════════════════════════════════

def is_asian_session():
    return 0 <= datetime.now(timezone.utc).hour < 7

def session_name():
    h = datetime.now(timezone.utc).hour
    if 0  <= h < 7:  return "🌏 Asie (bloqué)"
    if 7  <= h < 13: return "🇬🇧 Londres"
    if 13 <= h < 17: return "🇺🇸 New York"
    return "🔀 Overlap NY/Asia"

def is_weekend():
    return datetime.now(timezone.utc).weekday() >= 5

def active_markets():
    return WEEKEND_MARKETS if is_weekend() else ALL_MARKETS

# ════════════════════════════════════════════════════
#  FETCH BINANCE (BTC)
# ════════════════════════════════════════════════════

def _binance_klines(symbol, interval, limit):
    url = (f"https://fapi.binance.com/fapi/v1/klines"
           f"?symbol={symbol}&interval={interval}&limit={limit+1}")
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "AlphaBot/11"})
        with urllib.request.urlopen(req, context=ssl_ctx, timeout=8) as r:
            data = json.loads(r.read())
        candles = [{"t": int(c[0])//1000, "o": float(c[1]),
                    "h": float(c[2]), "l": float(c[3]),
                    "c": float(c[4]), "v": float(c[5])} for c in data]
        return candles[:-1]
    except Exception as e:
        log.warning(f"[{symbol}] binance_klines({interval}): {e}")
        return []

def fetch_m1_binance(symbol):
    return _binance_klines(symbol, "1m", CANDLE_LIMIT)

def fetch_m15_binance(symbol):
    return _binance_klines(symbol, "15m", HTF_LIMIT)

def fetch_live_price_binance(symbol):
    url = f"https://fapi.binance.com/fapi/v1/ticker/price?symbol={symbol}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "AlphaBot/11"})
        with urllib.request.urlopen(req, context=ssl_ctx, timeout=4) as r:
            return float(json.loads(r.read())["price"])
    except Exception as e:
        log.warning(f"[{symbol}] live_price_binance: {e}")
        return None

# ════════════════════════════════════════════════════
#  FETCH YAHOO FINANCE (Gold + Forex)
# ════════════════════════════════════════════════════

def _yahoo_klines(yahoo_sym, interval, range_str):
    encoded = urllib.parse.quote(yahoo_sym, safe="")
    url = (f"https://query1.finance.yahoo.com/v8/finance/chart/"
           f"{encoded}?interval={interval}&range={range_str}")
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (AlphaBot/11)"})
        with urllib.request.urlopen(req, context=ssl_ctx, timeout=10) as r:
            data = json.loads(r.read())
        result = data["chart"]["result"][0]
        ts = result["timestamp"]
        q  = result["indicators"]["quote"][0]
        vols = q.get("volume", [None]*len(ts))
        candles = []
        for i in range(len(ts)):
            o, h, l, c = q["open"][i], q["high"][i], q["low"][i], q["close"][i]
            if None in (o, h, l, c):
                continue
            v = vols[i] if vols[i] is not None else 1.0
            candles.append({"t": ts[i], "o": o, "h": h, "l": l,
                            "c": c, "v": float(v)})
        return candles[:-1]
    except Exception as e:
        log.warning(f"[{yahoo_sym}] yahoo_klines({interval}): {e}")
        return []

def fetch_m1_yahoo(yahoo_sym):
    return _yahoo_klines(yahoo_sym, "1m", "1d")

def fetch_m15_yahoo(yahoo_sym):
    return _yahoo_klines(yahoo_sym, "15m", "5d")

def fetch_live_price_yahoo(yahoo_sym):
    encoded = urllib.parse.quote(yahoo_sym, safe="")
    url = (f"https://query1.finance.yahoo.com/v8/finance/chart/"
           f"{encoded}?interval=1m&range=1d")
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (AlphaBot/11)"})
        with urllib.request.urlopen(req, context=ssl_ctx, timeout=6) as r:
            data = json.loads(r.read())
        meta  = data["chart"]["result"][0]["meta"]
        price = meta.get("regularMarketPrice") or meta.get("previousClose")
        return float(price) if price else None
    except Exception as e:
        log.warning(f"[{yahoo_sym}] live_price_yahoo: {e}")
        return None

# ════════════════════════════════════════════════════
#  ROUTER
# ════════════════════════════════════════════════════

def fetch_m1(market):
    if market["source"] == "binance":
        return fetch_m1_binance(market["symbol"])
    return fetch_m1_yahoo(market["yahoo_sym"])

def fetch_m15(market):
    if market["source"] == "binance":
        return fetch_m15_binance(market["symbol"])
    return fetch_m15_yahoo(market["yahoo_sym"])

def fetch_live_price(market):
    if market["source"] == "binance":
        return fetch_live_price_binance(market["symbol"])
    return fetch_live_price_yahoo(market["yahoo_sym"])

# ════════════════════════════════════════════════════
#  [NEW] CACHE M15 — évite de recharger à chaque M1
# ════════════════════════════════════════════════════

def htf_trend_cached(market):
    """Tendance M15 avec cache de 15 min. Réduit drastiquement les appels Yahoo."""
    symbol = market["symbol"]
    now    = time.time()
    cached = _m15_cache.get(symbol)
    if cached and (now - cached["ts"]) < M15_CACHE_TTL:
        return cached["trend"]
    # Refresh
    candles = fetch_m15(market)
    if not candles or len(candles) < 12:
        trend = "ranging"
    else:
        sh, sl = find_swings(candles, lb=3)
        trend  = market_structure(sh, sl)
    _m15_cache[symbol] = {"trend": trend, "ts": now}
    return trend

# ════════════════════════════════════════════════════
#  ANALYSE TECHNIQUE
# ════════════════════════════════════════════════════

def find_swings(candles, lb=5):
    n = len(candles)
    sh, sl = [], []
    for i in range(lb, n - lb):
        win_h = [candles[j]["h"] for j in range(i-lb, i+lb+1)]
        win_l = [candles[j]["l"] for j in range(i-lb, i+lb+1)]
        if candles[i]["h"] == max(win_h):
            sh.append({"idx": i, "price": candles[i]["h"]})
        if candles[i]["l"] == min(win_l):
            sl.append({"idx": i, "price": candles[i]["l"]})
    return sh, sl

def market_structure(sh, sl):
    if len(sh) < 2 or len(sl) < 2:
        return "ranging"
    if sh[-1]["price"] > sh[-2]["price"] and sl[-1]["price"] > sl[-2]["price"]:
        return "bullish"
    if sh[-1]["price"] < sh[-2]["price"] and sl[-1]["price"] < sl[-2]["price"]:
        return "bearish"
    return "ranging"

def calc_atr(candles, period=14):
    if len(candles) < period + 1:
        return 0
    trs = [max(candles[i]["h"]-candles[i]["l"],
               abs(candles[i]["h"]-candles[i-1]["c"]),
               abs(candles[i]["l"]-candles[i-1]["c"]))
           for i in range(1, len(candles))]
    return sum(trs[-period:]) / period

# ════════════════════════════════════════════════════
#  PATTERNS ICT/SMC
# ════════════════════════════════════════════════════

def check_double_top(candles, sh, sl, close):
    if len(sh) < 2: return None
    n = len(candles)
    h1, h2 = sh[-2], sh[-1]
    if h1["idx"] < n-60 or h2["idx"] < n-20: return None
    if abs(h1["price"]-h2["price"])/h1["price"] > 0.0008: return None
    midlows = [s for s in sl if h1["idx"] < s["idx"] < h2["idx"]]
    if not midlows: return None
    neck = min(midlows, key=lambda x: x["price"])["price"]
    if close < neck:
        return {"direction": "SELL", "score_extra": 4,
                "reason": f"Double Top @ {round(max(h1['price'],h2['price']),5)} | Neck {round(neck,5)} ✅"}
    return None

def check_double_bottom(candles, sh, sl, close):
    if len(sl) < 2: return None
    n = len(candles)
    l1, l2 = sl[-2], sl[-1]
    if l1["idx"] < n-60 or l2["idx"] < n-20: return None
    if abs(l1["price"]-l2["price"])/l1["price"] > 0.0008: return None
    midhighs = [s for s in sh if l1["idx"] < s["idx"] < l2["idx"]]
    if not midhighs: return None
    neck = max(midhighs, key=lambda x: x["price"])["price"]
    if close > neck:
        return {"direction": "BUY", "score_extra": 4,
                "reason": f"Double Bottom @ {round(min(l1['price'],l2['price']),5)} | Neck {round(neck,5)} ✅"}
    return None

def check_choch(candles, sh, sl, trend, close):
    if trend == "bullish" and len(sl) >= 2:
        lvl = sl[-2]["price"]
        if close < lvl:
            return {"direction": "SELL", "score_extra": 3,
                    "reason": f"CHoCH baissier — close {round(close,5)} < HL {round(lvl,5)} ✅"}
    if trend == "bearish" and len(sh) >= 2:
        lvl = sh[-2]["price"]
        if close > lvl:
            return {"direction": "BUY", "score_extra": 3,
                    "reason": f"CHoCH haussier — close {round(close,5)} > LH {round(lvl,5)} ✅"}
    return None

def check_bos(sh, sl, trend, close):
    if trend == "bullish" and sh:
        lvl = sh[-1]["price"]
        if close > lvl:
            return {"direction": "BUY", "score_extra": 3,
                    "reason": f"BOS haussier @ {round(lvl,5)} ✅"}
    if trend == "bearish" and sl:
        lvl = sl[-1]["price"]
        if close < lvl:
            return {"direction": "SELL", "score_extra": 3,
                    "reason": f"BOS baissier @ {round(lvl,5)} ✅"}
    return None

def check_order_block(candles, direction, close, atr):
    window = candles[-40:]
    for i in range(1, len(window)-4):
        c = window[i]
        if direction == "SELL" and c["c"] > c["o"]:
            fut = [window[j]["l"] for j in range(i+1, min(i+5, len(window)))]
            if fut and min(fut) < c["l"] - atr:
                if c["l"] <= close <= c["h"]:
                    return {"score_extra": 3,
                            "reason": f"OB bearish [{round(c['l'],5)}-{round(c['h'],5)}] ✅"}
        if direction == "BUY" and c["c"] < c["o"]:
            fut = [window[j]["h"] for j in range(i+1, min(i+5, len(window)))]
            if fut and max(fut) > c["h"] + atr:
                if c["l"] <= close <= c["h"]:
                    return {"score_extra": 3,
                            "reason": f"OB bullish [{round(c['l'],5)}-{round(c['h'],5)}] ✅"}
    return None

def check_fvg(candles, close):
    for i in range(2, len(candles[-30:])):
        w = candles[-30:]
        c0, c2 = w[i-2], w[i]
        gb = c2["l"] - c0["h"]
        gs = c0["l"] - c2["h"]
        if gb > 0 and c0["h"] <= close <= c2["l"]:
            return {"direction": "BUY", "score_extra": 3,
                    "reason": f"FVG bullish [{round(c0['h'],5)}-{round(c2['l'],5)}] ✅"}
        if gs > 0 and c2["h"] <= close <= c0["l"]:
            return {"direction": "SELL", "score_extra": 3,
                    "reason": f"FVG bearish [{round(c2['h'],5)}-{round(c0['l'],5)}] ✅"}
    return None

def check_liquidity_sweep(candles, sh, sl):
    if len(candles) < 3: return None
    p, c = candles[-2], candles[-1]
    if sl:
        lvl = sl[-1]["price"]
        if p["l"] < lvl and c["c"] > lvl:
            return {"direction": "BUY", "score_extra": 4,
                    "reason": f"Liq Sweep BUY @ {round(lvl,5)} ✅"}
    if sh:
        lvl = sh[-1]["price"]
        if p["h"] > lvl and c["c"] < lvl:
            return {"direction": "SELL", "score_extra": 4,
                    "reason": f"Liq Sweep SELL @ {round(lvl,5)} ✅"}
    return None

def check_breaker_block(candles, trend, close, atr):
    window = candles[-50:]
    demand, supply = [], []
    for i in range(1, len(window)-2):
        c, nxt = window[i], window[i+1]
        rng = c["h"] - c["l"]
        if rng == 0: continue
        nb = abs(nxt["c"]-nxt["o"])
        if c["c"] < c["o"] and nxt["c"] > nxt["o"] and nb > rng*1.5:
            demand.append({"top": c["h"], "bot": c["l"]})
        if c["c"] > c["o"] and nxt["c"] < nxt["o"] and nb > rng*1.5:
            supply.append({"top": c["h"], "bot": c["l"]})
    if trend == "bearish":
        for z in reversed(supply):
            if z["bot"]*0.993 < close < z["bot"]*1.001:
                return {"direction": "SELL", "score_extra": 4,
                        "reason": f"Breaker Block SELL [{round(z['bot'],5)}-{round(z['top'],5)}] ✅"}
    if trend == "bullish":
        for z in reversed(demand):
            if z["top"]*0.999 < close < z["top"]*1.007:
                return {"direction": "BUY", "score_extra": 4,
                        "reason": f"Breaker Block BUY [{round(z['bot'],5)}-{round(z['top'],5)}] ✅"}
    return None

def check_hh_failed(candles, sh, sl, close):
    if len(sh) < 3 or not sl: return None
    if sh[-1]["price"] < sh[-2]["price"]:
        hl = sl[-1]["price"]
        if close < hl:
            return {"direction": "SELL", "score_extra": 4,
                    "reason": (f"HH Failed {round(sh[-2]['price'],5)}"
                               f"→{round(sh[-1]['price'],5)} | HL cassé ✅")}
    return None

def check_fakeout(candles, sh, sl, close):
    if len(candles) < 3: return None
    spike, conf = candles[-2], candles[-1]
    if sl:
        lvl = sl[-1]["price"]
        if spike["l"] < lvl and conf["c"] > lvl:
            return {"direction": "BUY", "score_extra": 3,
                    "reason": f"Fakeout BUY @ {round(lvl,5)} ✅"}
    if sh:
        lvl = sh[-1]["price"]
        if spike["h"] > lvl and conf["c"] < lvl:
            return {"direction": "SELL", "score_extra": 3,
                    "reason": f"Fakeout SELL @ {round(lvl,5)} ✅"}
    return None

def check_fib(sh, sl, close, direction):
    if direction == "BUY" and sh and sl:
        lo, hi = sl[-1]["price"], sh[-1]["price"]
        if hi <= lo: return None
        f5, f6 = hi-(hi-lo)*0.5, hi-(hi-lo)*0.618
        if f6 <= close <= f5:
            return {"score_extra": 2,
                    "reason": f"Fib 0.5-0.618 [{round(f6,5)}-{round(f5,5)}] ✅"}
    if direction == "SELL" and sh and sl:
        lo, hi = sl[-1]["price"], sh[-1]["price"]
        if lo >= hi: return None
        f5, f6 = lo+(hi-lo)*0.5, lo+(hi-lo)*0.618
        if f5 <= close <= f6:
            return {"score_extra": 2,
                    "reason": f"Fib 0.5-0.618 [{round(f5,5)}-{round(f6,5)}] ✅"}
    return None

# ════════════════════════════════════════════════════
#  CONSTRUCTION SIGNAL
# ════════════════════════════════════════════════════

def build_signal(direction, close, atr, setup, confirmations, base):
    sl_d = max(atr * 1.8, close * 0.003)
    if sl_d == 0: return None
    if direction == "SELL":
        sl  = close + sl_d
        tp1 = close - sl_d * MIN_RR
        tp2 = close - sl_d * TARGET_RR
        tp3 = close - sl_d * MAX_RR
    else:
        sl  = close - sl_d
        tp1 = close + sl_d * MIN_RR
        tp2 = close + sl_d * TARGET_RR
        tp3 = close + sl_d * MAX_RR
    score  = min(base + sum(c.get("score_extra", 0) for c in confirmations), 10)
    reason = "\n  ✦ ".join(c["reason"] for c in confirmations if "reason" in c)
    return {"direction": direction, "setup": setup,
            "entry": round(close, 6), "sl": round(sl, 6),
            "tp1": round(tp1, 6), "tp2": round(tp2, 6), "tp3": round(tp3, 6),
            "rr": round(TARGET_RR, 1), "score": score,
            "reason": "  ✦ " + reason, "atr": round(atr, 6)}

# ════════════════════════════════════════════════════
#  MOTEUR SETUPS (sur M1 fermée)
# ════════════════════════════════════════════════════

def evaluate(candles, is_yahoo=False):
    if len(candles) < 40: return []
    close = candles[-1]["c"]
    atr   = calc_atr(candles)
    if atr == 0: return []

    c    = candles[-1]
    body = abs(c["c"] - c["o"])
    rng  = c["h"] - c["l"]
    if rng > 0 and body/rng < 0.15: return []

    if not is_yahoo:
        vols = [x["v"] for x in candles[-20:] if x["v"] > 0]
        if vols and candles[-1]["v"] < (sum(vols)/len(vols)) * 0.4:
            return []

    sh, sl = find_swings(candles)
    trend  = market_structure(sh, sl)
    sigs   = []

    dt = check_double_top(candles, sh, sl, close)
    if dt:
        confs = [dt]
        for extra in [check_choch(candles, sh, sl, trend, close),
                      check_order_block(candles, "SELL", close, atr),
                      check_fib(sh, sl, close, "SELL")]:
            if extra: confs.append(extra)
        s = build_signal("SELL", close, atr, "Double Top", confs, 5)
        if s: sigs.append(s)

    db = check_double_bottom(candles, sh, sl, close)
    if db:
        confs = [db]
        for extra in [check_choch(candles, sh, sl, trend, close),
                      check_order_block(candles, "BUY", close, atr),
                      check_fib(sh, sl, close, "BUY")]:
            if extra: confs.append(extra)
        s = build_signal("BUY", close, atr, "Double Bottom", confs, 5)
        if s: sigs.append(s)

    choch = check_choch(candles, sh, sl, trend, close)
    if choch:
        d  = choch["direction"]
        ob = check_order_block(candles, d, close, atr)
        if ob:
            confs = [choch, ob]
            f = check_fib(sh, sl, close, d)
            if f: confs.append(f)
            s = build_signal(d, close, atr, "CHoCH + OB", confs, 5)
            if s: sigs.append(s)

    bos = check_bos(sh, sl, trend, close)
    fvg = check_fvg(candles, close)
    if bos and fvg and bos["direction"] == fvg["direction"]:
        confs = [bos, fvg]
        ob = check_order_block(candles, bos["direction"], close, atr)
        if ob: confs.append(ob)
        s = build_signal(bos["direction"], close, atr, "BOS + FVG", confs, 5)
        if s: sigs.append(s)

    sw = check_liquidity_sweep(candles, sh, sl)
    bb_res = check_breaker_block(candles, trend, close, atr)
    if sw and bb_res and sw["direction"] == bb_res["direction"]:
        confs = [sw, bb_res]
        f = check_fib(sh, sl, close, sw["direction"])
        if f: confs.append(f)
        s = build_signal(sw["direction"], close, atr, "Liq Sweep + BB", confs, 6)
        if s: sigs.append(s)

    hh = check_hh_failed(candles, sh, sl, close)
    if hh:
        confs = [hh]
        ob = check_order_block(candles, "SELL", close, atr)
        if ob: confs.append(ob)
        s = build_signal("SELL", close, atr, "HH Failed", confs, 5)
        if s: sigs.append(s)

    fko = check_fakeout(candles, sh, sl, close)
    if fko:
        confs = [fko]
        ob = check_order_block(candles, fko["direction"], close, atr)
        if ob: confs.append(ob)
        s = build_signal(fko["direction"], close, atr, "Fakeout", confs, 4)
        if s: sigs.append(s)

    if choch:
        d = choch["direction"]
        f = check_fib(sh, sl, close, d)
        if f:
            s = build_signal(d, close, atr, "CHoCH + Fib", [choch, f], 4)
            if s: sigs.append(s)

    seen, out = set(), []
    for s in sorted(sigs, key=lambda x: x["score"], reverse=True):
        k = (s["direction"], s["setup"])
        if k not in seen:
            seen.add(k)
            out.append(s)
    return out

# ════════════════════════════════════════════════════
#  SCORE GLOBAL
# ════════════════════════════════════════════════════

def global_score(sig, trend_m1, trend_m15, vol_pct):
    pts = sig["score"] * 5
    if (sig["direction"] == "SELL" and trend_m1 == "bearish") or \
       (sig["direction"] == "BUY"  and trend_m1 == "bullish"):
        pts += 8
    elif trend_m1 == "ranging":
        pts += 3
    if (sig["direction"] == "SELL" and trend_m15 == "bearish") or \
       (sig["direction"] == "BUY"  and trend_m15 == "bullish"):
        pts += 12
    elif trend_m15 == "ranging":
        pts += 2
    pts += min(vol_pct * 200, 10)
    pts += min((sig["rr"] - MIN_RR) * 5, 10)
    return round(min(pts, 100), 1)

# ════════════════════════════════════════════════════
#  TELEGRAM MULTI-DIFFUSION
# ════════════════════════════════════════════════════

def send_telegram(text):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    for chat_id in CHAT_IDS:
        body = json.dumps({"chat_id": chat_id, "text": text,
                           "parse_mode": "HTML",
                           "disable_web_page_preview": True}).encode()
        try:
            req = urllib.request.Request(url, data=body,
                  headers={"Content-Type": "application/json"}, method="POST")
            with urllib.request.urlopen(req, context=ssl_ctx, timeout=10) as r:
                resp = json.loads(r.read())
                if not resp.get("ok"):
                    log.error(f"TG [{chat_id}]: {resp}")
                else:
                    log.info(f"TG ✅ envoyé → {chat_id}")
        except Exception as e:
            log.error(f"send_telegram [{chat_id}]: {e}")
        time.sleep(0.2)

def test_telegram():
    """Test de connectivité Telegram au démarrage."""
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/getMe"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "AlphaBot/11"})
        with urllib.request.urlopen(req, context=ssl_ctx, timeout=10) as r:
            resp = json.loads(r.read())
        if resp.get("ok"):
            name = resp["result"].get("username", "?")
            log.info(f"✅ Telegram OK — bot @{name}")
            return True
        else:
            log.error(f"❌ Telegram KO: {resp}")
            return False
    except Exception as e:
        log.error(f"❌ Telegram test: {e}")
        return False

def format_msg(sig, label, trend_m1, trend_m15, score, live_price,
               category="", executed=False):
    de   = "📈🟢 BUY" if sig["direction"] == "BUY" else "📉🔴 SELL"
    em1  = {"bullish": "📈", "bearish": "📉", "ranging": "↔️"}.get(trend_m1, "")
    em15 = {"bullish": "📈", "bearish": "📉", "ranging": "↔️"}.get(trend_m15, "")
    st   = "⭐" * min(int(sig["rr"]), 5)
    lv   = "\n⚡ <b>ORDRE LIVE PLACÉ ✅</b>" if executed else ""
    wk   = "\n🌙 <i>Week-end</i>" if is_weekend() else ""
    cat  = f"\n🏷 <i>{category}</i>" if category else ""
    align = ("✅ Aligné M15" if
             (sig["direction"]=="BUY" and trend_m15=="bullish") or
             (sig["direction"]=="SELL" and trend_m15=="bearish")
             else "⚠️ Contre M15")
    return (
        f"{de} — <b>AlphaBot Signal v11.4</b>\n"
        f"{'═'*32}\n"
        f"📌 <b>Marché:</b> {label}{cat}\n"
        f"🔧 <b>Setup:</b> {sig['setup']}\n"
        f"⏱ <b>Entrée M1</b> | Bougie FERMÉE ✅\n"
        f"📊 Trend M1 : {em1} {trend_m1.upper()}\n"
        f"📊 Trend M15: {em15} {trend_m15.upper()} — {align}\n"
        f"🕐 Session: {session_name()}\n"
        f"{'─'*32}\n"
        f"💰 <b>Entrée :</b> {sig['entry']}\n"
        f"🔴 <b>SL :</b>    {sig['sl']}\n"
        f"🎯 <b>TP1 (1:{MIN_RR:.0f}):</b> {sig['tp1']}\n"
        f"🏆 <b>TP2 (1:{TARGET_RR:.0f}):</b> {sig['tp2']}\n"
        f"💎 <b>TP3 (1:{MAX_RR:.0f}):</b> {sig['tp3']}\n"
        f"📊 R:R 1:{sig['rr']} {st}\n"
        f"{'─'*32}\n"
        f"🔍 <b>Confirmations:</b>\n{sig['reason']}\n"
        f"{'─'*32}\n"
        f"💡 Score: {score}/100 | Live: {live_price}"
        f"{lv}{wk}\n"
        f"⚠️ <i>Max 1-2% risque/trade</i>\n"
        f"🤖 <i>AlphaBot v11.4 | leaderOdg</i>"
    )

# ════════════════════════════════════════════════════
#  [NEW] PERSISTANCE SIGNAUX
# ════════════════════════════════════════════════════

def load_signals():
    """Charge le fichier JSON des signaux. Retourne une liste."""
    if not os.path.exists(SIGNALS_FILE):
        return []
    with _file_lock:
        try:
            with open(SIGNALS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            log.error(f"load_signals: {e}")
            return []

def save_signals(signals):
    """Sauvegarde la liste complète dans le JSON."""
    with _file_lock:
        try:
            with open(SIGNALS_FILE, "w", encoding="utf-8") as f:
                json.dump(signals, f, indent=2, ensure_ascii=False)
        except Exception as e:
            log.error(f"save_signals: {e}")

def log_signal(sig, symbol, label, category, score, trend_m1, trend_m15):
    """Enregistre un nouveau signal dans le fichier JSON."""
    signals = load_signals()
    now_utc = datetime.now(timezone.utc)
    entry = {
        "id":        len(signals) + 1,
        "ts":        now_utc.isoformat(),
        "date":      now_utc.strftime("%Y-%m-%d"),
        "symbol":    symbol,
        "label":     label,
        "category":  category,
        "direction": sig["direction"],
        "setup":     sig["setup"],
        "entry":     sig["entry"],
        "sl":        sig["sl"],
        "tp1":       sig["tp1"],
        "tp2":       sig["tp2"],
        "tp3":       sig["tp3"],
        "score":     score,
        "trend_m1":  trend_m1,
        "trend_m15": trend_m15,
        # statuts : open | tp1 | tp2 | tp3 | sl | expired
        "status":    "open",
        "tp1_hit":   False,
        "tp2_hit":   False,
        "tp3_hit":   False,
        "sl_hit":    False,
        "close_ts":  None,
    }
    signals.append(entry)
    save_signals(signals)
    log.info(f"📝 Signal #{entry['id']} enregistré ({symbol} {sig['direction']})")
    return entry["id"]

def update_signal_status(sig_id, field, value):
    """Met à jour un champ d'un signal par son id."""
    signals = load_signals()
    for s in signals:
        if s["id"] == sig_id:
            s[field] = value
            if field in ("sl_hit", "tp3_hit"):
                s["status"] = "sl" if field == "sl_hit" else "tp3"
                s["close_ts"] = datetime.now(timezone.utc).isoformat()
            elif field == "tp2_hit":
                s["status"] = "tp2"
            elif field == "tp1_hit":
                s["status"] = "tp1"
            break
    save_signals(signals)

# ════════════════════════════════════════════════════
#  [NEW] MONITORING TP/SL (thread dédié)
# ════════════════════════════════════════════════════

def _get_live_price_by_symbol(symbol):
    """Récupère le prix live pour n'importe quel symbol."""
    market = MARKET_BY_SYMBOL.get(symbol)
    if not market:
        return None
    return fetch_live_price(market)

def monitor_tpsl():
    """
    Thread qui tourne en arrière-plan.
    Vérifie toutes les 60s si les signaux ouverts ont touché TP ou SL.
    Envoie une notification Telegram à chaque événement.
    """
    log.info("🔍 Monitor TP/SL démarré")
    while not _shutdown.is_set():
        try:
            signals = load_signals()
            open_sigs = [s for s in signals if s["status"] == "open"]
            if open_sigs:
                log.info(f"🔍 Monitoring {len(open_sigs)} signal(s) ouvert(s)...")
            for s in open_sigs:
                price = _get_live_price_by_symbol(s["symbol"])
                if price is None:
                    continue
                d    = s["direction"]
                sid  = s["id"]
                lbl  = s["label"]

                # ── SL touché ──────────────────────────────────────
                if not s["sl_hit"]:
                    sl_hit = (d == "BUY"  and price <= s["sl"]) or \
                             (d == "SELL" and price >= s["sl"])
                    if sl_hit:
                        update_signal_status(sid, "sl_hit", True)
                        loss_pips = abs(s["entry"] - s["sl"])
                        send_telegram(
                            f"🛑 <b>STOP LOSS TOUCHÉ</b>\n"
                            f"{'─'*28}\n"
                            f"📌 {lbl} | {'🟢 BUY' if d=='BUY' else '🔴 SELL'}\n"
                            f"🔧 {s['setup']} | Score {s['score']}/100\n"
                            f"{'─'*28}\n"
                            f"🎯 Entrée : {s['entry']}\n"
                            f"🛑 SL : {s['sl']} ← touché @ {round(price,6)}\n"
                            f"📅 {s['date']} | Signal #{sid}\n"
                            f"🤖 <i>AlphaBot v11.4 | leaderOdg</i>"
                        )
                        log.info(f"🛑 SL touché — #{sid} {lbl} {d}")
                        continue

                # ── TP1 touché ─────────────────────────────────────
                if not s["tp1_hit"]:
                    tp1_hit = (d == "BUY"  and price >= s["tp1"]) or \
                              (d == "SELL" and price <= s["tp1"])
                    if tp1_hit:
                        update_signal_status(sid, "tp1_hit", True)
                        send_telegram(
                            f"✅ <b>TP1 TOUCHÉ 🎯</b>\n"
                            f"{'─'*28}\n"
                            f"📌 {lbl} | {'🟢 BUY' if d=='BUY' else '🔴 SELL'}\n"
                            f"🔧 {s['setup']} | Score {s['score']}/100\n"
                            f"{'─'*28}\n"
                            f"🎯 Entrée : {s['entry']}\n"
                            f"✅ TP1 (1:{MIN_RR:.0f}) : {s['tp1']} ✓\n"
                            f"🏆 TP2 (1:{TARGET_RR:.0f}) : {s['tp2']} ← prochain\n"
                            f"📅 {s['date']} | Signal #{sid}\n"
                            f"💡 <i>Déplacer SL au BE recommandé</i>\n"
                            f"🤖 <i>AlphaBot v11.4 | leaderOdg</i>"
                        )
                        log.info(f"✅ TP1 touché — #{sid} {lbl} {d}")

                # ── TP2 touché ─────────────────────────────────────
                if s["tp1_hit"] and not s["tp2_hit"]:
                    tp2_hit = (d == "BUY"  and price >= s["tp2"]) or \
                              (d == "SELL" and price <= s["tp2"])
                    if tp2_hit:
                        update_signal_status(sid, "tp2_hit", True)
                        send_telegram(
                            f"🏆 <b>TP2 TOUCHÉ 🎯🎯</b>\n"
                            f"{'─'*28}\n"
                            f"📌 {lbl} | {'🟢 BUY' if d=='BUY' else '🔴 SELL'}\n"
                            f"🔧 {s['setup']} | Score {s['score']}/100\n"
                            f"{'─'*28}\n"
                            f"🎯 Entrée : {s['entry']}\n"
                            f"✅ TP1 ✓ | ✅ TP2 (1:{TARGET_RR:.0f}) : {s['tp2']} ✓\n"
                            f"💎 TP3 (1:{MAX_RR:.0f}) : {s['tp3']} ← prochain\n"
                            f"📅 {s['date']} | Signal #{sid}\n"
                            f"🤖 <i>AlphaBot v11.4 | leaderOdg</i>"
                        )
                        log.info(f"🏆 TP2 touché — #{sid} {lbl} {d}")

                # ── TP3 touché ─────────────────────────────────────
                if s["tp2_hit"] and not s["tp3_hit"]:
                    tp3_hit = (d == "BUY"  and price >= s["tp3"]) or \
                              (d == "SELL" and price <= s["tp3"])
                    if tp3_hit:
                        update_signal_status(sid, "tp3_hit", True)
                        send_telegram(
                            f"💎 <b>TP3 TOUCHÉ — OBJECTIF PLEIN ✅✅✅</b>\n"
                            f"{'─'*28}\n"
                            f"📌 {lbl} | {'🟢 BUY' if d=='BUY' else '🔴 SELL'}\n"
                            f"🔧 {s['setup']} | Score {s['score']}/100\n"
                            f"{'─'*28}\n"
                            f"✅ TP1 ✓ | ✅ TP2 ✓ | 💎 TP3 (1:{MAX_RR:.0f}) ✓\n"
                            f"📊 R:R 1:{MAX_RR:.0f} atteint\n"
                            f"📅 {s['date']} | Signal #{sid}\n"
                            f"🤖 <i>AlphaBot v11.4 | leaderOdg</i>"
                        )
                        log.info(f"💎 TP3 touché — #{sid} {lbl} {d}")

        except Exception as e:
            log.error(f"monitor_tpsl: {e}")

        _shutdown.wait(60)  # Vérifie toutes les 60 secondes

# ════════════════════════════════════════════════════
#  [NEW] RAPPORTS QUOTIDIEN / HEBDOMADAIRE
# ════════════════════════════════════════════════════

def _build_stats(signals_list):
    """Calcule les statistiques depuis une liste de signaux."""
    total = len(signals_list)
    if total == 0:
        return {"total": 0, "tp1": 0, "tp2": 0, "tp3": 0,
                "sl": 0, "open": 0, "winrate": 0.0}
    tp1_c = sum(1 for s in signals_list if s["tp1_hit"])
    tp2_c = sum(1 for s in signals_list if s["tp2_hit"])
    tp3_c = sum(1 for s in signals_list if s["tp3_hit"])
    sl_c  = sum(1 for s in signals_list if s["sl_hit"])
    open_c= sum(1 for s in signals_list if s["status"] == "open")
    closed = tp1_c + sl_c
    wr    = round(tp1_c / closed * 100, 1) if closed > 0 else 0.0
    return {"total": total, "tp1": tp1_c, "tp2": tp2_c,
            "tp3": tp3_c, "sl": sl_c, "open": open_c, "winrate": wr}

def _symbol_breakdown(signals_list):
    """Breakdown par symbol."""
    by_sym = {}
    for s in signals_list:
        sym = s["symbol"]
        if sym not in by_sym:
            by_sym[sym] = {"label": s["label"], "count": 0, "tp": 0, "sl": 0}
        by_sym[sym]["count"] += 1
        if s["tp1_hit"]: by_sym[sym]["tp"] += 1
        if s["sl_hit"]:  by_sym[sym]["sl"] += 1
    lines = []
    for sym, d in sorted(by_sym.items(), key=lambda x: x[1]["count"], reverse=True):
        closed = d["tp"] + d["sl"]
        wr = round(d["tp"]/closed*100) if closed > 0 else 0
        lines.append(f"  {d['label']}: {d['count']} signaux | ✅{d['tp']} ❌{d['sl']} ({wr}% WR)")
    return "\n".join(lines) if lines else "  Aucun"

def send_daily_report():
    """Rapport journalier — envoyé à 22h00 UTC."""
    now   = datetime.now(timezone.utc)
    today = now.strftime("%Y-%m-%d")
    all_s = load_signals()
    today_s = [s for s in all_s if s["date"] == today]
    st    = _build_stats(today_s)
    bkd   = _symbol_breakdown(today_s)
    wr_bar = "🟢" * int(st["winrate"]/20) + "⬜" * (5 - int(st["winrate"]/20))
    msg = (
        f"📊 <b>RAPPORT JOURNALIER — AlphaBot v11.4</b>\n"
        f"{'═'*32}\n"
        f"📅 <b>Date :</b> {today}\n"
        f"🕙 <b>Heure :</b> 22:00 UTC\n"
        f"{'─'*32}\n"
        f"📤 <b>Signaux envoyés :</b> {st['total']}\n"
        f"  ✅ TP1 touché   : {st['tp1']}\n"
        f"  🏆 TP2 touché   : {st['tp2']}\n"
        f"  💎 TP3 touché   : {st['tp3']}\n"
        f"  🛑 SL touché    : {st['sl']}\n"
        f"  🔄 En cours     : {st['open']}\n"
        f"{'─'*32}\n"
        f"📈 <b>Win Rate :</b> {st['winrate']}% {wr_bar}\n"
        f"{'─'*32}\n"
        f"📌 <b>Par marché :</b>\n{bkd}\n"
        f"{'─'*32}\n"
        f"🤖 <i>AlphaBot v11.4 | leaderOdg</i>"
    )
    send_telegram(msg)
    log.info(f"📊 Rapport quotidien envoyé — {today} | {st['total']} signaux | WR {st['winrate']}%")

def send_weekly_report():
    """Rapport hebdomadaire — envoyé dimanche 22h00 UTC."""
    now    = datetime.now(timezone.utc)
    # Semaine du lundi au dimanche
    start  = now - timedelta(days=now.weekday())   # lundi
    start  = start.replace(hour=0, minute=0, second=0, microsecond=0)
    dates  = [(start + timedelta(days=i)).strftime("%Y-%m-%d") for i in range(7)]
    all_s  = load_signals()
    week_s = [s for s in all_s if s["date"] in dates]
    st     = _build_stats(week_s)
    bkd    = _symbol_breakdown(week_s)
    wr_bar = "🟢" * int(st["winrate"]/20) + "⬜" * (5 - int(st["winrate"]/20))
    # Meilleur setup de la semaine
    setup_stats = {}
    for s in week_s:
        k = s["setup"]
        if k not in setup_stats:
            setup_stats[k] = {"tp": 0, "sl": 0}
        if s["tp1_hit"]: setup_stats[k]["tp"] += 1
        if s["sl_hit"]:  setup_stats[k]["sl"] += 1
    best_setup = ""
    best_wr    = -1
    for k, v in setup_stats.items():
        closed = v["tp"] + v["sl"]
        if closed >= 2:
            wr = v["tp"] / closed * 100
            if wr > best_wr:
                best_wr    = wr
                best_setup = k
    best_line = f"\n🏅 <b>Meilleur setup :</b> {best_setup} ({round(best_wr,0):.0f}% WR)" if best_setup else ""
    msg = (
        f"📈 <b>RAPPORT HEBDOMADAIRE — AlphaBot v11.4</b>\n"
        f"{'═'*32}\n"
        f"📅 <b>Semaine :</b> {dates[0]} → {dates[6]}\n"
        f"{'─'*32}\n"
        f"📤 <b>Total signaux :</b> {st['total']}\n"
        f"  ✅ TP1 : {st['tp1']}  🏆 TP2 : {st['tp2']}  💎 TP3 : {st['tp3']}\n"
        f"  🛑 SL  : {st['sl']}  🔄 Ouverts : {st['open']}\n"
        f"{'─'*32}\n"
        f"📊 <b>Win Rate :</b> {st['winrate']}% {wr_bar}{best_line}\n"
        f"{'─'*32}\n"
        f"📌 <b>Par marché :</b>\n{bkd}\n"
        f"{'─'*32}\n"
        f"🤖 <i>AlphaBot v11.4 | leaderOdg</i>"
    )
    send_telegram(msg)
    log.info(f"📈 Rapport hebdomadaire envoyé | {st['total']} signaux | WR {st['winrate']}%")

def send_heartbeat():
    """Signal de vie toutes les 6h."""
    global signal_count
    open_c = sum(1 for s in load_signals() if s["status"] == "open")
    send_telegram(
        f"💓 <b>AlphaBot v11.4 — EN LIGNE</b>\n"
        f"{'─'*26}\n"
        f"🕐 {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M')} UTC\n"
        f"📊 Session: {session_name()}\n"
        f"📤 Signaux totaux: {signal_count}\n"
        f"🔄 Signaux ouverts: {open_c}\n"
        f"{'─'*26}\n"
        f"🤖 <i>AlphaBot v11.4 | leaderOdg</i>"
    )
    log.info(f"💓 Heartbeat envoyé | {signal_count} signaux | {open_c} ouverts")

# ════════════════════════════════════════════════════
#  BINANCE LIVE TRADING
# ════════════════════════════════════════════════════

def _sign(params):
    q   = urllib.parse.urlencode(params)
    sig = hmac.new(BINANCE_API_SECRET.encode(), q.encode(), hashlib.sha256).hexdigest()
    return q + "&signature=" + sig

def b_post(path, params):
    params.update({"timestamp": int(time.time()*1000), "recvWindow": 5000})
    body = _sign(params).encode()
    try:
        req = urllib.request.Request(
            f"https://fapi.binance.com{path}", data=body,
            headers={"X-MBX-APIKEY": BINANCE_API_KEY,
                     "Content-Type": "application/x-www-form-urlencoded"},
            method="POST")
        with urllib.request.urlopen(req, context=ssl_ctx, timeout=10) as r:
            return json.loads(r.read())
    except Exception as e:
        log.error(f"b_post {path}: {e}")
        return None

def b_get(path, params=None):
    params = params or {}
    params.update({"timestamp": int(time.time()*1000), "recvWindow": 5000})
    try:
        req = urllib.request.Request(
            f"https://fapi.binance.com{path}?{_sign(params)}",
            headers={"X-MBX-APIKEY": BINANCE_API_KEY})
        with urllib.request.urlopen(req, context=ssl_ctx, timeout=10) as r:
            return json.loads(r.read())
    except Exception as e:
        log.error(f"b_get {path}: {e}")
        return None

def get_balance():
    data = b_get("/fapi/v2/balance")
    if not data: return 0.0
    for a in data:
        if a.get("asset") == "USDT":
            return float(a.get("availableBalance", 0))
    return 0.0

def get_prec(symbol):
    try:
        req = urllib.request.Request(
            "https://fapi.binance.com/fapi/v1/exchangeInfo",
            headers={"User-Agent": "AlphaBot/11"})
        with urllib.request.urlopen(req, context=ssl_ctx, timeout=10) as r:
            info = json.loads(r.read())
        for s in info["symbols"]:
            if s["symbol"] != symbol: continue
            pp, ss = s["pricePrecision"], 0.001
            for f in s["filters"]:
                if f["filterType"] == "LOT_SIZE": ss = float(f["stepSize"])
            return pp, ss
    except Exception as e:
        log.error(f"get_prec: {e}")
    return 2, 0.001

def rs(val, step):
    if step == 0: return val
    dec = len(f"{step:.10f}".rstrip("0").split(".")[-1]) if "." in str(step) else 0
    return round(round(val/step)*step, dec)

def place_order(sig, market):
    if market["source"] != "binance": return False
    symbol = market["symbol"]
    if not LIVE_TRADING:
        log.info(f"[PAPER] {sig['direction']} {symbol} @ {sig['entry']}")
        return True
    bal = get_balance()
    if bal < 5: return False
    sl_d = abs(sig["entry"] - sig["sl"])
    if sl_d == 0: return False
    pp, ss = get_prec(symbol)
    qty    = rs((bal * RISK_PER_TRADE_PCT/100 / sl_d) * USE_LEVERAGE, ss)
    if qty <= 0: return False
    side = sig["direction"]
    cl   = "SELL" if side == "BUY" else "BUY"
    b_post("/fapi/v1/leverage", {"symbol": symbol, "leverage": USE_LEVERAGE})
    r = b_post("/fapi/v1/order",
               {"symbol": symbol, "side": side, "type": "MARKET", "quantity": qty})
    if not r or "orderId" not in r: return False
    time.sleep(0.5)
    b_post("/fapi/v1/order", {"symbol": symbol, "side": cl,
                               "type": "STOP_MARKET",
                               "stopPrice": round(sig["sl"], pp),
                               "closePosition": "true"})
    b_post("/fapi/v1/order", {"symbol": symbol, "side": cl,
                               "type": "TAKE_PROFIT_MARKET",
                               "stopPrice": round(sig["tp2"], pp),
                               "closePosition": "true"})
    return True

# ════════════════════════════════════════════════════
#  HELPERS
# ════════════════════════════════════════════════════

def is_cooldown(symbol):
    return (time.time() - last_signal_time.get(symbol, 0)) < SIGNAL_COOLDOWN

def set_cooldown(symbol):
    last_signal_time[symbol] = time.time()

# ════════════════════════════════════════════════════
#  PROCESS SYMBOLE
# ════════════════════════════════════════════════════

def process_symbol(market):
    global signal_count
    symbol   = market["symbol"]
    label    = market["label"]
    category = market.get("category", "")

    if is_asian_session(): return
    if is_cooldown(symbol): return

    live = fetch_live_price(market)
    if live is None: return

    now    = int(time.time())
    c_open = now - (now % 60)
    state  = symbol_state.setdefault(symbol, {"last": 0})
    if c_open <= state["last"]: return

    candles_m1 = fetch_m1(market)
    if not candles_m1 or len(candles_m1) < 40: return

    state["last"] = c_open

    close   = candles_m1[-1]["c"]
    atr     = calc_atr(candles_m1)
    vol_pct = (atr / close * 100) if close > 0 else 0
    sh, sl  = find_swings(candles_m1)
    trend_m1 = market_structure(sh, sl)

    # [FIX] Cache M15 — évite appels répétés Yahoo
    trend_m15 = htf_trend_cached(market)

    log.info(f"[{symbol}] M1 close={close} | M1:{trend_m1} | M15:{trend_m15} | "
             f"ATR%={vol_pct:.4f} | session={session_name()}")

    is_yahoo = (market["source"] == "yahoo")
    sigs = evaluate(candles_m1, is_yahoo=is_yahoo)
    if not sigs: return

    min_score_asset = market.get("min_score", 50)

    for sig in sigs:
        score = global_score(sig, trend_m1, trend_m15, vol_pct)

        if trend_m15 != "ranging":
            if (sig["direction"] == "BUY"  and trend_m15 == "bearish") or \
               (sig["direction"] == "SELL" and trend_m15 == "bullish"):
                log.info(f"[{symbol}] Signal {sig['direction']} ignoré — contre tendance M15 {trend_m15}")
                continue

        log.info(f"[{symbol}] {sig['setup']} | {sig['direction']} | "
                 f"score={score}/{min_score_asset} | M15={trend_m15}")

        if score < min_score_asset:
            log.info(f"[{symbol}] Score {score} < seuil {min_score_asset} — ignoré")
            continue

        executed = False
        if score >= MIN_SCORE_LIVE:
            executed = place_order(sig, market)

        # Enregistre le signal dans le JSON (tracking TP/SL)
        sig_id = log_signal(sig, symbol, label, category, score, trend_m1, trend_m15)

        msg = format_msg(sig, label, trend_m1, trend_m15, score, live,
                         category=category, executed=executed)
        send_telegram(msg)
        set_cooldown(symbol)
        signal_count += 1
        log.info(f"{'⚡' if executed else '✅'} Signal #{signal_count} (DB#{sig_id}): "
                 f"{symbol} {sig['direction']} | score={score} | M15={trend_m15}")
        break

# ════════════════════════════════════════════════════
#  [NEW] SCHEDULER — Rapports & Heartbeat
# ════════════════════════════════════════════════════

def check_scheduler():
    """Appelé dans la boucle principale. Gère rapports et heartbeat."""
    global _last_daily_report_day, _last_weekly_report_week, _last_heartbeat_h
    now = datetime.now(timezone.utc)

    # ── Heartbeat toutes les N heures ────────────────
    current_h_slot = now.hour // HEARTBEAT_EVERY_H
    if _last_heartbeat_h != current_h_slot:
        _last_heartbeat_h = current_h_slot
        try:
            send_heartbeat()
        except Exception as e:
            log.error(f"heartbeat: {e}")

    # ── Rapport quotidien à DAILY_REPORT_HOUR UTC ────
    if now.hour == DAILY_REPORT_HOUR and _last_daily_report_day != now.date():
        _last_daily_report_day = now.date()
        try:
            send_daily_report()
        except Exception as e:
            log.error(f"daily_report: {e}")

    # ── Rapport hebdomadaire dimanche 22h UTC ────────
    if now.weekday() == 6 and now.hour == DAILY_REPORT_HOUR:
        week_id = now.isocalendar()[1]
        if _last_weekly_report_week != week_id:
            _last_weekly_report_week = week_id
            try:
                send_weekly_report()
            except Exception as e:
                log.error(f"weekly_report: {e}")

# ════════════════════════════════════════════════════
#  [NEW] SIGTERM / SIGINT — Arrêt propre sur VPS
# ════════════════════════════════════════════════════

def _handle_signal(signum, frame):
    sig_name = "SIGTERM" if signum == signal.SIGTERM else "SIGINT"
    log.info(f"⛔ {sig_name} reçu — arrêt propre...")
    send_telegram(
        f"⛔ <b>AlphaBot v11.4 — ARRÊT</b>\n"
        f"Signal {sig_name} reçu. Le bot s'arrête proprement.\n"
        f"📤 Signaux session: {signal_count}\n"
        f"🤖 <i>AlphaBot v11.4 | leaderOdg</i>"
    )
    _shutdown.set()

# ════════════════════════════════════════════════════
#  MAIN
# ════════════════════════════════════════════════════

def main():
    global signal_count

    # Handlers arrêt propre
    signal.signal(signal.SIGTERM, _handle_signal)
    signal.signal(signal.SIGINT,  _handle_signal)

    log.info("╔══════════════════════════════════════════════╗")
    log.info("║  AlphaBot Signal v11.4 — BTC+Gold+7 Forex  ║")
    log.info("╚══════════════════════════════════════════════╝")
    log.info(f"  Destinataires Telegram : {len(CHAT_IDS)} compte(s)")
    log.info(f"  Log fichier           : {LOG_FILE}")
    log.info(f"  Signaux fichier       : {SIGNALS_FILE}")

    # Test Telegram
    if not test_telegram():
        log.warning("⚠️ Telegram KO — vérifier le token. Le bot continue quand même.")

    # Charger compteur de la session précédente
    existing = load_signals()
    log.info(f"📂 {len(existing)} signaux historiques chargés")

    wk    = is_weekend()
    asian = is_asian_session()
    mkts  = active_markets()

    send_telegram(
        f"🤖 <b>AlphaBot Signal v11.4 DÉMARRÉ</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"⚡ Scan temps réel | Entrée <b>M1</b> | Tendance <b>M15</b>\n"
        f"🚫 Session Asiatique (00:00–07:00 UTC) bloquée\n"
        f"🕐 Session: {session_name()}"
        f"{'  ⛔ PAUSE' if asian else '  ✅ ACTIF'}\n"
        f"📌 <b>Marchés ({len(mkts)}):</b>\n"
        f"  BTC/USDT | XAU/USD\n"
        f"  EUR/USD | GBP/USD | USD/JPY | USD/CHF\n"
        f"  AUD/USD | USD/CAD | NZD/USD\n"
        f"🗓 {'🌙 Week-end → BTC + Gold' if wk else '📊 Semaine → Tous les marchés'}\n"
        f"📣 Diffusion: <b>{len(CHAT_IDS)} destinataire(s)</b>\n"
        f"💹 {'🟢 LIVE' if LIVE_TRADING else '🟡 Paper'} | "
        f"Levier {USE_LEVERAGE}x | Risque {RISK_PER_TRADE_PCT}%\n"
        f"🎯 RR: 1:{MIN_RR:.0f} | 1:{TARGET_RR:.0f} | 1:{MAX_RR:.0f}\n"
        f"📋 Tracking TP/SL actif ✅\n"
        f"📊 Rapport quotidien à {DAILY_REPORT_HOUR}h UTC\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🤖 <i>leaderOdg — AlphaBot v11.4</i>"
    )

    # Démarrer le thread monitoring TP/SL
    monitor_thread = threading.Thread(target=monitor_tpsl, daemon=True, name="TPSL-Monitor")
    monitor_thread.start()
    log.info("🔍 Thread monitoring TP/SL démarré")

    # ── Boucle principale ──────────────────────────────
    while not _shutdown.is_set():
        try:
            mkts = active_markets()
            for m in sorted(mkts, key=lambda x: x["priority"]):
                if _shutdown.is_set(): break
                try:
                    process_symbol(m)
                except Exception as e:
                    log.error(f"[{m['symbol']}] {e}")
                time.sleep(0.3)

            # Vérifier rapports / heartbeat
            check_scheduler()

        except Exception as e:
            log.error(f"Boucle principale: {e}")

        _shutdown.wait(POLL_INTERVAL_SEC)

    log.info("✅ AlphaBot arrêté proprement.")

if __name__ == "__main__":
    main()
