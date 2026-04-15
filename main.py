
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
╔══════════════════════════════════════════════════════════════════╗
║         AlphaBot Signal v9.3 — by leaderOdg                    ║
║  ⚡ Scan LIVE 3s | Confirmation bougie M1 fermée               ║
║  📊 ICT/SMC | RR 1:3-5 | BTC + Gold Only                      ║
║  🔧 v9.3 — Filtre HTF M15 | Score 75+ | Cooldown 30min        ║
║  ✅ FIXES: suppression Fakeout doublon, confluence 2+,         ║
║            filtre tendance HTF, 1 signal/cycle max             ║
╚══════════════════════════════════════════════════════════════════╝

CHANGELOG v9.2 → v9.3:
  [FIX] Suppression check_fakeout (doublon de check_liquidity_sweep)
  [FIX] Confluence minimum 2 confirmations obligatoires
  [FIX] Filtre HTF M15 : direction doit être alignée avec M15
  [FIX] 1 seul signal par cycle (meilleur score uniquement)
  [FIX] MIN_SCORE_LIVE 65 → 75
  [FIX] SIGNAL_COOLDOWN 600s → 1800s (30 min)
  [FIX] MIN_SCORE_EMIT 45 → 60 (seuil envoi Telegram)
  [NEW] fetch_candles_htf() pour M15
  [NEW] global_score +15 si aligné HTF (au lieu de +10)
"""

import time
import json
import logging
import ssl
import hashlib
import hmac
import urllib.request
import urllib.parse
from datetime import datetime, timezone

BOT_TOKEN          = "8665812395:AAFO4BMTIrBCQJYVL8UytO028TcB1sDfgbI"
CHAT_ID            = "-1002335466840"
BINANCE_API_KEY    = "VOTRE_API_KEY"
BINANCE_API_SECRET = "VOTRE_API_SECRET"
LIVE_TRADING       = False
RISK_PER_TRADE_PCT = 1.0
USE_LEVERAGE       = 10

# ─── PARAMÈTRES CRITIQUES (modifiés v9.3) ─────────────
MIN_SCORE_LIVE     = 75    # v9.2: 65 → v9.3: 75
MIN_SCORE_EMIT     = 60    # v9.2: 45 → v9.3: 60 (seuil envoi Telegram)
SIGNAL_COOLDOWN    = 1800  # v9.2: 600s → v9.3: 1800s (30 min)
MIN_CONFIRMATIONS  = 2     # v9.3: confluence obligatoire
# ──────────────────────────────────────────────────────

POLL_INTERVAL_SEC  = 3
CANDLE_LIMIT       = 150
MIN_RR             = 3.0
TARGET_RR          = 4.0
MAX_RR             = 5.0

ALL_MARKETS = [
    {"symbol": "BTCUSDT",  "label": "BTC/USDT",  "pip": 0.1,  "priority": 1},
    {"symbol": "XAUUSDT",  "label": "XAU/USDT",  "pip": 0.01, "priority": 2},
]
WEEKEND_MARKETS = ALL_MARKETS  # BTC + Gold actifs même le week-end

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s [%(levelname)s] %(message)s",
                    datefmt="%H:%M:%S")
log = logging.getLogger("AlphaBot")

ssl_ctx = ssl.create_default_context()
ssl_ctx.check_hostname = False
ssl_ctx.verify_mode    = ssl.CERT_NONE

last_signal_time = {}
signal_count     = 0
symbol_state     = {}

# ─── FETCH ───────────────────────────────────────────

def fetch_candles_m1(symbol):
    """Récupère les bougies M1 fermées (timeframe principal)."""
    url = (f"https://fapi.binance.com/fapi/v1/klines"
           f"?symbol={symbol}&interval=1m&limit={CANDLE_LIMIT+1}")
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "AlphaBot/9.3"})
        with urllib.request.urlopen(req, context=ssl_ctx, timeout=8) as r:
            data = json.loads(r.read())
        candles = [{"t": int(c[0])//1000, "o": float(c[1]),
                    "h": float(c[2]), "l": float(c[3]),
                    "c": float(c[4]), "v": float(c[5])} for c in data]
        return candles[:-1]  # retire bougie en cours
    except Exception as e:
        log.warning(f"[{symbol}] fetch_candles_m1: {e}")
        return []

def fetch_candles_htf(symbol, interval="15m", limit=60):
    """
    [v9.3 NEW] Récupère les bougies HTF (M15 par défaut) pour le filtre de tendance.
    On prend 60 bougies M15 = 15 heures de contexte.
    """
    url = (f"https://fapi.binance.com/fapi/v1/klines"
           f"?symbol={symbol}&interval={interval}&limit={limit+1}")
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "AlphaBot/9.3"})
        with urllib.request.urlopen(req, context=ssl_ctx, timeout=8) as r:
            data = json.loads(r.read())
        candles = [{"t": int(c[0])//1000, "o": float(c[1]),
                    "h": float(c[2]), "l": float(c[3]),
                    "c": float(c[4]), "v": float(c[5])} for c in data]
        return candles[:-1]
    except Exception as e:
        log.warning(f"[{symbol}] fetch_candles_htf({interval}): {e}")
        return []

def fetch_live_price(symbol):
    url = f"https://fapi.binance.com/fapi/v1/ticker/price?symbol={symbol}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "AlphaBot/9.3"})
        with urllib.request.urlopen(req, context=ssl_ctx, timeout=4) as r:
            return float(json.loads(r.read())["price"])
    except Exception as e:
        log.warning(f"[{symbol}] live_price: {e}")
        return None

def is_weekend():
    return datetime.now(timezone.utc).weekday() >= 5

def active_markets():
    return WEEKEND_MARKETS if is_weekend() else ALL_MARKETS

# ─── ANALYSE ─────────────────────────────────────────

def find_swings(candles, lb=5):
    n  = len(candles)
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
    """Détermine la tendance à partir des swings."""
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

# ─── PATTERNS (bougies FERMÉES) ──────────────────────

def check_double_top(candles, sh, sl, close):
    if len(sh) < 2: return None
    n = len(candles)
    h1, h2 = sh[-2], sh[-1]
    if h1["idx"] < n-60 or h2["idx"] < n-20: return None
    if abs(h1["price"]-h2["price"])/h1["price"] > 0.0006: return None
    midlows = [s for s in sl if h1["idx"] < s["idx"] < h2["idx"]]
    if not midlows: return None
    neck = min(midlows, key=lambda x: x["price"])["price"]
    if close < neck:
        return {"direction": "SELL", "score_extra": 4,
                "reason": f"Double Top @ {round(max(h1['price'],h2['price']),4)} | Neck {round(neck,4)} ✅"}
    return None

def check_double_bottom(candles, sh, sl, close):
    if len(sl) < 2: return None
    n = len(candles)
    l1, l2 = sl[-2], sl[-1]
    if l1["idx"] < n-60 or l2["idx"] < n-20: return None
    if abs(l1["price"]-l2["price"])/l1["price"] > 0.0006: return None
    midhighs = [s for s in sh if l1["idx"] < s["idx"] < l2["idx"]]
    if not midhighs: return None
    neck = max(midhighs, key=lambda x: x["price"])["price"]
    if close > neck:
        return {"direction": "BUY", "score_extra": 4,
                "reason": f"Double Bottom @ {round(min(l1['price'],l2['price']),4)} | Neck {round(neck,4)} ✅"}
    return None

def check_choch(candles, sh, sl, trend, close):
    if trend == "bullish" and len(sl) >= 2:
        lvl = sl[-2]["price"]
        if close < lvl:
            return {"direction": "SELL", "score_extra": 3,
                    "reason": f"CHoCH baissier — close {round(close,4)} < HL {round(lvl,4)} ✅"}
    if trend == "bearish" and len(sh) >= 2:
        lvl = sh[-2]["price"]
        if close > lvl:
            return {"direction": "BUY", "score_extra": 3,
                    "reason": f"CHoCH haussier — close {round(close,4)} > LH {round(lvl,4)} ✅"}
    return None

def check_bos(sh, sl, trend, close):
    if trend == "bullish" and sh:
        lvl = sh[-1]["price"]
        if close > lvl:
            return {"direction": "BUY", "score_extra": 3,
                    "reason": f"BOS haussier @ {round(lvl,4)} ✅"}
    if trend == "bearish" and sl:
        lvl = sl[-1]["price"]
        if close < lvl:
            return {"direction": "SELL", "score_extra": 3,
                    "reason": f"BOS baissier @ {round(lvl,4)} ✅"}
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
                            "reason": f"OB bearish [{round(c['l'],4)}-{round(c['h'],4)}] ✅"}
        if direction == "BUY" and c["c"] < c["o"]:
            fut = [window[j]["h"] for j in range(i+1, min(i+5, len(window)))]
            if fut and max(fut) > c["h"] + atr:
                if c["l"] <= close <= c["h"]:
                    return {"score_extra": 3,
                            "reason": f"OB bullish [{round(c['l'],4)}-{round(c['h'],4)}] ✅"}
    return None

def check_fvg(candles, close):
    for i in range(2, len(candles[-30:])):
        w = candles[-30:]
        c0, c2 = w[i-2], w[i]
        gb = c2["l"] - c0["h"]
        gs = c0["l"] - c2["h"]
        if gb > 0 and c0["h"] <= close <= c2["l"]:
            return {"direction": "BUY", "score_extra": 3,
                    "reason": f"FVG bullish [{round(c0['h'],4)}-{round(c2['l'],4)}] ✅"}
        if gs > 0 and c2["h"] <= close <= c0["l"]:
            return {"direction": "SELL", "score_extra": 3,
                    "reason": f"FVG bearish [{round(c2['h'],4)}-{round(c0['l'],4)}] ✅"}
    return None

def check_liquidity_sweep(candles, sh, sl):
    """
    Sweep de liquidité : la bougie précédente perce un niveau clé,
    la bougie actuelle fermée le récupère (rejection confirmée).
    NOTE v9.3 : check_fakeout SUPPRIMÉ (doublon identique de cette fonction).
    """
    if len(candles) < 3: return None
    p, c = candles[-2], candles[-1]
    if sl:
        lvl = sl[-1]["price"]
        if p["l"] < lvl and c["c"] > lvl:
            return {"direction": "BUY", "score_extra": 4,
                    "reason": f"Liq Sweep BUY @ {round(lvl,4)} ✅"}
    if sh:
        lvl = sh[-1]["price"]
        if p["h"] > lvl and c["c"] < lvl:
            return {"direction": "SELL", "score_extra": 4,
                    "reason": f"Liq Sweep SELL @ {round(lvl,4)} ✅"}
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
                        "reason": f"Breaker Block SELL retest [{round(z['bot'],4)}-{round(z['top'],4)}] ✅"}
    if trend == "bullish":
        for z in reversed(demand):
            if z["top"]*0.999 < close < z["top"]*1.007:
                return {"direction": "BUY", "score_extra": 4,
                        "reason": f"Breaker Block BUY retest [{round(z['bot'],4)}-{round(z['top'],4)}] ✅"}
    return None

def check_hh_failed(candles, sh, sl, close):
    if len(sh) < 3 or not sl: return None
    if sh[-1]["price"] < sh[-2]["price"]:
        hl = sl[-1]["price"]
        if close < hl:
            return {"direction": "SELL", "score_extra": 4,
                    "reason": (f"HH Failed {round(sh[-2]['price'],4)}→{round(sh[-1]['price'],4)} "
                               f"| HL {round(hl,4)} cassé ✅")}
    return None

def check_fib(sh, sl, close, direction):
    if direction == "BUY" and sh and sl:
        lo, hi = sl[-1]["price"], sh[-1]["price"]
        if hi <= lo: return None
        f5, f6 = hi-(hi-lo)*0.5, hi-(hi-lo)*0.618
        if f6 <= close <= f5:
            return {"score_extra": 2, "reason": f"Fib 0.5-0.618 [{round(f6,4)}-{round(f5,4)}] ✅"}
    if direction == "SELL" and sh and sl:
        lo, hi = sl[-1]["price"], sh[-1]["price"]
        if lo >= hi: return None
        f5, f6 = lo+(hi-lo)*0.5, lo+(hi-lo)*0.618
        if f5 <= close <= f6:
            return {"score_extra": 2, "reason": f"Fib 0.5-0.618 [{round(f5,4)}-{round(f6,4)}] ✅"}
    return None

# ─── CONSTRUCTION SIGNAL ─────────────────────────────

def build_signal(direction, close, atr, setup, confirmations, base):
    """
    [v9.3 FIX] Confluence obligatoire : MIN_CONFIRMATIONS = 2.
    Un signal avec une seule confirmation est rejeté immédiatement.
    """
    if len(confirmations) < MIN_CONFIRMATIONS:
        return None  # ← NOUVEAU : rejette les signaux faibles
    sl_d  = max(atr * 1.8, close * 0.003)
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
            "nb_confirmations": len(confirmations)}

# ─── MOTEUR SETUPS ───────────────────────────────────

def evaluate(candles, live_price, htf_trend="ranging"):
    """
    [v9.3] Nouveau paramètre htf_trend (tendance M15).
    Filtre : si HTF n'est pas ranging, rejette les signaux contre-tendance.
    Setup 7 (Fakeout) SUPPRIMÉ — doublon de Liq Sweep.
    """
    if len(candles) < 40: return []
    close = candles[-1]["c"]
    atr   = calc_atr(candles)
    if atr == 0: return []

    # Filtre doji
    c = candles[-1]
    body = abs(c["c"]-c["o"])
    rng  = c["h"]-c["l"]
    if rng > 0 and body/rng < 0.20: return []

    # Filtre volume faible
    vols = [x["v"] for x in candles[-20:] if x["v"] > 0]
    if vols and candles[-1]["v"] < (sum(vols)/len(vols))*0.4: return []

    sh, sl = find_swings(candles)
    trend  = market_structure(sh, sl)
    sigs   = []

    def aligned_with_htf(direction):
        """
        [v9.3 NEW] Vérifie que la direction est alignée avec la tendance HTF.
        Si HTF = ranging, on accepte toutes les directions.
        Si HTF = bullish, on rejette les SELL.
        Si HTF = bearish, on rejette les BUY.
        Exception : CHoCH (renversement) est autorisé même contre HTF.
        """
        if htf_trend == "ranging":
            return True
        if htf_trend == "bullish" and direction == "SELL":
            return False
        if htf_trend == "bearish" and direction == "BUY":
            return False
        return True

    def try_add(direction, setup, base, confirmations):
        """Construit et ajoute un signal si valide et aligné HTF."""
        if not aligned_with_htf(direction):
            log.debug(f"[HTF FILTER] {setup} {direction} rejeté (HTF={htf_trend})")
            return
        s = build_signal(direction, close, atr, setup, confirmations, base)
        if s: sigs.append(s)

    # ─ Setup 1: Double Top confirmé ──────────────────
    dt = check_double_top(candles, sh, sl, close)
    if dt:
        confs = [dt]
        for extra in [check_choch(candles, sh, sl, trend, close),
                      check_order_block(candles, "SELL", close, atr),
                      check_fib(sh, sl, close, "SELL")]:
            if extra and extra.get("direction", "SELL") == "SELL":
                confs.append(extra)
        try_add("SELL", "Double Top", 5, confs)

    # ─ Setup 2: Double Bottom confirmé ───────────────
    db = check_double_bottom(candles, sh, sl, close)
    if db:
        confs = [db]
        for extra in [check_choch(candles, sh, sl, trend, close),
                      check_order_block(candles, "BUY", close, atr),
                      check_fib(sh, sl, close, "BUY")]:
            if extra and extra.get("direction", "BUY") == "BUY":
                confs.append(extra)
        try_add("BUY", "Double Bottom", 5, confs)

    # ─ Setup 3: CHoCH + OB ───────────────────────────
    # CHoCH = renversement de tendance → autorisé même contre HTF (pas de filtre HTF ici)
    choch = check_choch(candles, sh, sl, trend, close)
    if choch:
        d  = choch["direction"]
        ob = check_order_block(candles, d, close, atr)
        if ob:
            confs = [choch, ob]
            f = check_fib(sh, sl, close, d)
            if f: confs.append(f)
            # CHoCH = renversement de tendance, pas de filtre HTF intentionnel
            s = build_signal(d, close, atr, "CHoCH + OB", confs, 5)
            if s: sigs.append(s)

    # ─ Setup 4: BOS + FVG ────────────────────────────
    bos = check_bos(sh, sl, trend, close)
    fvg = check_fvg(candles, close)
    if bos and fvg and bos["direction"] == fvg["direction"]:
        confs = [bos, fvg]
        ob = check_order_block(candles, bos["direction"], close, atr)
        if ob: confs.append(ob)
        try_add(bos["direction"], "BOS + FVG", 5, confs)

    # ─ Setup 5: Liq Sweep + Breaker Block ────────────
    sw = check_liquidity_sweep(candles, sh, sl)
    bb = check_breaker_block(candles, trend, close, atr)
    if sw and bb and sw["direction"] == bb["direction"]:
        confs = [sw, bb]
        f = check_fib(sh, sl, close, sw["direction"])
        if f: confs.append(f)
        try_add(sw["direction"], "Liq Sweep + BB", 6, confs)

    # ─ Setup 6: HH Failed ────────────────────────────
    hh = check_hh_failed(candles, sh, sl, close)
    if hh:
        confs = [hh]
        ob = check_order_block(candles, "SELL", close, atr)
        if ob: confs.append(ob)
        # HH Failed nécessite OB pour la confluence minimale
        try_add("SELL", "HH Failed", 5, confs)

    # ─ Setup 7: Fakeout — SUPPRIMÉ v9.3 ─────────────
    # Raison : doublon exact de check_liquidity_sweep.
    # Résultat v9.2 : ~40% des trades, winrate catastrophique.
    # check_fakeout() retirée du code.

    # ─ Setup 8: CHoCH + Fib ──────────────────────────
    if choch:
        d = choch["direction"]
        f = check_fib(sh, sl, close, d)
        if f:
            # CHoCH seul + Fib = 2 confirmations → OK pour confluence
            s = build_signal(d, close, atr, "CHoCH + Fib", [choch, f], 4)
            if s: sigs.append(s)

    # ─ Dédoublonnage + tri par score ─────────────────
    seen = set()
    out  = []
    for s in sorted(sigs, key=lambda x: x["score"], reverse=True):
        k = (s["direction"], s["setup"])
        if k not in seen:
            seen.add(k)
            out.append(s)
    return out

# ─── SCORE GLOBAL ────────────────────────────────────

def global_score(sig, trend, vol_pct, htf_trend="ranging"):
    """
    [v9.3] Bonus HTF aligné augmenté : +15 (v9.2: +10).
    Bonus confluence supplémentaire : +3 par confirmation au-delà de 2.
    """
    pts  = sig["score"] * 5
    # Alignement tendance M1
    pts += 10 if (sig["direction"]=="SELL" and trend=="bearish") or \
                 (sig["direction"]=="BUY"  and trend=="bullish") else \
           4  if trend=="ranging" else 0
    # [v9.3] Alignement tendance HTF M15 (+15 si aligné, +5 si ranging)
    pts += 15 if (sig["direction"]=="SELL" and htf_trend=="bearish") or \
                 (sig["direction"]=="BUY"  and htf_trend=="bullish") else \
           5  if htf_trend=="ranging" else 0
    # Volume
    pts += min(vol_pct * 200, 15)
    # RR
    pts += min((sig["rr"] - MIN_RR) * 5, 10)
    # [v9.3] Bonus confluence : +3 par conf supplémentaire au-delà de 2
    extra_confs = sig.get("nb_confirmations", 2) - 2
    pts += min(extra_confs * 3, 9)
    return round(min(pts, 100), 1)

# ─── TELEGRAM ────────────────────────────────────────

def send_telegram(text):
    url  = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    body = json.dumps({"chat_id": CHAT_ID, "text": text,
                       "parse_mode": "HTML",
                       "disable_web_page_preview": True}).encode()
    try:
        req = urllib.request.Request(url, data=body,
              headers={"Content-Type":"application/json"}, method="POST")
        with urllib.request.urlopen(req, context=ssl_ctx, timeout=10) as r:
            resp = json.loads(r.read())
            if not resp.get("ok"):
                log.error(f"TG: {resp}")
    except Exception as e:
        log.error(f"send_telegram: {e}")

def format_msg(sig, label, trend, htf_trend, score, live_price, executed=False):
    de  = "📈🟢 BUY" if sig["direction"]=="BUY" else "📉🔴 SELL"
    te  = {"bullish":"📈","bearish":"📉","ranging":"↔️"}.get(trend,"")
    hte = {"bullish":"📈","bearish":"📉","ranging":"↔️"}.get(htf_trend,"")
    st  = "⭐"*min(int(sig["rr"]),5)
    lv  = "\n⚡ <b>ORDRE LIVE PLACÉ ✅</b>" if executed else ""
    wk  = "\n🌙 <i>Week-end — BTC Only</i>" if is_weekend() else ""
    nc  = sig.get("nb_confirmations", 2)
    return (
        f"{de} — <b>AlphaBot Signal v9.3</b>\n"
        f"{'═'*32}\n"
        f"📌 <b>Marché:</b> {label}\n"
        f"🔧 <b>Setup:</b> {sig['setup']}\n"
        f"⏱ M1 | Bougie FERMÉE ✅\n"
        f"📊 Trend M1: {te} {trend.upper()}\n"
        f"📊 Trend M15: {hte} {htf_trend.upper()}\n"
        f"🔗 <b>Confluences:</b> {nc} confirmation(s)\n"
        f"{'─'*32}\n"
        f"💰 <b>Entrée:</b> {sig['entry']}\n"
        f"🔴 <b>SL:</b> {sig['sl']}\n"
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
        f"🤖 <i>AlphaBot v9.3 | leaderOdg</i>"
    )

# ─── BINANCE LIVE TRADING ────────────────────────────

BINANCE_TRADABLE = {"BTCUSDT", "XAUUSDT"}

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
        req = urllib.request.Request("https://fapi.binance.com/fapi/v1/exchangeInfo",
                                     headers={"User-Agent":"AlphaBot/9.3"})
        with urllib.request.urlopen(req, context=ssl_ctx, timeout=10) as r:
            info = json.loads(r.read())
        for s in info["symbols"]:
            if s["symbol"] != symbol: continue
            pp, ss, ts = s["pricePrecision"], 0.001, 0.1
            for f in s["filters"]:
                if f["filterType"] == "LOT_SIZE": ss = float(f["stepSize"])
                if f["filterType"] == "PRICE_FILTER": ts = float(f["tickSize"])
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
        log.info(f"[PAPER] {sig['direction']} {symbol} @ {sig['entry']}")
        return True
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
                               "stopPrice":round(sig["sl"],pp),"closePosition":"true"})
    b_post("/fapi/v1/order", {"symbol":symbol,"side":cl,"type":"TAKE_PROFIT_MARKET",
                               "stopPrice":round(sig["tp2"],pp),"closePosition":"true"})
    return True

# ─── HELPERS ─────────────────────────────────────────

def is_cooldown(symbol):
    return (time.time() - last_signal_time.get(symbol, 0)) < SIGNAL_COOLDOWN

def set_cooldown(symbol):
    last_signal_time[symbol] = time.time()

# ─── PROCESS SYMBOLE ─────────────────────────────────

def process_symbol(market):
    """
    [v9.3] Ajout fetch M15 pour htf_trend.
    1 seul signal émis par cycle (meilleur score uniquement).
    Seuil d'émission Telegram : MIN_SCORE_EMIT = 60.
    Seuil d'exécution ordre   : MIN_SCORE_LIVE = 75.
    """
    global signal_count
    symbol = market["symbol"]
    label  = market["label"]

    if is_cooldown(symbol): return

    live = fetch_live_price(symbol)
    if live is None: return

    # Vérification nouvelle bougie M1
    now    = int(time.time())
    c_open = now - (now % 60)
    state  = symbol_state.setdefault(symbol, {"last": 0})
    if c_open <= state["last"]: return
    state["last"] = c_open

    # ─ Fetch bougies M1 (analyse principale) ─────────
    candles = fetch_candles_m1(symbol)
    if not candles or len(candles) < 40: return

    # ─ [v9.3] Fetch bougies M15 (filtre tendance HTF) ─
    candles_htf = fetch_candles_htf(symbol, interval="15m", limit=60)
    sh_htf, sl_htf = find_swings(candles_htf, lb=3) if len(candles_htf) >= 10 else ([], [])
    htf_trend = market_structure(sh_htf, sl_htf) if candles_htf else "ranging"

    close   = candles[-1]["c"]
    atr     = calc_atr(candles)
    vol_pct = (atr / close * 100) if close > 0 else 0
    sh, sl  = find_swings(candles)
    trend   = market_structure(sh, sl)

    log.info(f"[{symbol}] close={close} | M1={trend} | M15={htf_trend} | "
             f"ATR%={vol_pct:.3f} | live={live}")

    # ─ Évaluation avec filtre HTF ────────────────────
    sigs = evaluate(candles, live, htf_trend=htf_trend)
    if not sigs: return

    # ─ [v9.3] Sélection du meilleur signal uniquement ─
    best_sig   = None
    best_score = 0
    for sig in sigs:
        score = global_score(sig, trend, vol_pct, htf_trend=htf_trend)
        log.info(f"[{symbol}] {sig['setup']} | {sig['direction']} | "
                 f"score={score} | confs={sig['nb_confirmations']} | RR 1:{sig['rr']}")
        if score > best_score:
            best_score = score
            best_sig   = sig

    if best_sig is None or best_score < MIN_SCORE_EMIT:
        log.info(f"[{symbol}] Meilleur score {best_score} < {MIN_SCORE_EMIT} → rejeté")
        return

    executed = False
    if best_score >= MIN_SCORE_LIVE:
        executed = place_order(best_sig, symbol)

    msg = format_msg(best_sig, label, trend, htf_trend, best_score, live, executed)
    send_telegram(msg)
    set_cooldown(symbol)
    signal_count += 1
    log.info(f"{'⚡' if executed else '✅'} Signal #{signal_count}: "
             f"{symbol} {best_sig['direction']} | score={best_score} | "
             f"confs={best_sig['nb_confirmations']}")

# ─── MAIN ────────────────────────────────────────────

def main():
    log.info("╔══════════════════════════════════════════╗")
    log.info("║  AlphaBot Signal v9.3 — LIVE SCANNER    ║")
    log.info("╚══════════════════════════════════════════╝")
    log.info(f"  MIN_SCORE_LIVE={MIN_SCORE_LIVE} | MIN_SCORE_EMIT={MIN_SCORE_EMIT}")
    log.info(f"  COOLDOWN={SIGNAL_COOLDOWN}s | MIN_CONFLUENCES={MIN_CONFIRMATIONS}")

    wk = is_weekend()
    send_telegram(
        f"🤖 <b>AlphaBot Signal v9.3 DÉMARRÉ</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"⚡ Scan temps réel toutes les {POLL_INTERVAL_SEC}s\n"
        f"📊 Signal: bougie M1 FERMÉE uniquement\n"
        f"📈 Filtre tendance: M1 + M15 alignés\n"
        f"🔗 Confluence min: {MIN_CONFIRMATIONS} confirmations\n"
        f"⏱ Cooldown: {SIGNAL_COOLDOWN//60} min entre signaux\n"
        f"🗓 Marchés actifs → BTC + Gold\n"
        f"💹 {'🟢 LIVE TRADING' if LIVE_TRADING else '🟡 Paper Mode'} | "
        f"Levier {USE_LEVERAGE}x | Risque {RISK_PER_TRADE_PCT}%\n"
        f"🎯 Score émission: {MIN_SCORE_EMIT}+ | Exécution: {MIN_SCORE_LIVE}+\n"
        f"🎯 RR: 1:{MIN_RR:.0f} | 1:{TARGET_RR:.0f} | 1:{MAX_RR:.0f}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🔧 Fixes v9.3: HTF M15 | Fakeout supprimé\n"
        f"        Confluence 2+ | Score 75+ | CD 30min\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🤖 <i>leaderOdg — AlphaBot</i>"
    )

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
            log.error(f"Boucle principale: {e}")
        time.sleep(POLL_INTERVAL_SEC)

if __name__ == "__main__":
    main()
