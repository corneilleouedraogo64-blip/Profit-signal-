
"""
╔══════════════════════════════════════════════════════════════════╗
║   ALPHABOT SIGNAL v6.28                                         ║
║   Scanner SMC/ICT → Signal Telegram → Tu trades manuellement    ║
║                                                                  ║
║   ✅ [v2-v5] Toute la logique précédente (multi-sources,       ║
║              CSV log, backtest, liquidity sweep, HTF bias…)     ║
║                                                                  ║
║   🆕 [v6.28] DISPLACEMENT + RETRACEMENT TO OB                  ║
║          → Pattern ICT le plus puissant (chart XAUUSD 06/04)  ║
║          → Displacement ≥ 1.5×ATR → OB identifié              ║
║          → Retrace 30–85% → entrée dans l'OB                  ║
║          → +2 score si prix dans l'OB | +1 si approche        ║
║          → Override HTF quand prix est dans l'OB               ║
║          → Entrée SL sous/sur l'extrême du displacement        ║
║                                                                  ║
║   🆕 [v6.27] MACRO SCORE FONDAMENTAL                           ║
║          → CPI / NFP / GDP depuis ForexFactory                 ║
║          → Score par devise : actual vs forecast               ║
║          → Bloque si macro fortement opposé au HTF (≥2pts)    ║
║          → Bonus +1 si macro aligné avec direction             ║
║          → Affiché dans le signal Telegram                     ║
║                                                                  ║
║   🆕 [v6.26] CHOCH OVERRIDE + M5 SCAN DIRECT                  ║
║          → CHoCH détecté = direction forcée (BEAR ou BULL)     ║
║          → Override HTF + displacement si contradictoires      ║
║          → M5 alignment non bloquant si CHoCH/displacement     ║
║          → Displacement = le plus RÉCENT (pas le plus fort)    ║
║          → Élimine les signaux à contre-tendance               ║
║                                                                  ║
║   🆕 [v6.25] DISPLACEMENT OVERRIDE (flux d'ordre LTF)          ║
║          → Impulse ≥ 2×ATR récente prime sur le biais HTF      ║
║          → Direction du signal = direction du displacement      ║
║          → Entrée au 50% du move (OTE institutionnel)          ║
║          → +2 score si prix dans la zone 50%                   ║
║          → Évite les BUY contre une impulse baissière forte    ║
║                                                                  ║
║   🆕 [v6.22] VOL BYPASS TOTAL BTC WEEKEND                      ║
║          → Filtre volatilité désactivé pour BTCUSD sam/dim      ║
║          → ATR/price loggé pour info mais non bloquant          ║
║          → Filtres ICT actifs : Regime + BOS + PD + Score + LTF ║
║                                                                  ║
║   🆕 [v6.21] VOLATILITÉ ADAPTATIVE WEEKEND / SILVER BULLET    ║
║          → Seuil -40% le weekend (crypto compression normale)   ║
║          → Seuil -20% en fenêtre Silver Bullet                  ║
║          → Market Regime relaxé BTC weekend (≤12 swings)        ║
║          → Élimine les faux négatifs du dimanche matin          ║
║                                                                  ║
║   🆕 [v6] #1 ORDER BLOCKS ICT + MITIGATION                    ║
║          → Dernière bougie opposée avant un impulse ≥ 2×ATR    ║
║          → Tracking mitigation (OB déjà touché = ignoré)        ║
║          → Remplace find_sd_zone() — beaucoup plus précis       ║
║          → Score /6 conservé, composante #5 = Order Block       ║
║                                                                  ║
║   🆕 [v6] #2 BOS / CHoCH VRAIS                                ║
║          → find_swings() : Swing H/L propres (fenêtre ±2)      ║
║          → detect_bos_choch() : structure institutionnelle      ║
║          → BOS = continuation | CHoCH = retournement           ║
║          → Affiché dans le signal Telegram + loggé CSV         ║
║          → Probabilité +3% si BOS confirmé                     ║
║                                                                  ║
║   🆕 [v6] #3 FILTRE FOREXFACTORY RÉEL                         ║
║          → API JSON : nfs.faireconomy.media/ff_calendar_…      ║
║          → Cache en mémoire 60min                               ║
║          → Bloque par devise (EURUSD bloque EUR+USD events)     ║
║          → Fenêtre ±15min..+45min configurable                  ║
║          → Fallback horaires fixes si FF indisponible           ║
║                                                                  ║
║   INSTALLATION :                                                 ║
║     pip install yfinance pandas requests                        ║
║     pip install ccxt          # crypto Binance                  ║
║                                                                  ║
║   LANCEMENT :                                                    ║
║     python alphabot_signal_v6.py                                ║
║     python alphabot_signal_v6.py --backtest XAUUSD 90          ║
║     python alphabot_signal_v6.py --backtest ALL 30             ║
║     python alphabot_signal_v6.py --stats                       ║
╚══════════════════════════════════════════════════════════════════╝
"""

import time
import csv
import sys
import json
import argparse
import requests
import traceback
from datetime import datetime, date, timedelta, timezone
from pathlib import Path

# pandas / yfinance / ccxt supprimés — données via requests uniquement


# ════════════════════════════════════════════════════════
#  🔑  CONFIGURATION — REMPLIS CES LIGNES
# ════════════════════════════════════════════════════════

TG_TOKEN   = "8665812395:AAFO4BMTIrBCQJYVL8UytO028TcB1sDfgbI"
TG_CHAT_ID = "6982051442"
# Si TG_TOKEN est vide, les signaux s'affichent uniquement dans la console (mode test)

TWELVE_DATA_KEY = ""   # Gratuit sur https://twelvedata.com/

BALANCE    = 1000.0
RISK_PCT   = 0.02      # 2% par trade

SIGNALS_CSV  = "signals_log.csv"
BACKTEST_DIR = "backtest_results"

# ── Watchlist ─────────────────────────────────────────
SYMBOLS = {
    "EURUSD": {"yf": "EURUSD=X",  "td": "EUR/USD",  "src": "forex"},
    "GBPUSD": {"yf": "GBPUSD=X",  "td": "GBP/USD",  "src": "forex"},
    "USDJPY": {"yf": "USDJPY=X",  "td": "USD/JPY",  "src": "forex"},
    "AUDUSD": {"yf": "AUDUSD=X",  "td": "AUD/USD",  "src": "forex"},
    "USDCAD": {"yf": "USDCAD=X",  "td": "USD/CAD",  "src": "forex"},
    "EURJPY": {"yf": "EURJPY=X",  "td": "EUR/JPY",  "src": "forex"},
    "GBPJPY": {"yf": "GBPJPY=X",  "td": "GBP/JPY",  "src": "forex"},
    "EURGBP": {"yf": "EURGBP=X",  "td": "EUR/GBP",  "src": "forex"},
    "XAUUSD": {"yf": "GC=F",      "td": "XAU/USD",  "src": "forex"},
    "XAGUSD": {"yf": "SI=F",      "td": "XAG/USD",  "src": "forex"},
    "USOIL":  {"yf": "CL=F",      "td": "WTI/USD",  "src": "index"},
    "US30":   {"yf": "YM=F",      "td": "DJI",      "src": "index"},
    "US100":  {"yf": "NQ=F",      "td": "NDX",      "src": "index"},
    "BTCUSD": {"yf": "BTC-USD",   "td": "BTC/USD",  "src": "crypto", "ccxt": "BTC/USDT"},
    "ETHUSD": {"yf": "ETH-USD",   "td": "ETH/USD",  "src": "crypto", "ccxt": "ETH/USDT"},
}

# ── [v6] Devises impactées par symbole (pour filtre ForexFactory) ──
SYMBOL_CURRENCIES = {
    "EURUSD": ["EUR", "USD"], "GBPUSD": ["GBP", "USD"],
    "USDJPY": ["USD", "JPY"], "AUDUSD": ["AUD", "USD"],
    "USDCAD": ["USD", "CAD"], "EURJPY": ["EUR", "JPY"],
    "GBPJPY": ["GBP", "JPY"], "EURGBP": ["EUR", "GBP"],
    "XAUUSD": ["USD"],        "XAGUSD": ["USD"],
    "USOIL":  ["USD"],        "US30":   ["USD"],
    "US100":  ["USD"],        "BTCUSD": [],  # crypto non bloquée
    "ETHUSD": [],
}

PIP_VALUES = {
    "XAUUSD": 1.0,  "XAGUSD": 0.5,  "BTCUSD": 1.0,  "ETHUSD": 0.1,
    "USOIL":  1.0,  "US30":   1.0,  "US100":  1.0,
    "EURUSD": 10.0, "GBPUSD": 10.0, "USDJPY": 9.0,
    "AUDUSD": 10.0, "USDCAD": 10.0, "EURJPY": 9.0,
    "GBPJPY": 9.0,  "EURGBP": 10.0,
}

VOLATILITY_THRESHOLDS = {
    "XAUUSD": 0.0010, "BTCUSD": 0.0050, "ETHUSD": 0.0050,
    "US30": 0.0008, "US100": 0.0008, "USOIL": 0.0015, "XAGUSD": 0.0015,
    "_forex": 0.0005,
}

PREMIUM_SYMBOLS = {"XAUUSD", "US30", "US100", "BTCUSD", "GBPUSD"}

# ── News horaires fixes (fallback si ForexFactory indispo) ────────
NEWS_BLOCK_TIMES_UTC = [(8,55),(9,0),(9,30),(13,30),(15,0),(18,0),(18,30)]
NEWS_BLOCK_MINUTES   = 4

# ── [v6] ForexFactory ─────────────────────────────────────────────
FF_CALENDAR_URL    = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"
FF_TZ_OFFSET_HOURS = 5     # ForexFactory = Eastern Time → UTC (+5h approximation)
FF_NEWS_WINDOW_MIN = 45    # Bloquer X min avant une news High Impact
FF_NEWS_BACK_MIN   = 15    # Bloquer X min après le début d'une news
FF_NEWS_ENABLED    = True  # False = fallback horaires fixes uniquement

# ── [v6] Order Blocks ─────────────────────────────────────────────
OB_LOOKBACK      = 80   # Bougies à analyser pour trouver les OBs
OB_IMPULSE_ATR   = 2.0  # Impulse minimum après l'OB (en × ATR)
OB_TOLERANCE_ATR = 0.5  # Tolérance pour "price dans l'OB" (en × ATR)

# ── [v6] Structure BOS/CHoCH ──────────────────────────────────────
SWING_WINDOW    = 2    # Fenêtre ±N bougies pour swing highs/lows
STRUCT_LOOKBACK = 60   # Bougies pour l'analyse de structure

ATR_PERIOD       = 14
MST_LOOKBACK     = 60
IMPULSE_LOOKBACK = 80
IMPULSE_MIN_ATR  = 1.5
FIB_LOW, FIB_HIGH = 0.45, 0.60
FVG_LOOKBACK     = 50
FVG_FILL_MIN     = 0.30
FVG_FILL_MAX     = 0.85
SCORE_MIN        = 4
RR_MIN           = 3.0
SL_ATR_MARGIN    = 0.3
CHOCH_LOOKBACK   = 30

SESSION_WINDOWS  = [(7, 12), (13, 18)]
BAD_HOURS        = {0: range(0, 8), 4: range(17, 24)}
SCORE_PROBABILITY = {6: 75, 5: 68, 4: 60, 3: 50}

SCAN_INTERVAL     = 300
COOLDOWN_MIN      = 60
DAILY_REPORT_HOUR = 17

TD_INTERVAL  = {"15m": "15min", "5m": "5min", "1h": "1h", "1d": "1day"}
TD_PERIOD_DAYS = {"5d": 5, "2d": 2, "30d": 30, "90d": 90}


# ════════════════════════════════════════════════════════
#  📊  STATS EN MÉMOIRE
# ════════════════════════════════════════════════════════
stats = {
    "signals_today": 0, "signals_total": 0,
    "filtered_vol":  0, "filtered_news": 0,
    "sweep_signals": 0, "ob_signals":    0,
    "bos_signals":   0, "choch_signals": 0,
    "by_symbol":  {},
    "by_session": {"🇬🇧 London": 0, "🇺🇸 New York": 0},
    "data_source": {"twelvedata": 0, "ccxt": 0, "yfinance": 0},
    "start_time": datetime.now(timezone.utc).strftime("%H:%M UTC"),
    "start_date": str(date.today()),
}
_last_report_day = None

# [v6] Cache ForexFactory (refresh toutes les heures)
_ff_cache = {"data": None, "fetched_at": None}


# ════════════════════════════════════════════════════════
#  🖨️  LOG
# ════════════════════════════════════════════════════════
def log(msg, level="INFO"):
    colors = {
        "INFO":    "\033[96m",
        "SIGNAL":  "\033[92m",
        "WARN":    "\033[93m",
        "ERROR":   "\033[91m",
        "SCAN":    "\033[94m",
        "HTF":     "\033[35m",
        "SESSION": "\033[33m",
        "STATS":   "\033[36m",
        "FILTER":  "\033[90m",
        "DATA":    "\033[34m",
        "BACKTEST":"\033[95m",
        "SMC":     "\033[32m",
    }
    col = colors.get(level, "")
    ts  = datetime.now().strftime("%H:%M:%S")
    print(f"{col}[{ts}][{level}] {msg}\033[0m", flush=True)


# ════════════════════════════════════════════════════════
#  👥  GESTION MULTI-USERS (broadcast à tous les abonnés)
# ════════════════════════════════════════════════════════
USERS_FILE = "bot_users.json"
_users: set = set()   # Chat IDs enregistrés

def load_users():
    """Charge les users depuis le fichier JSON."""
    global _users
    if Path(USERS_FILE).exists():
        try:
            with open(USERS_FILE, encoding="utf-8") as f:
                data = json.load(f)
            _users = set(str(x) for x in data.get("users", []))
            log(f"👥 {len(_users)} user(s) chargé(s) depuis {USERS_FILE}", "INFO")
        except Exception as e:
            log(f"Erreur chargement users: {e}", "WARN")
    # Toujours inclure le TG_CHAT_ID admin par défaut
    if TG_CHAT_ID:
        _users.add(str(TG_CHAT_ID))

def save_users():
    """Sauvegarde les users dans le fichier JSON."""
    try:
        with open(USERS_FILE, "w", encoding="utf-8") as f:
            json.dump({"users": list(_users)}, f, indent=2)
    except Exception as e:
        log(f"Erreur sauvegarde users: {e}", "WARN")

def register_user(chat_id: str):
    """Enregistre un nouvel user."""
    chat_id = str(chat_id)
    if chat_id not in _users:
        _users.add(chat_id)
        save_users()
        log(f"👥 Nouvel user enregistré: {chat_id} | Total: {len(_users)}", "INFO")
        return True
    return False

def unregister_user(chat_id: str):
    """Retire un user."""
    chat_id = str(chat_id)
    if chat_id in _users:
        _users.discard(chat_id)
        save_users()
        log(f"👥 User retiré: {chat_id} | Total: {len(_users)}", "INFO")
        return True
    return False


# ── Polling Telegram pour /start et /stop ─────────────
_last_update_id = 0

def poll_telegram_commands():
    """
    Polling léger : récupère les commandes /start et /stop.
    Appelé à chaque cycle de scan (non-bloquant).
    /start → enregistre le user → envoi signal direct
    /stop  → retire le user
    """
    global _last_update_id
    if not TG_TOKEN:
        return
    try:
        resp = requests.get(
            f"https://api.telegram.org/bot{TG_TOKEN}/getUpdates",
            params={"offset": _last_update_id + 1, "timeout": 1, "limit": 20},
            timeout=5,
        )
        if resp.status_code != 200:
            return
        data = resp.json()
        for update in data.get("result", []):
            _last_update_id = update["update_id"]
            msg_obj = update.get("message") or update.get("channel_post")
            if not msg_obj:
                continue
            chat_id = str(msg_obj["chat"]["id"])
            text    = (msg_obj.get("text") or "").strip().lower()

            if text.startswith("/start"):
                is_new = register_user(chat_id)
                welcome = (
                    f"🤖 <b>AlphaBot Signal v6.29</b>\\n"
                    f"{'─'*30}\\n"
                    f"{'✅ Bienvenue ! Tu recevras tous les signaux ICT/SMC.' if is_new else '✅ Tu étais déjà abonné !'}"
                    f"\\n\\n📊 {len(SYMBOLS)} marchés scannés | Score min {SCORE_MIN}/6"
                    f"\\n💰 Risque {RISK_PCT*100:.0f}% par trade"
                    f"\\n\\n🔴 /stop pour se désabonner"
                )
                _tg_single(chat_id, welcome)

            elif text.startswith("/stop"):
                removed = unregister_user(chat_id)
                bye = "✅ Désabonné. Tu ne recevras plus de signaux." if removed else "ℹ️ Tu n'étais pas abonné."
                _tg_single(chat_id, bye)

    except Exception as e:
        log(f"poll_commands erreur: {e}", "WARN")


# ════════════════════════════════════════════════════════
#  📲  TELEGRAM — BROADCAST MULTI-USERS
# ════════════════════════════════════════════════════════
def _tg_single(chat_id: str, msg: str):
    """Envoie un message à un seul chat_id."""
    try:
        resp = requests.post(
            f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage",
            json={"chat_id": chat_id, "text": msg, "parse_mode": "HTML"},
            timeout=10,
        )
        if resp.status_code == 403:
            # User a bloqué le bot → le retirer
            log(f"TG 403 → user {chat_id} bloqué, retiré", "WARN")
            _users.discard(chat_id)
            save_users()
        elif resp.status_code not in (200, 400):
            log(f"TG {chat_id} erreur {resp.status_code}", "WARN")
    except Exception as e:
        log(f"TG exception {chat_id}: {e}", "WARN")

def tg(msg: str):
    """
    Broadcast le message à TOUS les users enregistrés.
    Si aucun user → envoie au TG_CHAT_ID admin par défaut.
    """
    if not TG_TOKEN:
        log("⚠️  Configure TG_TOKEN !", "WARN")
        return
    targets = _users if _users else ({str(TG_CHAT_ID)} if TG_CHAT_ID else set())
    if not targets:
        log("⚠️  Aucun destinataire TG configuré !", "WARN")
        return
    for chat_id in list(targets):
        _tg_single(chat_id, msg)
        if len(targets) > 1:
            time.sleep(0.05)  # anti-flood Telegram


# ════════════════════════════════════════════════════════
#  📡  SOURCES DE DONNÉES (identique v5)
# ════════════════════════════════════════════════════════

def _rates_from_yahoo_json(data: dict):
    """Extrait la liste OHLC depuis la réponse JSON brute de Yahoo Finance."""
    try:
        result = data.get("chart", {}).get("result")
        if not result:
            return None
        r    = result[0]
        ohlc = r.get("indicators", {}).get("quote", [{}])[0]
        opens  = ohlc.get("open",  [])
        highs  = ohlc.get("high",  [])
        lows   = ohlc.get("low",   [])
        closes = ohlc.get("close", [])
        rates  = []
        for i in range(len(closes)):
            try:
                if None in (opens[i], highs[i], lows[i], closes[i]):
                    continue
                rates.append({
                    "open":  float(opens[i]),
                    "high":  float(highs[i]),
                    "low":   float(lows[i]),
                    "close": float(closes[i]),
                })
            except (IndexError, TypeError, ValueError):
                continue
        return rates if len(rates) >= 20 else None
    except Exception:
        return None


def _fetch_twelvedata(symbol_info: dict, interval: str, period: str):
    """Twelve Data REST API — fiable pour Forex, matières, indices."""
    if not TWELVE_DATA_KEY:
        return None
    td_symbol   = symbol_info.get("td")
    td_interval = TD_INTERVAL.get(interval)
    if not td_symbol or not td_interval:
        return None
    days       = TD_PERIOD_DAYS.get(period, 5)
    outputsize = min(days * 100, 5000)
    try:
        resp = requests.get(
            "https://api.twelvedata.com/time_series",
            params={
                "symbol": td_symbol, "interval": td_interval,
                "outputsize": outputsize, "apikey": TWELVE_DATA_KEY,
                "format": "JSON",
            },
            timeout=15,
        )
        data = resp.json()
        if data.get("status") == "error" or "values" not in data:
            log(f"TwelveData erreur: {data.get('message','?')}", "WARN")
            return None
        rates = []
        for bar in reversed(data["values"]):
            try:
                rates.append({
                    "open":  float(bar["open"]),  "high": float(bar["high"]),
                    "low":   float(bar["low"]),   "close": float(bar["close"]),
                })
            except (KeyError, ValueError):
                continue
        if len(rates) < 20:
            return None
        stats["data_source"]["twelvedata"] += 1
        return rates
    except Exception as e:
        log(f"TwelveData exception: {e}", "WARN")
        return None


def _fetch_binance(symbol_info: dict, interval: str, period: str):
    """Binance REST public — sans ccxt, sans dépendance externe."""
    raw = symbol_info.get("ccxt")      # ex. "BTC/USDT"
    if not raw:
        return None
    binance_symbol = raw.replace("/", "")   # → "BTCUSDT"
    tf_map = {"15m": "15m", "5m": "5m", "1h": "1h", "1d": "1d"}
    tf     = tf_map.get(interval)
    if not tf:
        return None
    days  = TD_PERIOD_DAYS.get(period, 5)
    limit = min(days * 96 + 50, 1000)
    try:
        resp = requests.get(
            "https://api.binance.com/api/v3/klines",
            params={"symbol": binance_symbol, "interval": tf, "limit": limit},
            timeout=15,
        )
        data = resp.json()
        if not isinstance(data, list) or len(data) < 20:
            return None
        rates = [
            {"open": float(k[1]), "high": float(k[2]),
             "low":  float(k[3]), "close": float(k[4])}
            for k in data
        ]
        stats["data_source"]["ccxt"] += 1
        return rates
    except Exception as e:
        log(f"Binance REST exception: {e}", "WARN")
        return None


def _fetch_yahoo(symbol_info: dict, interval: str, period: str):
    """Yahoo Finance REST directement — sans yfinance ni pandas."""
    yf_ticker = symbol_info.get("yf")
    if not yf_ticker:
        return None
    period_map = {"5d": "5d", "2d": "2d", "30d": "1mo", "90d": "3mo"}
    yf_range   = period_map.get(period, "5d")
    try:
        resp = requests.get(
            f"https://query1.finance.yahoo.com/v8/finance/chart/{yf_ticker}",
            params={"interval": interval, "range": yf_range},
            headers={"User-Agent": "Mozilla/5.0 AlphaBot/6.0"},
            timeout=15,
        )
        rates = _rates_from_yahoo_json(resp.json())
        if rates:
            stats["data_source"]["yfinance"] += 1
        return rates
    except Exception as e:
        log(f"Yahoo {yf_ticker} {interval}: {e}", "WARN")
        return None


def get_rates(symbol: str, interval: str, period: str):
    """Récupère données OHLC avec fallback automatique."""
    info = SYMBOLS.get(symbol, {})
    src  = info.get("src", "forex")
    if src == "crypto":
        rates = _fetch_binance(info, interval, period)
        if rates:
            log(f"  {symbol} [{interval}] via Binance REST ✅", "DATA")
            return rates
    if src in ("forex", "index") and TWELVE_DATA_KEY:
        rates = _fetch_twelvedata(info, interval, period)
        if rates:
            log(f"  {symbol} [{interval}] via TwelveData ✅", "DATA")
            return rates
    rates = _fetch_yahoo(info, interval, period)
    if rates:
        log(f"  {symbol} [{interval}] via Yahoo REST (fallback) ⚠️", "DATA")
    return rates


# ════════════════════════════════════════════════════════
#  📝  LOGGING CSV DES SIGNAUX
# ════════════════════════════════════════════════════════

CSV_FIELDS = [
    "id", "datetime_utc", "symbol", "direction", "session", "day",
    "score", "probability", "entry_type", "has_sweep",
    # [v6] nouveaux champs
    "has_ob", "ob_type", "ob_lo", "ob_hi",
    "last_structure_event", "m15_structure",
    # prix
    "price", "sl", "tp1", "tp2", "tp3",
    "risk_usd", "lot", "rr",
    # HTF
    "htf_daily", "htf_h4", "htf_bias",
    # confluences
    "fvg", "ob", "equi", "rejection_m15", "rejection_m5",
    # résultat (à remplir manuellement)
    "result", "rr_achieved", "notes",
]


def _next_signal_id():
    if not Path(SIGNALS_CSV).exists():
        return 1
    with open(SIGNALS_CSV, newline="", encoding="utf-8") as f:
        return len(list(csv.DictReader(f))) + 1


def log_signal_csv(sig: dict, sess: str, tp1, tp2, tp3, risk_usd, lot, prob):
    """Enregistre un signal dans signals_log.csv."""
    ob_info  = sig.get("ob")
    bos_info = sig.get("bos_choch", {})
    write_header = (
        not Path(SIGNALS_CSV).exists()
        or Path(SIGNALS_CSV).stat().st_size == 0
    )
    with open(SIGNALS_CSV, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        if write_header:
            writer.writeheader()
        writer.writerow({
            "id":                   _next_signal_id(),
            "datetime_utc":         datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M"),
            "symbol":               sig["symbol"],
            "direction":            sig["direction"],
            "session":              sess,
            "day":                  datetime.now(timezone.utc).strftime("%A"),
            "score":                sig["score"],
            "probability":          prob,
            "entry_type":           sig["entry_type"],
            "has_sweep":            int(sig.get("has_sweep", False)),
            "has_ob":               int(ob_info is not None),
            "ob_type":              ob_info["type"] if ob_info else "",
            "ob_lo":                round(ob_info["lo"], 5) if ob_info else "",
            "ob_hi":                round(ob_info["hi"], 5) if ob_info else "",
            "last_structure_event": bos_info.get("last_event") or "",
            "m15_structure":        bos_info.get("structure") or "",
            "price":                sig["price"],
            "sl":                   sig["sl"],
            "tp1":                  tp1, "tp2": tp2, "tp3": tp3,
            "risk_usd":             risk_usd,
            "lot":                  lot,
            "rr":                   RR_MIN,
            "htf_daily":            sig["htf"]["daily"],
            "htf_h4":               sig["htf"]["h4"],
            "htf_bias":             sig["htf"]["bias"],
            "fvg":                  int(sig["fvg"] is not None),
            "ob":                   int(ob_info is not None),
            "equi":                 int(sig["equi"]),
            "rejection_m15":        sig["rejection"] or "",
            "rejection_m5":         sig.get("rej_m5") or "",
            "result":               "",
            "rr_achieved":          "",
            "notes":                "",
        })
    log(f"📝 Signal loggé dans {SIGNALS_CSV}", "STATS")


def print_csv_stats():
    """Affiche les statistiques réelles depuis le CSV (--stats)."""
    if not Path(SIGNALS_CSV).exists():
        print("Aucun signal enregistré.")
        return
    with open(SIGNALS_CSV, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    total   = len(rows)
    results = [r for r in rows if r.get("result") in ("WIN", "LOSS", "PARTIAL")]
    wins    = [r for r in results if r["result"] == "WIN"]
    losses  = [r for r in results if r["result"] == "LOSS"]
    partial = [r for r in results if r["result"] == "PARTIAL"]
    winrate = len(wins) / len(results) * 100 if results else 0
    gain_r  = sum(float(r["rr_achieved"]) for r in wins   if r.get("rr_achieved"))
    loss_r  = sum(float(r["rr_achieved"]) for r in losses if r.get("rr_achieved"))
    pf      = gain_r / loss_r if loss_r > 0 else float("inf")
    by_sym  = {}
    for r in results:
        s = r["symbol"]
        if s not in by_sym: by_sym[s] = {"w": 0, "l": 0, "p": 0}
        if   r["result"] == "WIN":     by_sym[s]["w"] += 1
        elif r["result"] == "LOSS":    by_sym[s]["l"] += 1
        else:                          by_sym[s]["p"] += 1
    # Stats OB
    ob_results = [r for r in results if r.get("has_ob") == "1"]
    ob_wins    = [r for r in ob_results if r["result"] == "WIN"]
    ob_wr      = len(ob_wins) / len(ob_results) * 100 if ob_results else 0
    print("\n" + "═"*52)
    print("  ALPHABOT v6 — STATISTIQUES RÉELLES")
    print("═"*52)
    print(f"  Signaux total     : {total}")
    print(f"  Résultats connus  : {len(results)}")
    print(f"  ✅ WIN            : {len(wins)}")
    print(f"  ❌ LOSS           : {len(losses)}")
    print(f"  🔶 PARTIAL        : {len(partial)}")
    print(f"  📊 Winrate        : {winrate:.1f}%")
    print(f"  📈 Profit Factor  : {pf:.2f}")
    print(f"  🏦 OB trades      : {len(ob_results)}  WR OB: {ob_wr:.1f}%")
    print("─"*52)
    print("  Par symbole :")
    for sym, d in sorted(by_sym.items(), key=lambda x: x[1]["w"], reverse=True):
        tt  = d["w"] + d["l"] + d["p"]
        wr  = d["w"] / tt * 100 if tt else 0
        print(f"    {sym:10} W:{d['w']} L:{d['l']} P:{d['p']}  WR:{wr:.0f}%")
    print("═"*52 + "\n")


# ════════════════════════════════════════════════════════
#  🔬  BACKTESTING
# ════════════════════════════════════════════════════════

def _get_historical_rates(symbol: str, interval: str, days: int):
    """Données historiques longues pour backtesting."""
    info   = SYMBOLS.get(symbol, {})
    period = f"{days}d"
    if TWELVE_DATA_KEY and info.get("src") != "crypto":
        try:
            td_symbol   = info.get("td")
            td_interval = TD_INTERVAL.get(interval, "15min")
            outputsize  = min(days * 96, 5000)
            resp = requests.get(
                "https://api.twelvedata.com/time_series",
                params={"symbol": td_symbol, "interval": td_interval,
                        "outputsize": outputsize, "apikey": TWELVE_DATA_KEY},
                timeout=20,
            )
            data = resp.json()
            if "values" in data:
                rates = [
                    {"open": float(b["open"]), "high": float(b["high"]),
                     "low":  float(b["low"]),  "close": float(b["close"])}
                    for b in reversed(data["values"])
                ]
                if len(rates) >= 100:
                    log(f"  Backtest {symbol}: {len(rates)} bougies via TwelveData", "BACKTEST")
                    return rates
        except Exception:
            pass
    try:
        yf_ticker = info.get("yf", symbol)
        rates = _fetch_yahoo({"yf": yf_ticker}, interval, f"{days}d")
        if rates:
            log(f"  Backtest {symbol}: {len(rates)} bougies via Yahoo REST", "BACKTEST")
        return rates
    except Exception as e:
        log(f"  Backtest {symbol} erreur données: {e}", "WARN")
        return None


def backtest_symbol(symbol: str, days: int = 90):
    """Backtesting M15 sur données historiques."""
    log(f"Backtesting {symbol} sur {days}j...", "BACKTEST")
    if days > 60 and not TWELVE_DATA_KEY:
        log(
            f"  {symbol}: yfinance limite M15 à 60j. "
            f"Fournis TWELVE_DATA_KEY ou réduis à --backtest {symbol} 60",
            "WARN",
        )
        days = 60
    rates = _get_historical_rates(symbol, "15m", days)
    if not rates or len(rates) < 200:
        log(f"  {symbol}: données insuffisantes", "WARN")
        return None
    rates_d = _get_historical_rates(symbol, "1d", days)
    if not rates_d:
        log(f"  {symbol}: pas de données Daily", "WARN")
        return None

    trades = []
    for i in range(100, len(rates) - 20):
        window = rates[:i+1]
        price  = window[-1]["close"]
        atr    = calc_atr(window)
        if not is_volatile_enough(symbol, atr, price):
            continue

        bos_info  = detect_bos_choch(window)
        mst       = bos_info["structure"]
        if mst == "NEUTRAL":
            continue

        direction = "BULL" if mst == "BULLISH" else "BEAR"
        impulse   = find_impulse(window, atr)
        equi      = in_equilibrium(price, impulse) if impulse else False
        fvg       = find_fvg(window, direction, price, atr)
        obs       = find_order_blocks(window, direction, atr)
        ob        = get_best_unmitigated_ob(window, obs, direction, price, atr)
        rej       = check_rejection(window, direction)
        score     = score_signal(mst, impulse, equi, fvg, ob, rej)

        if score < SCORE_MIN:
            continue

        sl   = calc_sl_choch(window, direction, price, atr)
        risk = abs(price - sl)
        if risk <= 0:
            continue

        sign  = 1 if direction == "BULL" else -1
        tp1   = price + risk * 1.0 * sign
        tp3   = price + risk * RR_MIN * sign
        future = rates[i+1:i+21]
        result = "LOSS"
        rr_hit = 0.0

        for bar in future:
            if direction == "BULL":
                if bar["low"] <= sl:    result = "LOSS"; break
                if bar["high"] >= tp1:  rr_hit = max(rr_hit, 1.0)
                if bar["high"] >= tp3:  result = "WIN"; rr_hit = 3.0; break
            else:
                if bar["high"] >= sl:   result = "LOSS"; break
                if bar["low"] <= tp1:   rr_hit = max(rr_hit, 1.0)
                if bar["low"] <= tp3:   result = "WIN"; rr_hit = 3.0; break

        trades.append({
            "symbol": symbol, "direction": direction, "score": score,
            "entry": price, "sl": sl, "tp3": tp3,
            "result": result, "rr_hit": rr_hit,
            "has_ob": ob is not None,
            "last_event": bos_info.get("last_event"),
        })

    return trades


def run_backtest(symbols_list, days=90):
    """Lance le backtest sur une liste de symboles et affiche le rapport."""
    log(f"═══ BACKTEST {days}j sur {len(symbols_list)} symboles ═══", "BACKTEST")
    all_trades = []
    for symbol in symbols_list:
        trades = backtest_symbol(symbol, days)
        if trades:
            all_trades.extend(trades)

    if not all_trades:
        log("Aucun trade généré. Vérifiez les données.", "WARN")
        return

    wins    = [t for t in all_trades if t["result"] == "WIN"]
    losses  = [t for t in all_trades if t["result"] == "LOSS"]
    total   = len(all_trades)
    winrate = len(wins) / total * 100 if total else 0
    gain_r  = sum(t["rr_hit"] for t in wins)
    loss_r  = sum(1.0 for t in losses)
    pf      = gain_r / loss_r if loss_r > 0 else float("inf")

    equity = 0.0; peak = 0.0; max_dd = 0.0
    for t in all_trades:
        equity += t["rr_hit"] if t["result"] == "WIN" else -1.0
        if equity > peak: peak = equity
        dd = peak - equity
        if dd > max_dd: max_dd = dd

    expectancy = (
        (winrate / 100 * (gain_r / len(wins) if wins else 0))
        - ((1 - winrate / 100) * 1.0)
    )

    # Stats par score
    by_score = {}
    for t in all_trades:
        s = t["score"]
        if s not in by_score: by_score[s] = {"w": 0, "l": 0}
        if t["result"] == "WIN": by_score[s]["w"] += 1
        else:                    by_score[s]["l"] += 1

    # Stats par symbole
    by_sym = {}
    for t in all_trades:
        s = t["symbol"]
        if s not in by_sym: by_sym[s] = {"w": 0, "l": 0}
        if t["result"] == "WIN": by_sym[s]["w"] += 1
        else:                    by_sym[s]["l"] += 1

    # Stats OB
    ob_trades = [t for t in all_trades if t.get("has_ob")]
    ob_wins   = [t for t in ob_trades  if t["result"] == "WIN"]
    ob_wr     = len(ob_wins) / len(ob_trades) * 100 if ob_trades else 0

    # Stats BOS
    bos_trades = [t for t in all_trades if t.get("last_event") and "BOS" in t["last_event"]]
    bos_wins   = [t for t in bos_trades if t["result"] == "WIN"]
    bos_wr     = len(bos_wins) / len(bos_trades) * 100 if bos_trades else 0

    # Sauvegarde JSON
    Path(BACKTEST_DIR).mkdir(exist_ok=True)
    report = {
        "date": str(date.today()), "days": days, "symbols": symbols_list,
        "total_trades": total, "wins": len(wins), "losses": len(losses),
        "winrate_pct": round(winrate, 2), "profit_factor": round(pf, 3),
        "max_drawdown_r": round(max_dd, 2), "expectancy_r": round(expectancy, 3),
        "ob_trades": len(ob_trades), "ob_winrate_pct": round(ob_wr, 2),
        "bos_trades": len(bos_trades), "bos_winrate_pct": round(bos_wr, 2),
        "by_score": by_score, "by_symbol": by_sym,
    }
    fname = f"{BACKTEST_DIR}/backtest_{date.today()}.json"
    with open(fname, "w") as f:
        json.dump(report, f, indent=2)

    print("\n" + "═"*54)
    print(f"  BACKTEST ALPHABOT v6 — {days}j — {len(symbols_list)} symboles")
    print("═"*54)
    print(f"  Trades simulés       : {total}")
    print(f"  ✅ WIN               : {len(wins)}")
    print(f"  ❌ LOSS              : {len(losses)}")
    print(f"  📊 Winrate           : {winrate:.1f}%")
    print(f"  📈 Profit Factor     : {pf:.2f}")
    print(f"  📉 Max Drawdown      : {max_dd:.1f}R")
    print(f"  💡 Expectancy        : {expectancy:+.2f}R/trade")
    print(f"  🏦 Trades avec OB    : {len(ob_trades)}  WR: {ob_wr:.1f}%")
    print(f"  📐 Trades avec BOS   : {len(bos_trades)} WR: {bos_wr:.1f}%")
    print("─"*54)
    print("  Par score :")
    for s in sorted(by_score.keys(), reverse=True):
        d = by_score[s]; tt = d["w"] + d["l"]
        wr = d["w"] / tt * 100 if tt else 0
        print(f"    Score {s}/6 : W:{d['w']} L:{d['l']}  WR:{wr:.0f}%")
    print("─"*54)
    print("  Par symbole (top 8) :")
    for sym, d in sorted(by_sym.items(), key=lambda x: x[1]["w"], reverse=True)[:8]:
        tt = d["w"] + d["l"]; wr = d["w"] / tt * 100 if tt else 0
        print(f"    {sym:10} W:{d['w']} L:{d['l']}  WR:{wr:.0f}%")
    print("═"*54)
    print(f"  Rapport sauvegardé : {fname}")
    print("═"*54 + "\n")
    return report


# ════════════════════════════════════════════════════════
#  🕐  SESSION / JOUR
# ════════════════════════════════════════════════════════
# Symboles crypto actifs 24h/24, 7j/7
CRYPTO_SYMBOLS = {"BTCUSD"}

def in_active_session(symbol: str = ""):
    """Retourne True si le marché est actif pour ce symbole.
    Le crypto est toujours actif. Forex/indices : sessions Londres + NY uniquement."""
    now  = datetime.now(timezone.utc)
    wday = now.weekday()  # 5=samedi, 6=dimanche

    # Crypto : actif 24h/24, 7j/7 — sauf dimanche soir (liquidité très faible)
    if symbol in CRYPTO_SYMBOLS:
        if wday == 6 and now.hour < 5:   # dimanche avant 5h UTC
            return False
        return True

    # Forex / Indices : fermé le weekend
    if wday >= 5:
        return False
    if wday in BAD_HOURS and now.hour in BAD_HOURS[wday]:
        return False
    for start, end in SESSION_WINDOWS:
        if start <= now.hour < end:
            return True
    return False


def session_name(symbol: str = ""):
    now  = datetime.now(timezone.utc)
    hour = now.hour
    wday = now.weekday()
    if symbol in CRYPTO_SYMBOLS and wday >= 5:
        return "₿ Crypto Weekend"
    if 7  <= hour < 12: return "🇬🇧 London"
    if 13 <= hour < 18: return "🇺🇸 New York"
    return "💤 Hors session"


def bad_day_reason(symbol: str = ""):
    """Retourne une raison de blocage, ou chaîne vide si OK."""
    if symbol in CRYPTO_SYMBOLS:
        return ""   # crypto jamais bloqué par bad_day
    now  = datetime.now(timezone.utc)
    wday = now.weekday()
    if wday >= 5:                         return "⚠️ Weekend — marchés Forex/Indices fermés"
    if wday == 0 and now.hour < 8:        return "⚠️ Lundi matin — liquidité faible"
    if wday == 4 and now.hour >= 17:      return "⚠️ Vendredi soir — clôture hebdo"
    return ""


def _is_near_news_fallback():
    """Filtre horaires fixes (fallback si ForexFactory indisponible)."""
    now      = datetime.now(timezone.utc)
    now_mins = now.hour * 60 + now.minute
    for h, m in NEWS_BLOCK_TIMES_UTC:
        if abs(now_mins - (h * 60 + m)) <= NEWS_BLOCK_MINUTES:
            return True
    return False


# ════════════════════════════════════════════════════════
#  📰  [v6] FILTRE FOREXFACTORY RÉEL
# ════════════════════════════════════════════════════════

def _parse_ff_datetime(date_str: str, time_str: str):
    """
    Parse date/heure ForexFactory (Eastern Time) en datetime UTC.
    FF_TZ_OFFSET_HOURS = 5 (EST) ou 4 (EDT) — approximation.
    """
    try:
        ts = (time_str or "").strip()
        if not ts or ts.lower() in ("all day", "tentative"):
            dt_et = datetime.strptime(date_str.strip(), "%Y-%m-%d")
            return dt_et + timedelta(hours=FF_TZ_OFFSET_HOURS)
        dt_str = f"{date_str.strip()} {ts}"
        for fmt in ("%Y-%m-%d %I:%M%p", "%Y-%m-%d %I%p", "%Y-%m-%d %H:%M"):
            try:
                dt_et = datetime.strptime(dt_str, fmt)
                return dt_et + timedelta(hours=FF_TZ_OFFSET_HOURS)
            except ValueError:
                continue
    except Exception:
        pass
    return None


def fetch_ff_calendar():
    """
    Télécharge le calendrier ForexFactory de la semaine.
    Cache en mémoire 60 minutes pour économiser les requêtes.
    """
    global _ff_cache
    now = datetime.now(timezone.utc)

    # Retourne le cache si encore valide
    if (_ff_cache["data"] is not None
            and _ff_cache["fetched_at"] is not None
            and (now - _ff_cache["fetched_at"]).total_seconds() < 3600):
        return _ff_cache["data"]

    try:
        resp = requests.get(
            FF_CALENDAR_URL,
            timeout=10,
            headers={"User-Agent": "Mozilla/5.0 AlphaBot/6.0"},
        )
        if resp.status_code == 200:
            data = resp.json()
            _ff_cache = {"data": data, "fetched_at": now}
            high_count = sum(
                1 for e in data
                if str(e.get("impact", "")).lower() in ("high", "3")
            )
            log(f"📰 ForexFactory: {len(data)} events ({high_count} High Impact)", "DATA")
            return data
        else:
            log(f"ForexFactory HTTP {resp.status_code} — fallback horaires fixes", "WARN")
    except Exception as e:
        log(f"ForexFactory erreur: {e} — fallback horaires fixes", "WARN")

    return _ff_cache.get("data") or []


def is_high_impact_news(symbol: str):
    """
    [v6] Vérifie si une news HIGH IMPACT ForexFactory est imminente
    pour les devises du symbole donné.

    Fenêtre de blocage : FF_NEWS_BACK_MIN minutes avant jusqu'à
    FF_NEWS_WINDOW_MIN minutes après la news.

    Retourne (bloqué: bool, description: str | None)
    Fallback sur horaires fixes si FF indisponible.
    """
    if not FF_NEWS_ENABLED:
        return _is_near_news_fallback(), None

    currencies = SYMBOL_CURRENCIES.get(symbol, [])
    events     = fetch_ff_calendar()

    if not events:
        return _is_near_news_fallback(), None

    now = datetime.now(timezone.utc)

    for event in events:
        # Filtre impact HIGH uniquement
        impact = str(event.get("impact", "")).lower()
        if impact not in ("high", "3"):
            continue

        # Filtre devise
        event_currency = str(event.get("country", "")).upper()
        if currencies and event_currency not in currencies:
            continue

        # Parse heure
        dt_utc = _parse_ff_datetime(
            str(event.get("date", "")),
            str(event.get("time", ""))
        )
        if dt_utc is None:
            continue

        diff_min = (dt_utc - now).total_seconds() / 60

        # Fenêtre : -FF_NEWS_BACK_MIN → +FF_NEWS_WINDOW_MIN
        if -FF_NEWS_BACK_MIN <= diff_min <= FF_NEWS_WINDOW_MIN:
            title = event.get("title", "News")
            sign  = "+" if diff_min > 0 else ""
            desc  = f"{event_currency} — {title} ({sign}{int(diff_min)}min)"
            return True, desc

    return False, None


# ════════════════════════════════════════════════════════
#  📊  [v6.27] MACRO SCORE — Inflation / Chômage / Croissance
# ════════════════════════════════════════════════════════

# Mots-clés macro par catégorie
_MACRO_KEYWORDS = {
    "inflation":  ["CPI", "PPI", "PCE", "INFLATION", "CORE INFLATION",
                   "PRICE INDEX", "PRICE PRESSURE"],
    "emploi":     ["NFP", "NON-FARM", "UNEMPLOYMENT", "JOBLESS", "EMPLOYMENT",
                   "PAYROLL", "LABOR", "LABOUR", "CLAIMS"],
    "croissance": ["GDP", "GROWTH", "RETAIL SALES", "PMI", "ISM",
                   "MANUFACTURING", "SERVICES", "TRADE BALANCE"],
}

# Sens attendu : "actual > forecast" = bon ou mauvais pour la devise ?
# BULL = actual > forecast est positif pour la devise
# BEAR = actual > forecast est négatif pour la devise (ex: chômage élevé = mauvais)
_MACRO_SENTIMENT = {
    "inflation":  "BULL",   # inflation haute → banque centrale hawkish → devise forte
    "emploi":     "BULL",   # emploi fort → économie saine → devise forte
    "croissance": "BULL",   # croissance forte → devise forte
}

# Catégorie inverse : chômage élevé = mauvais
_MACRO_INVERSE = ["UNEMPLOYMENT", "JOBLESS", "CLAIMS"]


def _parse_macro_value(val):
    """Parse une valeur macro (ex: '3.2%', '250K', '2.1') en float."""
    if not val:
        return None
    try:
        clean = str(val).strip().replace("%", "").replace("K", "000").replace("M", "000000").replace(",", "")
        return float(clean)
    except (ValueError, TypeError):
        return None


def get_macro_score(currency: str) -> dict:
    """
    [v6.27] Calcule un score macroéconomique pour une devise donnée.

    Analyse les événements ForexFactory récents (30 derniers jours) :
    - CPI / PPI / PCE → inflation
    - NFP / Unemployment → emploi
    - GDP / PMI / Retail Sales → croissance

    Compare actual vs forecast :
    - actual > forecast = signal positif pour la devise (+1)
    - actual < forecast = signal négatif (-1)
    - pas de données = 0

    Retourne :
    {
        "currency": str,
        "score": int,          # -3 à +3
        "bias": "BULL"|"BEAR"|"NEUTRAL",
        "details": [str, ...]  # détails pour le log
    }
    """
    events  = fetch_ff_calendar()
    details = []
    total   = 0
    count   = 0

    for event in events:
        title    = str(event.get("title", "")).upper()
        country  = str(event.get("country", "")).upper()

        if country != currency.upper():
            continue

        actual   = _parse_macro_value(event.get("actual"))
        forecast = _parse_macro_value(event.get("forecast"))

        if actual is None or forecast is None:
            continue

        # Identifie la catégorie
        category = None
        for cat, keywords in _MACRO_KEYWORDS.items():
            if any(kw in title for kw in keywords):
                category = cat
                break
        if not category:
            continue

        # Calcule le signal
        diff = actual - forecast
        if abs(diff) < 0.001:
            continue

        # Inverse si indicateur négatif (chômage)
        is_inverse = any(kw in title for kw in _MACRO_INVERSE)
        signal = 1 if diff > 0 else -1
        if is_inverse:
            signal = -signal

        total += signal
        count += 1
        direction_str = "↑ BULL" if signal > 0 else "↓ BEAR"
        details.append(f"{title[:30]} | {direction_str} (act:{actual} vs prev:{forecast})")

    if count == 0:
        bias  = "NEUTRAL"
        score = 0
    else:
        score = max(-3, min(3, total))
        if score >= 1:
            bias = "BULL"
        elif score <= -1:
            bias = "BEAR"
        else:
            bias = "NEUTRAL"

    return {"currency": currency, "score": score, "bias": bias,
            "details": details[:3], "count": count}


def get_symbol_macro(symbol: str) -> dict:
    """
    Calcule le macro score combiné des deux devises d'un symbole.

    EURUSD → score EUR - score USD
    BTCUSD, indices → None (pas de macro fondamentale directe)
    """
    currencies = SYMBOL_CURRENCIES.get(symbol, [])
    if len(currencies) < 2:
        return None   # crypto ou index → pas de macro cross

    c1, c2 = currencies[0], currencies[1]
    m1 = get_macro_score(c1)
    m2 = get_macro_score(c2)

    # Score combiné : positif = c1 plus fort que c2
    combined = m1["score"] - m2["score"]

    if combined >= 1:
        bias = "BULL"   # c1 plus fort → symbole haussier
    elif combined <= -1:
        bias = "BEAR"   # c2 plus fort → symbole baissier
    else:
        bias = "NEUTRAL"

    return {
        "c1": c1, "c2": c2,
        "score_c1": m1["score"], "score_c2": m2["score"],
        "combined": combined,
        "bias": bias,
        "details_c1": m1["details"],
        "details_c2": m2["details"],
    }


def is_volatile_enough(symbol, atr, price):
    """
    Vérifie si la volatilité est suffisante pour un signal ICT.

    [v6.21] Seuil adaptatif :
    - Weekend  : seuil ×0.60 (crypto compressé de 20-40 % le sam/dim)
    - Silver Bullet : seuil ×0.80 (fenêtres ICT haute probabilité)
    - Semaine normale : seuil nominal

    Ratio = ATR / Price — mesure la volatilité relative du marché.
    """
    if price == 0:
        return False

    threshold = VOLATILITY_THRESHOLDS.get(symbol, VOLATILITY_THRESHOLDS["_forex"])

    now  = datetime.now(timezone.utc)
    wday = now.weekday()

    if wday >= 5:
        # Weekend : marché crypto compressé → tolérance 40 % plus haute
        threshold *= 0.60
        log(f"    [vol] weekend → seuil adaptatif ×0.60 = {threshold:.5f}", "FILTER")
    elif is_silver_bullet_window():
        # Fenêtre Silver Bullet : on accepte une vol légèrement plus faible
        threshold *= 0.80
        log(f"    [vol] Silver Bullet → seuil adaptatif ×0.80 = {threshold:.5f}", "FILTER")

    return (atr / price) >= threshold


# ════════════════════════════════════════════════════════
#  💧  LIQUIDITY SWEEP
# ════════════════════════════════════════════════════════
def detect_liquidity_sweep(rates, direction):
    if len(rates) < 12: return False
    last   = rates[-2]
    window = rates[-12:-2]
    if direction == "BULL":
        return (last["low"] < min(r["low"] for r in window)
                and last["close"] > last["open"])
    else:
        return (last["high"] > max(r["high"] for r in window)
                and last["close"] < last["open"])


# ════════════════════════════════════════════════════════
#  🎯  PROBABILITÉ DYNAMIQUE
# ════════════════════════════════════════════════════════
def dynamic_probability(score, session, symbol, has_sweep,
                         has_ob=False, last_event=None):
    base = SCORE_PROBABILITY.get(score, 40)
    if session == "🇺🇸 New York": base += 5
    if symbol in PREMIUM_SYMBOLS:  base += 5
    if has_sweep:                   base += 5
    if has_ob:                      base += 3   # [v6] OB non mitigé confirmé
    if last_event in ("BOS_BULL", "BOS_BEAR"):
        base += 3                               # [v6] BOS = structure institutionnelle
    return min(base, 92)


# ════════════════════════════════════════════════════════
#  📊  INDICATEURS SMC — BASE
# ════════════════════════════════════════════════════════
def calc_atr(rates, period=ATR_PERIOD):
    trs = [
        max(
            rates[i]["high"] - rates[i]["low"],
            abs(rates[i]["high"] - rates[i-1]["close"]),
            abs(rates[i]["low"]  - rates[i-1]["close"]),
        )
        for i in range(1, len(rates))
    ]
    if not trs: return 1.0
    return sum(trs[-period:]) / period if len(trs) >= period else trs[-1]


# ════════════════════════════════════════════════════════
#  📐  [v6] STRUCTURE AVANCÉE : SWING H/L → BOS / CHoCH
# ════════════════════════════════════════════════════════

def find_swings(rates, lookback=STRUCT_LOOKBACK, window=SWING_WINDOW):
    """
    Détecte les Swing Highs et Swing Lows proprement.

    Un Swing High = le plus haut point parmi les ±window bougies voisines.
    Un Swing Low  = le plus bas  point parmi les ±window bougies voisines.

    Retourne (swing_highs, swing_lows) :
      chacun est une liste de tuples (index_relatif, prix)
    """
    r = rates[-lookback:] if len(rates) > lookback else rates
    swing_highs, swing_lows = [], []

    for i in range(window, len(r) - window):
        h_vals = [r[j]["high"] for j in range(i - window, i + window + 1)]
        l_vals = [r[j]["low"]  for j in range(i - window, i + window + 1)]

        if r[i]["high"] == max(h_vals):
            swing_highs.append((i, r[i]["high"]))

        if r[i]["low"] == min(l_vals):
            swing_lows.append((i, r[i]["low"]))

    return swing_highs, swing_lows


def detect_bos_choch(rates, lookback=STRUCT_LOOKBACK):
    """
    [v6] Analyse de structure institutionnelle SMC/ICT.

    BOS (Break of Structure) :
    ┌─ Structure BULLISH → price casse le dernier Swing High → continuation ↗
    └─ Structure BEARISH → price casse le dernier Swing Low  → continuation ↘

    CHoCH (Change of Character) :
    ┌─ Structure BULLISH → price casse le dernier Swing Low  → retournement baissier
    └─ Structure BEARISH → price casse le dernier Swing High → retournement haussier

    Retourne un dict :
    {
      "structure":  "BULLISH" | "BEARISH" | "NEUTRAL",
      "last_event": "BOS_BULL" | "BOS_BEAR" | "CHOCH_BULL" | "CHOCH_BEAR" | None,
      "last_sh":    float | None,   ← dernier Swing High
      "last_sl":    float | None,   ← dernier Swing Low
    }
    """
    r  = rates[-lookback:] if len(rates) > lookback else rates
    sh_list, sl_list = find_swings(r)

    result = {
        "structure":  "NEUTRAL",
        "last_event": None,
        "last_sh":    None,
        "last_sl":    None,
    }

    if len(sh_list) < 2 or len(sl_list) < 2:
        return result

    prev_sh, last_sh = sh_list[-2][1], sh_list[-1][1]
    prev_sl, last_sl = sl_list[-2][1], sl_list[-1][1]

    result["last_sh"] = last_sh
    result["last_sl"] = last_sl

    # ── Détermination de la structure ─────────────────
    # Higher Highs + Higher Lows  = BULLISH (trend haussier)
    # Lower Highs  + Lower Lows   = BEARISH (trend baissier)
    if last_sh > prev_sh and last_sl > prev_sl:
        result["structure"] = "BULLISH"
    elif last_sh < prev_sh and last_sl < prev_sl:
        result["structure"] = "BEARISH"

    last_close = r[-1]["close"]

    # ── Détection BOS / CHoCH ────────────────────────
    if result["structure"] == "BULLISH":
        if last_close > last_sh:
            result["last_event"] = "BOS_BULL"    # Continuation haussière ✅
        elif last_close < last_sl:
            result["last_event"] = "CHOCH_BEAR"  # Retournement baissier ⚠️

    elif result["structure"] == "BEARISH":
        if last_close < last_sl:
            result["last_event"] = "BOS_BEAR"    # Continuation baissière ✅
        elif last_close > last_sh:
            result["last_event"] = "CHOCH_BULL"  # Retournement haussier ⚠️

    return result


def market_structure(rates, lookback=MST_LOOKBACK):
    """
    Wrapper rétrocompatible v5 → utilise detect_bos_choch() en interne.
    Retourne "BULLISH" | "BEARISH" | "NEUTRAL"
    """
    return detect_bos_choch(rates, lookback)["structure"]


# ════════════════════════════════════════════════════════
#  🏦  [v6] ORDER BLOCKS ICT VRAIS
# ════════════════════════════════════════════════════════

def find_order_blocks(rates, direction: str, atr: float,
                       lookback: int = OB_LOOKBACK):
    """
    [v6] Détecte les Order Blocks ICT authentiques.

    Définition :
    ┌ Bullish OB = dernière bougie BEARISH (close < open) juste avant
    │  un mouvement haussier fort (≥ OB_IMPULSE_ATR × ATR dans les 15 bougies)
    └ Bearish OB = dernière bougie BULLISH (close > open) juste avant
       un mouvement baissier fort

    Retourne une liste d'OBs (du plus ancien au plus récent) :
    [{"idx": int, "hi": float, "lo": float, "mid": float, "type": str}, ...]
    """
    obs      = []
    start    = max(0, len(rates) - lookback)
    min_move = OB_IMPULSE_ATR * atr

    for i in range(start, len(rates) - 5):
        c = rates[i]

        if direction == "BULL":
            # Candidate : bougie bearish
            if c["close"] >= c["open"]:
                continue
            # Vérifie si un mouvement haussier fort suit
            for j in range(i + 1, min(i + 16, len(rates))):
                if (rates[j]["high"] - c["low"]) >= min_move:
                    obs.append({
                        "idx":  i,
                        "hi":   c["high"],
                        "lo":   c["low"],
                        "mid":  (c["high"] + c["low"]) / 2,
                        "type": "BULL_OB",
                    })
                    break

        else:  # direction == "BEAR"
            # Candidate : bougie bullish
            if c["close"] <= c["open"]:
                continue
            # Vérifie si un mouvement baissier fort suit
            for j in range(i + 1, min(i + 16, len(rates))):
                if (c["high"] - rates[j]["low"]) >= min_move:
                    obs.append({
                        "idx":  i,
                        "hi":   c["high"],
                        "lo":   c["low"],
                        "mid":  (c["high"] + c["low"]) / 2,
                        "type": "BEAR_OB",
                    })
                    break

    return obs


# ════════════════════════════════════════════════════════
#  🆕  [v6.28] DISPLACEMENT + RETRACEMENT TO OB
#       Le setup ICT le plus puissant — celui du chart XAUUSD
# ════════════════════════════════════════════════════════
def detect_displacement_ob_entry(rates, atr):
    """
    Détecte le setup "Displacement → OB → Retracement → Entrée".

    Pattern exact (chart XAUUSD 06/04) :
    ┌─────────────────────────────────────────────────────┐
    │  1. Displacement fort (≥ 1.5×ATR) sur 1-5 bougies  │
    │  2. OB = dernière bougie opposée avant le move      │
    │  3. Prix monte / descend loin de l'OB               │
    │  4. Prix RETRACE vers la zone OB                    │
    │  5. → Entrée dans la direction du displacement      │
    └─────────────────────────────────────────────────────┘

    Retourne :
    {
      "direction":  "BULL" | "BEAR",
      "ob_hi":      float,   ← haut de l'OB
      "ob_lo":      float,   ← bas de l'OB
      "ob_mid":     float,   ← 50% de l'OB
      "disp_hi":    float,   ← extrême du displacement
      "disp_lo":    float,
      "strength":   float,   ← force en × ATR
      "retrace_pct":float,   ← % de retracement actuel
      "in_ob":      bool,    ← prix actuellement dans l'OB
    }
    ou None si pattern absent.
    """
    if len(rates) < 20:
        return None

    price  = rates[-1]["close"]
    window = rates[-30:] if len(rates) >= 30 else rates
    n      = len(window)

    # ── Cherche le displacement le plus récent ──────────
    for span in range(1, 6):
        for i in range(n - span - 2, max(n - 20, 1), -1):
            start = window[i]["open"]
            end   = window[i + span]["close"]
            move  = end - start
            strength = abs(move) / atr

            if strength < 1.5:
                continue

            direction = "BULL" if move > 0 else "BEAR"

            # Extrêmes du displacement
            disp_hi = max(window[j]["high"] for j in range(i, i + span + 1))
            disp_lo = min(window[j]["low"]  for j in range(i, i + span + 1))

            # ── OB = dernière bougie opposée AVANT le displacement ──
            ob = None
            for k in range(i - 1, max(i - 8, -1), -1):
                c = window[k]
                if direction == "BULL" and c["close"] < c["open"]:
                    # Bougie bearish avant move haussier = OB haussier
                    ob = {"hi": c["high"], "lo": c["low"],
                          "mid": (c["high"] + c["low"]) / 2}
                    break
                elif direction == "BEAR" and c["close"] > c["open"]:
                    # Bougie bullish avant move baissier = OB baissier
                    ob = {"hi": c["high"], "lo": c["low"],
                          "mid": (c["high"] + c["low"]) / 2}
                    break

            if ob is None:
                continue

            # ── Vérifie que le prix a voyagé loin de l'OB après le move ──
            post_move = window[i + span:]
            if not post_move:
                continue

            if direction == "BULL":
                max_after = max(c["high"] for c in post_move)
                # Prix a bien monté loin (≥ 1×ATR au-dessus de l'OB)
                if max_after < ob["hi"] + atr:
                    continue
                # Retracement actuel vers l'OB
                span_move = max_after - ob["lo"]
                retrace   = (max_after - price) / span_move if span_move > 0 else 0
                in_ob     = (ob["lo"] - atr * 0.3) <= price <= (ob["hi"] + atr * 0.3)

            else:  # BEAR
                min_after = min(c["low"] for c in post_move)
                if min_after > ob["lo"] - atr:
                    continue
                span_move = ob["hi"] - min_after
                retrace   = (price - min_after) / span_move if span_move > 0 else 0
                in_ob     = (ob["lo"] - atr * 0.3) <= price <= (ob["hi"] + atr * 0.3)

            # Retracement valide : entre 30% et 85% du move (pas trop peu, pas trop)
            if not (0.30 <= retrace <= 0.85):
                continue

            return {
                "direction":   direction,
                "ob_hi":       round(ob["hi"], 5),
                "ob_lo":       round(ob["lo"], 5),
                "ob_mid":      round(ob["mid"], 5),
                "disp_hi":     round(disp_hi, 5),
                "disp_lo":     round(disp_lo, 5),
                "strength":    round(strength, 1),
                "retrace_pct": round(retrace * 100, 1),
                "in_ob":       in_ob,
            }

    return None


def get_best_unmitigated_ob(rates, obs: list, direction: str,
                              price: float, atr: float):
    """
    [v6] Sélectionne le meilleur Order Block non mitigé dans lequel
    le prix actuel se trouve (± OB_TOLERANCE_ATR × ATR).

    Mitigation = au moins une bougie a FERMÉ à l'intérieur de l'OB
    après sa formation. Un OB mitigé perd son pouvoir.

    Parcours du plus récent au plus ancien (on préfère l'OB le plus proche).
    """
    if not obs:
        return None

    tolerance = OB_TOLERANCE_ATR * atr

    for ob in reversed(obs):
        idx = ob["idx"]

        # ── Vérification mitigation ─────────────────────────
        mitigated = False
        for k in range(idx + 1, len(rates) - 1):
            close_k = rates[k]["close"]
            if ob["lo"] <= close_k <= ob["hi"]:
                mitigated = True
                break

        if mitigated:
            continue  # OB déjà consommé → on ignore

        # ── Price dans l'OB (avec tolérance) ────────────────
        if (ob["lo"] - tolerance) <= price <= (ob["hi"] + tolerance):
            return ob

    return None


# ════════════════════════════════════════════════════════
#  📊  AUTRES INDICATEURS SMC
# ════════════════════════════════════════════════════════

def get_htf_bias(symbol):
    """Biais HTF : Daily + H4 (reconstruit depuis H1)."""
    rates_d  = get_rates(symbol, "1d", "90d")
    daily    = (market_structure(rates_d, 40)
                if rates_d and len(rates_d) >= 20 else "NEUTRAL")
    rates_h4 = get_rates(symbol, "1h", "30d")
    h4 = "NEUTRAL"
    if rates_h4 and len(rates_h4) >= 20:
        h4_rates = []
        for i in range(0, len(rates_h4) - 3, 4):
            block = rates_h4[i:i+4]
            h4_rates.append({
                "open":  block[0]["open"],
                "high":  max(b["high"] for b in block),
                "low":   min(b["low"]  for b in block),
                "close": block[-1]["close"],
            })
        h4 = market_structure(h4_rates, 30) if len(h4_rates) >= 10 else "NEUTRAL"
    if   daily == "BULLISH" and h4 in ("BULLISH", "NEUTRAL"): bias = "BULL"
    elif daily == "BEARISH" and h4 in ("BEARISH", "NEUTRAL"): bias = "BEAR"
    elif daily == "NEUTRAL" and h4 == "BULLISH": bias = "BULL"   # semi-biais haussier
    elif daily == "NEUTRAL" and h4 == "BEARISH": bias = "BEAR"   # semi-biais baissier
    elif daily == "BULLISH" and h4 == "BEARISH": bias = "BULL"   # Daily prime sur H4
    elif daily == "BEARISH" and h4 == "BULLISH": bias = "BEAR"   # Daily prime sur H4
    else: bias = "NEUTRAL"
    return {"bias": bias, "daily": daily, "h4": h4}


def find_impulse(rates, atr):
    """Détecte le mouvement impulsif le plus fort dans la fenêtre."""
    best, best_size = None, 0
    start = max(0, len(rates) - IMPULSE_LOOKBACK)
    for i in range(start, len(rates) - 5):
        for j in range(i + 3, min(i + 25, len(rates) - 2)):
            move = abs(rates[j]["close"] - rates[i]["close"])
            if move >= IMPULSE_MIN_ATR * atr and move > best_size:
                best_size = move
                best = {
                    "start_px": rates[i]["close"],
                    "end_px":   rates[j]["close"],
                    "dir": "BULL" if rates[j]["close"] > rates[i]["close"] else "BEAR",
                }
    return best


def find_recent_displacement(rates, atr, lookback=15):
    """
    [v6.25] Détecte un displacement institutionnel récent fort.

    Définition ICT :
    Un displacement = move ≥ 2×ATR sur 1 à 5 bougies consécutives
    dans les `lookback` dernières bougies M15/M5.

    Si détecté → la direction LTF suit ce displacement (pas le HTF).
    Le 50% du move = zone d'entrée optimale (OTE).

    Retourne :
      {"direction": "BULL"|"BEAR",
       "hi": float, "lo": float,
       "entry_50": float,         ← entrée au 50% du move
       "sl_beyond": float,        ← SL au-delà de l'extrême
       "strength": float}         ← taille en × ATR
    ou None si aucun displacement récent.
    """
    if len(rates) < lookback + 3:
        return None

    window = rates[-lookback:]
    best   = None
    best_strength = 0.0

    for span in (1, 2, 3, 4, 5):
        for i in range(len(window) - span - 1, 1, -1):
            start_c = window[i]
            end_c   = window[i + span]
            move    = end_c["close"] - start_c["open"]
            strength = abs(move) / atr

            if strength < 2.0:
                continue

            age = len(window) - i - span
            if age > 8:
                continue  # trop vieux

            # Priorité : le plus récent parmi ceux ≥ 2×ATR
            # (on prend le premier trouvé = le plus récent car on itère en sens inverse)
            hi = max(window[j]["high"] for j in range(i, i + span + 1))
            lo = min(window[j]["low"]  for j in range(i, i + span + 1))

            direction  = "BULL" if move > 0 else "BEAR"
            entry_50   = (hi + lo) / 2
            sl_margin  = atr * SL_ATR_MARGIN
            sl_beyond  = (lo - sl_margin) if direction == "BULL" else (hi + sl_margin)

            return {
                "direction":  direction,
                "hi":         hi,
                "lo":         lo,
                "entry_50":   round(entry_50, 5),
                "sl_beyond":  round(sl_beyond, 5),
                "strength":   round(strength, 1),
                "age_bars":   age,
            }

    return None


def in_equilibrium(price, impulse):
    """Price dans la zone 45–60% de l'impulse (Fibonacci équilibre)."""
    lo   = min(impulse["start_px"], impulse["end_px"])
    hi   = max(impulse["start_px"], impulse["end_px"])
    span = hi - lo
    if span == 0: return False
    return (lo + span * FIB_LOW) <= price <= (lo + span * FIB_HIGH)


def find_fvg(rates, direction, price, atr):
    """Fair Value Gap : écart de prix non comblé entre 3 bougies."""
    for i in range(max(1, len(rates) - FVG_LOOKBACK), len(rates) - 2):
        c1, c3 = rates[i-1], rates[i+1]
        if direction == "BULL" and c3["low"] > c1["high"]:
            lo, hi = c1["high"], c3["low"]
            size   = hi - lo
            if size < atr * 0.08: continue
            fill = (price - lo) / size
            if FVG_FILL_MIN <= fill <= FVG_FILL_MAX:
                return {"lo": lo, "hi": hi}
        elif direction == "BEAR" and c3["high"] < c1["low"]:
            lo, hi = c3["high"], c1["low"]
            size   = hi - lo
            if size < atr * 0.08: continue
            fill = (hi - price) / size
            if FVG_FILL_MIN <= fill <= FVG_FILL_MAX:
                return {"lo": lo, "hi": hi}
    return None


# ════════════════════════════════════════════════════════
#  🆕  [v6+] PD ARRAYS — Premium / Discount Zones
# ════════════════════════════════════════════════════════
def get_pd_array(rates, lookback=60):
    """
    Calcule les zones Premium / Discount du dernier range majeur.
    Discount  ≤ 50 % du range → zone d'achat
    Premium   ≥ 50 % du range → zone de vente
    Equilibrium = exactement 50 %

    Retourne {"hi": float, "lo": float, "eq": float, "zone": "DISCOUNT"|"PREMIUM"|"EQ"}
    """
    r  = rates[-lookback:] if len(rates) > lookback else rates
    hi = max(b["high"] for b in r)
    lo = min(b["low"]  for b in r)
    eq = (hi + lo) / 2
    price = rates[-1]["close"]
    span  = hi - lo
    if span == 0:
        return None
    pct = (price - lo) / span   # 0 = bas du range, 1 = haut
    if pct <= 0.45:
        zone = "DISCOUNT"
    elif pct >= 0.55:
        zone = "PREMIUM"
    else:
        zone = "EQ"
    return {"hi": hi, "lo": lo, "eq": eq, "zone": zone, "pct": round(pct * 100, 1)}


def pd_array_aligned(pd, direction):
    """
    Vérifie que le signal est dans la bonne zone PD.
    BULL en DISCOUNT = ✅ | BEAR en PREMIUM = ✅
    Tout le reste = ❌
    """
    if pd is None:
        return True   # pas de données = on laisse passer
    if direction == "BULL" and pd["zone"] in ("DISCOUNT", "EQ"):
        return True
    if direction == "BEAR" and pd["zone"] in ("PREMIUM", "EQ"):
        return True
    return False


# ════════════════════════════════════════════════════════
#  🆕  [v6+] SILVER BULLET WINDOWS
# ════════════════════════════════════════════════════════
def is_silver_bullet_window():
    """
    Fenêtres Silver Bullet ICT (heure NY = UTC-4 en été, UTC-5 en hiver).
    On utilise UTC-5 (approximation stable).
      London SB  : 02h00–05h00 NY  → 07h00–10h00 UTC
      NY AM SB   : 10h00–11h00 NY  → 15h00–16h00 UTC  ← la plus forte
      NY PM SB   : 14h00–15h00 NY  → 19h00–20h00 UTC
    """
    hour_utc = datetime.now(timezone.utc).hour
    return hour_utc in (7, 8, 9, 15, 19)


# ════════════════════════════════════════════════════════
#  🆕  [v6+] JUDAS SWING (faux breakout précis)
# ════════════════════════════════════════════════════════
def detect_judas_swing(rates, direction, atr):
    """
    Judas Swing ICT : faux breakout d'un swing high/low
    suivi d'un retour immédiat (≤ 3 bougies) dans l'OB ou la zone.

    Critères :
    1. Une bougie récente casse le swing high/low précédent
    2. Elle referme à l'intérieur (wick de rejet)
    3. La bougie suivante confirme le retour dans la bonne direction
    """
    if len(rates) < 15:
        return False
    window = rates[-15:]
    ref    = window[:-4]
    recents = window[-4:]

    if direction == "BULL":
        swing_lo = min(r["low"] for r in ref)
        for i, c in enumerate(recents[:-1]):
            nxt = recents[i + 1]
            # Bougie casse sous swing_lo mais referme au-dessus
            if c["low"] < swing_lo and c["close"] > swing_lo:
                # Bougie suivante bullish = confirmation
                if nxt["close"] > nxt["open"]:
                    return True
    else:
        swing_hi = max(r["high"] for r in ref)
        for i, c in enumerate(recents[:-1]):
            nxt = recents[i + 1]
            if c["high"] > swing_hi and c["close"] < swing_hi:
                if nxt["close"] < nxt["open"]:
                    return True
    return False


# ════════════════════════════════════════════════════════
#  🆕  [v6+] INVERSION FVG (iFVG)
# ════════════════════════════════════════════════════════
def detect_inversion_fvg(rates, direction, atr):
    """
    iFVG : un ancien FVG haussier cassé à la baisse devient bearish iFVG
    (et vice versa) → zone de rejet ultra-forte.

    Retourne {"lo": float, "hi": float, "type": "iFVG_BULL"|"iFVG_BEAR"} ou None.
    """
    if len(rates) < 10:
        return None
    price = rates[-1]["close"]

    # Cherche les FVG haussiers dans l'historique, puis vérifie s'ils ont été cassés
    for i in range(max(1, len(rates) - FVG_LOOKBACK), len(rates) - 5):
        c1, c3 = rates[i-1], rates[i+1]

        # FVG haussier original
        if c3["low"] > c1["high"]:
            fvg_lo, fvg_hi = c1["high"], c3["low"]
            # A-t-il été cassé par la suite ? (close en dessous du FVG lo)
            for k in range(i + 2, len(rates) - 1):
                if rates[k]["close"] < fvg_lo:
                    # Cassé → iFVG bearish
                    if direction == "BEAR" and fvg_lo <= price <= fvg_hi:
                        return {"lo": fvg_lo, "hi": fvg_hi, "type": "iFVG_BEAR"}
                    break

        # FVG baissier original
        if c3["high"] < c1["low"]:
            fvg_lo, fvg_hi = c3["high"], c1["low"]
            for k in range(i + 2, len(rates) - 1):
                if rates[k]["close"] > fvg_hi:
                    # Cassé → iFVG bullish
                    if direction == "BULL" and fvg_lo <= price <= fvg_hi:
                        return {"lo": fvg_lo, "hi": fvg_hi, "type": "iFVG_BULL"}
                    break
    return None


# ════════════════════════════════════════════════════════
#  🆕  [v6+] BREAKER BLOCKS
# ════════════════════════════════════════════════════════
def detect_breaker_block(rates, direction, atr):
    """
    Breaker Block : zone créée après un BOS + retour sur le niveau cassé.
    Plus puissant qu'un OB classique en continuation de tendance.

    Bullish Breaker : ancien swing high cassé → retour sur ce niveau → achat
    Bearish Breaker : ancien swing low cassé  → retour sur ce niveau → vente
    """
    if len(rates) < 20:
        return None
    price  = rates[-1]["close"]
    window = rates[-40:] if len(rates) >= 40 else rates

    highs = [(i, window[i]["high"]) for i in range(2, len(window)-2)
             if window[i]["high"] == max(window[j]["high"] for j in range(i-2, i+3))]
    lows  = [(i, window[i]["low"]) for i in range(2, len(window)-2)
             if window[i]["low"]  == min(window[j]["low"]  for j in range(i-2, i+3))]

    tolerance = atr * 0.5

    if direction == "BULL" and highs:
        # Cherche un ancien swing high cassé puis retesté
        for idx, sh_price in highs[:-1]:
            # Le prix a-t-il cassé ce swing high ?
            broke = any(window[k]["close"] > sh_price for k in range(idx+1, len(window)-1))
            if broke:
                # Est-on maintenant proche de ce niveau (retest) ?
                if abs(price - sh_price) <= tolerance:
                    return {"level": sh_price, "type": "BREAKER_BULL"}

    if direction == "BEAR" and lows:
        for idx, sl_price in lows[:-1]:
            broke = any(window[k]["close"] < sl_price for k in range(idx+1, len(window)-1))
            if broke:
                if abs(price - sl_price) <= tolerance:
                    return {"level": sl_price, "type": "BREAKER_BEAR"}
    return None


# ════════════════════════════════════════════════════════
#  🆕  [v6+] UNICORN MODEL (setup rare, RR 1:5+)
# ════════════════════════════════════════════════════════
def is_unicorn_model(rates, direction, atr, bos_info, has_sweep, fvg, ob):
    """
    Unicorn Model ICT :
    1. Liquidity sweep ✅
    2. BOS ou CHoCH fort ✅
    3. Displacement (impulse ≥ 1.5×ATR) ✅
    4. Entrée dans le FVG ou OB créé après le sweep ✅

    Retourne True si toutes les conditions sont réunies.
    """
    if not has_sweep:
        return False
    if bos_info.get("last_event") not in ("BOS_BULL", "BOS_BEAR", "CHOCH_BULL", "CHOCH_BEAR"):
        return False

    # Displacement : move fort sur les 5 dernières bougies
    recent = rates[-6:]
    move   = max(abs(recent[i]["close"] - recent[i-1]["close"]) for i in range(1, len(recent)))
    if move < atr * 1.5:
        return False

    # Entrée dans FVG ou OB
    if fvg is None and ob is None:
        return False

    return True


def check_rejection(rates, direction):
    """Détecte Pinbar / Engulfing / Bloc de rejet."""
    if len(rates) < 4: return None
    c, prev = rates[-2], rates[-3]
    rng = c["high"] - c["low"]
    if rng == 0: return None
    body       = abs(c["close"] - c["open"])
    upper_wick = c["high"] - max(c["open"], c["close"])
    lower_wick = min(c["open"], c["close"]) - c["low"]
    if direction == "BULL":
        if lower_wick / rng >= 0.55 and body / rng <= 0.35: return "PINBAR_BULL"
        if (c["close"] > c["open"]
                and c["close"] > prev["high"]
                and c["open"] < prev["close"]):             return "ENGULFING_BULL"
        if c["close"] > c["open"] and body / rng >= 0.65:  return "BLOC_BULL"
    else:
        if upper_wick / rng >= 0.55 and body / rng <= 0.35: return "PINBAR_BEAR"
        if (c["close"] < c["open"]
                and c["close"] < prev["low"]
                and c["open"] > prev["close"]):             return "ENGULFING_BEAR"
        if c["close"] < c["open"] and body / rng >= 0.65:  return "BLOC_BEAR"
    return None


# ════════════════════════════════════════════════════════
#  🆕  [v6+] CONFIRM LTF REACTION + OTE
# ════════════════════════════════════════════════════════
def confirm_ltf_reaction(rates_m5, direction, atr_m5):
    """
    Vérifie une réaction M5 claire dans la direction du bias.
    Critères (au moins 1) :
      - Displacement M5 : impulse ≥ 1×ATR dans la bonne direction
      - OTE M5 : retracement 62–79% du dernier swing M5
      - Rejet M5 clair (Pinbar / Engulfing)
    """
    if not rates_m5 or len(rates_m5) < 10:
        return False, "données M5 insuffisantes"

    # 1. Displacement
    last = rates_m5[-1]
    prev = rates_m5[-2]
    if direction == "BULL":
        displacement = last["close"] - prev["low"]
    else:
        displacement = prev["high"] - last["close"]
    if displacement >= atr_m5:
        return True, "Displacement M5 ✅"

    # 2. OTE 62–79% sur le dernier swing M5
    if len(rates_m5) >= 20:
        highs = [r["high"] for r in rates_m5[-20:]]
        lows  = [r["low"]  for r in rates_m5[-20:]]
        swing_hi = max(highs)
        swing_lo = min(lows)
        span = swing_hi - swing_lo
        if span > 0:
            price = rates_m5[-1]["close"]
            if direction == "BULL":
                retrace = (swing_hi - price) / span
            else:
                retrace = (price - swing_lo) / span
            if 0.62 <= retrace <= 0.79:
                return True, "OTE 62-79% M5 🎯"

    # 3. Rejet M5
    rej = check_rejection(rates_m5, direction)
    if rej:
        return True, f"Rejet M5 {rej}"

    return False, "pas de réaction LTF"


# ════════════════════════════════════════════════════════
#  🆕  [v6+] INDUCEMENT (faux breakout avant vrai move)
# ════════════════════════════════════════════════════════
def is_inducement(rates, direction, atr):
    """
    Détecte un inducement : le prix a cassé un swing
    puis est revenu violemment → piège retail avant le vrai move.
    Signal haussier si on voit : faux break baissier + retour rapide au-dessus.
    """
    if len(rates) < 15:
        return False
    window = rates[-15:]
    lows   = [r["low"]  for r in window[:-3]]
    highs  = [r["high"] for r in window[:-3]]
    last   = window[-1]

    if direction == "BULL":
        swing_lo = min(lows)
        # Faux break : une bougie récente a cassé sous le swing puis refermé au-dessus
        for i in range(-4, -1):
            c = window[i]
            if c["low"] < swing_lo and c["close"] > swing_lo:
                # Et maintenant le prix est remonté loin du faux break
                if last["close"] > swing_lo + 0.3 * atr:
                    return True
    else:
        swing_hi = max(highs)
        for i in range(-4, -1):
            c = window[i]
            if c["high"] > swing_hi and c["close"] < swing_hi:
                if last["close"] < swing_hi - 0.3 * atr:
                    return True
    return False


# ════════════════════════════════════════════════════════
#  🆕  [v6+] MARKET REGIME FILTER (trending vs chop)
# ════════════════════════════════════════════════════════
def market_is_trending(rates, lookback=60, symbol=""):
    """
    Détermine si le marché est en tendance ou en range.
    Méthode : compte les swing highs/lows sur les N dernières bougies.

    [v6.21] Seuil adaptatif :
    > 8  swings = range (semaine)
    > 12 swings = range (BTC weekend) — liquidité faible = swings fréquents normaux

    Retourne (is_trending: bool, swing_count: int)
    """
    r = rates[-lookback:] if len(rates) > lookback else rates
    swing_count = 0
    for i in range(2, len(r) - 2):
        if r[i]["high"] == max(r[j]["high"] for j in range(i-2, i+3)):
            swing_count += 1
        if r[i]["low"] == min(r[j]["low"] for j in range(i-2, i+3)):
            swing_count += 1

    # Seuil relaxé pour BTC le weekend (moves erratiques = swings élevés normaux)
    wday = datetime.now(timezone.utc).weekday()
    max_swings = 12 if (symbol == "BTCUSD" and wday >= 5) else 8

    is_trending = swing_count <= max_swings
    return is_trending, swing_count


# ════════════════════════════════════════════════════════
#  🆕  [v6+] TP DYNAMIQUE sur prochaine liquidité
# ════════════════════════════════════════════════════════
def find_next_liquidity(rates, direction, price, atr):
    """
    Trouve le prochain pool de liquidité (equal highs/lows, previous swing).
    Utilisé pour calculer un TP dynamique plus précis que RR fixe.
    Retourne le prix cible ou None.
    """
    if len(rates) < 30:
        return None
    window = rates[-60:] if len(rates) >= 60 else rates

    if direction == "BULL":
        # Cherche les equal highs ou le dernier Swing High au-dessus du prix
        candidates = []
        for i in range(2, len(window) - 2):
            h = window[i]["high"]
            if h > price + atr * 0.5:
                # Equal high : deux highs très proches
                neighbors = [window[j]["high"] for j in range(max(0,i-5), i)]
                if any(abs(h - n) < atr * 0.3 for n in neighbors):
                    candidates.append(h)
                # Ou swing high isolé
                if window[i]["high"] == max(window[j]["high"] for j in range(i-2, i+3)):
                    candidates.append(h)
        candidates = [c for c in candidates if c > price + atr]
        return min(candidates) if candidates else None
    else:
        candidates = []
        for i in range(2, len(window) - 2):
            l = window[i]["low"]
            if l < price - atr * 0.5:
                neighbors = [window[j]["low"] for j in range(max(0,i-5), i)]
                if any(abs(l - n) < atr * 0.3 for n in neighbors):
                    candidates.append(l)
                if window[i]["low"] == min(window[j]["low"] for j in range(i-2, i+3)):
                    candidates.append(l)
        candidates = [c for c in candidates if c < price - atr]
        return max(candidates) if candidates else None


# ════════════════════════════════════════════════════════
#  🆕  [v6+] FILTRE CORRÉLATION
# ════════════════════════════════════════════════════════
# Groupes de paires corrélées : on ne prend qu'un signal par groupe à la fois
CORRELATION_GROUPS = [
    {"EURUSD", "GBPUSD", "EURGBP", "EURJPY", "GBPJPY"},   # majeurs EUR/GBP
    {"USDJPY", "USDCAD"},                                    # USD haussier
    {"XAUUSD", "XAGUSD"},                                    # métaux
    {"BTCUSD", "ETHUSD"},                                    # crypto
]

_active_signals: dict = {}   # {symbol: timestamp}

def correlation_blocked(symbol, cooldowns):
    """Retourne True si un symbole corrélé a déjà un signal actif récent."""
    for group in CORRELATION_GROUPS:
        if symbol in group:
            for other in group:
                if other == symbol: continue
                if other in cooldowns:
                    elapsed = (time.time() - cooldowns[other]) / 60
                    if elapsed < COOLDOWN_MIN:
                        return True, other
    return False, None


# ════════════════════════════════════════════════════════
#  🆕  [v6+] KILLZONE (2 premières heures London/NY)
# ════════════════════════════════════════════════════════
def in_killzone():
    """
    Killzone = fenêtre haute probabilité ICT.
    London : 07h00–09h00 UTC
    New York: 13h00–15h00 UTC
    """
    hour = datetime.now(timezone.utc).hour
    return (7 <= hour < 9) or (13 <= hour < 15)


def score_signal(mst, impulse, equi, fvg, ob, rej):
    """
    Score /6 (inchangé vs v5, mais composante #5 = Order Block [v6]) :
      1. Structure M15 confirmée (BOS aligné au biais HTF)
      2. Impulse fort détecté
      3. Equilibrium 50% (retracement Fibonacci)
      4. FVG (Fair Value Gap) en confluence
      5. Order Block non mitigé  ← [v6] remplace SD zone basique
      6. Rejet de prix (Pinbar / Engulfing / Bloc)
    """
    return sum([
        mst != "NEUTRAL",
        impulse is not None,
        equi,
        fvg is not None,
        ob  is not None,   # [v6] Order Block ICT
        rej is not None,
    ])


def signal_label(score, has_sweep, has_ob=False, unicorn=False):
    if unicorn:                              return "🦄 UNICORN"
    if score >= 6 and has_sweep and has_ob: return "⚡ ELITE ICT"
    if score >= 6 and has_sweep:            return "⚡ ELITE"
    if score >= 6:                          return "⚡ MAX"
    if score >= 5:                          return "🔥 STRONG"
    return "📊 MEDIUM"


def calc_sl_choch(rates, direction, entry, atr):
    """SL basé sur le dernier CHoCH valide (swing structurel)."""
    r     = rates[-CHOCH_LOOKBACK:]
    lows  = [x["low"]  for x in r]
    highs = [x["high"] for x in r]
    if direction == "BULL":
        swing_lows = [
            lows[i] for i in range(2, len(lows)-2)
            if lows[i] == min(lows[i-2:i+3])
        ]
        if len(swing_lows) >= 2:
            for k in range(len(swing_lows)-1, 0, -1):
                if swing_lows[k] > swing_lows[k-1]:
                    sl = swing_lows[k] - atr * SL_ATR_MARGIN
                    if sl < entry: return round(sl, 5)
        sl = min(lows) - atr * SL_ATR_MARGIN
    else:
        swing_highs = [
            highs[i] for i in range(2, len(highs)-2)
            if highs[i] == max(highs[i-2:i+3])
        ]
        if len(swing_highs) >= 2:
            for k in range(len(swing_highs)-1, 0, -1):
                if swing_highs[k] < swing_highs[k-1]:
                    sl = swing_highs[k] + atr * SL_ATR_MARGIN
                    if sl > entry: return round(sl, 5)
        sl = max(highs) + atr * SL_ATR_MARGIN
    dist = abs(entry - sl)
    mn, mx = entry * 0.001, entry * 0.06
    if dist < mn: sl = entry - mn if direction == "BULL" else entry + mn
    if dist > mx: sl = entry - mx if direction == "BULL" else entry + mx
    return round(sl, 5)


def calc_lot(symbol, entry, sl, balance, risk_pct):
    """Calcul du lot en fonction du risque $."""
    risk_usd = balance * risk_pct
    sl_dist  = abs(entry - sl)
    if sl_dist == 0: return 0.01
    pv  = PIP_VALUES.get(symbol, 1.0)
    lot = risk_usd / (sl_dist * pv * 100)
    return max(0.01, min(round(lot, 2), 10.0))


# ════════════════════════════════════════════════════════
#  🔍  ANALYSE COMPLÈTE DU SYMBOLE
# ════════════════════════════════════════════════════════
def analyze_symbol(symbol, cooldowns=None):
    """
    Analyse complète d'un symbole :
    1. Biais HTF (Daily + H4)
    2. Données M15 + filtre volatilité
    3. Market Regime Filter (trending vs chop)
    4. Structure BOS/CHoCH avancée
    5. Order Blocks ICT + mitigation
    6. FVG, impulse, equilibrium, rejet M15
    7. Inducement detection
    8. Confirmation LTF M5 (OTE / displacement / rejet)
    9. Liquidity Sweep + TP dynamique
    10. Score /6 + filtre SCORE_MIN + corrélation
    """
    htf = get_htf_bias(symbol)
    log(f"  {symbol} HTF → Daily:{htf['daily']} H4:{htf['h4']} Biais:{htf['bias']}", "HTF")
    if htf["bias"] == "NEUTRAL":
        return None

    # [v6.27] Macro Score fondamental
    macro = get_symbol_macro(symbol)
    if macro:
        log(
            f"  {symbol} MACRO → {macro['c1']}:{macro['score_c1']:+d} "
            f"{macro['c2']}:{macro['score_c2']:+d} "
            f"Combined:{macro['combined']:+d} Bias:{macro['bias']}",
            "HTF",
        )
        # Si macro FORTEMENT opposé au HTF → skip (fondamental contre technique)
        if macro["bias"] != "NEUTRAL" and macro["bias"] != htf["bias"]:
            if abs(macro["combined"]) >= 2:
                log(
                    f"  {symbol}: Macro {macro['bias']} ({macro['combined']:+d}) "
                    f"oppose HTF {htf['bias']} → skip",
                    "FILTER",
                )
                return None

    rates_m15 = get_rates(symbol, "15m", "5d")
    if not rates_m15 or len(rates_m15) < 60:
        return None

    price = rates_m15[-1]["close"]
    atr   = calc_atr(rates_m15)

    wday = datetime.now(timezone.utc).weekday()
    _btc_weekend = (symbol == "BTCUSD" and wday >= 5)
    if not _btc_weekend and not is_volatile_enough(symbol, atr, price):
        log(f"  {symbol}: volatilité insuffisante — skip", "FILTER")
        stats["filtered_vol"] += 1
        return None
    if _btc_weekend:
        log(f"  {symbol}: vol bypass weekend → filtres ICT actifs (ATR/p={atr/price:.5f})", "FILTER")

    # [v6+] Market Regime Filter
    is_trending, swing_count = market_is_trending(rates_m15, symbol=symbol)
    if not is_trending:
        # BTC weekend : l'accumulation génère naturellement beaucoup de swings → on bypasse
        if _btc_weekend:
            log(f"  {symbol}: range détecté ({swing_count} swings) → bypass weekend accumulation", "FILTER")
        else:
            log(f"  {symbol}: marché en range ({swing_count} swings) — skip", "FILTER")
            return None

    # [v6] Structure BOS/CHoCH
    bos_info = detect_bos_choch(rates_m15)
    mst      = bos_info["structure"]
    _sh_str = f"{bos_info['last_sh']:.5g}" if bos_info["last_sh"] else "n/a"
    _sl_str = f"{bos_info['last_sl']:.5g}" if bos_info["last_sl"] else "n/a"
    log(
        f"  {symbol} Structure M15: {mst} | "
        f"SH:{_sh_str} SL:{_sl_str} | "
        f"Event:{bos_info['last_event']}",
        "SMC",
    )

    # [v6.28] DISPLACEMENT + RETRACEMENT TO OB — setup prioritaire
    # Détecte le pattern exact du chart XAUUSD :
    # displacement fort → prix retrace dans l'OB → entrée dans la direction du move
    disp_ob = detect_displacement_ob_entry(rates_m15, atr)
    if disp_ob:
        log(
            f"  {symbol} 🎯 DISP+OB {disp_ob['direction']} "
            f"{disp_ob['strength']}×ATR | "
            f"OB:{disp_ob['ob_lo']:.5g}–{disp_ob['ob_hi']:.5g} | "
            f"Retrace:{disp_ob['retrace_pct']}% | "
            f"InOB:{'✅' if disp_ob['in_ob'] else '⏳'}",
            "SMC",
        )

    # [v6.26] CHOCH OVERRIDE ──────────────────────────────────────
    # CHoCH = retournement institutionnel confirmé → force la direction
    # CHOCH_BEAR = vente immédiate | CHOCH_BULL = achat immédiat
    # Prime sur le HTF ET sur le displacement — c'est la règle ICT fondamentale
    last_evt = bos_info.get("last_event")
    choch_dir = None
    if last_evt == "CHOCH_BEAR":
        choch_dir = "BEAR"
        log(f"  {symbol} 🔄 CHoCH BEAR → direction forcée SELL (override HTF)", "SMC")
    elif last_evt == "CHOCH_BULL":
        choch_dir = "BULL"
        log(f"  {symbol} 🔄 CHoCH BULL → direction forcée BUY (override HTF)", "SMC")

    # [v6.25] DISPLACEMENT OVERRIDE ─────────────────────────────
    # Un displacement fort récent (≥ 2×ATR) prime sur le biais HTF
    # pour la direction LTF. Le HTF reste utilisé comme filtre de fond.
    displacement = find_recent_displacement(rates_m15, atr)
    htf_dir = "BULL" if htf["bias"] == "BULL" else "BEAR"

    if choch_dir:
        # CHoCH prime sur tout
        dirs = [choch_dir]
        if not displacement or displacement["direction"] != choch_dir:
            displacement = None  # displacement contradictoire = ignoré
    elif disp_ob and disp_ob["in_ob"]:
        # [v6.28] Prix dans l'OB après displacement → setup prioritaire
        dirs = [disp_ob["direction"]]
        log(f"  {symbol} 🎯 Prix DANS l'OB post-displacement → {disp_ob['direction']} (override HTF)", "SMC")
    elif displacement:
        disp_dir = displacement["direction"]
        if disp_dir != htf_dir:
            log(
                f"  {symbol} ⚡ DISPLACEMENT {displacement['strength']}×ATR "
                f"→ direction {disp_dir} (override HTF {htf_dir})",
                "SMC",
            )
        else:
            log(
                f"  {symbol} ✅ DISPLACEMENT {displacement['strength']}×ATR "
                f"aligné HTF {htf_dir}",
                "SMC",
            )
        dirs = [disp_dir]
    else:
        displacement = None
        dirs = [htf_dir]
    best = {"score": -1}

    for d in dirs:
        impulse = find_impulse(rates_m15, atr)
        equi    = in_equilibrium(price, impulse) if impulse else False
        fvg     = find_fvg(rates_m15, d, price, atr)

        # [v6] Order Blocks
        obs = find_order_blocks(rates_m15, d, atr)
        ob  = get_best_unmitigated_ob(rates_m15, obs, d, price, atr)
        if ob:
            log(
                f"  {symbol} OB {ob['type']} non mitigé: "
                f"{ob['lo']:.5g} – {ob['hi']:.5g}",
                "SMC",
            )

        # [v6+] Inducement + Judas Swing
        has_inducement = is_inducement(rates_m15, d, atr)
        has_judas      = detect_judas_swing(rates_m15, d, atr)
        if has_inducement or has_judas:
            log(f"  {symbol} {'Judas Swing' if has_judas else 'Inducement'} détecté 🪤", "SMC")

        # [v6+] iFVG
        ifvg = detect_inversion_fvg(rates_m15, d, atr)
        if ifvg:
            log(f"  {symbol} iFVG {ifvg['type']}: {ifvg['lo']:.5g}–{ifvg['hi']:.5g}", "SMC")

        # [v6+] Breaker Block
        breaker = detect_breaker_block(rates_m15, d, atr)
        if breaker:
            log(f"  {symbol} Breaker Block {breaker['type']} @ {breaker['level']:.5g}", "SMC")

        rej = check_rejection(rates_m15, d)
        sc  = score_signal(mst, impulse, equi, fvg, ob, rej)

        # [v6+] Bonus score
        if has_inducement or has_judas: sc = min(sc + 1, 6)
        if ifvg:                        sc = min(sc + 1, 6)
        if breaker:                     sc = min(sc + 1, 6)
        if is_silver_bullet_window():   sc = min(sc + 1, 6)
        if in_killzone():               sc = min(sc + 1, 6)

        # [v6+] PD Array
        pd = get_pd_array(rates_m15)
        pd_ok = pd_array_aligned(pd, d)
        if not pd_ok:
            log(f"  {symbol} PD Array bloqué → prix en {pd['zone']} ({pd['pct']}%) pour {d}", "FILTER")
            sc = max(sc - 2, 0)   # pénalité forte si zone opposée

        # [v6+] Unicorn Model
        unicorn = is_unicorn_model(rates_m15, d, atr, bos_info,
                                   detect_liquidity_sweep(rates_m15, d),
                                   fvg, ob)
        if unicorn:
            log(f"  {symbol} 🦄 UNICORN MODEL détecté !", "SMC")
            sc = min(sc + 2, 6)

        # [v6.28] Bonus si pattern Displacement+OB actif
        if disp_ob and disp_ob["direction"] == d:
            if disp_ob["in_ob"]:
                sc = min(sc + 2, 6)   # prix dans l'OB = setup parfait
                log(f"  {symbol} 🎯 InOB +2 score → {sc}/6", "SMC")
            else:
                sc = min(sc + 1, 6)   # retracement en cours, pas encore dans l'OB

        # [v6.25] Bonus si prix proche du 50% du displacement (OTE optimal)
        at_displacement_50 = False
        if displacement and displacement["direction"] == d:
            dist_to_50 = abs(price - displacement["entry_50"])
            if dist_to_50 <= atr * 0.5:
                at_displacement_50 = True
                sc = min(sc + 2, 6)
                log(f"  {symbol} 🎯 Prix au 50% displacement → +2 score", "SMC")

        # Malus si displacement opposé au HTF (incohérence macro)
        if displacement and displacement["direction"] != htf_dir:
            sc = max(sc - 1, 0)

        # [v6.27] Bonus macro aligné
        if macro and macro["bias"] == d:
            sc = min(sc + 1, 6)

        if sc > best["score"]:
            best = {
                "symbol":         symbol,
                "score":          sc,
                "direction":      d,
                "mst":            mst,
                "equi":           equi,
                "fvg":            fvg,
                "ob":             ob,
                "sd":             ob,
                "rejection":      rej,
                "price":          price,
                "atr":            atr,
                "rates_m15":      rates_m15,
                "entry_type":     "PULLBACK" if equi else "DIRECT",
                "htf":            htf,
                "bos_choch":      bos_info,
                "has_inducement": has_inducement or has_judas,
                "has_judas":      has_judas,
                "in_killzone":    in_killzone(),
                "in_silver_bullet": is_silver_bullet_window(),
                "swing_count":    swing_count,
                "pd_array":       pd,
                "ifvg":           ifvg,
                "breaker":        breaker,
                "unicorn":        unicorn,
                "displacement":   displacement,
                "at_disp_50":     at_displacement_50,
                "choch_override": choch_dir,
                "macro":          macro,
                "disp_ob":        disp_ob,
            }

    # Score minimum : 3/6 pour BTC le weekend, 4/6 sinon
    wday = datetime.now(timezone.utc).weekday()
    score_min = 3 if (symbol == "BTCUSD" and wday >= 5) else SCORE_MIN

    if best["score"] < score_min:
        return None

    rates_m5 = get_rates(symbol, "5m", "2d")
    if not rates_m5 or len(rates_m5) < 20:
        return None

    direction  = best["direction"]
    atr_m5     = calc_atr(rates_m5)
    mst_m5     = market_structure(rates_m5, 30)
    m5_aligned = (
        (direction == "BULL" and mst_m5 == "BULLISH") or
        (direction == "BEAR" and mst_m5 == "BEARISH")
    )
    # [v6.26] Si CHoCH ou displacement override actif → M5 alignment non bloquant
    # Le CHoCH est lui-même un retournement, M5 peut être encore dans l'ancienne direction
    override_active = (choch_dir is not None) or (best.get("displacement") is not None)
    if not m5_aligned and not override_active:
        return None
    if not m5_aligned and override_active:
        log(f"  {symbol}: M5 non aligné mais override actif → on continue", "FILTER")

    # [v6+] Confirmation LTF (OTE / displacement / rejet M5)
    ltf_ok, ltf_reason = confirm_ltf_reaction(rates_m5, direction, atr_m5)
    if not ltf_ok:
        log(f"  {symbol}: LTF non confirmé ({ltf_reason}) — skip", "FILTER")
        return None
    log(f"  {symbol}: LTF confirmé → {ltf_reason}", "SMC")

    rej_m5    = check_rejection(rates_m5, direction)
    has_sweep = detect_liquidity_sweep(rates_m15, direction)

    sl   = calc_sl_choch(rates_m15, direction, price, atr)
    risk = abs(price - sl)
    if risk <= 0:
        return None

    # [v6+] TP dynamique sur prochaine liquidité
    sign        = 1 if direction == "BULL" else -1
    tp_liquidity = find_next_liquidity(rates_m15, direction, price, atr)
    if tp_liquidity and abs(tp_liquidity - price) >= risk * RR_MIN:
        dynamic_tp = tp_liquidity
    else:
        dynamic_tp = None   # fallback RR fixe dans send_signal

    best.update({
        "sl":          sl,
        "risk":        risk,
        "sign":        sign,
        "mst_m5":      mst_m5,
        "rej_m5":      rej_m5,
        "has_sweep":   has_sweep,
        "ltf_reason":  ltf_reason,
        "dynamic_tp":  dynamic_tp,
    })
    return best


# ════════════════════════════════════════════════════════
#  📡  SIGNAL TELEGRAM + CSV
# ════════════════════════════════════════════════════════
def send_signal(sig, sess):
    symbol    = sig["symbol"]
    direction = sig["direction"]
    price     = sig["price"]
    sl        = sig["sl"]
    risk      = sig["risk"]
    sign      = sig["sign"]
    score     = sig["score"]
    htf       = sig["htf"]
    et        = sig["entry_type"]
    has_sweep = sig.get("has_sweep", False)
    rej_m5    = sig.get("rej_m5")
    ob        = sig.get("ob")
    bos_info  = sig.get("bos_choch", {})
    last_evt  = bos_info.get("last_event")

    tp1 = round(price + risk * 1.0 * sign, 5)
    tp2 = round(price + risk * 2.0 * sign, 5)
    tp3 = round(price + risk * 3.0 * sign, 5)

    # [v6+] TP dynamique si disponible
    dynamic_tp = sig.get("dynamic_tp")
    if dynamic_tp:
        tp3 = round(dynamic_tp, 5)

    lot      = calc_lot(symbol, price, sl, BALANCE, RISK_PCT)
    risk_usd = round(BALANCE * RISK_PCT, 2)
    prob     = dynamic_probability(
        score, sess, symbol, has_sweep,
        has_ob=(ob is not None), last_event=last_evt,
    )
    label    = signal_label(score, has_sweep, has_ob=(ob is not None), unicorn=sig.get("unicorn", False))

    dir_emoji  = "🟢 BUY"  if direction == "BULL" else "🔴 SELL"
    et_emoji   = "🔄 PULLBACK" if et == "PULLBACK" else "⚡ DIRECT"
    daily_icon = "📈" if htf["daily"] == "BULLISH" else ("📉" if htf["daily"] == "BEARISH" else "➡️")
    h4_icon    = "📈" if htf["h4"]    == "BULLISH" else ("📉" if htf["h4"]    == "BEARISH" else "➡️")

    # ── BOS/CHoCH texte ───────────────────────────────
    evt_labels = {
        "BOS_BULL":   "✅ BOS ↗ (continuation)",
        "BOS_BEAR":   "✅ BOS ↘ (continuation)",
        "CHOCH_BULL": "🔄 CHoCH ↗ (retournement)",
        "CHOCH_BEAR": "🔄 CHoCH ↘ (retournement)",
    }
    evt_str = evt_labels.get(last_evt, "➖ Pas d'event récent")

    # ── Liste des confluences ─────────────────────────
    setup_items = []
    if sig.get("choch_override"):
        setup_items.append(f"✔ CHoCH Override → {sig['choch_override']} 🔄")
    disp_ob = sig.get("disp_ob")
    if disp_ob:
        tag = "🎯 InOB" if disp_ob["in_ob"] else "⏳ Approche OB"
        setup_items.append(
            f"✔ {tag} | Displacement {disp_ob['strength']}×ATR "
            f"({disp_ob['ob_lo']:.5g}–{disp_ob['ob_hi']:.5g}) "
            f"Retrace:{disp_ob['retrace_pct']}%"
        )
    macro = sig.get("macro")
    if macro and macro["bias"] != "NEUTRAL":
        emoji = "📈" if macro["bias"] == "BULL" else "📉"
        setup_items.append(
            f"✔ Macro {emoji} {macro['c1']}:{macro['score_c1']:+d} "
            f"vs {macro['c2']}:{macro['score_c2']:+d}"
        )
    if sig.get("at_disp_50"):
        disp = sig["displacement"]
        setup_items.append(
            f"✔ Displacement {disp['strength']}×ATR → 50% OTE 🎯 "
            f"({disp['lo']:.5g}–{disp['hi']:.5g})"
        )
    elif sig.get("displacement"):
        disp = sig["displacement"]
        setup_items.append(
            f"✔ Displacement {disp['strength']}×ATR ({disp['direction']}) ⚡"
        )
    if htf["bias"] != "NEUTRAL":
        setup_items.append("✔ HTF aligné")
    if sig["fvg"]:
        setup_items.append("✔ FVG")
    if ob:
        setup_items.append(f"✔ Order Block 🏦 ({ob['lo']:.5g}–{ob['hi']:.5g})")
    if sig["equi"]:
        setup_items.append("✔ Equilibrium 50%")
    if sig["rejection"]:
        setup_items.append(f"✔ Rejet M15 ({sig['rejection']})")
    if rej_m5:
        setup_items.append(f"✔ Rejet M5 ({rej_m5})")
    if has_sweep:
        setup_items.append("✔ Liquidity Sweep 💧")
    if sig.get("has_judas"):
        setup_items.append("✔ Judas Swing 🪤")
    elif sig.get("has_inducement"):
        setup_items.append("✔ Inducement 🪤")
    if sig.get("in_silver_bullet"):
        setup_items.append("✔ Silver Bullet ⚡")
    if sig.get("in_killzone") and not sig.get("in_silver_bullet"):
        setup_items.append("✔ Killzone London/NY ⚡")
    if sig.get("ltf_reason"):
        setup_items.append(f"✔ LTF confirmé → {sig['ltf_reason']}")
    if sig.get("ifvg"):
        setup_items.append(f"✔ iFVG {sig['ifvg']['type']} 🔄")
    if sig.get("breaker"):
        setup_items.append(f"✔ Breaker Block @ {sig['breaker']['level']:.5g} 🧱")
    pd = sig.get("pd_array")
    if pd:
        setup_items.append(f"✔ PD Array : {pd['zone']} ({pd['pct']}%)")
    if sig.get("unicorn"):
        setup_items.append("✔ 🦄 UNICORN MODEL")
    if sig.get("dynamic_tp"):
        setup_items.append(f"✔ TP sur liquidité cible 🎯")
    setup_str = "\n".join(f"  {x}" for x in setup_items)

    msg = (
        f"{'═'*34}\n"
        f"🔥 <b>ALPHABOT ELITE SIGNAL v6</b>\n"
        f"{'═'*34}\n"
        f"📊 <b>{symbol}</b>  —  {dir_emoji}  {label}\n"
        f"⏰ {sess}  |  📅 {datetime.now(timezone.utc).strftime('%A %d/%m')}\n"
        f"{'─'*34}\n"
        f"🎯 <b>Probabilité : {prob}%</b>  |  Score : {score}/6\n"
        f"{'─'*34}\n"
        f"🌍 Daily : {daily_icon} {htf['daily']}  |  H4 : {h4_icon} {htf['h4']}\n"
        f"  Biais : <b>{htf['bias']}</b>  |  {et_emoji}\n"
        f"📐 Structure M15 : {evt_str}\n"
        f"{'─'*34}\n"
        f"⚡ <b>Confluences</b>\n{setup_str}\n"
        f"{'─'*34}\n"
        f"  Entrée : <b>{price:.5g}</b>  |  SL : <b>{sl:.5g}</b>\n"
        f"  TP1 : <b>{tp1:.5g}</b> → +<b>${round(risk_usd*1,2)}</b>\n"
        f"  TP2 : <b>{tp2:.5g}</b> → +<b>${round(risk_usd*2,2)}</b>\n"
        f"  TP3 : <b>{tp3:.5g}</b> → +<b>${round(risk_usd*3,2)}</b> 🎯\n"
        f"  ❌ SL : -<b>${risk_usd}</b>\n"
        f"{'─'*34}\n"
        f"💰 ${BALANCE:.0f}  |  Risque {RISK_PCT*100:.0f}% = <b>${risk_usd}</b>  |  Lot <b>{lot}</b>\n"
        f"{'═'*34}\n"
        f"⚡ <i>MT5 manuel  |  #ICT #SMC #AlphaBot</i>"
    )

    tg(msg)
    log_signal_csv(sig, sess, tp1, tp2, tp3, risk_usd, lot, prob)

    # Mise à jour stats mémoire
    stats["signals_today"] += 1
    stats["signals_total"] += 1
    if has_sweep: stats["sweep_signals"] += 1
    if ob:        stats["ob_signals"]    += 1
    if last_evt and "BOS"   in last_evt: stats["bos_signals"]   += 1
    if last_evt and "CHOCH" in last_evt: stats["choch_signals"] += 1
    if symbol not in stats["by_symbol"]:
        stats["by_symbol"][symbol] = {"sent": 0, "score_sum": 0}
    stats["by_symbol"][symbol]["sent"]      += 1
    stats["by_symbol"][symbol]["score_sum"] += score
    if sess in stats["by_session"]:
        stats["by_session"][sess] += 1

    log(
        f"📡 {symbol} {direction} score={score}/6 prob={prob}% lot={lot} "
        f"OB={'✅' if ob else '❌'} evt={last_evt or '—'}",
        "SIGNAL",
    )


# ════════════════════════════════════════════════════════
#  📋  RAPPORT JOURNALIER
# ════════════════════════════════════════════════════════
def send_daily_report():
    src = stats["data_source"]
    top = sorted(stats["by_symbol"].items(),
                 key=lambda x: x[1]["sent"], reverse=True)[:5]
    top_str = "".join(
        f"  {sym}: {d['sent']} signaux | "
        f"score moy {d['score_sum']/d['sent']:.1f}/6\n"
        for sym, d in top
    )
    msg = (
        f"{'═'*34}\n"
        f"📋 <b>RAPPORT JOURNALIER — AlphaBot v6</b>\n"
        f"📅 {stats['start_date']}\n"
        f"{'═'*34}\n"
        f"📡 Aujourd'hui : <b>{stats['signals_today']}</b>  |  Total : <b>{stats['signals_total']}</b>\n"
        f"💧 Avec sweep  : <b>{stats['sweep_signals']}</b>\n"
        f"🏦 Avec OB     : <b>{stats['ob_signals']}</b>\n"
        f"📐 BOS : {stats['bos_signals']}  |  CHoCH : {stats['choch_signals']}\n"
        f"🚫 Filtrés vol : {stats['filtered_vol']}  |  News : {stats['filtered_news']}\n"
        f"{'─'*34}\n"
        f"📡 Sources : TD:{src['twelvedata']} ccxt:{src['ccxt']} yf:{src['yfinance']}\n"
        f"{'─'*34}\n"
        f"🇬🇧 London : {stats['by_session'].get('🇬🇧 London',0)}  "
        f"🇺🇸 NY : {stats['by_session'].get('🇺🇸 New York',0)}\n"
        f"{'─'*34}\n"
        f"🏆 Top marchés :\n{top_str}"
        f"📝 Log : {SIGNALS_CSV}\n"
        f"{'═'*34}"
    )
    tg(msg)
    log("📋 Rapport journalier envoyé", "STATS")


# ════════════════════════════════════════════════════════
#  🚀  BOUCLE PRINCIPALE
# ════════════════════════════════════════════════════════
def main():
    global _last_report_day

    log("═══════════════════════════════════════════════════════════")
    log("  AlphaBot SIGNAL v6.29                                     ")
    log("  Volatilité Priority + Multi-User Broadcast               ")
    log("═══════════════════════════════════════════════════════════")

    # ── Chargement des users ──────────────────────────────
    load_users()
    log(f"👥 {len(_users)} abonné(s) actif(s)", "INFO")

    if TWELVE_DATA_KEY:
        log("✅ TwelveData API configurée", "DATA")
    else:
        log("⚠️  Pas de clé TwelveData → fallback Yahoo Finance REST", "WARN")

    log("✅ Binance REST activé → crypto sans dépendance externe", "DATA")

    if FF_NEWS_ENABLED:
        log("✅ Filtre ForexFactory activé", "DATA")
        fetch_ff_calendar()   # Pre-fetch au démarrage
    else:
        log("⚠️  ForexFactory désactivé → filtre horaires fixes", "WARN")

    if not TG_TOKEN or not TG_CHAT_ID:
        log("⚠️  TG_TOKEN / TG_CHAT_ID non configurés → MODE CONSOLE (signaux affichés ici uniquement)", "WARN")
    else:
        tg(
            f"🤖 <b>AlphaBot SIGNAL v6.29 — Démarré</b>\n"
            f"{'─'*32}\n"
            f"📊 {len(SYMBOLS)} marchés | SMC/ICT Elite\n"
            f"🔥 Priorité Volatilité activée 🆕\n"
            f"👥 Broadcast multi-users 🆕 | /start pour s'abonner\n"
            f"🏦 Order Blocks ICT + Mitigation tracking\n"
            f"📐 BOS / CHoCH structure avancée\n"
            f"📰 News : {'ForexFactory live 🟢' if FF_NEWS_ENABLED else 'horaires fixes ⚠️'}\n"
            f"📡 Données : {'TwelveData' if TWELVE_DATA_KEY else 'Yahoo REST'} + Binance REST\n"
            f"💰 ${BALANCE:.0f} | Risque {RISK_PCT*100:.0f}%\n"
            f"✅ Prêt ! | {len(_users)} abonné(s)"
        )

    cooldowns    = {}
    cycle        = 0
    _last_status = 0   # timestamp du dernier message statut TG (toutes les heures)

    while True:
        cycle  += 1
        now     = time.time()
        utcnow  = datetime.now(timezone.utc)
        wday    = utcnow.weekday()   # 5=sam, 6=dim
        weekend = wday >= 5

        log(f"━━━ CYCLE {cycle} | {'₿ WEEKEND BTC' if weekend else session_name()} | {utcnow.strftime('%H:%M UTC')}")

        # ── Rapport journalier automatique ─────────────────
        today = utcnow.date()
        if utcnow.hour == DAILY_REPORT_HOUR and _last_report_day != today:
            send_daily_report()
            _last_report_day = today

        # ── Polling commandes Telegram (/start /stop) ──────
        poll_telegram_commands()

        # ── Sélection des symboles actifs pour ce cycle ────
        if weekend:
            active = ["BTCUSD"]   # weekend → BTC uniquement
            log("₿ Mode weekend — scan BTC uniquement", "SESSION")
        else:
            active = [s for s in SYMBOLS if not bad_day_reason(s) and in_active_session(s)]
            if not active:
                log("💤 Hors session — aucun marché actif", "SESSION")

        # ── 🔥 PRIORITÉ VOLATILITÉ — trier par ATR/price desc ──
        # Scanne les marchés les plus volatils EN PREMIER pour capter
        # les setups ICT sur les mouvements les plus forts du cycle.
        if len(active) > 1:
            vol_scores = {}
            for sym in active:
                try:
                    r = get_rates(sym, "15m", "2d")
                    if r and len(r) >= 14:
                        a = calc_atr(r)
                        p = r[-1]["close"]
                        vol_scores[sym] = (a / p) if p > 0 else 0
                    else:
                        vol_scores[sym] = 0
                except Exception:
                    vol_scores[sym] = 0
            active = sorted(active, key=lambda s: vol_scores.get(s, 0), reverse=True)
            top3 = [(s, f"{vol_scores.get(s,0)*100:.3f}%") for s in active[:3]]
            log(f"🔥 Priorité vol (ATR%) → {top3}", "FILTER")

        # ── Heartbeat Telegram toutes les 12h (message minimal) ──
        if now - _last_status >= 43200:  # 12h
            tg(
                f"🟢 AlphaBot v6 actif | "
                f"{utcnow.strftime('%H:%M UTC')} | "
                f"Signaux : {stats['signals_today']}"
            )
            _last_status = now

        # ── Scan des symboles actifs ───────────────────────
        signals_this_cycle = 0
        for symbol in active:
            # Cooldown par symbole
            if symbol in cooldowns:
                elapsed = (now - cooldowns[symbol]) / 60
                if elapsed < COOLDOWN_MIN:
                    continue

            # Filtre news (crypto non bloqué par FF)
            blocked, news_desc = is_high_impact_news(symbol)
            if blocked:
                log(f"  📰 {symbol} bloqué → {news_desc}", "FILTER")
                stats["filtered_news"] += 1
                continue

            # [v6+] Filtre corrélation
            corr_blocked, corr_sym = correlation_blocked(symbol, cooldowns)
            if corr_blocked:
                log(f"  {symbol} bloqué → corrélé avec {corr_sym} (signal récent)", "FILTER")
                continue

            log(f"  🔍 Scan {symbol}...", "SCAN")
            try:
                sig = analyze_symbol(symbol, cooldowns)
            except Exception as e:
                log(f"  {symbol} erreur: {e}", "WARN")
                continue

            if sig is None:
                continue

            sess = session_name(symbol)
            send_signal(sig, sess)
            cooldowns[symbol] = time.time()
            signals_this_cycle += 1
            time.sleep(1.5)

        if not signals_this_cycle and active:
            log(f"  Aucune entrée ce cycle ({', '.join(active)})", "SCAN")

        log(f"Prochain scan dans {SCAN_INTERVAL}s...")
        time.sleep(SCAN_INTERVAL)


# ════════════════════════════════════════════════════════
#  🖥️  CLI
# ════════════════════════════════════════════════════════
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="AlphaBot Signal v6.21")
    parser.add_argument(
        "--backtest", nargs="+", metavar=("SYMBOL", "DAYS"),
        help="Lance le backtest. Ex: --backtest XAUUSD 90  ou  --backtest ALL 30",
    )
    parser.add_argument(
        "--stats", action="store_true",
        help="Affiche les statistiques réelles depuis signals_log.csv",
    )
    args = parser.parse_args()

    if args.stats:
        print_csv_stats()

    elif args.backtest:
        sym_arg  = args.backtest[0].upper()
        days_arg = int(args.backtest[1]) if len(args.backtest) > 1 else 90
        syms     = list(SYMBOLS.keys()) if sym_arg == "ALL" else [sym_arg]
        run_backtest(syms, days_arg)

    else:
        try:
            main()
        except KeyboardInterrupt:
            log("Bot arrêté manuellement.")
            send_daily_report()
            tg("⛔ AlphaBot Signal v6.0 arrêté.")
        except Exception as e:
            log(f"ERREUR CRITIQUE: {e}", "ERROR")
            log(traceback.format_exc(), "ERROR")
            tg(f"🚨 <b>AlphaBot Signal v6.21 crash</b>\n<code>{str(e)[:400]}</code>")
