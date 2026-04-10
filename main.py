#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
╔══════════════════════════════════════════════════════════════════╗
║         AlphaBot Signal v11.3 — by leaderOdg                   ║
║  ⚡ Scan LIVE 3s | Bougie M5 fermée | Score ≥75               ║
║  📸 Graphiques annotés | 🤖 Commandes interactives            ║
║  ✅ Validation Leader avant publication (boutons inline)       ║
║  🌐 v11.3-render : Flask health server pour Render.com        ║
║  🔧 [FIX] 1 seul message /analyse | Anti-doublon cmds        ║
╚══════════════════════════════════════════════════════════════════╝

CHANGEMENTS v11.2 vs v11.1 :
  - [FIX CRITIQUE] LEADER_CHAT_ID séparé du GROUP_CHAT_ID
  - [FIX] Tolérance Double Top/Bottom : 0.0006 → 0.003 (signaux plus fréquents)
  - [FIX] Order Block : condition de confirmation assouplie
  - [NEW] EMA 20 / EMA 50 : filtre tendance + bonus score
  - [NEW] Engulfing candle : confirmation supplémentaire (+3 pts)
  - [NEW] Momentum 3 bougies : filtre direction
  - [NEW] Min 3 confirmations pour setups BOS/CHoCH (was 2)
  - [NEW] Pénalité ranging dans global_score
  - [NEW] Bonus score si 3+ confirmations alignées
  - [UPD] SIGNAL_COOLDOWN : 600 → 900s (15 min) — moins de spam
  - [UPD] Score minimum publication : 72 → 75

WORKFLOW :
  1. Bot détecte un setup valide (score ≥ 75)
  2. Génère le graphique annoté
  3. Envoie au LEADER en privé avec boutons ✅ YES / ❌ NO / ✏️ MODIFY
  4. Leader appuie → bot publie (ou annule) dans le groupe

COMMANDES :
  /analyse BTCUSDT  /signal  /stats  /update #1  /session  /aide  /pending

INSTALL :
  pip install matplotlib
"""

import time, json, logging, ssl, hashlib, hmac, os
import urllib.request, urllib.parse, io, threading
from datetime import datetime, timezone

# ── Flask (health server pour Render.com) ──────────────────────────
try:
    from flask import Flask, jsonify
    FLASK_AVAILABLE = True
except ImportError:
    FLASK_AVAILABLE = False

try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    CHART_AVAILABLE = True
except ImportError:
    CHART_AVAILABLE = False

# ══════════════════════════════════════════════════════════════════
#  CONFIG — modifier ces valeurs
# ══════════════════════════════════════════════════════════════════
BOT_TOKEN          = "8665812395:AAFO4BMTIrBCQJYVL8UytO028TcB1sDfgbI"
GROUP_CHAT_ID      = "-1002335466840"   # groupe public (publication finale)
LEADER_CHAT_ID     = "6982051442"       # ← TON ID perso Telegram (validation privée)
                                        # → obtenu avec @userinfobot

BINANCE_API_KEY    = "VOTRE_API_KEY"
BINANCE_API_SECRET = "VOTRE_API_SECRET"
LIVE_TRADING       = False
RISK_PER_TRADE_PCT = 1.0
USE_LEVERAGE       = 10
MIN_SCORE_LIVE     = 75               # ← relevé à 75 pour meilleure qualité
POLL_INTERVAL_SEC  = 3
CANDLE_LIMIT       = 100
MIN_RR             = 3.0
TARGET_RR          = 4.0
MAX_RR             = 5.0
SIGNAL_COOLDOWN    = 900              # ← 15 min entre signaux par symbole
CHART_CANDLES      = 60
VALIDATION_TIMEOUT = 300

ALL_MARKETS = [
    {"symbol": "BTCUSDT",  "label": "BTC/USDT",  "priority": 1},
    {"symbol": "ETHUSDT",  "label": "ETH/USDT",  "priority": 2},
    {"symbol": "SOLUSDT",  "label": "SOL/USDT",  "priority": 3},
    {"symbol": "BNBUSDT",  "label": "BNB/USDT",  "priority": 4},
    {"symbol": "XRPUSDT",  "label": "XRP/USDT",  "priority": 5},
    {"symbol": "DOGEUSDT", "label": "DOGE/USDT", "priority": 6},
    {"symbol": "ADAUSDT",  "label": "ADA/USDT",  "priority": 7},
    {"symbol": "LINKUSDT", "label": "LINK/USDT", "priority": 8},
]
SYMBOL_MAP      = {m["symbol"]: m for m in ALL_MARKETS}
WEEKEND_MARKETS = [ALL_MARKETS[0]]

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s [%(levelname)s] %(message)s",
                    datefmt="%H:%M:%S")
log = logging.getLogger("AlphaBot")

ssl_ctx = ssl.create_default_context()
ssl_ctx.check_hostname = False
ssl_ctx.verify_mode    = ssl.CERT_NONE

# ══════════════════════════════════════════════════════════════════
#  ÉTAT GLOBAL
# ══════════════════════════════════════════════════════════════════
last_signal_time   = {}
signal_count       = 0
symbol_state       = {}
last_update_id     = 0
pending_validation = {}   # {sig_id → payload}
active_signals     = {}   # {sig_id → payload}
stats = {"total": 0, "published": 0, "rejected": 0, "tp": 0, "sl": 0, "rr_sum": 0.0}
# [FIX v11.3] Anti-spam commandes : évite les doubles envois (même chat, même cmd)
_cmd_last_time     = {}   # {(chat_id, cmd) → timestamp}

# ══════════════════════════════════════════════════════════════════
#  FETCH BINANCE
# ══════════════════════════════════════════════════════════════════
def fetch_candles_m5(symbol, limit=None):
    limit = limit or CANDLE_LIMIT
    url = (f"https://fapi.binance.com/fapi/v1/klines"
           f"?symbol={symbol}&interval=5m&limit={limit+1}")
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "AlphaBot/11.2"})
        with urllib.request.urlopen(req, context=ssl_ctx, timeout=8) as r:
            data = json.loads(r.read())
        candles = [{"t": int(c[0])//1000, "o": float(c[1]),
                    "h": float(c[2]), "l": float(c[3]),
                    "c": float(c[4]), "v": float(c[5])} for c in data]
        return candles[:-1]  # exclure bougie en cours
    except Exception as e:
        log.warning(f"[{symbol}] fetch_candles: {e}")
        return []

def fetch_live_price(symbol):
    url = f"https://fapi.binance.com/fapi/v1/ticker/price?symbol={symbol}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "AlphaBot/11.2"})
        with urllib.request.urlopen(req, context=ssl_ctx, timeout=4) as r:
            return float(json.loads(r.read())["price"])
    except Exception as e:
        log.warning(f"[{symbol}] live_price: {e}")
        return None

def is_weekend():
    return datetime.now(timezone.utc).weekday() >= 5

def is_active_session():
    h = datetime.now(timezone.utc).hour
    return 7 <= h < 21

def active_markets():
    return WEEKEND_MARKETS if is_weekend() else ALL_MARKETS

# ══════════════════════════════════════════════════════════════════
#  ANALYSE TECHNIQUE
# ══════════════════════════════════════════════════════════════════
def find_swings(candles, lb=5):
    n = len(candles)
    sh, sl = [], []
    for i in range(lb, n - lb):
        wh = [candles[j]["h"] for j in range(i-lb, i+lb+1)]
        wl = [candles[j]["l"] for j in range(i-lb, i+lb+1)]
        if candles[i]["h"] == max(wh): sh.append({"idx": i, "price": candles[i]["h"]})
        if candles[i]["l"] == min(wl): sl.append({"idx": i, "price": candles[i]["l"]})
    return sh, sl

def market_structure(sh, sl):
    if len(sh) < 2 or len(sl) < 2: return "ranging"
    if sh[-1]["price"] > sh[-2]["price"] and sl[-1]["price"] > sl[-2]["price"]: return "bullish"
    if sh[-1]["price"] < sh[-2]["price"] and sl[-1]["price"] < sl[-2]["price"]: return "bearish"
    return "ranging"

def calc_atr(candles, period=14):
    if len(candles) < period + 1: return 0
    trs = [max(candles[i]["h"]-candles[i]["l"],
               abs(candles[i]["h"]-candles[i-1]["c"]),
               abs(candles[i]["l"]-candles[i-1]["c"]))
           for i in range(1, len(candles))]
    return sum(trs[-period:]) / period

# ── [NEW] EMA ──────────────────────────────────────────────────────
def calc_ema(candles, period):
    """EMA classique sur les closes."""
    if len(candles) < period: return None
    closes = [c["c"] for c in candles]
    k = 2 / (period + 1)
    ema = sum(closes[:period]) / period
    for price in closes[period:]:
        ema = price * k + ema * (1 - k)
    return ema

# ── [NEW] Engulfing ────────────────────────────────────────────────
def check_engulfing(candles, direction):
    """Bougie englobante = confirmation de direction."""
    if len(candles) < 2: return None
    prev, curr = candles[-2], candles[-1]
    if direction == "BUY":
        if (prev["c"] < prev["o"] and            # précédente baissière
                curr["c"] > curr["o"] and         # actuelle haussière
                curr["c"] > prev["o"] and         # engloble body
                curr["o"] < prev["c"]):
            return {"score_extra": 3,
                    "reason": f"Engulfing BUY @ {round(curr['c'],4)} ✅"}
    if direction == "SELL":
        if (prev["c"] > prev["o"] and            # précédente haussière
                curr["c"] < curr["o"] and         # actuelle baissière
                curr["c"] < prev["o"] and         # engloble body
                curr["o"] > prev["c"]):
            return {"score_extra": 3,
                    "reason": f"Engulfing SELL @ {round(curr['c'],4)} ✅"}
    return None

# ── [NEW] Momentum 3 bougies ───────────────────────────────────────
def check_momentum(candles, direction):
    """Vérifie que les 3 dernières bougies ont un biais cohérent."""
    if len(candles) < 4: return False
    last3 = candles[-4:-1]
    if direction == "BUY":
        return sum(1 for c in last3 if c["c"] > c["o"]) >= 2
    if direction == "SELL":
        return sum(1 for c in last3 if c["c"] < c["o"]) >= 2
    return False

def check_double_top(candles, sh, sl, close):
    if len(sh) < 2: return None
    n = len(candles)
    h1, h2 = sh[-2], sh[-1]
    if h1["idx"] < n-60 or h2["idx"] < n-20: return None
    # [FIX] tolérance 0.003 (0.3%) au lieu de 0.0006 (0.06%)
    if abs(h1["price"]-h2["price"])/h1["price"] > 0.003: return None
    midlows = [s for s in sl if h1["idx"] < s["idx"] < h2["idx"]]
    if not midlows: return None
    neck = min(midlows, key=lambda x: x["price"])["price"]
    if close < neck:
        return {"direction": "SELL", "score_extra": 4,
                "reason": f"Double Top @ {round(max(h1['price'],h2['price']),4)} | Neck {round(neck,4)} ✅",
                "zone": max(h1["price"], h2["price"])}
    return None

def check_double_bottom(candles, sh, sl, close):
    if len(sl) < 2: return None
    n = len(candles)
    l1, l2 = sl[-2], sl[-1]
    if l1["idx"] < n-60 or l2["idx"] < n-20: return None
    # [FIX] tolérance 0.003 (0.3%) au lieu de 0.0006 (0.06%)
    if abs(l1["price"]-l2["price"])/l1["price"] > 0.003: return None
    midhighs = [s for s in sh if l1["idx"] < s["idx"] < l2["idx"]]
    if not midhighs: return None
    neck = max(midhighs, key=lambda x: x["price"])["price"]
    if close > neck:
        return {"direction": "BUY", "score_extra": 4,
                "reason": f"Double Bottom @ {round(min(l1['price'],l2['price']),4)} | Neck {round(neck,4)} ✅",
                "zone": min(l1["price"], l2["price"])}
    return None

def check_choch(candles, sh, sl, trend, close):
    if trend == "bullish" and len(sl) >= 2:
        lvl = sl[-2]["price"]
        if close < lvl:
            return {"direction": "SELL", "score_extra": 3,
                    "reason": f"CHoCH baissier < HL {round(lvl,4)} ✅", "zone": lvl}
    if trend == "bearish" and len(sh) >= 2:
        lvl = sh[-2]["price"]
        if close > lvl:
            return {"direction": "BUY", "score_extra": 3,
                    "reason": f"CHoCH haussier > LH {round(lvl,4)} ✅", "zone": lvl}
    return None

def check_bos(sh, sl, trend, close):
    if trend == "bullish" and sh:
        lvl = sh[-1]["price"]
        if close > lvl:
            return {"direction": "BUY", "score_extra": 3,
                    "reason": f"BOS haussier @ {round(lvl,4)} ✅", "zone": lvl}
    if trend == "bearish" and sl:
        lvl = sl[-1]["price"]
        if close < lvl:
            return {"direction": "SELL", "score_extra": 3,
                    "reason": f"BOS baissier @ {round(lvl,4)} ✅", "zone": lvl}
    return None

def check_order_block(candles, direction, close, atr):
    """
    [FIX v11.2] Condition assouplie : on vérifie que les bougies suivantes
    cassent le body du OB (pas besoin d'un ATR complet).
    """
    window = candles[-40:]
    for i in range(1, len(window)-4):
        c = window[i]
        body_hi = max(c["o"], c["c"])
        body_lo = min(c["o"], c["c"])
        if direction == "SELL" and c["c"] > c["o"]:
            # OB bearish : bougie haussière suivie d'une baisse du body
            fut = [window[j]["l"] for j in range(i+1, min(i+5, len(window)))]
            if fut and min(fut) < body_lo and body_lo <= close <= body_hi:
                return {"score_extra": 3,
                        "reason": f"OB bearish [{round(body_lo,4)}-{round(body_hi,4)}] ✅",
                        "ob_lo": body_lo, "ob_hi": body_hi}
        if direction == "BUY" and c["c"] < c["o"]:
            # OB bullish : bougie baissière suivie d'une hausse du body
            fut = [window[j]["h"] for j in range(i+1, min(i+5, len(window)))]
            if fut and max(fut) > body_hi and body_lo <= close <= body_hi:
                return {"score_extra": 3,
                        "reason": f"OB bullish [{round(body_lo,4)}-{round(body_hi,4)}] ✅",
                        "ob_lo": body_lo, "ob_hi": body_hi}
    return None

def check_fvg(candles, close):
    w = candles[-30:]
    for i in range(2, len(w)):
        c0, c2 = w[i-2], w[i]
        gb = c2["l"] - c0["h"]
        gs = c0["l"] - c2["h"]
        if gb > 0 and c0["h"] <= close <= c2["l"]:
            return {"direction": "BUY", "score_extra": 3,
                    "reason": f"FVG bullish [{round(c0['h'],4)}-{round(c2['l'],4)}] ✅",
                    "fvg_lo": c0["h"], "fvg_hi": c2["l"]}
        if gs > 0 and c2["h"] <= close <= c0["l"]:
            return {"direction": "SELL", "score_extra": 3,
                    "reason": f"FVG bearish [{round(c2['h'],4)}-{round(c0['l'],4)}] ✅",
                    "fvg_lo": c2["h"], "fvg_hi": c0["l"]}
    return None

def check_liquidity_sweep(candles, sh, sl):
    if len(candles) < 3: return None
    p, c = candles[-2], candles[-1]
    if sl:
        lvl = sl[-1]["price"]
        if p["l"] < lvl and c["c"] > lvl:
            return {"direction": "BUY", "score_extra": 4,
                    "reason": f"Liq Sweep BUY @ {round(lvl,4)} ✅", "zone": lvl}
    if sh:
        lvl = sh[-1]["price"]
        if p["h"] > lvl and c["c"] < lvl:
            return {"direction": "SELL", "score_extra": 4,
                    "reason": f"Liq Sweep SELL @ {round(lvl,4)} ✅", "zone": lvl}
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
                        "reason": f"Breaker SELL [{round(z['bot'],4)}-{round(z['top'],4)}] ✅",
                        "ob_lo": z["bot"], "ob_hi": z["top"]}
    if trend == "bullish":
        for z in reversed(demand):
            if z["top"]*0.999 < close < z["top"]*1.007:
                return {"direction": "BUY", "score_extra": 4,
                        "reason": f"Breaker BUY [{round(z['bot'],4)}-{round(z['top'],4)}] ✅",
                        "ob_lo": z["bot"], "ob_hi": z["top"]}
    return None

def check_hh_failed(candles, sh, sl, close):
    if len(sh) < 3 or not sl: return None
    if sh[-1]["price"] < sh[-2]["price"]:
        hl = sl[-1]["price"]
        if close < hl:
            return {"direction": "SELL", "score_extra": 4,
                    "reason": f"HH Failed → HL {round(hl,4)} cassé ✅", "zone": hl}
    return None

def check_fakeout(candles, sh, sl, close):
    if len(candles) < 3: return None
    spike, conf = candles[-2], candles[-1]
    if sl:
        lvl = sl[-1]["price"]
        if spike["l"] < lvl and conf["c"] > lvl:
            return {"direction": "BUY", "score_extra": 3,
                    "reason": f"Fakeout BUY @ {round(lvl,4)} ✅", "zone": lvl}
    if sh:
        lvl = sh[-1]["price"]
        if spike["h"] > lvl and conf["c"] < lvl:
            return {"direction": "SELL", "score_extra": 3,
                    "reason": f"Fakeout SELL @ {round(lvl,4)} ✅", "zone": lvl}
    return None

def check_fib(sh, sl, close, direction):
    if direction == "BUY" and sh and sl:
        lo, hi = sl[-1]["price"], sh[-1]["price"]
        if hi <= lo: return None
        f5, f6 = hi-(hi-lo)*0.5, hi-(hi-lo)*0.618
        if f6 <= close <= f5:
            return {"score_extra": 2,
                    "reason": f"Fib 0.5-0.618 [{round(f6,4)}-{round(f5,4)}] ✅",
                    "fib_lo": f6, "fib_hi": f5}
    if direction == "SELL" and sh and sl:
        lo, hi = sl[-1]["price"], sh[-1]["price"]
        if lo >= hi: return None
        f5, f6 = lo+(hi-lo)*0.5, lo+(hi-lo)*0.618
        if f5 <= close <= f6:
            return {"score_extra": 2,
                    "reason": f"Fib 0.5-0.618 [{round(f5,4)}-{round(f6,4)}] ✅",
                    "fib_lo": f5, "fib_hi": f6}
    return None

# ══════════════════════════════════════════════════════════════════
#  BUILD SIGNAL
# ══════════════════════════════════════════════════════════════════
def build_signal(direction, close, atr, setup, confirmations, base):
    sl_d = max(atr * 1.8, close * 0.003)
    if sl_d == 0: return None
    if direction == "SELL":
        sl, tp1, tp2, tp3 = (close+sl_d, close-sl_d*MIN_RR,
                             close-sl_d*TARGET_RR, close-sl_d*MAX_RR)
    else:
        sl, tp1, tp2, tp3 = (close-sl_d, close+sl_d*MIN_RR,
                             close+sl_d*TARGET_RR, close+sl_d*MAX_RR)
    score = min(base + sum(c.get("score_extra",0) for c in confirmations), 10)
    reason = "\n  ✦ ".join(c["reason"] for c in confirmations if "reason" in c)
    return {"direction": direction, "setup": setup,
            "entry": round(close,6), "sl": round(sl,6),
            "tp1": round(tp1,6), "tp2": round(tp2,6), "tp3": round(tp3,6),
            "rr": round(TARGET_RR, 1), "score": score,
            "reason": "  ✦ " + reason, "atr": round(atr,6),
            "confirmations": confirmations}

# ══════════════════════════════════════════════════════════════════
#  MOTEUR SETUPS
# ══════════════════════════════════════════════════════════════════
def evaluate(candles, live_price):
    if len(candles) < 40: return []
    close = candles[-1]["c"]
    atr   = calc_atr(candles)
    if atr == 0: return []

    # Filtre bougie doji (pas de signal sur indécision)
    c    = candles[-1]
    body = abs(c["c"]-c["o"])
    rng  = c["h"]-c["l"]
    if rng > 0 and body/rng < 0.20: return []

    # Filtre volume faible
    vols = [x["v"] for x in candles[-20:] if x["v"] > 0]
    if vols and candles[-1]["v"] < (sum(vols)/len(vols))*0.4: return []

    sh, sl = find_swings(candles)
    trend  = market_structure(sh, sl)
    sigs   = []

    # ── Setup 1: Double Top ─────────────────────────────────────
    dt = check_double_top(candles, sh, sl, close)
    if dt:
        d = "SELL"
        confs = [dt] + [x for x in [
            check_choch(candles,sh,sl,trend,close),
            check_order_block(candles,d,close,atr),
            check_fib(sh,sl,close,d),
            check_engulfing(candles,d),
        ] if x and x.get("direction",d)==d]
        if len(confs) >= 2:
            s = build_signal(d, close, atr, "Double Top Confirmé", confs, 6)
            if s: sigs.append(s)

    # ── Setup 2: Double Bottom ──────────────────────────────────
    db = check_double_bottom(candles, sh, sl, close)
    if db:
        d = "BUY"
        confs = [db] + [x for x in [
            check_choch(candles,sh,sl,trend,close),
            check_order_block(candles,d,close,atr),
            check_fib(sh,sl,close,d),
            check_engulfing(candles,d),
        ] if x and x.get("direction",d)==d]
        if len(confs) >= 2:
            s = build_signal(d, close, atr, "Double Bottom Confirmé", confs, 6)
            if s: sigs.append(s)

    # ── Setup 3: CHoCH + OB [min 3 confs] ──────────────────────
    choch = check_choch(candles, sh, sl, trend, close)
    if choch:
        d  = choch["direction"]
        ob = check_order_block(candles, d, close, atr)
        if ob:
            confs = [choch, ob]
            for extra in [check_fib(sh,sl,close,d),
                          check_engulfing(candles,d),
                          check_fvg(candles,close)]:
                if extra and extra.get("direction",d)==d:
                    confs.append(extra)
            # [NEW] min 3 confirmations pour CHoCH
            if len(confs) >= 3:
                s = build_signal(d, close, atr, "CHoCH + OB", confs, 5)
                if s: sigs.append(s)

    # ── Setup 4: BOS + FVG [min 3 confs] ───────────────────────
    bos = check_bos(sh, sl, trend, close)
    fvg = check_fvg(candles, close)
    if bos and fvg and bos["direction"] == fvg["direction"]:
        d = bos["direction"]
        confs = [bos, fvg]
        for extra in [check_order_block(candles,d,close,atr),
                      check_engulfing(candles,d),
                      check_fib(sh,sl,close,d)]:
            if extra and extra.get("direction",d)==d:
                confs.append(extra)
        # [NEW] min 3 confirmations pour BOS
        if len(confs) >= 3:
            s = build_signal(d, close, atr, "BOS + FVG", confs, 5)
            if s: sigs.append(s)

    # ── Setup 5: Liq Sweep + Breaker ────────────────────────────
    sw = check_liquidity_sweep(candles, sh, sl)
    bb = check_breaker_block(candles, trend, close, atr)
    if sw and bb and sw["direction"] == bb["direction"]:
        d = sw["direction"]
        confs = [sw, bb]
        for extra in [check_fib(sh,sl,close,d),
                      check_engulfing(candles,d),
                      check_fvg(candles,close)]:
            if extra and extra.get("direction",d)==d:
                confs.append(extra)
        s = build_signal(d, close, atr, "Liq Sweep + BB", confs, 7)
        if s: sigs.append(s)

    # ── Setup 6: HH Failed ──────────────────────────────────────
    hh = check_hh_failed(candles, sh, sl, close)
    if hh:
        d = "SELL"
        confs = [hh]
        for extra in [check_order_block(candles,d,close,atr),
                      check_engulfing(candles,d)]:
            if extra: confs.append(extra)
        if len(confs) >= 2:
            s = build_signal(d, close, atr, "HH Failed + Break", confs, 5)
            if s: sigs.append(s)

    # ── Setup 7: Fakeout ────────────────────────────────────────
    fko = check_fakeout(candles, sh, sl, close)
    if fko:
        d = fko["direction"]
        confs = [fko]
        for extra in [check_order_block(candles,d,close,atr),
                      check_engulfing(candles,d)]:
            if extra: confs.append(extra)
        if len(confs) >= 2:
            s = build_signal(d, close, atr, "Fakeout Confirmé", confs, 4)
            if s: sigs.append(s)

    # ── Setup 8: CHoCH + Fib ────────────────────────────────────
    if choch:
        d = choch["direction"]
        f = check_fib(sh, sl, close, d)
        if f:
            confs = [choch, f]
            eng = check_engulfing(candles, d)
            if eng: confs.append(eng)
            if len(confs) >= 2:
                s = build_signal(d, close, atr, "CHoCH + Fib", confs, 4)
                if s: sigs.append(s)

    # Dédoublonner et trier par score décroissant
    seen, out = set(), []
    for s in sorted(sigs, key=lambda x: x["score"], reverse=True):
        k = (s["direction"], s["setup"])
        if k not in seen:
            seen.add(k)
            out.append(s)
    return out

# ══════════════════════════════════════════════════════════════════
#  SCORE GLOBAL — avec EMA + momentum + pénalité ranging
# ══════════════════════════════════════════════════════════════════
def global_score(sig, trend, vol_pct, ema20=None, ema50=None):
    close = sig["entry"]
    pts   = sig["score"] * 5   # max 50

    # Alignement tendance
    is_buy = sig["direction"] == "BUY"
    if   (is_buy and trend=="bullish") or (not is_buy and trend=="bearish"):
        pts += 10
    elif trend == "ranging":
        pts -= 5   # [NEW] pénalité ranging
    # else (contra-trend) : 0 bonus

    # [NEW] EMA 20 alignment bonus
    if ema20 is not None:
        if (is_buy and close > ema20) or (not is_buy and close < ema20):
            pts += 5

    # [NEW] EMA 50 alignment bonus
    if ema50 is not None:
        if (is_buy and close > ema50) or (not is_buy and close < ema50):
            pts += 5

    # Volatilité
    pts += min(vol_pct * 200, 15)

    # R:R bonus
    pts += min((sig["rr"] - MIN_RR) * 5, 15)

    # [NEW] Bonus multi-confirmations (3+)
    n_confs = len(sig.get("confirmations", []))
    if n_confs >= 4:
        pts += 8
    elif n_confs >= 3:
        pts += 4

    return round(min(pts, 100), 1)

# ══════════════════════════════════════════════════════════════════
#  GRAPHIQUE ANNOTÉ (dark theme)
# ══════════════════════════════════════════════════════════════════
def generate_chart(candles, sig, label, trend, score):
    if not CHART_AVAILABLE: return None
    data = candles[-CHART_CANDLES:]
    n    = len(data)

    BG    = "#0d1117"; GRID = "#1c2330"; UP_C = "#26a69a"; DN_C = "#ef5350"
    TEXT  = "#e6edf3"; ENTRY_C = "#f5c518"; SL_C = "#ff4d6d"
    TP1_C = "#4caf50"; TP2_C = "#00e676"; TP3_C = "#b9f6ca"
    is_buy   = sig["direction"] == "BUY"
    dir_col  = "#00c896" if is_buy else "#ff4d6d"

    fig, ax = plt.subplots(figsize=(14, 7), facecolor=BG)
    ax.set_facecolor(BG)

    # Bougies
    for i, c in enumerate(data):
        col = UP_C if c["c"] >= c["o"] else DN_C
        ax.plot([i, i], [c["l"], c["h"]], color=col, linewidth=0.8, zorder=2)
        body_lo = min(c["o"], c["c"])
        body_hi = max(c["o"], c["c"])
        ax.add_patch(plt.Rectangle((i-0.35, body_lo), 0.7,
                                   max(body_hi-body_lo, 1e-9),
                                   color=col, zorder=3))

    # EMA 20 et EMA 50 sur le graphique
    ema20_vals, ema50_vals = [], []
    closes_all = [c["c"] for c in data]
    if len(closes_all) >= 20:
        k20 = 2/21
        e20 = sum(closes_all[:20])/20
        ema20_vals = [None]*19
        for p in closes_all[20:]:
            e20 = p*k20 + e20*(1-k20)
            ema20_vals.append(e20)
        ema20_vals = [None]*19 + [e20 if i==0 else None for i,_ in enumerate(closes_all[20:])]
        # recalcul propre
        k20 = 2/21
        e20 = sum(closes_all[:20])/20
        ev20 = [None]*19
        for p in closes_all[20:]:
            e20 = p*k20 + e20*(1-k20)
            ev20.append(e20)
        ax.plot(range(len(ev20)), ev20,
                color="#f5c518", linewidth=0.9, alpha=0.7, linestyle="-", label="EMA20")
    if len(closes_all) >= 50:
        k50 = 2/51
        e50 = sum(closes_all[:50])/50
        ev50 = [None]*49
        for p in closes_all[50:]:
            e50 = p*k50 + e50*(1-k50)
            ev50.append(e50)
        ax.plot(range(len(ev50)), ev50,
                color="#9c27b0", linewidth=0.9, alpha=0.7, linestyle="-", label="EMA50")

    # Zones (OB / FVG / Fib) depuis confirmations
    for conf in sig.get("confirmations", []):
        if "ob_lo" in conf and "ob_hi" in conf:
            ax.axhspan(conf["ob_lo"], conf["ob_hi"],
                       alpha=0.18, color=dir_col, zorder=1)
            mid = (conf["ob_lo"]+conf["ob_hi"])/2
            ax.text(0.5, mid, " OB", transform=ax.get_yaxis_transform(),
                    color=dir_col, fontsize=7, va="center", fontweight="bold")
        if "fvg_lo" in conf and "fvg_hi" in conf:
            ax.axhspan(conf["fvg_lo"], conf["fvg_hi"],
                       alpha=0.14, color="#9c27b0", zorder=1)
            mid = (conf["fvg_lo"]+conf["fvg_hi"])/2
            ax.text(0.5, mid, " FVG", transform=ax.get_yaxis_transform(),
                    color="#ce93d8", fontsize=7, va="center")
        if "fib_lo" in conf and "fib_hi" in conf:
            ax.axhspan(conf["fib_lo"], conf["fib_hi"],
                       alpha=0.10, color="#ff9800", zorder=1)
        if "zone" in conf:
            ax.axhline(conf["zone"], color="#607d8b",
                       linewidth=0.7, linestyle=":", alpha=0.7)

    # Lignes de prix
    def hline(price, color, lbl, lw=1.2, ls="--"):
        ax.axhline(price, color=color, linewidth=lw, linestyle=ls, alpha=0.95, zorder=4)
        ax.annotate(f" {lbl}  {price}",
                    xy=(n+0.5, price), xycoords="data",
                    color=color, fontsize=8, va="center", fontweight="bold",
                    bbox=dict(boxstyle="round,pad=0.2", fc=BG, ec=color, alpha=0.85))

    hline(sig["entry"], ENTRY_C, "⚡ ENTRY", lw=2.0, ls="-")
    hline(sig["sl"],    SL_C,    "🔴 SL")
    hline(sig["tp1"],   TP1_C,   f"🎯 TP1 1:{MIN_RR:.0f}")
    hline(sig["tp2"],   TP2_C,   f"🏆 TP2 1:{TARGET_RR:.0f}")
    hline(sig["tp3"],   TP3_C,   f"💎 TP3 1:{MAX_RR:.0f}")

    # Zone colorée SL/TP
    entry = sig["entry"]
    if is_buy:
        ax.axhspan(sig["sl"], entry, alpha=0.07, color="#ff4d6d", zorder=0)
        ax.axhspan(entry, sig["tp2"], alpha=0.06, color="#00c896", zorder=0)
    else:
        ax.axhspan(entry, sig["sl"], alpha=0.07, color="#ff4d6d", zorder=0)
        ax.axhspan(sig["tp2"], entry, alpha=0.06, color="#00c896", zorder=0)

    # Flèche direction
    arrow_dy = sig["atr"] * 2.5
    if is_buy:
        ax.annotate("", xy=(n-1, sig["entry"]+arrow_dy),
                    xytext=(n-1, sig["entry"]-arrow_dy*0.4),
                    arrowprops=dict(arrowstyle="-|>", color=dir_col,
                                   lw=2.5, mutation_scale=18))
    else:
        ax.annotate("", xy=(n-1, sig["entry"]-arrow_dy),
                    xytext=(n-1, sig["entry"]+arrow_dy*0.4),
                    arrowprops=dict(arrowstyle="-|>", color=dir_col,
                                   lw=2.5, mutation_scale=18))

    dir_txt = "▲  BUY" if is_buy else "▼  SELL"
    ax.text(0.01, 0.97, dir_txt, transform=ax.transAxes,
            color=dir_col, fontsize=20, fontweight="bold", va="top")

    badge_col = "#00c896" if score >= 80 else "#f5c518" if score >= 75 else "#ff4d6d"
    ax.text(0.99, 0.97, f"Score {score}/100", transform=ax.transAxes,
            color=badge_col, fontsize=12, fontweight="bold", va="top", ha="right",
            bbox=dict(boxstyle="round,pad=0.4", fc=BG, ec=badge_col, alpha=0.9))

    te = {"bullish":"📈","bearish":"📉","ranging":"↔"}.get(trend,"")
    ax.set_title(
        f"AlphaBot v11.2 | {label} | M5 | {sig['setup']} | RR 1:{sig['rr']} | {te} {trend.upper()}",
        color=TEXT, fontsize=10, pad=8)

    ax.tick_params(colors=TEXT, labelsize=7)
    for sp in ax.spines.values(): sp.set_edgecolor(GRID)
    ax.grid(True, color=GRID, linewidth=0.5, zorder=0)
    ax.set_xlim(-1, n + 8)
    all_p = [c["l"] for c in data] + [c["h"] for c in data]
    margin = (max(all_p)-min(all_p)) * 0.18
    ax.set_ylim(min(all_p)-margin, max(all_p)+margin)
    ax.text(0.99, 0.01, datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
            transform=ax.transAxes, color="#607d8b", fontsize=7, ha="right", va="bottom")

    plt.tight_layout()
    buf = io.BytesIO()
    plt.savefig(buf, format="png", dpi=130, bbox_inches="tight",
                facecolor=BG, edgecolor="none")
    plt.close(fig)
    buf.seek(0)
    return buf.read()

# ══════════════════════════════════════════════════════════════════
#  TELEGRAM — ENVOI
# ══════════════════════════════════════════════════════════════════
def tg_post(endpoint, payload):
    url  = f"https://api.telegram.org/bot{BOT_TOKEN}/{endpoint}"
    body = json.dumps(payload).encode()
    try:
        req = urllib.request.Request(url, data=body,
              headers={"Content-Type":"application/json"}, method="POST")
        with urllib.request.urlopen(req, context=ssl_ctx, timeout=15) as r:
            resp = json.loads(r.read())
            if not resp.get("ok"):
                log.error(f"TG/{endpoint}: {resp}")
            return resp
    except Exception as e:
        log.error(f"tg_post/{endpoint}: {e}")
        return {}

def send_telegram(text, chat_id=None, reply_markup=None):
    payload = {"chat_id": chat_id or GROUP_CHAT_ID,
               "text": text, "parse_mode": "HTML",
               "disable_web_page_preview": True}
    if reply_markup:
        payload["reply_markup"] = reply_markup
    return tg_post("sendMessage", payload)

def send_photo(photo_bytes, caption="", chat_id=None, reply_markup=None):
    boundary = "AlphaBotBoundary112"
    body = b""
    def field(name, value):
        return (f"--{boundary}\r\nContent-Disposition: form-data; "
                f'name="{name}"\r\n\r\n{value}\r\n').encode()
    body += field("chat_id", chat_id or GROUP_CHAT_ID)
    body += field("parse_mode", "HTML")
    body += field("caption", caption)
    if reply_markup:
        body += field("reply_markup", json.dumps(reply_markup))
    body += (f"--{boundary}\r\nContent-Disposition: form-data; "
             f'name="photo"; filename="chart.png"\r\n'
             f"Content-Type: image/png\r\n\r\n").encode()
    body += photo_bytes
    body += f"\r\n--{boundary}--\r\n".encode()
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto"
    try:
        req = urllib.request.Request(
            url, data=body,
            headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
            method="POST")
        with urllib.request.urlopen(req, context=ssl_ctx, timeout=20) as r:
            resp = json.loads(r.read())
            if not resp.get("ok"):
                log.error(f"TG/sendPhoto: {resp}")
            return resp
    except Exception as e:
        log.error(f"send_photo: {e}")
        return {}

def answer_callback(callback_query_id, text="✅"):
    tg_post("answerCallbackQuery",
            {"callback_query_id": callback_query_id, "text": text})

def edit_message_text(chat_id, message_id, text):
    tg_post("editMessageText",
            {"chat_id": chat_id, "message_id": message_id,
             "text": text, "parse_mode": "HTML"})

# ══════════════════════════════════════════════════════════════════
#  WORKFLOW VALIDATION LEADER
# ══════════════════════════════════════════════════════════════════
def send_validation_request(sig_id, sig, label, trend, score, candles, live):
    """Envoie le graphique + résumé au LEADER en privé avec boutons inline."""
    is_buy = sig["direction"] == "BUY"
    de     = "📈🟢 BUY" if is_buy else "📉🔴 SELL"
    te     = {"bullish":"📈","bearish":"📉","ranging":"↔️"}.get(trend,"")

    rr_ok      = "✅" if sig["rr"] >= MIN_RR else "❌"
    session_ok = "✅" if is_active_session() else "⚠️"
    trend_ok   = "✅" if (is_buy and trend=="bullish") or \
                         (not is_buy and trend=="bearish") else \
                 "⚠️" if trend=="ranging" else "❌"
    score_ok   = "✅" if score >= 80 else "⚠️" if score >= 75 else "❌"
    n_confs    = len(sig.get("confirmations", []))

    validation_msg = (
        f"🔔 <b>SIGNAL EN ATTENTE — #{sig_id}</b>\n"
        f"{'═'*34}\n"
        f"📌 Marché : <b>{label}</b>\n"
        f"🔧 Setup  : {sig['setup']}\n"
        f"📊 Trend  : {te} {trend.upper()}\n"
        f"🔗 Confirmations : {n_confs}\n"
        f"⏱ M5 | Bougie FERMÉE\n"
        f"{'─'*34}\n"
        f"💰 <b>Entrée :</b> {sig['entry']}\n"
        f"🔴 <b>SL :</b>     {sig['sl']}\n"
        f"🎯 <b>TP1 (1:{MIN_RR:.0f}) :</b> {sig['tp1']}\n"
        f"🏆 <b>TP2 (1:{TARGET_RR:.0f}) :</b> {sig['tp2']}\n"
        f"💎 <b>TP3 (1:{MAX_RR:.0f}) :</b> {sig['tp3']}\n"
        f"📊 R:R  1:{sig['rr']}\n"
        f"{'─'*34}\n"
        f"🔍 <b>Confirmations :</b>\n{sig['reason']}\n"
        f"{'─'*34}\n"
        f"🧪 <b>Checklist :</b>\n"
        f"  {rr_ok} RR ≥ {MIN_RR:.0f} (actuel : 1:{sig['rr']})\n"
        f"  {trend_ok} Alignement tendance\n"
        f"  {session_ok} Session London/NY\n"
        f"  {score_ok} Score : {score}/100\n"
        f"{'─'*34}\n"
        f"💡 Live : {live}\n"
        f"⏳ Timeout auto : {VALIDATION_TIMEOUT//60} min\n"
        f"{'═'*34}\n"
        f"👇 <b>Valider ou rejeter :</b>"
    )

    keyboard = {"inline_keyboard": [[
        {"text": "✅  PUBLIER",   "callback_data": f"YES:{sig_id}"},
        {"text": "❌  ANNULER",   "callback_data": f"NO:{sig_id}"},
        {"text": "✏️  MODIFIER",  "callback_data": f"MODIFY:{sig_id}"},
    ]]}

    chart = generate_chart(candles, sig, label, trend, score) if CHART_AVAILABLE else None

    resp = {}
    if chart:
        resp = send_photo(chart, caption=validation_msg,
                          chat_id=LEADER_CHAT_ID, reply_markup=keyboard)
    else:
        resp = send_telegram(validation_msg, chat_id=LEADER_CHAT_ID,
                             reply_markup=keyboard)

    msg_id = resp.get("result", {}).get("message_id")
    pending_validation[sig_id] = {
        "sig": sig, "label": label, "trend": trend,
        "score": score, "live": live, "candles": candles,
        "ts": time.time(), "msg_id": msg_id
    }
    log.info(f"[VALIDATION] Signal #{sig_id} envoyé au leader (privé) — en attente")


def publish_signal(sig_id, executed=False):
    """Publie le signal dans le groupe après validation leader."""
    if sig_id not in pending_validation:
        return
    pd      = pending_validation.pop(sig_id)
    sig     = pd["sig"]
    label   = pd["label"]
    trend   = pd["trend"]
    score   = pd["score"]
    live    = pd["live"]
    candles = pd["candles"]
    is_buy  = sig["direction"] == "BUY"
    de      = "📈🟢 BUY" if is_buy else "📉🔴 SELL"
    te      = {"bullish":"📈","bearish":"📉","ranging":"↔️"}.get(trend,"")
    st      = "⭐" * min(int(sig["rr"]), 5)
    wk      = "\n🌙 <i>Week-end — BTC Only</i>" if is_weekend() else ""

    pub_msg = (
        f"{de} — <b>AlphaBot Signal v11.2</b> ✅\n"
        f"{'═'*32}\n"
        f"📌 <b>Marché :</b> {label}\n"
        f"🔧 <b>Setup :</b>  {sig['setup']}\n"
        f"⏱ M5 | Bougie FERMÉE ✅\n"
        f"📊 Trend : {te} {trend.upper()}\n"
        f"{'─'*32}\n"
        f"💰 <b>Entrée :</b>        {sig['entry']}\n"
        f"🔴 <b>Stop Loss :</b>     {sig['sl']}\n"
        f"🎯 <b>TP1 (1:{MIN_RR:.0f}) :</b>   {sig['tp1']}\n"
        f"🏆 <b>TP2 (1:{TARGET_RR:.0f}) :</b>   {sig['tp2']}\n"
        f"💎 <b>TP3 (1:{MAX_RR:.0f}) :</b>   {sig['tp3']}\n"
        f"📊 R:R 1:{sig['rr']}  {st}\n"
        f"{'─'*32}\n"
        f"🔍 <b>Confirmations :</b>\n{sig['reason']}\n"
        f"{'─'*32}\n"
        f"💡 Score : {score}/100 | Live : {live}"
        f"{wk}\n"
        f"{'─'*32}\n"
        f"⚠️ <i>Gestion du risque : max 1-2% du capital</i>\n"
        f"🆔 Signal <code>#{sig_id}</code>\n"
        f"🤖 <i>AlphaBot | leaderOdg</i>"
    )

    chart = generate_chart(candles, sig, label, trend, score) if CHART_AVAILABLE else None
    if chart:
        send_photo(chart, caption=pub_msg, chat_id=GROUP_CHAT_ID)
    else:
        send_telegram(pub_msg, chat_id=GROUP_CHAT_ID)

    active_signals[sig_id] = {**pd, "published_at": time.time()}
    stats["published"] += 1
    log.info(f"✅ Signal #{sig_id} PUBLIÉ dans le groupe")


def reject_signal(sig_id, reason="Annulé par le leader"):
    if sig_id not in pending_validation:
        return
    pd = pending_validation.pop(sig_id)
    stats["rejected"] += 1
    log.info(f"❌ Signal #{sig_id} REJETÉ — {reason}")
    send_telegram(
        f"❌ <b>Signal #{sig_id} annulé</b>\n"
        f"Marché : {pd['label']} | Setup : {pd['sig']['setup']}\n"
        f"Raison : {reason}",
        chat_id=LEADER_CHAT_ID
    )


def timeout_check():
    """Annule automatiquement les signaux non traités après VALIDATION_TIMEOUT."""
    while True:
        now = time.time()
        expired = [sid for sid, pd in list(pending_validation.items())
                   if now - pd["ts"] > VALIDATION_TIMEOUT]
        for sid in expired:
            reject_signal(sid, reason=f"Timeout {VALIDATION_TIMEOUT//60}min — aucune réponse")
        time.sleep(30)

# ══════════════════════════════════════════════════════════════════
#  POLLING TELEGRAM (messages + callbacks)
# ══════════════════════════════════════════════════════════════════
def get_updates():
    global last_update_id
    url = (f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates"
           f"?offset={last_update_id+1}&timeout=5")
    try:
        req = urllib.request.Request(url, headers={"User-Agent":"AlphaBot/11.2"})
        with urllib.request.urlopen(req, context=ssl_ctx, timeout=12) as r:
            data = json.loads(r.read())
        updates = data.get("result", [])
        if updates:
            last_update_id = updates[-1]["update_id"]
        return updates
    except Exception:
        return []


def handle_callback(cq):
    """Gère les clics sur les boutons inline (YES / NO / MODIFY)."""
    cb_id   = cq["id"]
    data    = cq.get("data", "")
    user    = cq.get("from", {}).get("first_name", "?")
    msg_id  = cq.get("message", {}).get("message_id")
    chat_id = cq.get("message", {}).get("chat", {}).get("id")

    if ":" not in data:
        answer_callback(cb_id, "❓ Action inconnue")
        return

    action, sig_id = data.split(":", 1)

    if action == "YES":
        if sig_id not in pending_validation:
            answer_callback(cb_id, "⚠️ Signal déjà traité ou expiré")
            return
        answer_callback(cb_id, "✅ Publication en cours…")
        if msg_id:
            edit_message_text(chat_id, msg_id,
                              f"✅ <b>Signal #{sig_id} validé par {user} — publication en cours…</b>")
        publish_signal(sig_id)

    elif action == "NO":
        if sig_id not in pending_validation:
            answer_callback(cb_id, "⚠️ Signal déjà traité ou expiré")
            return
        answer_callback(cb_id, "❌ Signal annulé")
        if msg_id:
            edit_message_text(chat_id, msg_id,
                              f"❌ <b>Signal #{sig_id} annulé par {user}</b>")
        reject_signal(sig_id, reason=f"Rejeté manuellement par {user}")

    elif action == "MODIFY":
        if sig_id not in pending_validation:
            answer_callback(cb_id, "⚠️ Signal déjà traité ou expiré")
            return
        answer_callback(cb_id, "✏️ Mode modification")
        pd  = pending_validation[sig_id]
        sig = pd["sig"]
        send_telegram(
            f"✏️ <b>Modification Signal #{sig_id}</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"Valeurs actuelles :\n"
            f"  Entrée : <code>{sig['entry']}</code>\n"
            f"  SL     : <code>{sig['sl']}</code>\n"
            f"  TP1    : <code>{sig['tp1']}</code>\n"
            f"  TP2    : <code>{sig['tp2']}</code>\n\n"
            f"Réponds avec la commande :\n"
            f"<code>/set#{sig_id} entry=X sl=Y tp1=A tp2=B</code>\n\n"
            f"Ou pour valider :\n"
            f"<code>/confirmer #{sig_id}</code>",
            chat_id=LEADER_CHAT_ID
        )


def handle_command(text, chat_id):
    """Commandes texte."""
    parts = text.strip().split()
    cmd   = parts[0].lower().split("@")[0]
    args  = parts[1:]

    # [FIX v11.3] Anti-doublon : ignore si même commande déjà traitée il y a < 8s
    _key = (chat_id, cmd)
    if time.time() - _cmd_last_time.get(_key, 0) < 8:
        log.info(f"[CMD] Doublon ignoré : {cmd} from {chat_id}")
        return
    _cmd_last_time[_key] = time.time()

    # ── /aide ─────────────────────────────────────────────────────
    if cmd in ("/aide", "/start", "/help"):
        send_telegram(
            "🤖 <b>AlphaBot v11.2 — Commandes</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "📊 <b>/analyse BTCUSDT</b> — Analyse + graphique\n"
            "📡 <b>/signal</b>          — Dernier signal actif\n"
            "🔄 <b>/update #1</b>       — Statut d'un signal\n"
            "📈 <b>/stats</b>           — Performance globale\n"
            "🕐 <b>/session</b>         — État session trading\n"
            "⏳ <b>/pending</b>         — Signaux en attente\n"
            "🤖 <i>AlphaBot v11.2 | leaderOdg</i>",
            chat_id=chat_id
        )

    # ── /session ──────────────────────────────────────────────────
    elif cmd == "/session":
        h  = datetime.now(timezone.utc).hour
        wk = is_weekend()
        send_telegram(
            f"{'🟢 SESSION ACTIVE' if is_active_session() else '🔴 HORS SESSION'}\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"🕐 UTC : <b>{h:02d}h</b>\n"
            f"🗓 Mode : {'🌙 Week-end' if wk else '📊 Semaine'}\n"
            f"London  07h–16h  {'✅' if 7<=h<16 else '❌'}\n"
            f"New York 12h–21h {'✅' if 12<=h<21 else '❌'}",
            chat_id=chat_id
        )

    # ── /pending ──────────────────────────────────────────────────
    elif cmd == "/pending":
        if not pending_validation:
            send_telegram("📭 Aucun signal en attente de validation.", chat_id=chat_id)
        else:
            lines = []
            for sid, pd in pending_validation.items():
                age = int(time.time()-pd["ts"])
                lines.append(f"  #{sid} — {pd['label']} {pd['sig']['direction']} "
                             f"| score {pd['score']} | {age}s")
            send_telegram(
                f"⏳ <b>{len(pending_validation)} signal(s) en attente</b>\n"
                + "\n".join(lines), chat_id=chat_id)

    # ── /signal ───────────────────────────────────────────────────
    elif cmd == "/signal":
        if not active_signals:
            send_telegram("📭 Aucun signal publié actif.", chat_id=chat_id)
        else:
            sid, pd = list(active_signals.items())[-1]
            sig  = pd["sig"]
            sym  = [s for s,m in SYMBOL_MAP.items() if m["label"]==pd["label"]]
            live = fetch_live_price(sym[0]) if sym else "?"
            send_telegram(
                f"📡 <b>Dernier signal #{sid}</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━━━\n"
                f"Marché : {pd['label']} | {sig['direction']}\n"
                f"Entrée : {sig['entry']} | Live : {live}\n"
                f"SL : {sig['sl']} | TP2 : {sig['tp2']}\n"
                f"Setup : {sig['setup']}",
                chat_id=chat_id
            )

    # ── /update #id ───────────────────────────────────────────────
    elif cmd == "/update":
        sid = (args[0].replace("#","") if args else "")
        if not sid or sid not in active_signals:
            send_telegram(f"❌ Signal #{sid} introuvable.", chat_id=chat_id)
            return
        pd   = active_signals[sid]
        sig  = pd["sig"]
        sym  = [s for s,m in SYMBOL_MAP.items() if m["label"]==pd["label"]]
        live = fetch_live_price(sym[0]) if sym else None
        if not live:
            send_telegram("⚠️ Prix live indisponible.", chat_id=chat_id)
            return
        is_buy = sig["direction"] == "BUY"
        sl_hit = (is_buy and live <= sig["sl"]) or (not is_buy and live >= sig["sl"])
        tp1_ok = (is_buy and live >= sig["tp1"]) or (not is_buy and live <= sig["tp1"])
        tp2_ok = (is_buy and live >= sig["tp2"]) or (not is_buy and live <= sig["tp2"])
        if sl_hit:     status = "❌ <b>SL TOUCHÉ</b>"
        elif tp2_ok:   status = "🏆 <b>TP2 ATTEINT !</b>"
        elif tp1_ok:   status = "🎯 <b>TP1 ATTEINT — passer en BE</b>"
        else:
            pct = round(abs(live-sig["entry"])/max(abs(sig["tp2"]-sig["entry"]),1e-9)*100,1)
            status = f"🔄 En cours ({pct}% vers TP2)"
        send_telegram(
            f"🔄 <b>Update #{sid} — {pd['label']}</b>\n"
            f"Live : <b>{live}</b> | {status}\n"
            f"Entrée : {sig['entry']} | SL : {sig['sl']} | TP2 : {sig['tp2']}",
            chat_id=chat_id
        )

    # ── /stats ────────────────────────────────────────────────────
    elif cmd == "/stats":
        total = stats["total"]
        pub   = stats["published"]
        rej   = stats["rejected"]
        tp    = stats["tp"]
        sl_n  = stats["sl"]
        wr    = round(tp/pub*100,1) if pub > 0 else 0
        rr_m  = round(stats["rr_sum"]/tp,2) if tp > 0 else 0
        send_telegram(
            f"📊 <b>Performance AlphaBot v11.2</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"🔢 Signaux détectés : {total}\n"
            f"✅ Publiés          : {pub}\n"
            f"❌ Rejetés          : {rej}\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"🏆 TP atteints      : {tp}\n"
            f"🛑 SL touchés       : {sl_n}\n"
            f"📈 Winrate          : <b>{wr}%</b>\n"
            f"💰 RR moyen         : <b>1:{rr_m}</b>\n"
            f"🤖 <i>leaderOdg — AlphaBot v11.2</i>",
            chat_id=chat_id
        )

    # ── /confirmer #id ────────────────────────────────────────────
    elif cmd.startswith("/confirmer"):
        sid = (args[0].replace("#","") if args else "")
        if sid in pending_validation:
            publish_signal(sid)
            send_telegram(f"✅ Signal #{sid} publié.", chat_id=chat_id)
        else:
            send_telegram(f"❌ Signal #{sid} introuvable.", chat_id=chat_id)

    # ── /set#id entry=X sl=Y tp1=A tp2=B ─────────────────────────
    elif cmd.startswith("/set#"):
        sid = cmd.replace("/set#","")
        if sid not in pending_validation:
            send_telegram(f"❌ Signal #{sid} introuvable.", chat_id=chat_id)
            return
        pd  = pending_validation[sid]
        sig = pd["sig"]
        for arg in args:
            if "=" in arg:
                key, val = arg.split("=", 1)
                try:
                    sig[key.strip()] = float(val.strip())
                except ValueError:
                    pass
        pending_validation[sid]["sig"] = sig
        send_telegram(
            f"✏️ Signal #{sid} modifié :\n"
            f"Entrée : {sig['entry']} | SL : {sig['sl']}\n"
            f"TP1 : {sig['tp1']} | TP2 : {sig['tp2']}\n\n"
            f"→ <code>/confirmer #{sid}</code> pour publier",
            chat_id=chat_id
        )

    # ── /analyse SYMBOL ───────────────────────────────────────────
    elif cmd == "/analyse":
        symbol = (args[0].upper() if args else "BTCUSDT")
        if not symbol.endswith("USDT"): symbol += "USDT"
        label  = SYMBOL_MAP.get(symbol, {}).get("label", symbol)
        # [FIX v11.3] PAS de message "en cours" — un seul message final
        candles = fetch_candles_m5(symbol, limit=CANDLE_LIMIT)
        if not candles or len(candles) < 40:
            send_telegram(f"❌ Données insuffisantes pour {symbol}.", chat_id=chat_id)
            return
        close   = candles[-1]["c"]
        atr     = calc_atr(candles)
        sh, sl  = find_swings(candles)
        trend   = market_structure(sh, sl)
        vol_pct = (atr/close*100) if close > 0 else 0
        live    = fetch_live_price(symbol) or close
        ema20   = calc_ema(candles, 20)
        ema50   = calc_ema(candles, 50)
        te      = {"bullish":"📈 BULLISH","bearish":"📉 BEARISH","ranging":"↔️ RANGING"}.get(trend,trend)
        key_h   = round(sh[-1]["price"],4) if sh else "N/A"
        key_l   = round(sl[-1]["price"],4) if sl else "N/A"
        fvg     = check_fvg(candles, close)
        ob_b    = check_order_block(candles, "BUY",  close, atr)
        ob_s    = check_order_block(candles, "SELL", close, atr)
        zones   = ""
        if fvg:  zones += f"\n  ✦ {fvg['reason']}"
        if ob_b: zones += f"\n  ✦ {ob_b['reason']}"
        if ob_s: zones += f"\n  ✦ {ob_s['reason']}"
        sigs     = evaluate(candles, live)
        ema_txt  = f"\n  EMA20 : {round(ema20,4) if ema20 else 'N/A'} | EMA50 : {round(ema50,4) if ema50 else 'N/A'}"
        if sigs:
            best  = max(sigs, key=lambda x: global_score(x, trend, vol_pct, ema20, ema50))
            score = global_score(best, trend, vol_pct, ema20, ema50)
            note  = f"\n\n🎯 <b>Setup détecté :</b> {best['setup']} (score {score}/100)"
            chart = generate_chart(candles, best, label, trend, score) if CHART_AVAILABLE else None
        else:
            note  = "\n\n⏳ Aucun setup actif"
            chart = None
        msg = (
            f"📊 <b>Analyse {label} M5</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"💹 Prix live : <b>{live}</b>\n"
            f"📈 Structure : <b>{te}</b>\n"
            f"📊 ATR M5   : {round(atr,4)} ({round(vol_pct,3)}%)"
            f"{ema_txt}\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"🔑 <b>Zones clés :</b>\n"
            f"  Résistance : {key_h}\n"
            f"  Support    : {key_l}"
            f"{zones}{note}\n"
            f"🤖 <i>AlphaBot v11.2 | leaderOdg</i>"
        )
        if chart:
            send_photo(chart, caption=msg, chat_id=chat_id)
        else:
            send_telegram(msg, chat_id=chat_id)


def poll_loop():
    """Thread unique — gère messages ET callback queries."""
    while True:
        try:
            updates = get_updates()
            for upd in updates:
                if "callback_query" in upd:
                    try:
                        handle_callback(upd["callback_query"])
                    except Exception as e:
                        log.error(f"[CB] {e}")
                msg = upd.get("message") or upd.get("channel_post")
                if msg:
                    text = msg.get("text","")
                    cid  = str(msg.get("chat",{}).get("id",""))
                    if text.startswith("/"):
                        log.info(f"[CMD] {text} from {cid}")
                        try:
                            handle_command(text, cid)
                        except Exception as e:
                            log.error(f"[CMD] {e}")
        except Exception as e:
            log.error(f"poll_loop: {e}")
        time.sleep(2)

# ══════════════════════════════════════════════════════════════════
#  BINANCE LIVE TRADING
# ══════════════════════════════════════════════════════════════════
BINANCE_TRADABLE = {"BTCUSDT","ETHUSDT","SOLUSDT","BNBUSDT",
                    "XRPUSDT","DOGEUSDT","ADAUSDT","LINKUSDT"}

def _sign(params):
    q = urllib.parse.urlencode(params)
    return q + "&signature=" + hmac.new(
        BINANCE_API_SECRET.encode(), q.encode(), hashlib.sha256).hexdigest()

def b_post(path, params):
    params.update({"timestamp": int(time.time()*1000), "recvWindow": 5000})
    body = _sign(params).encode()
    try:
        req = urllib.request.Request(
            f"https://fapi.binance.com{path}", data=body,
            headers={"X-MBX-APIKEY": BINANCE_API_KEY,
                     "Content-Type": "application/x-www-form-urlencoded"}, method="POST")
        with urllib.request.urlopen(req, context=ssl_ctx, timeout=10) as r:
            return json.loads(r.read())
    except Exception as e:
        log.error(f"b_post {path}: {e}"); return None

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
        log.error(f"b_get {path}: {e}"); return None

def get_balance():
    data = b_get("/fapi/v2/balance")
    if not data: return 0.0
    for a in data:
        if a.get("asset") == "USDT": return float(a.get("availableBalance", 0))
    return 0.0

def get_prec(symbol):
    try:
        req = urllib.request.Request("https://fapi.binance.com/fapi/v1/exchangeInfo",
                                     headers={"User-Agent":"AlphaBot/11.2"})
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

def place_order(sig, symbol):
    if symbol not in BINANCE_TRADABLE: return False
    if not LIVE_TRADING:
        log.info(f"[PAPER] {sig['direction']} {symbol} @ {sig['entry']}"); return True
    bal = get_balance()
    if bal < 5: return False
    sl_d = abs(sig["entry"]-sig["sl"])
    if sl_d == 0: return False
    pp, ss = get_prec(symbol)
    qty = rs((bal * RISK_PER_TRADE_PCT/100 / sl_d) * USE_LEVERAGE, ss)
    if qty <= 0: return False
    side = sig["direction"]
    cl   = "SELL" if side=="BUY" else "BUY"
    b_post("/fapi/v1/leverage", {"symbol": symbol, "leverage": USE_LEVERAGE})
    r = b_post("/fapi/v1/order", {"symbol":symbol,"side":side,"type":"MARKET","quantity":qty})
    if not r or "orderId" not in r: return False
    time.sleep(0.5)
    b_post("/fapi/v1/order", {"symbol":symbol,"side":cl,"type":"STOP_MARKET",
                               "stopPrice":round(sig["sl"],pp),"closePosition":"true",
                               "timeInForce":"GTC"})
    b_post("/fapi/v1/order", {"symbol":symbol,"side":cl,"type":"TAKE_PROFIT_MARKET",
                               "stopPrice":round(sig["tp2"],pp),"closePosition":"true",
                               "timeInForce":"GTC"})
    return True

# ══════════════════════════════════════════════════════════════════
#  HELPERS
# ══════════════════════════════════════════════════════════════════
def is_cooldown(symbol):
    return (time.time() - last_signal_time.get(symbol, 0)) < SIGNAL_COOLDOWN

def set_cooldown(symbol):
    last_signal_time[symbol] = time.time()

# ══════════════════════════════════════════════════════════════════
#  PROCESS SYMBOLE
# ══════════════════════════════════════════════════════════════════
def process_symbol(market):
    global signal_count
    symbol = market["symbol"]
    label  = market["label"]
    if is_cooldown(symbol): return
    if not is_active_session(): return

    live = fetch_live_price(symbol)
    if live is None: return

    now    = int(time.time())
    c_open = now - (now % 300)
    state  = symbol_state.setdefault(symbol, {"last": 0})
    if c_open <= state["last"]: return

    candles = fetch_candles_m5(symbol)
    if not candles or len(candles) < 50: return
    state["last"] = c_open

    close   = candles[-1]["c"]
    atr     = calc_atr(candles)
    vol_pct = (atr / close * 100) if close > 0 else 0
    sh, sl  = find_swings(candles)
    trend   = market_structure(sh, sl)

    # [NEW] Calcul EMA pour le scoring
    ema20 = calc_ema(candles, 20)
    ema50 = calc_ema(candles, 50)

    log.info(f"[{symbol}] M5 | close={close} trend={trend} ATR%={vol_pct:.3f} "
             f"EMA20={round(ema20,2) if ema20 else 'N/A'} EMA50={round(ema50,2) if ema50 else 'N/A'}")

    sigs = evaluate(candles, live)
    if not sigs: return

    for sig in sigs:
        score = global_score(sig, trend, vol_pct, ema20, ema50)
        log.info(f"[{symbol}] {sig['setup']} | {sig['direction']} | score={score} | confs={len(sig['confirmations'])}")
        if score < MIN_SCORE_LIVE:
            continue

        signal_count += 1
        sig_id = str(signal_count)
        stats["total"] += 1

        if LIVE_TRADING and score >= MIN_SCORE_LIVE:
            place_order(sig, symbol)

        send_validation_request(sig_id, sig, label, trend, score, candles, live)
        set_cooldown(symbol)
        break

# ══════════════════════════════════════════════════════════════════
#  FLASK HEALTH SERVER — Render.com exige un port ouvert
# ══════════════════════════════════════════════════════════════════
def run_health_server():
    """
    Mini serveur Flask sur le port Render (env PORT ou 10000).
    Expose / et /health pour les health checks de Render.
    Tourne dans un thread daemon séparé — n'impacte pas le bot.
    """
    if not FLASK_AVAILABLE:
        log.warning("Flask absent — health server désactivé → pip install flask")
        return

    app = Flask("AlphaBot-Health")

    @app.route("/")
    def index():
        return jsonify({
            "status": "running",
            "bot": "AlphaBot Signal v11.2",
            "author": "leaderOdg",
            "signals_total": stats.get("total", 0),
            "signals_published": stats.get("published", 0),
            "pending": len(pending_validation),
            "active": len(active_signals),
            "mode": "LIVE" if LIVE_TRADING else "Paper",
        })

    @app.route("/health")
    def health():
        return jsonify({"ok": True}), 200

    @app.route("/stats")
    def api_stats():
        return jsonify(stats)

    port = int(os.environ.get("PORT", 10000))
    log.info(f"🌐 Health server Flask démarré sur port {port}")
    # use_reloader=False obligatoire (déjà dans un thread)
    app.run(host="0.0.0.0", port=port, use_reloader=False, debug=False)


# ══════════════════════════════════════════════════════════════════
#  MAIN
# ══════════════════════════════════════════════════════════════════
def main():
    log.info("╔══════════════════════════════════════════════════╗")
    log.info("║  AlphaBot Signal v11.3 — VALIDATION LEADER      ║")
    log.info("║  📸 Chart | EMA20/50 | ✅ Boutons | 🔄 Monitor  ║")
    log.info("║  🔧 [FIX] 1 msg /analyse | Anti-doublon cmds   ║")
    log.info("╚══════════════════════════════════════════════════╝")

    if not CHART_AVAILABLE:
        log.warning("matplotlib absent — graphiques désactivés → pip install matplotlib")

    wk = is_weekend()
    send_telegram(
        f"🤖 <b>AlphaBot v11.3 DÉMARRÉ</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"⚡ Scan M5 | Score ≥{MIN_SCORE_LIVE} | Min 3 confirmations\n"
        f"✅ Mode : <b>VALIDATION LEADER</b> (privé → groupe)\n"
        f"🔧 [FIX] /analyse = 1 seul message | Anti-doublon cmds\n"
        f"📸 Graphiques : {'✅ (EMA20/50 inclus)' if CHART_AVAILABLE else '❌ (pip install matplotlib)'}\n"
        f"⏳ Timeout validation : {VALIDATION_TIMEOUT//60} min\n"
        f"🗓 {'🌙 Week-end → BTC Only' if wk else '📊 Semaine → Tous marchés'}\n"
        f"💹 {'🟢 LIVE TRADING' if LIVE_TRADING else '🟡 Paper Mode'}\n"
        f"🔧 Cooldown : {SIGNAL_COOLDOWN//60} min/symbole\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"Commandes : /aide | /analyse | /stats | /pending\n"
        f"🤖 <i>leaderOdg — AlphaBot v11.3</i>",
        chat_id=LEADER_CHAT_ID
    )

    threading.Thread(target=poll_loop,        daemon=True, name="TgPoll").start()
    threading.Thread(target=timeout_check,    daemon=True, name="Timeout").start()
    threading.Thread(target=run_health_server, daemon=True, name="Flask").start()
    log.info("🧵 Threads démarrés : polling + timeout + health server")

    while True:
        try:
            mkts = active_markets()
            for m in sorted(mkts, key=lambda x: x["priority"]):
                try:
                    process_symbol(m)
                except Exception as e:
                    log.error(f"[{m['symbol']}] {e}")
                time.sleep(0.3)
        except Exception as e:
            log.error(f"Boucle: {e}")
        time.sleep(POLL_INTERVAL_SEC)

if __name__ == "__main__":
    main()

