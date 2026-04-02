

"""
╔══════════════════════════════════════════════════════════════════╗
║   ALPHABOT FUTURES LIVE v5.0 — STRATÉGIE ICT PURE             ║
║   Impulsion → Retracement 50% → FVG/OB → Sweep → Rejet      ║
║   Full Auto | Binance USDT-M Futures | Capital micro (<$50)   ║
║   21 marchés | SL structurel | Risk adaptatif | TP 50/30/20%  ║
║   Pure stdlib | Pydroid3 Android compatible                   ║
╚══════════════════════════════════════════════════════════════════╝

STRATÉGIE v4.0 — ENTRÉES HAUTE PROBABILITÉ SEULEMENT :

  ① IMPULSE SCAN     — Détecte le plus fort mouvement directionnel
                        sur les 80 dernières bougies (M1).
                        Force mesurée en multiples d'ATR.

  ② RETRACEMENT 50%  — Prix doit être exactement dans la zone
                        [45% – 58%] de l'impulsion (premium/discount).
                        Zone la plus liquide, là où les Smart Money entrent.

  ③ FVG FILL         — Fair Value Gap dans la zone 50% ?
                        Le gap (imbalance) doit être partiellement comblé.
                        C'est la "magnet zone" qui attire le prix.

  ④ ORDER BLOCK      — Bonus si un OB bullish/bearish est aussi présent
                        dans la zone. Confluence maximale.

  ⑤ REJET CONFIRMÉ  — La dernière bougie DOIT montrer un rejet clair :
                        Hammer, Engulfing, Tweezer, Pin Bar.
                        Sans rejet = pas d'entrée, peu importe le reste.

SCORING (max 8) :
  +1  Impulse > 1.5× ATR (mouvement réel)
  +1  Impulse > 3.0× ATR (mouvement fort — bonus)
  +2  FVG présente et partiellement comblée dans la zone
  +1  Order Block confluent dans la zone
  +2  Bougie de rejet validée
  +1  Prise de liquidité (sweep high/low) détectée
  ──────────────────────────────────────────────────────
  Entrée si score ≥ 4 (FVG + rejet minimum)

PROTECTIONS (héritées v3) :
  ① SL structurel   — SwingLow/High + marge ATR
  ② Pause auto      — 3 SL consécutifs → pause 30min
  ③ Risk adaptatif  — croît avec le compte, réduit en cas de pertes
  ④ Profit lock     — protège 50% des gains session
  ⑤ Micro compte    — levier 50-75x adaptatif, 1 position max sous $10
"""

import os, json, csv, time, hmac, hashlib, math, copy
from datetime import datetime
from urllib import request as urlreq, parse as urlparse, error as urlerr
from typing import Optional, Tuple, List, Dict

# ═══════════════════════════════════════════════════════════════
#  🔑  CONFIGURATION — 2 MÉTHODES (choisir une)
# ═══════════════════════════════════════════════════════════════

# ┌─────────────────────────────────────────────────────────────┐
# │  MÉTHODE 1 (recommandée VPS) : variables d'environnement   │
# │  Dans ton terminal VPS :                                   │
# │    export BINANCE_KEY="ta_clé"                             │
# │    export BINANCE_SECRET="ton_secret"                      │
# │    export TG_TOKEN="ton_token"                             │
# │    export TG_CHAT_ID="ton_chat_id"                         │
# │                                                             │
# │  MÉTHODE 2 (fallback) : coller directement ci-dessous     │
# │  Ne jamais partager ce fichier si tu utilises méthode 2   │
# └─────────────────────────────────────────────────────────────┘

# ══ COLLE TES NOUVELLES CLÉS ICI (après révocation des anciennes) ══
API_KEY    = os.environ.get("BINANCE_KEY",    "71ZEp7Et0NSEQ3kaT52bigzcni7t7H6WD6iMP8AWvZR0Z0lTLWsZngigRBSFIWTE")
API_SECRET = os.environ.get("BINANCE_SECRET", "JpAFPnepk9a3uQDf7uHqFEDeuD2kgmBHYItlXEixabxCkEDlRabnGC6bBoF4IYy6")
TG_TOKEN   = os.environ.get("TG_TOKEN",       "8665812395:AAFO4BMTIrBCQJYVL8UytO028TcB1sDfgbI")
# ⚠️  IMPORTANT : TG_CHAT_ID ≠ TG_TOKEN !
# Pour trouver ton vrai chat_id :
#   1. Envoie n'importe quel message à ton bot sur Telegram
#   2. Ouvre : https://api.telegram.org/bot<TON_TOKEN>/getUpdates
#   3. Cherche "chat":{"id": XXXXXXXXX} — c'est ton chat_id (souvent négatif pour un groupe)
# Sur Render : mets la valeur dans la variable d'env TG_CHAT_ID
TG_CHAT_ID = os.environ.get("TG_CHAT_ID",     "6982051442")
# ══ Pour le testnet Binance, change aussi BASE_URL plus bas ══

# ═══════════════════════════════════════════════════════════════
#  ⚙️  PARAMÈTRES DE TRADING
# ═══════════════════════════════════════════════════════════════

# ── Capital & Levier ──────────────────────────────────────────
LEVERAGE         = 20      # levier USDT-M Futures
MAX_MARGIN_PCT   = 0.15    # max 15% du balance en marge / trade
MIN_BALANCE_USD  = 1.0     # stop total si balance < $1 (micro compte autorisé)

# ── Risk adaptatif (voir tiers ci-dessous) ────────────────────
RISK_TIERS = [
    # (multiplicateur_min, multiplicateur_max, risk_pct_base)
    # risk_pct_base = risque pour signal SOLIDE (score 5)
    # Le risque réel est ensuite multiplié selon la qualité du signal
    (1.0,  1.5,  0.050),   # base → +50% gains : 5.0% (solide)
    (1.5,  2.0,  0.050),   # +50% → ×2         : 5.0%
    (2.0,  3.0,  0.045),   # ×2   → ×3         : 4.5%
    (3.0,  5.0,  0.040),   # ×3   → ×5         : 4.0%
    (5.0,  999,  0.035),   # ×5+               : 3.5% (compte bien garni)
]

# ── Risque selon qualité du signal ────────────────────────────
# Le % de risque s'adapte automatiquement au score ICT/SMC.
# Plus le signal est propre, plus on mise — mais jamais > 10%.
SIGNAL_RISK_SCALE = {
    7: 0.080,   # ÉLITE  — score parfait 7/7  → 8%  (max agressif)
    6: 0.065,   # PREMIUM— score 6/7          → 6.5%
    5: 0.050,   # SOLIDE — score 5/7          → 5%  (base)
    4: 0.050,   # ✅ BON  — score 4/7          → 5%  (micro compte)
    3: 0.050,   # ✅ MIN  — score 3/7          → 5%  (plancher)
}
RISK_MAX_CAP = 0.08   # jamais dépasser 8% quoi qu'il arrive
RISK_MIN_PCT = 0.05   # plancher 5% sur micro compte

# ── Frais Binance Futures ─────────────────────────────────────
FEE_RATE = 0.0004   # 0.04% taker (total aller-retour = 0.08%)

# ── Positions & timing ────────────────────────────────────────
MAX_POSITIONS     = 2     # max 2 positions simultanées (ICT : qualité > quantité)
COOLDOWN_MIN      = 15    # minutes d'attente / paire après clôture
SCAN_INTERVAL_SEC  = 60    # secondes entre chaque cycle
KLINES_LIMIT       = 220   # bougies M1 récupérées
TG_SUMMARY_CYCLES  = 60    # résumé Telegram toutes les N cycles (≈ 60min)

# ── Protection consécutive ────────────────────────────────────
MAX_CONSEC_SL     = 3     # pause après N SL consécutifs
PAUSE_AFTER_SL_MIN = 30   # durée de la pause (minutes)

# ── Profit lock (protection des gains session) ────────────────
# Si le balance redescend à moins de PROFIT_LOCK_PCT des gains accumulés
# depuis le début de session → arrêt du bot pour protéger les gains
PROFIT_LOCK_PCT   = 0.50  # conserver au moins 50% des gains session

# ── TP Split ─────────────────────────────────────────────────
TP_SPLIT = [
    {"r": 1.0, "pct": 0.50},   # R1 — 50% position @ 1R
    {"r": 2.0, "pct": 0.30},   # R2 — 30% position @ 2R
    {"r": 3.0, "pct": 0.20},   # R3 — 20% position @ 3R
]

# ── Pool complet — 21 marchés scannés ────────────────────────
# Le bot scanne TOUS ces marchés à chaque cycle, puis sélectionne
# uniquement les TOP_N_SYMBOLS avec le meilleur score signal.
SYMBOLS = [
    # ── Tier 1 : liquidité maximale, patterns fiables ──────────
    "ETHUSDT",   "BNBUSDT",   "DOGEUSDT",  "SOLUSDT",   "XRPUSDT",
    # ── Tier 2 : volatilité modérée, Fibonacci net ─────────────
    "APTUSDT",   "LINKUSDT",  "OPUSDT",    "AVAXUSDT",  "ADAUSDT",
    # ── Tier 3 : bons scalps, mouvements réguliers ─────────────
    "LTCUSDT",   "POLUSDT",   "UNIUSDT",   "AAVEUSDT",  "NEARUSDT",
    # ── Tier 4 : haute volatilité, opportunités ciblées ────────
    "FTMUSDT",   "XLMUSDT",   "TRXUSDT",   "SANDUSDT",  "ALGOUSDT",
    "ETCUSDT",
    # Note: MATICUSDT renommé POLUSDT par Binance (Polygon → POL)
]

# ── Sélection des meilleures paires à trader ──────────────────
# Parmi les 21 marchés scannés, seuls les TOP_N_SYMBOLS sont
# retenus pour l'ouverture réelle (classés par score signal).
TOP_N_SYMBOLS = 8

# ── Moteur de signal v4.0 — Paramètres ──────────────────────
# ── Détection d'impulsion ──────────────────────────────────
IMPULSE_LOOKBACK    = 80     # bougies analysées pour trouver le swing
IMPULSE_MIN_ATR     = 1.5    # l'impulsion doit faire ≥ 1.5× ATR
IMPULSE_STRONG_ATR  = 3.0    # bonus score si ≥ 3× ATR (mouvement fort)
# ── Zone de retracement ────────────────────────────────────
FIB_ZONE_LOW        = 0.45   # borne basse de la zone 50% (45%)
FIB_ZONE_HIGH       = 0.58   # borne haute de la zone 50% (58%)
# ── FVG (Fair Value Gap / imbalance) ──────────────────────
FVG_LOOKBACK        = 50     # fenêtre de recherche FVG
FVG_MIN_SIZE_ATR    = 0.2    # taille minimale du gap (× ATR)
FVG_FILL_MIN        = 0.30   # gap doit être comblé à ≥ 30%
# ── Order Block ───────────────────────────────────────────
OB_LOOKBACK         = 10     # fenêtre OB dans la zone
# ── Bougie de rejet ────────────────────────────────────────
REJECTION_WICK_RATIO = 0.55  # mèche ≥ 55% du range total
REJECTION_BODY_RATIO = 0.55  # ou corps ≥ 55% (bougie forte)
REJECTION_ENGULF_MULT = 1.20 # engulfing : corps > 1.2× corps précédent
REJECTION_TWEEZER_TOL = 0.002 # tolérance tweezer (0.2%)
# ── Score seuil ────────────────────────────────────────────
SCORE_MAX           = 8
SCORE_THRESH        = {"LOW": 4, "NORMAL": 4, "HIGH": 4}
# ── Volatilité (ATR % du prix) ─────────────────────────────
ATR_PERIOD          = 14
ATR_LOW_MULT        = 0.003
ATR_HIGH_MULT       = 0.018
# ── SL dynamique ───────────────────────────────────────────
SL_ATR_MIN_FACTOR   = 1.5    # SL minimum = 1.5× ATR de l'entrée

# ── Mode Sniper ───────────────────────────────────────────────
# 1 trade maximum par heure, uniquement le meilleur signal
SNIPER_MODE          = True    # activer/désactiver le mode sniper
SNIPER_COOLDOWN_MIN  = 20      # ✅ FIX: était 60min → trop rare sur micro compte
SNIPER_MIN_SCORE     = 4       # ✅ FIX: était 6 → bloquait TOUT (score max réel = 5-6)

# ── Corrélation BTC ───────────────────────────────────────────
# Si activé, n'entre en LONG que si BTC est haussier, SHORT si BTC est baissier.
# Filtre les trades à contre-tendance macro.
BTC_CORRELATION      = True    # activer le filtre corrélation BTC
BTC_LOOKBACK         = 80      # bougies M1 BTC pour déterminer la tendance

# ── Prise de liquidité (Liquidity Sweep / Stop Hunt) ──────────
# Bonus signal : le prix a chassé un high/low récent PUIS est revenu dans la zone.
# C'est la confirmation que les Smart Money ont pris la liquidité et vont reverser.
LIQ_SWEEP_LOOKBACK   = 25      # bougies analysées pour détecter le sweep
LIQ_SWEEP_SCORE      = 1       # bonus de score si sweep détecté (+1)
LIQ_SWEEP_ENABLED    = True    # activer la détection de sweep

# ── Tendance de fond (HTF via bougies M1) ─────────────────────
# Analyse les 150 dernières bougies M1 pour déterminer la tendance structurelle.
# On ne trade QUE dans le sens de la tendance (sauf signal exceptionnel score ≥ 6).
TREND_LOOKBACK       = 150     # bougies pour la tendance de fond
TREND_FILTER_ENABLED = True    # activer le filtre de tendance
TREND_MIN_SCORE_OVERRIDE = 6   # score minimum pour ignorer le filtre tendance

# ── Couleurs ANSI ─────────────────────────────────────────────
GRN="\033[92m"; RED="\033[91m"; YEL="\033[93m"
CYN="\033[96m"; MAG="\033[95m"; BLD="\033[1m"; RST="\033[0m"
def grn(t): return f"{GRN}{t}{RST}"
def red(t): return f"{RED}{t}{RST}"
def yel(t): return f"{YEL}{t}{RST}"
def cyn(t): return f"{CYN}{t}{RST}"
def mag(t): return f"{MAG}{t}{RST}"
def bld(t): return f"{BLD}{t}{RST}"
def sep(c="─", n=64): return cyn(c * n)

# ═══════════════════════════════════════════════════════════════
#  📈  ÉTAT DE SESSION (mémoire du bot)
# ═══════════════════════════════════════════════════════════════
class SessionState:
    """
    Centralise toutes les métriques de la session en cours.
    Persiste en JSON pour survivre aux redémarrages.
    """
    FILE = "session_state.json"

    def __init__(self, start_balance: float):
        self.start_balance   = start_balance  # balance au démarrage
        self.peak_balance    = start_balance  # plus haut atteint
        self.current_balance = start_balance
        self.session_pnl     = 0.0
        self.total_trades    = 0
        self.wins            = 0
        self.losses          = 0
        self.consecutive_sl  = 0
        self.paused          = False
        self.pause_until     = 0.0
        self.start_time      = time.time()
        self.last_summary_cycle = 0
        self.last_trade_time    = 0.0
        # ── Stats détaillées ──────────────────────────────────
        self.longs           = 0     # nombre de trades LONG
        self.shorts          = 0     # nombre de trades SHORT
        self.total_rr        = 0.0   # somme R réalisés (pour R:R moyen)
        self.max_drawdown    = 0.0   # drawdown max session ($)

    @property
    def win_rate(self) -> float:
        if self.total_trades == 0: return 0.0
        return round(self.wins / self.total_trades * 100, 1)

    @property
    def session_gain_mult(self) -> float:
        """Multiplicateur de croissance depuis le départ."""
        if self.start_balance <= 0: return 1.0
        return self.current_balance / self.start_balance

    def adaptive_risk_pct(self, score: int = 5) -> float:
        """
        Risque adaptatif selon DEUX axes :
          1. Croissance du compte (RISK_TIERS) — réduit quand le compte grossit
          2. Qualité du signal ICT/SMC (SIGNAL_RISK_SCALE) — augmente si signal parfait

        Logique :
          - Micro compte (<$10) : utilise directement SIGNAL_RISK_SCALE
          - Compte normal       : base RISK_TIERS × facteur signal
          - Plafond absolu      : RISK_MAX_CAP (8%)
          - Plancher micro      : RISK_MIN_PCT (5%)
        """
        # ── Risque de base selon le tier de croissance ────────
        mult      = self.session_gain_mult
        base_risk = RISK_TIERS[-1][2]
        for t_min, t_max, risk in RISK_TIERS:
            if t_min <= mult < t_max:
                base_risk = risk
                break

        # ── Micro compte : signal quality direct ──────────────
        if self.current_balance < 10.0:
            signal_risk = SIGNAL_RISK_SCALE.get(score, RISK_MIN_PCT)
            # ── CORRECTION FIX#2 : plafond strict 5% sur micro compte < $5
            # Score 7 → 8% sur $3 = 45% du compte en marge → trop dangereux.
            # On bride à 5% max tant que le capital est sous $5.
            if self.current_balance < 5.0:
                signal_risk = min(signal_risk, 0.05)
            return min(signal_risk, RISK_MAX_CAP)

        # ── Compte normal : base × facteur signal ─────────────
        # Score 7 → +60% du base | Score 6 → +30% | Score 5 → base
        signal_bonus = {7: 1.60, 6: 1.30, 5: 1.00}.get(score, 1.00)
        final_risk   = base_risk * signal_bonus
        return min(final_risk, RISK_MAX_CAP)

    def record_win(self, pnl: float, direction: str = "", rr: float = 0.0):
        self.wins           += 1
        self.total_trades   += 1
        self.session_pnl    += pnl
        self.consecutive_sl  = 0
        self.total_rr       += rr
        self.peak_balance    = max(self.peak_balance,
                                   self.current_balance + pnl)
        if direction == "LONG":  self.longs  += 1
        if direction == "SHORT": self.shorts += 1

    def record_loss(self, pnl: float, direction: str = "", rr: float = 0.0):
        self.losses         += 1
        self.total_trades   += 1
        self.session_pnl    += pnl
        self.consecutive_sl += 1
        self.total_rr       += rr
        # Drawdown max
        dd = self.peak_balance - self.current_balance
        if dd > self.max_drawdown:
            self.max_drawdown = dd
        if direction == "LONG":  self.longs  += 1
        if direction == "SHORT": self.shorts += 1

    @property
    def avg_rr(self) -> float:
        if self.total_trades == 0: return 0.0
        return round(self.total_rr / self.total_trades, 2)

    def check_pause(self) -> Tuple[bool, str]:
        """
        Vérifie si le bot doit se mettre en pause.
        Retourne (should_pause, reason).
        """
        # Déjà en pause ?
        if self.paused:
            if time.time() < self.pause_until:
                remaining = round((self.pause_until - time.time()) / 60, 1)
                return True, f"Pause active — {remaining}min restantes"
            else:
                self.paused = False
                return False, ""

        # 3 SL consécutifs
        if self.consecutive_sl >= MAX_CONSEC_SL:
            self.paused      = True
            self.pause_until = time.time() + PAUSE_AFTER_SL_MIN * 60
            return True, f"{MAX_CONSEC_SL} SL consécutifs"

        # Profit lock : protection des gains session
        if self.session_pnl > 0:
            gain_protected = self.session_pnl * PROFIT_LOCK_PCT
            balance_floor  = self.start_balance + gain_protected
            if self.current_balance < balance_floor:
                return True, (
                    f"Profit lock déclenché "
                    f"(balance ${self.current_balance:.2f} "
                    f"< floor ${balance_floor:.2f})"
                )

        return False, ""

    def session_duration(self) -> str:
        elapsed = int(time.time() - self.start_time)
        h, m    = divmod(elapsed // 60, 60)
        return f"{h}h{m:02d}m"

    def sniper_can_trade(self) -> Tuple[bool, str]:
        """
        Mode Sniper : vérifie le cooldown global entre trades.
        Retourne (peut_trader, raison).
        """
        if not SNIPER_MODE:
            return True, "sniper OFF"
        elapsed_min = (time.time() - self.last_trade_time) / 60
        if elapsed_min < SNIPER_COOLDOWN_MIN:
            wait = round(SNIPER_COOLDOWN_MIN - elapsed_min, 1)
            return False, f"sniper cooldown {wait}min"
        return True, "OK"

    def sniper_record_trade(self):
        self.last_trade_time = time.time()

# ═══════════════════════════════════════════════════════════════
#  📝  LOGGER
# ═══════════════════════════════════════════════════════════════
LOG_FILE = f"alphabot_v2_{datetime.now().strftime('%Y%m%d')}.log"

def log(msg: str, level: str = "INFO"):
    ts  = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    col = {"INFO": CYN, "TRADE": GRN, "WARN": YEL,
           "ERROR": RED, "PAUSE": MAG, "SL": RED, "TP": GRN}.get(level, RST)
    line = f"[{ts}][{level}] {msg}"
    print(f"{col}{line}{RST}", flush=True)   # flush=True → visible immédiatement sur Render
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass

def log_trade_open(symbol, direction, entry, sl, tps, qty, score, risk_usd):
    """Log détaillé d'ouverture de trade — visible dans les logs Render."""
    arrow = "LONG >>>" if direction == "LONG" else "SHORT <<<"
    tp_str = " | ".join(
        f"TP{i+1}={t['price']:.6f}(@{t['r']}R,{int(t['pct']*100)}%)"
        for i, t in enumerate(tps)
    )
    log(f"{'='*60}", "TRADE")
    log(f"TRADE OUVERT [{arrow}] {symbol}", "TRADE")
    log(f"  Entree : {entry:.6f}", "TRADE")
    log(f"  SL     : {sl:.6f}  (risque ${risk_usd:.4f})", "TRADE")
    log(f"  {tp_str}", "TRADE")
    log(f"  Qte={qty}  Score={score}/{SCORE_MAX}", "TRADE")
    log(f"{'='*60}", "TRADE")

def log_trade_close(symbol, direction, entry, sl, tps, pnl, reason):
    """Log détaillé de clôture de trade."""
    win   = pnl >= 0
    label = "WIN +++" if win else "LOSS ---"
    tps_hit = [f"TP{i+1}" for i, t in enumerate(tps) if t.get("hit")]
    log(f"{'='*60}", "TRADE")
    log(f"TRADE CLOS [{label}] {symbol} {direction} — {reason}", "TP" if win else "SL")
    log(f"  Entree : {entry:.6f}  SL : {sl:.6f}", "TRADE")
    log(f"  TP touches : {', '.join(tps_hit) if tps_hit else 'AUCUN'}", "TRADE")
    log(f"  PnL    : ${pnl:+.4f}", "TP" if win else "SL")
    log(f"{'='*60}", "TRADE")

# ═══════════════════════════════════════════════════════════════
#  📨  TELEGRAM — NOTIFICATIONS RICHES
# ═══════════════════════════════════════════════════════════════
_tg_enabled = False  # activé après vérif au démarrage

def _tg_raw(msg: str):
    if not _tg_enabled: return
    # ✅ FIX: essaie HTML d'abord, fallback plain text si 400
    for parse_mode in ("HTML", None):
        try:
            url  = f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage"
            body = {"chat_id": TG_CHAT_ID, "text": msg}
            if parse_mode:
                body["parse_mode"] = parse_mode
            data = json.dumps(body).encode("utf-8")
            req  = urlreq.Request(
                url, data=data,
                headers={"Content-Type": "application/json"},
            )
            urlreq.urlopen(req, timeout=10)
            return  # succès
        except Exception as e:
            if parse_mode is None:
                log(f"Telegram erreur: {e}", "WARN")
            # sinon on réessaie sans parse_mode

def tg_check() -> bool:
    """Vérifie que le token Telegram est valide au démarrage."""
    global _tg_enabled
    placeholders = ("COLLE_TON_TOKEN_TELEGRAM_ICI", "COLLE_TON_NOUVEAU_TOKEN_TG",
                    "", "REMPLACE_PAR_TON_CHAT_ID")
    if TG_TOKEN in placeholders or TG_CHAT_ID in placeholders:
        log("Telegram non configuré — notifications désactivées", "WARN")
        log(f"  TG_TOKEN   = {'OK' if TG_TOKEN not in placeholders else '❌ MANQUANT'}", "WARN")
        log(f"  TG_CHAT_ID = {'OK' if TG_CHAT_ID not in placeholders else '❌ MANQUANT'}", "WARN")
        return False

    # ── Vérif token ───────────────────────────────────────────
    try:
        url = f"https://api.telegram.org/bot{TG_TOKEN}/getMe"
        with urlreq.urlopen(url, timeout=8) as r:
            data = json.loads(r.read())
            if data.get("ok"):
                _tg_enabled = True
                log(f"Telegram token OK → @{data['result']['username']}", "INFO")

                # ── Trouver le vrai chat_id via getUpdates ────
                try:
                    upd_url = f"https://api.telegram.org/bot{TG_TOKEN}/getUpdates"
                    with urlreq.urlopen(upd_url, timeout=8) as r2:
                        upd = json.loads(r2.read())
                        if upd.get("result"):
                            for msg in reversed(upd["result"]):
                                chat = (msg.get("message") or msg.get("channel_post",{})).get("chat",{})
                                if chat.get("id"):
                                    real_id = str(chat["id"])
                                    log(f"  Chat_id detecte via getUpdates : {real_id}", "INFO")
                                    if real_id != TG_CHAT_ID:
                                        log(f"  ⚠️  TG_CHAT_ID configure = '{TG_CHAT_ID}' "
                                            f"mais chat_id reel = '{real_id}'", "WARN")
                                        log(f"  >>> Mets TG_CHAT_ID={real_id} dans tes env vars Render <<<", "WARN")
                                    break
                        else:
                            log("  getUpdates vide — envoie un message a ton bot Telegram d'abord", "WARN")
                except Exception as e2:
                    log(f"  getUpdates echoue: {e2}", "WARN")

                # ── Test envoi message ─────────────────────────
                try:
                    test_url  = f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage"
                    test_body = json.dumps({
                        "chat_id": TG_CHAT_ID,
                        "text"   : "🤖 AlphaBot v4.0 — Telegram OK ✅\nLogs TP/SL/trades activés.",
                    }).encode("utf-8")
                    test_req = urlreq.Request(
                        test_url, data=test_body,
                        headers={"Content-Type": "application/json"},
                    )
                    urlreq.urlopen(test_req, timeout=8)
                    log(f"Telegram chat_id={TG_CHAT_ID} OK — messages actives", "INFO")
                except urlerr.HTTPError as e:
                    if e.code == 403:
                        log(
                            f"Telegram 403 : le bot ne peut pas ecrire dans chat_id={TG_CHAT_ID}. "
                            f"Envoie un message a ton bot puis corrige TG_CHAT_ID. "
                            f"Notifications desactivees.",
                            "WARN",
                        )
                        _tg_enabled = False
                    elif e.code == 400:
                        log(f"Telegram 400 : chat_id={TG_CHAT_ID} invalide (HTTP 400). "
                            f"Verifie TG_CHAT_ID dans tes env vars.", "WARN")
                        _tg_enabled = False
                    else:
                        log(f"Telegram test message echoue: HTTP {e.code}", "WARN")
                except Exception as e2:
                    log(f"Telegram test message echoue: {e2}", "WARN")

                return _tg_enabled
    except Exception as e:
        log(f"Telegram check echoue: {e}", "WARN")
    return False

def tg_send(msg: str):
    _tg_raw(msg)

def tg_startup(ss: SessionState):
    eff_lev    = get_effective_leverage(ss.start_balance)
    eff_margin = get_effective_margin_pct(ss.start_balance)
    micro_str  = " 🔬 MICRO COMPTE" if is_micro_account(ss.start_balance) else ""
    _tg_raw(
        f"<b>🤖 AlphaBot Futures v3.0 — DÉMARRÉ{micro_str}</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"💰 Balance départ : <code>${ss.start_balance:.2f} USDT</code>\n"
        f"⚙️ Levier effectif: <b>{eff_lev}x</b> (ISOLATED — adaptatif)\n"
        f"📊 Risque initial : {ss.adaptive_risk_pct(score=5)*100:.1f}%/trade\n"
        f"🔒 Max marge/trade: {eff_margin*100:.0f}% × {eff_lev}x "
        f"→ not. max <code>${ss.start_balance*eff_margin*eff_lev:.2f}</code>\n"
        f"🌐 Pool marchés   : {len(SYMBOLS)} paires scannées\n"
        f"🏆 Top sélection  : {TOP_N_SYMBOLS} meilleures paires tradées\n"
        f"⏸️ Pause auto     : après {MAX_CONSEC_SL} SL consécutifs ({PAUSE_AFTER_SL_MIN}min)\n"
        f"🔄 Scan toutes    : {SCAN_INTERVAL_SEC}s\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"<i>Multi-marchés massif — Capital preservation first. 💪</i>"
    )

def tg_trade_open(trade: dict, ss: SessionState):
    # Log console détaillé (visible Render même sans Telegram)
    log_trade_open(
        trade["symbol"], trade["direction"],
        trade["entry"], trade["sl"], trade["tps"],
        trade["qty"], trade["score"], trade["risk_usd"]
    )
    d        = trade["direction"]
    arrow    = "🟢 LONG" if d == "LONG" else "🔴 SHORT"
    tps      = trade["tps"]
    entry    = trade["entry"]
    sl       = trade["sl"]
    score    = trade["score"]
    eff_lev  = get_effective_leverage(ss.current_balance)
    notional = trade["qty"] * entry
    margin   = notional / eff_lev
    fees_est = notional * FEE_RATE * 2
    sl_pct   = round(abs(entry - sl) / entry * 100, 3)
    sl_usd   = abs(entry - sl) * trade["qty"]
    micro    = "🔬 MICRO" if is_micro_account(ss.current_balance) else ""

    # Label qualité signal
    tier_label = {7: "🏆 ÉLITE", 6: "💎 PREMIUM", 5: "✅ SOLIDE"}.get(score, "–")
    risk_used  = ss.adaptive_risk_pct(score=score) * 100

    # TP lines avec gain estimé net par niveau
    tp_lines = ""
    for i, t in enumerate(tps):
        tp_dist  = abs(t["price"] - entry)
        tp_gain  = tp_dist * trade["qty"] * t["pct"] - fees_est * t["pct"]
        tp_lines += (
            f"  TP{i+1} <code>{t['price']:.6f}</code>  "
            f"{int(t['pct']*100)}%pos  @{t['r']}R  "
            f"≈+<code>${tp_gain:.4f}</code>\n"
        )

    # Ratio R:R global (TP3)
    rr = round(abs(tps[-1]["price"] - entry) / abs(entry - sl), 2) if abs(entry - sl) > 0 else 0

    # Croissance compte
    growth = round((ss.session_gain_mult - 1) * 100, 1)
    growth_str = f"+{growth}%" if growth >= 0 else f"{growth}%"

    _tg_raw(
        f"<b>⚡ TRADE OUVERT — {arrow}</b> {micro}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"💱 Paire     : <b>{trade['symbol']}</b>\n"
        f"🎯 Entrée    : <code>{entry:.6f}</code>\n"
        f"🛑 SL        : <code>{sl:.6f}</code>  ({sl_pct}% / -${sl_usd:.4f})  [{trade.get('sl_source','–')}]\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"{tp_lines}"
        f"📐 R:R max   : 1:{rr}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📦 Quantité  : <code>{trade['qty']}</code>\n"
        f"💵 Notionnel : <code>${notional:.2f}</code>\n"
        f"🔐 Marge     : <code>${margin:.2f}</code>  (levier <b>{eff_lev}x</b> ISOLÉE)\n"
        f"💸 Frais est.: <code>~${fees_est:.4f}</code>\n"
        f"⚠️ Risque    : <code>${trade['risk_usd']:.4f}</code>  (<b>{risk_used:.1f}%</b> balance)\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📊 Signal    : {tier_label}  Score:{score}/{SCORE_MAX}\n"
        f"🕯️ CRT       : {trade['crt_name']}\n"
        f"📐 Fibonacci : {trade['fib_zone']}\n"
        f"🧲 Raison    : {trade['reason']}\n"
        f"🌡️ Volatil.  : {trade.get('vol_regime','–')}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"💰 Balance   : <code>${ss.current_balance:.2f}</code> USDT\n"
        f"📈 Session   : {ss.wins}W / {ss.losses}L  |  WR {ss.win_rate}%\n"
        f"💹 PnL sess  : <code>${ss.session_pnl:+.4f}</code>  ({growth_str})\n"
        f"🔄 Capital × : {ss.session_gain_mult:.2f}x\n"
        f"⏰ Durée     : {ss.session_duration()}\n"
        f"🎯 SL consec : {ss.consecutive_sl}/{MAX_CONSEC_SL}"
    )

def tg_trade_close(trade: dict, pnl: float, reason: str, ss: SessionState):
    # Log console détaillé (visible Render même sans Telegram)
    log_trade_close(
        trade["symbol"], trade["direction"],
        trade["entry"], trade["sl"], trade.get("tps", []),
        pnl, reason
    )
    win      = pnl >= 0
    emoji    = "🏆 WIN" if win else "💔 LOSS"
    dur      = round((time.time() - trade.get("open_time", time.time())) / 60, 1)
    notional = trade["qty"] * trade["entry"]
    fees_est = notional * FEE_RATE * 2
    pnl_net  = pnl - fees_est

    # R réalisé
    r_dist = abs(trade["entry"] - trade["sl"])
    r_real = round(abs(pnl) / (r_dist * trade["qty"]), 2) if r_dist > 0 else 0
    r_str  = f"+{r_real}R 🎯" if win else f"-{r_real}R"

    # Stats compte
    growth     = round((ss.session_gain_mult - 1) * 100, 1)
    growth_str = f"+{growth}%" if growth >= 0 else f"{growth}%"
    dd_str     = f"-${ss.max_drawdown:.4f}" if ss.max_drawdown > 0 else "$0"
    next_pos   = adaptive_max_positions(ss.current_balance)

    # TP touchés
    tps_hit = [t for t in trade.get("tps", []) if t.get("hit")]
    tp_str  = ", ".join(f"TP{i+1}" for i, t in enumerate(trade.get("tps",[])) if t.get("hit")) or "aucun"

    _tg_raw(
        f"<b>{emoji} — {trade['symbol']} {trade['direction']}</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🎯 Entrée    : <code>{trade['entry']:.6f}</code>\n"
        f"🛑 SL placé  : <code>{trade['sl']:.6f}</code>  [{trade.get('sl_source','–')}]\n"
        f"✅ TP touchés : {tp_str}\n"
        f"🔍 Clôture   : {reason}\n"
        f"⏱️ Durée     : {dur}min\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📊 PnL brut  : <code>${pnl:+.4f}</code>  ({r_str})\n"
        f"💸 Frais     : <code>-${fees_est:.4f}</code>\n"
        f"💡 PnL net   : <code>${pnl_net:+.4f}</code>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"💰 Balance   : <code>${ss.current_balance:.2f}</code> USDT\n"
        f"📈 Session   : {ss.wins}W / {ss.losses}L  |  WR {ss.win_rate}%\n"
        f"📊 Trades    : 🟢 {ss.longs} LONG  /  🔴 {ss.shorts} SHORT\n"
        f"📐 R:R moyen : {ss.avg_rr:+.2f}R\n"
        f"📉 Drawdown  : {dd_str}\n"
        f"💹 PnL sess  : <code>${ss.session_pnl:+.4f}</code>  ({growth_str})\n"
        f"🔄 Capital × : {ss.session_gain_mult:.2f}x\n"
        f"⚙️ Risque    : {ss.adaptive_risk_pct(score=5)*100:.1f}%/trade\n"
        f"🎯 SL consec : {ss.consecutive_sl}/{MAX_CONSEC_SL}\n"
        f"📍 Max pos   : {next_pos} (balance actuelle)\n"
        f"⏰ Durée sess: {ss.session_duration()}"
    )


def tg_pause(reason: str, ss: SessionState):
    _tg_raw(
        f"<b>⏸️ PAUSE AUTOMATIQUE</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"⚠️ Raison    : {reason}\n"
        f"⏳ Durée     : {PAUSE_AFTER_SL_MIN}min\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📊 Session   : {ss.wins}W/{ss.losses}L "
        f"| SL consécutifs: {ss.consecutive_sl}\n"
        f"💰 Balance   : <code>${ss.current_balance:.2f}</code> USDT\n"
        f"📈 PnL session: <code>${ss.session_pnl:+.4f}</code>\n"
        f"<i>Reprise dans {PAUSE_AFTER_SL_MIN} minutes...</i>"
    )

def tg_resume(ss: SessionState):
    _tg_raw(
        f"<b>▶️ REPRISE DU BOT</b>\n"
        f"💰 Balance: <code>${ss.current_balance:.2f}</code>\n"
        f"📊 {ss.wins}W/{ss.losses}L | PnL: ${ss.session_pnl:+.4f}"
    )

def tg_hourly_summary(ss: SessionState, positions: dict):
    pos_lines = ""
    for sym, t in positions.items():
        pos_lines += f"\n  • {sym} {t['direction']} @ {t['entry']:.6f}  SL:{t['sl']:.6f}"
    if not pos_lines:
        pos_lines = "\n  Aucune position ouverte"

    growth     = round((ss.session_gain_mult - 1) * 100, 1)
    growth_str = f"+{growth}%" if growth >= 0 else f"{growth}%"
    dd_str     = f"-${ss.max_drawdown:.4f}" if ss.max_drawdown > 0 else "$0"
    next_pos   = adaptive_max_positions(ss.current_balance)

    _tg_raw(
        f"<b>📊 RÉSUMÉ COMPTE — AlphaBot v3.0</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"💰 Balance     : <code>${ss.current_balance:.2f}</code> USDT\n"
        f"📈 Capital ×   : {ss.session_gain_mult:.2f}x  ({growth_str})\n"
        f"💹 PnL session : <code>${ss.session_pnl:+.4f}</code>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🏆 Bilan       : {ss.wins}W / {ss.losses}L  |  WR {ss.win_rate}%\n"
        f"📊 Trades      : 🟢 {ss.longs} LONG  /  🔴 {ss.shorts} SHORT\n"
        f"📐 R:R moyen   : {ss.avg_rr:+.2f}R\n"
        f"📉 Drawdown    : {dd_str}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"⚙️ Risque tier : {ss.adaptive_risk_pct(score=5)*100:.1f}%/trade\n"
        f"📍 Max pos     : {next_pos} (selon balance)\n"
        f"🎯 SL consec.  : {ss.consecutive_sl}/{MAX_CONSEC_SL}\n"
        f"⏰ Durée sess  : {ss.session_duration()}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"<b>Positions actives :</b>{pos_lines}"
    )

# ═══════════════════════════════════════════════════════════════
#  🔑  BINANCE FUTURES API (urllib — stdlib uniquement)
# ═══════════════════════════════════════════════════════════════
BASE_URL = "https://fapi.binance.com"

# ── Synchronisation horloge avec Binance ─────────────────────
_time_offset_ms: int = 0   # décalage entre horloge locale et serveur

def sync_server_time():
    """
    Calcule le décalage entre l'heure locale et l'heure du serveur Binance.
    Corrige l'erreur -1022 (Signature invalid) causée par un timestamp désynchronisé.
    """
    global _time_offset_ms
    try:
        url = f"{BASE_URL}/fapi/v1/time"
        with urlreq.urlopen(url, timeout=10) as r:
            server_time = json.loads(r.read())["serverTime"]
            local_time  = int(time.time() * 1000)
            _time_offset_ms = server_time - local_time
            log(f"⏱️  Synchro horloge OK — offset: {_time_offset_ms}ms", "INFO")
    except Exception as e:
        log(f"Synchro horloge échouée: {e} — offset=0", "WARN")
        _time_offset_ms = 0

def _get_timestamp() -> int:
    """Retourne le timestamp corrigé selon l'offset serveur."""
    return int(time.time() * 1000) + _time_offset_ms

def _sign(qs: str) -> str:
    """Signe la query string exacte (pas un dict)."""
    return hmac.new(API_SECRET.encode(), qs.encode(), hashlib.sha256).hexdigest()

def _request(method: str, path: str,
             params: dict = None, signed: bool = False,
             ignore_codes: tuple = ()) -> Optional[any]:
    """
    Envoie une requête à l'API Binance Futures.
    ignore_codes : tuple de codes d'erreur Binance à silencer (ex: (-4046,)).
    """
    params = dict(params or {})
    if signed:
        params["timestamp"]  = _get_timestamp()
        params["recvWindow"] = 10000
        # ⚠️ IMPORTANT : signer la query string EXACTE qui sera envoyée
        qs  = urlparse.urlencode(params)
        params["signature"] = _sign(qs)

    qs  = urlparse.urlencode(params)
    url = f"{BASE_URL}{path}"

    try:
        if method == "GET":
            req = urlreq.Request(
                f"{url}?{qs}",
                headers={"X-MBX-APIKEY": API_KEY},
            )
        elif method == "POST":
            req = urlreq.Request(
                url, data=qs.encode(), method="POST",
                headers={
                    "X-MBX-APIKEY": API_KEY,
                    "Content-Type": "application/x-www-form-urlencoded",
                },
            )
        elif method == "DELETE":
            req = urlreq.Request(
                f"{url}?{qs}", method="DELETE",
                headers={"X-MBX-APIKEY": API_KEY},
            )
        else:
            return None

        with urlreq.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode())

    except urlerr.HTTPError as e:
        body = e.read().decode()
        # Vérifier si c'est un code d'erreur à ignorer silencieusement
        try:
            api_code = json.loads(body).get("code", 0)
        except Exception:
            api_code = 0
        if api_code not in ignore_codes:
            # Tronquer les corps HTML (pages d'erreur Binance) — garder seulement le code
            body_log = body[:120] if body.strip().startswith("<") else body
            log(f"API {method} {path} → HTTP {e.code}: {body_log}", "ERROR")
        return None
    except Exception as e:
        log(f"API {method} {path} → {e}", "ERROR")
        return None

# ─── Endpoints ────────────────────────────────────────────────
def get_klines(symbol: str, interval: str = "1m", limit: int = 220):
    return _request("GET", "/fapi/v1/klines",
                    {"symbol": symbol, "interval": interval, "limit": limit})

def get_exchange_info():
    return _request("GET", "/fapi/v1/exchangeInfo")

def get_mark_price(symbol: str) -> Optional[dict]:
    """
    Mark price avec 3 fallbacks silencieux.
    Certains comptes / régions obtiennent un 404 sur /fapi/v1/markPrice.
    Ordre de tentative :
      1. /fapi/v1/premiumIndex  (mark price officiel, souvent plus stable)
      2. /fapi/v1/markPrice     (endpoint standard)
      3. /fapi/v1/ticker/price  (last price — toujours dispo)
    """
    for path in ("/fapi/v1/premiumIndex", "/fapi/v1/markPrice"):
        try:
            result = _request("GET", path, {"symbol": symbol},
                              ignore_codes=(-1121, -4000))
            if result and isinstance(result, dict) and "markPrice" in result:
                return result
        except Exception:
            pass
    # Fallback last price
    try:
        ticker = _request("GET", "/fapi/v1/ticker/price", {"symbol": symbol},
                          ignore_codes=(-1121, -4000))
        if ticker and "price" in ticker:
            return {"markPrice": ticker["price"], "symbol": symbol}
    except Exception:
        pass
    return None

def get_balance_usdt() -> float:
    resp = _request("GET", "/fapi/v2/balance", {}, signed=True)
    if not isinstance(resp, list): return 0.0
    for a in resp:
        if a.get("asset") == "USDT":
            return float(a.get("availableBalance", 0))
    return 0.0

def get_open_positions() -> List[dict]:
    resp = _request("GET", "/fapi/v2/positionRisk", {}, signed=True)
    if not isinstance(resp, list): return []
    return [p for p in resp if abs(float(p.get("positionAmt", 0))) > 1e-9]

def set_leverage_api(symbol: str, lev: int) -> bool:
    resp = _request("POST", "/fapi/v1/leverage",
                    {"symbol": symbol, "leverage": lev}, signed=True)
    return isinstance(resp, dict) and "leverage" in resp

def set_margin_isolated(symbol: str):
    """Passe en marge ISOLATED. -4046 = déjà isolée → on ignore silencieusement."""
    _request("POST", "/fapi/v1/marginType",
             {"symbol": symbol, "marginType": "ISOLATED"}, signed=True,
             ignore_codes=(-4046,))

def place_order(symbol: str, side: str, order_type: str,
                quantity: str, stop_price: str = None,
                reduce_only: bool = False,
                close_position: bool = False) -> Optional[dict]:
    """
    Place un ordre Futures Binance.

    close_position=True → "closePosition": "true"
      Utilisé pour le SL STOP_MARKET : ferme toute la position d'un coup.
      Évite le -4120 sur les comptes Portfolio Margin ou comptes spéciaux.
      ⚠️ Ne pas passer quantity quand closePosition=true (rejeté par Binance).

    reduce_only=True + quantity → clôture partielle (TPs).
    """
    params = {
        "symbol": symbol,
        "side"  : side,
        "type"  : order_type,
    }

    if close_position:
        # ── Mode closePosition : fermeture totale, pas de quantity ──
        params["closePosition"] = "true"
    else:
        params["quantity"]   = quantity
        params["reduceOnly"] = "true" if reduce_only else "false"

    if stop_price:
        params["stopPrice"]   = stop_price
        params["workingType"] = "MARK_PRICE"
        # ✅ FIX -4120 : STOP_MARKET / TAKE_PROFIT_MARKET n'acceptent PAS timeInForce
        if order_type in ("LIMIT", "STOP", "TAKE_PROFIT"):
            params["timeInForce"] = "GTC"

    return _request("POST", "/fapi/v1/order", params, signed=True)

def info_step(symbol: str) -> float:
    """Retourne le stepSize minimum d'un symbole (pour comparer remaining_qty)."""
    return _sym_info.get(symbol, {}).get("stepSize", 1.0)

def cancel_all_orders(symbol: str):
    _request("DELETE", "/fapi/v1/allOpenOrders",
             {"symbol": symbol}, signed=True)

def get_open_orders(symbol: str) -> List[dict]:
    """Retourne les ordres ouverts (SL/TP) pour un symbole."""
    resp = _request("GET", "/fapi/v1/openOrders", {"symbol": symbol}, signed=True)
    return resp if isinstance(resp, list) else []

# ═══════════════════════════════════════════════════════════════
#  📐  CACHE SYMBOLES BINANCE
# ═══════════════════════════════════════════════════════════════
_sym_info: Dict[str, dict] = {}

def load_symbol_info() -> bool:
    global _sym_info
    info = get_exchange_info()
    if not info or "symbols" not in info:
        log("Impossible de charger exchangeInfo", "ERROR")
        return False
    for s in info["symbols"]:
        sym = s["symbol"]
        d   = {"stepSize": 1.0, "tickSize": 0.0001,
               "minQty": 1.0, "minNotional": 5.0}
        for f in s.get("filters", []):
            ft = f["filterType"]
            if ft == "LOT_SIZE":
                d["stepSize"] = float(f["stepSize"])
                d["minQty"]   = float(f["minQty"])
            elif ft == "PRICE_FILTER":
                d["tickSize"] = float(f["tickSize"])
            elif ft == "MIN_NOTIONAL":
                d["minNotional"] = float(f.get("notional", 5.0))
        _sym_info[sym] = d
    log(f"Exchange info: {len(_sym_info)} symboles chargés", "INFO")
    return True

def _prec(step: float) -> int:
    if step <= 0 or step >= 1: return 0
    return max(0, -int(math.floor(math.log10(step))))

def round_step(v: float, step: float) -> float:
    if step <= 0: return v
    return round(math.floor(v / step) * step, _prec(step))

def round_tick(v: float, tick: float) -> float:
    if tick <= 0: return v
    return round(round(v / tick) * tick, _prec(tick))

def fmt_qty(qty: float, step: float)   -> str: return f"{qty:.{_prec(step)}f}"
def fmt_px(px: float,   tick: float)   -> str: return f"{px:.{_prec(tick)}f}"

# ═══════════════════════════════════════════════════════════════
#  💰  RISK MANAGER v3 — SL STRUCTUREL + LOT ADAPTATIF
# ═══════════════════════════════════════════════════════════════
def calc_atr(highs: list, lows: list, closes: list,
             n: int = ATR_PERIOD) -> float:
    """Wrapper public — utilisé par open_trade et scan."""
    return _calc_atr_simple(highs, lows, closes, n)

def structural_sl(highs: list, lows: list, direction: str,
                  entry: float, atr: float) -> Tuple[float, str]:
    """
    SL basé sur la STRUCTURE DU MARCHÉ — jamais sur un montant fixe.

    LONG  → SL = dernier swing low structurel - marge ATR
    SHORT → SL = dernier swing high structurel + marge ATR

    Priorité :
      1. Swing high/low des 20 dernières bougies (liquidité réelle)
      2. Fallback ATR×2 si pas de structure claire
      3. Buffer frais minimum (anti-chasse par spread)
    """
    margin = atr * 0.5   # marge sous/sur la structure

    if direction == "LONG":
        # Dernier swing low sur 20 bougies (exclu la dernière)
        recent_lows = lows[-21:-1]
        if recent_lows:
            swing_low = min(recent_lows)
            sl = swing_low - margin
            source = "SwingLow"
        else:
            sl = entry - atr * 2
            source = "ATR×2"

        # Vérif : SL ne doit pas être AU-DESSUS de l'entrée
        if sl >= entry:
            sl = entry - atr * 2
            source = "ATR×2_fix"

    else:  # SHORT
        # Dernier swing high sur 20 bougies
        recent_highs = highs[-21:-1]
        if recent_highs:
            swing_high = max(recent_highs)
            sl = swing_high + margin
            source = "SwingHigh"
        else:
            sl = entry + atr * 2
            source = "ATR×2"

        if sl <= entry:
            sl = entry + atr * 2
            source = "ATR×2_fix"

    # Buffer frais minimum (anti-chasse spread)
    fee_buffer = entry * FEE_RATE * 4
    dist = abs(entry - sl)
    if dist < fee_buffer:
        sl = entry - fee_buffer if direction == "LONG" else entry + fee_buffer
        source = "FEE_MIN"

    return sl, source

def dynamic_sl(entry: float, sl_signal: float, direction: str,
               atr: float) -> Tuple[float, str]:
    """
    Wrapper conservé pour compatibilité — utilise structural_sl en priorité.
    sl_signal = suggestion du moteur signal (OB/SMC).
    On garde le plus éloigné entre signal et structure ATR.
    """
    sl_struct = entry - atr * SL_ATR_MIN_FACTOR if direction == "LONG" else entry + atr * SL_ATR_MIN_FACTOR

    if direction == "LONG":
        sl = min(sl_signal, sl_struct)   # plus bas = plus de marge
    else:
        sl = max(sl_signal, sl_struct)   # plus haut = plus de marge

    source = "SMC+ATR"

    # Buffer frais
    fee_buffer  = entry * FEE_RATE * 2
    min_sl_dist = fee_buffer * 2
    if abs(entry - sl) < min_sl_dist:
        sl     = entry - min_sl_dist if direction == "LONG" else entry + min_sl_dist
        source = "FEE_BUFFER"

    return sl, source

def adaptive_max_positions(balance: float) -> int:
    """
    Règle stricte — 1 seule position même à $2.
    Le bot ne passe à 2 positions qu'à partir de $10.
    Plafond absolu : 3 positions, jamais dépassé.
    """
    if balance < 10:  return 1   # $0 → $9.99  : focus total
    if balance < 30:  return 2   # $10 → $29.99 : 2 positions max
    return 3                     # $30+          : 3 positions (plafond)

# ═══════════════════════════════════════════════════════════════
#  🔧  PARAMÈTRES ADAPTATIFS — MICRO COMPTE
#  Le levier et la marge s'ajustent automatiquement au capital.
#  Plus le compte est petit, plus on monte le levier ET la marge
#  autorisée pour pouvoir atteindre le notionnel minimum Binance ($5).
#  Le SL reste le vrai protecteur du capital — pas le levier.
# ═══════════════════════════════════════════════════════════════
def get_effective_leverage(balance: float) -> int:
    """
    Levier effectif selon le capital.
    Objectif : permettre un notionnel ≥ $5 même avec $1.
      $1–$2   → 75x  (marge 40% → notionnel min = $0.40×75 = $30) ✓
      $2–$5   → 50x  (marge 45% → notionnel min = $0.90×50 = $45) ✓
      $5–$15  → 30x  (marge 30% → notionnel min = $1.50×30 = $45) ✓
      $15–$50 → 25x  (marge 20%)
      $50+    → 20x  (standard)
    """
    if balance < 2:   return 75
    if balance < 5:   return 50
    if balance < 15:  return 30
    if balance < 50:  return 25
    return LEVERAGE   # 20x standard

def get_effective_margin_pct(balance: float) -> float:
    """
    % max du capital utilisable en marge par trade.
    En marge ISOLÉE, la perte max = marge engagée (capée par le SL bien avant).
    Micro compte : on autorise plus de marge pour atteindre le notionnel min Binance.
    """
    if balance < 2:   return 0.40   # $1-2   → 40% de marge max
    if balance < 5:   return 0.45   # $2-5   → 45%
    if balance < 15:  return 0.35   # $5-15  → 35%
    if balance < 50:  return 0.25   # $15-50 → 25%
    return MAX_MARGIN_PCT            # $50+   → 15% (standard)

def is_micro_account(balance: float) -> bool:
    """Retourne True si le compte est en mode micro ($0–$10)."""
    return balance < 10.0

def calc_position_size(symbol: str, balance: float, risk_pct: float,
                       entry: float, sl: float
                       ) -> Tuple[float, float, str]:
    """
    Sizing ADAPTATIF MICRO COMPTE :
      1. Levier et marge adaptés automatiquement au capital
      2. Lot calculé selon le risque et la distance SL (structure)
      3. Fallback minQty si le lot calculé est trop petit (micro trade)
      4. Sécurité : risque réel recalculé et plafonné à 10% si fallback

    Returns (qty, notional_usd, error_msg)
    """
    if symbol not in _sym_info:
        return 0.0, 0.0, f"Symbole inconnu: {symbol}"
    info = _sym_info[symbol]

    eff_lev        = get_effective_leverage(balance)
    eff_margin_pct = get_effective_margin_pct(balance)

    sl_dist_pct = abs(entry - sl) / entry if entry > 0 else 0

    # ── Filtres distance SL ───────────────────────────────────
    if sl_dist_pct < 0.0015:   # < 0.15% = SL trop serré
        return 0.0, 0.0, f"SL trop serré ({sl_dist_pct*100:.3f}%) → skip"
    if sl_dist_pct > 0.05:     # > 5% = risque excessif
        return 0.0, 0.0, f"SL trop large ({sl_dist_pct*100:.2f}%) → skip"

    # ── Lot adaptatif basé sur le risque et la structure ──────
    risk_usd     = balance * risk_pct
    notional_raw = risk_usd / sl_dist_pct
    max_notional = balance * eff_margin_pct * eff_lev
    notional     = min(notional_raw, max_notional)

    # ── Fallback minQty (micro trade) ─────────────────────────
    # Si le notionnel calculé < minimum Binance, on essaie avec
    # la quantité minimale autorisée par Binance.
    if notional < info["minNotional"]:
        min_qty_notional = info["minQty"] * entry
        if min_qty_notional >= info["minNotional"]:
            margin_needed = min_qty_notional / eff_lev
            if margin_needed <= balance * eff_margin_pct:
                actual_risk_pct = info["minQty"] * abs(entry - sl) / balance
                if actual_risk_pct <= 0.12:   # risque réel plafonné à 12%
                    # Fallback accepté — on utilise minQty
                    return info["minQty"], min_qty_notional, ""
        return 0.0, 0.0, (
            f"Notionnel ${notional:.2f} < min ${info['minNotional']} "
            f"(balance=${balance:.2f} lev={eff_lev}x)"
        )

    qty = round_step(notional / entry, info["stepSize"])
    if qty < info["minQty"]:
        # Dernier recours : minQty si proche
        min_qty_notional = info["minQty"] * entry
        if min_qty_notional >= info["minNotional"]:
            margin_needed = min_qty_notional / eff_lev
            if margin_needed <= balance * eff_margin_pct:
                return info["minQty"], min_qty_notional, ""
        return 0.0, 0.0, f"Qty {qty} < minQty {info['minQty']}"

    return qty, qty * entry, ""

# ═══════════════════════════════════════════════════════════════
#  📊  MOTEUR DE SIGNAL v4.0 — IMPULSE → 50% → FVG → REJET
# ═══════════════════════════════════════════════════════════════

# ── Utilitaire ATR ────────────────────────────────────────────
def _calc_atr_simple(highs: list, lows: list, closes: list,
                     n: int = ATR_PERIOD) -> float:
    """ATR sur les n dernières bougies."""
    if len(highs) < n + 1: return 0.0
    trs = [max(highs[i] - lows[i],
               abs(highs[i]  - closes[i-1]),
               abs(lows[i]   - closes[i-1])) for i in range(-n, 0)]
    return sum(trs) / len(trs)

# ── Étape 1 : Détection de l'impulsion ───────────────────────
def detect_impulse(highs: list, lows: list, closes: list,
                   atr: float) -> Optional[dict]:
    """
    Détecte le swing impulsif le plus récent et significatif.

    On cherche dans les IMPULSE_LOOKBACK dernières bougies :
      - Le plus haut (HH) et le plus bas (LL)
      - La direction : si HH arrivé après LL  → tendance BULLISH (setup LONG)
                       si LL arrivé après HH  → tendance BEARISH (setup SHORT)
      - La force de l'impulsion : range / ATR

    Retourne un dict ou None si pas d'impulsion valide.
    """
    if atr <= 0: return None
    n = min(IMPULSE_LOOKBACK, len(highs))
    sub_h = highs[-n:]
    sub_l = lows[-n:]

    # Indices du HH et LL dans la fenêtre
    hh_idx = sub_h.index(max(sub_h))
    ll_idx = sub_l.index(min(sub_l))

    hh = sub_h[hh_idx]
    ll = sub_l[ll_idx]
    impulse_range = hh - ll

    # L'impulsion doit être suffisamment grande
    if impulse_range < atr * IMPULSE_MIN_ATR:
        return None

    # Direction : quel extrême est arrivé en dernier ?
    if hh_idx > ll_idx:
        direction   = "LONG"    # HH après LL → impulsion haussière
        swing_start = ll
        swing_end   = hh
    else:
        direction   = "SHORT"   # LL après HH → impulsion baissière
        swing_start = hh
        swing_end   = ll

    force_atr = round(impulse_range / atr, 2)

    return {
        "direction"    : direction,
        "swing_high"   : hh,
        "swing_low"    : ll,
        "impulse_range": impulse_range,
        "force_atr"    : force_atr,   # ex: 2.4× ATR
    }

# ── Étape 2 : Vérification retracement 50% ───────────────────
def check_50_retracement(price: float, swing_high: float,
                          swing_low: float, direction: str) -> Tuple[bool, float, str]:
    """
    Le prix est-il dans la zone de retracement 50% (±FIB_ZONE_HIGH) ?

    Pour LONG  : après impulsion haussière, prix revient vers 50% = zone d'achat
    Pour SHORT : après impulsion baissière, prix revient vers 50% = zone de vente

    Retourne (dans_zone, ratio_fib, label_zone)
    """
    rng = swing_high - swing_low
    if rng < 1e-9: return False, 0.0, "–"

    # Ratio Fibonacci depuis le bas de l'impulsion
    fib_ratio = (swing_high - price) / rng if direction == "LONG" \
                else (price - swing_low) / rng

    fib_ratio = max(0.0, min(fib_ratio, 1.0))

    in_zone = FIB_ZONE_LOW <= fib_ratio <= FIB_ZONE_HIGH

    if fib_ratio >= 0.55:   label = "50–58% Discount🎯"
    elif fib_ratio >= 0.45: label = "50% Equilibrium✦"
    else:                   label = f"{fib_ratio*100:.0f}% (hors zone)"

    return in_zone, round(fib_ratio * 100, 1), label

# ── Étape 3a : Détection FVG dans la zone ────────────────────
def find_fvg_in_zone(highs: list, lows: list, opens: list,
                     closes: list, zone_price: float,
                     direction: str, atr: float) -> Tuple[bool, float, float, float]:
    """
    Cherche une Fair Value Gap (imbalance) dans la zone 50%.

    FVG Bullish : highs[i] < lows[i+2]  → gap entre deux bougies
    FVG Bearish : lows[i]  > highs[i+2] → gap inversé

    Le gap doit :
      - être dans la zone 50% (price ± 2×ATR)
      - avoir une taille ≥ FVG_MIN_SIZE_ATR × ATR
      - être partiellement comblé (prix a touché la zone)

    Retourne (found, fvg_top, fvg_bot, fill_pct)
    """
    n     = min(FVG_LOOKBACK, len(highs) - 2)
    best  = None
    best_fill = 0.0
    zone_tolerance = atr * 2

    for i in range(len(highs) - n - 1, len(highs) - 2):
        if direction == "LONG":
            # FVG bullish : gap entre high[i] et low[i+2]
            fvg_bot = highs[i]
            fvg_top = lows[i+2]
            if fvg_top <= fvg_bot: continue   # pas de gap

            gap_size = fvg_top - fvg_bot
            if gap_size < atr * FVG_MIN_SIZE_ATR: continue

            # Le gap est-il dans la zone ?
            fvg_mid = (fvg_top + fvg_bot) / 2
            if abs(fvg_mid - zone_price) > zone_tolerance: continue

            # Le prix a-t-il comblé une partie du gap ?
            current = closes[-1]
            if current <= fvg_bot: continue   # pas encore touché
            fill_pct = min((current - fvg_bot) / gap_size, 1.0)
            if fill_pct < FVG_FILL_MIN: continue

        else:  # SHORT
            # FVG bearish : gap entre low[i] et high[i+2]
            fvg_top = lows[i]
            fvg_bot = highs[i+2]
            if fvg_bot >= fvg_top: continue

            gap_size = fvg_top - fvg_bot
            if gap_size < atr * FVG_MIN_SIZE_ATR: continue

            fvg_mid = (fvg_top + fvg_bot) / 2
            if abs(fvg_mid - zone_price) > zone_tolerance: continue

            current = closes[-1]
            if current >= fvg_top: continue
            fill_pct = min((fvg_top - current) / gap_size, 1.0)
            if fill_pct < FVG_FILL_MIN: continue

        if fill_pct > best_fill:
            best_fill = fill_pct
            best      = (fvg_top, fvg_bot, fill_pct)

    if best:
        return True, best[0], best[1], best[2]
    return False, 0.0, 0.0, 0.0

# ── Étape 3b : Détection Order Block dans la zone ────────────
def find_ob_in_zone(opens: list, closes: list, highs: list, lows: list,
                    zone_price: float, direction: str, atr: float) -> Tuple[bool, float, float]:
    """
    Cherche un Order Block (dernière bougie opposée avant l'impulsion)
    dans la zone 50%.

    OB Bullish : dernière bougie BEARISH avant un fort mouvement haussier
    OB Bearish : dernière bougie BULLISH avant un fort mouvement baissier

    Retourne (found, ob_top, ob_bot)
    """
    n   = min(OB_LOOKBACK, len(closes) - 2)
    tol = atr * 1.5

    for i in range(len(closes) - n - 1, len(closes) - 1):
        if direction == "LONG":
            # OB bullish : bougie baissière
            if closes[i] >= opens[i]: continue
            ob_top = highs[i]
            ob_bot = lows[i]
        else:
            # OB bearish : bougie haussière
            if closes[i] <= opens[i]: continue
            ob_top = highs[i]
            ob_bot = lows[i]

        ob_mid = (ob_top + ob_bot) / 2
        if abs(ob_mid - zone_price) > tol: continue

        # Vérif : une bougie impulsive suit l'OB
        if i + 1 < len(closes):
            next_body = abs(closes[i+1] - opens[i+1])
            ob_body   = abs(closes[i]   - opens[i])
            if next_body > ob_body * 1.5:   # bougie suivante plus forte
                return True, ob_top, ob_bot

    return False, 0.0, 0.0

# ── Étape 4 : Bougie de rejet / retournement ─────────────────
def detect_rejection(opens: list, closes: list,
                     highs: list, lows: list,
                     direction: str) -> Tuple[bool, str]:
    """
    La bougie actuelle (ou la précédente) montre-t-elle un rejet
    de la zone 50% ?

    Types détectés :
      - Hammer / ShootingStar  (longue mèche dans la direction)
      - Bougie Forte (corps > 55% du range, dans le bon sens)
      - Engulfing (corps actuel > 1.2× corps précédent)
      - Tweezer Bottom/Top (double fond/sommet)
      - Inside Bar Break (bougie intérieure puis cassure)
    """
    if len(closes) < 3:
        return False, "NONE"

    # Bougie actuelle
    o, c, h, l = opens[-1], closes[-1], highs[-1], lows[-1]
    rng  = h - l
    body = abs(c - o)
    if rng < 1e-9: return False, "NONE"

    # Bougie précédente
    o1, c1, h1, l1 = opens[-2], closes[-2], highs[-2], lows[-2]
    body1 = abs(c1 - o1)

    # ── 1. Hammer / Shooting Star ─────────────────────────────
    lower_wick = min(o, c) - l
    upper_wick = h - max(o, c)
    if direction == "LONG" and lower_wick / rng >= REJECTION_WICK_RATIO:
        return True, "Hammer🔨"
    if direction == "SHORT" and upper_wick / rng >= REJECTION_WICK_RATIO:
        return True, "ShootingStar⭐"

    # ── 2. Bougie forte ───────────────────────────────────────
    if body / rng >= REJECTION_BODY_RATIO:
        if direction == "LONG"  and c > o: return True, "BullStrong↑"
        if direction == "SHORT" and c < o: return True, "BearStrong↓"

    # ── 3. Engulfing ──────────────────────────────────────────
    if body1 > 1e-9 and body > body1 * REJECTION_ENGULF_MULT:
        if direction == "LONG"  and c > o and c > max(o1, c1):
            return True, "BullEngulf↑"
        if direction == "SHORT" and c < o and c < min(o1, c1):
            return True, "BearEngulf↓"

    # ── 4. Tweezer Bottom / Top ───────────────────────────────
    tol = closes[-1] * REJECTION_TWEEZER_TOL
    if direction == "LONG"  and abs(l - l1) <= tol and c > c1:
        return True, "TweezerBot🟢"
    if direction == "SHORT" and abs(h - h1) <= tol and c < c1:
        return True, "TweezerTop🔴"

    # ── 5. Inside Bar Break ───────────────────────────────────
    if len(closes) >= 3:
        h2, l2 = highs[-3], lows[-3]
        inside = (h1 <= h2 * 1.001) and (l1 >= l2 * 0.999)
        if inside:
            if direction == "LONG"  and c > h1: return True, "InsideBreak↑"
            if direction == "SHORT" and c < l1: return True, "InsideBreak↓"

    # ── 6. Pin Bar ────────────────────────────────────────────
    # Corps dans le tiers supérieur/inférieur de la bougie
    if direction == "LONG":
        body_pos = (min(o, c) - l) / rng  # position du bas du corps
        if body_pos >= 0.60 and lower_wick / rng >= 0.40:
            return True, "PinBar🔑"
    else:
        body_pos = (h - max(o, c)) / rng  # position du haut du corps
        if body_pos >= 0.60 and upper_wick / rng >= 0.40:
            return True, "PinBar🔑"

    return False, "NONE"

# ── Volatilité (inchangée) ───────────────────────────────────
def vol_regime(highs, lows, closes, n: int = ATR_PERIOD):
    if len(highs) < n + 1: return "NORMAL", 0.0, SCORE_THRESH["NORMAL"]
    trs = [max(highs[i] - lows[i],
               abs(highs[i] - closes[i-1]),
               abs(lows[i]  - closes[i-1])) for i in range(-n, 0)]
    atr = sum(trs) / len(trs)
    pct = atr / closes[-1] if closes[-1] > 0 else 0
    if pct < ATR_LOW_MULT:  return "LOW",    pct, SCORE_THRESH["LOW"]
    if pct > ATR_HIGH_MULT: return "HIGH",   pct, SCORE_THRESH["HIGH"]
    return "NORMAL", pct, SCORE_THRESH["NORMAL"]

# ── Tendance de fond (Structure M1 longue) ────────────────────
def detect_structural_trend(highs: list, lows: list, closes: list,
                             n: int = TREND_LOOKBACK) -> str:
    """
    Détermine la tendance structurelle sur les N dernières bougies M1.

    Méthode Higher High / Lower Low :
      - LONG  : le prix fait des HH et HL (série de plus hauts et creux croissants)
      - SHORT : le prix fait des LH et LL (série de plus hauts et creux décroissants)
      - NEUTRE: structure mixte / range

    Utilisée pour filtrer les trades à contre-tendance.
    """
    if len(closes) < n:
        return "NEUTRE"

    sub_h = highs[-n:]
    sub_l = lows[-n:]

    # Découper en 3 tiers pour comparer l'évolution de la structure
    t1 = n // 3
    t2 = (n * 2) // 3

    # High et Low de chaque tiers
    h1 = max(sub_h[:t1]);      l1 = min(sub_l[:t1])
    h2 = max(sub_h[t1:t2]);    l2 = min(sub_l[t1:t2])
    h3 = max(sub_h[t2:]);      l3 = min(sub_l[t2:])

    # Tendance haussière : HH + HL sur les 3 tiers
    bullish = (h3 > h2 > h1) and (l3 > l2 > l1)
    # Tendance baissière : LH + LL sur les 3 tiers
    bearish = (h3 < h2 < h1) and (l3 < l2 < l1)

    if bullish: return "LONG"
    if bearish: return "SHORT"

    # Test moins strict : 2 tiers sur 3
    semi_bull = (h3 > h1) and (l3 > l1)
    semi_bear = (h3 < h1) and (l3 < l1)
    if semi_bull: return "LONG"
    if semi_bear: return "SHORT"
    return "NEUTRE"

# ── Prise de liquidité / Sweep ────────────────────────────────
def detect_liquidity_sweep(highs: list, lows: list, closes: list,
                            direction: str, atr: float) -> bool:
    """
    Détecte une prise de liquidité (stop hunt) avant retournement.

    Logique ICT / SMC :
      LONG  : le prix a cassé sous un swing low des N dernières bougies
              (chasse les stops des longs) PUIS est remonté au-dessus.
              → Signifie que les Smart Money ont absorbé les ventes et vont monter.

      SHORT : le prix a cassé au-dessus d'un swing high des N dernières bougies
              (chasse les stops des shorts) PUIS est redescendu en-dessous.
              → Signifie que les Smart Money ont distribué et vont baisser.

    Retourne True si un sweep est détecté dans les LIQ_SWEEP_LOOKBACK dernières bougies.
    """
    if not LIQ_SWEEP_ENABLED:
        return False
    if atr <= 0 or len(closes) < LIQ_SWEEP_LOOKBACK + 2:
        return False

    n       = min(LIQ_SWEEP_LOOKBACK, len(closes) - 2)
    current = closes[-1]
    tol     = atr * 0.15   # tolérance pour valider le retour au-dessus/en-dessous

    if direction == "LONG":
        # Cherche le plus bas swing sur N bougies AVANT la dernière
        recent_lows  = lows[-(n+1):-1]
        swing_low    = min(recent_lows)
        # La bougie la plus basse a-t-elle cassé le swing low ?
        swept = any(lows[-(n+1)+i] < swing_low - tol for i in range(len(recent_lows)))
        # Le prix actuel est-il remonté au-dessus ?
        recovered = current > swing_low + tol
        return swept and recovered

    else:  # SHORT
        # Cherche le plus haut swing sur N bougies AVANT la dernière
        recent_highs = highs[-(n+1):-1]
        swing_high   = max(recent_highs)
        # La bougie la plus haute a-t-elle cassé le swing high ?
        swept = any(highs[-(n+1)+i] > swing_high + tol for i in range(len(recent_highs)))
        # Le prix actuel est-il redescendu en-dessous ?
        recovered = current < swing_high - tol
        return swept and recovered

# ── Tendance BTC (corrélation macro) ─────────────────────────
_btc_trend_cache: dict = {"trend": "NEUTRE", "ts": 0.0}

def get_btc_trend() -> str:
    """
    Récupère et met en cache la tendance BTC sur BTC_LOOKBACK bougies M1.
    Cache de 3 minutes pour éviter trop d'appels API.
    Retourne "LONG", "SHORT" ou "NEUTRE".
    """
    global _btc_trend_cache
    if not BTC_CORRELATION:
        return "NEUTRE"   # filtre désactivé → neutre = pas de contrainte

    # Cache 3 minutes
    if time.time() - _btc_trend_cache["ts"] < 180:
        return _btc_trend_cache["trend"]

    try:
        raw = get_klines("BTCUSDT", "1m", BTC_LOOKBACK + 20)
        if not isinstance(raw, list) or len(raw) < BTC_LOOKBACK:
            return _btc_trend_cache["trend"]
        btc_h = [float(x[2]) for x in raw]
        btc_l = [float(x[3]) for x in raw]
        btc_c = [float(x[4]) for x in raw]
        trend = detect_structural_trend(btc_h, btc_l, btc_c, n=BTC_LOOKBACK)
        _btc_trend_cache = {"trend": trend, "ts": time.time()}
        log(f"  📈 BTC tendance: {trend}", "INFO")
        return trend
    except Exception as e:
        log(f"  BTC trend fetch échoué: {e}", "WARN")
        return _btc_trend_cache["trend"]

# ── Signal principal v4 ───────────────────────────────────────
def get_signal(opens: list, highs: list, lows: list,
               closes: list, score_thresh: int) -> Optional[dict]:
    """
    Stratégie complète v4 :
    1. Impulse détectée ?          (+1 normal, +1 bonus si fort)
    2. Prix au 50% de l'impulsion? (obligatoire)
    3. FVG dans la zone ?          (+2 si oui)
    4. OB dans la zone ?           (+1 si oui)
    5. Bougie de rejet ?           (+2 obligatoire)

    → Entrée si score ≥ score_thresh ET rejet présent ET FVG ou OB
    """
    if len(closes) < 60: return None

    price = closes[-1]
    atr   = _calc_atr_simple(highs, lows, closes)
    if atr <= 0: return None

    # ── 1. IMPULSE ───────────────────────────────────────────
    imp = detect_impulse(highs, lows, closes, atr)
    if imp is None:
        return None   # pas de mouvement significatif → on attend

    direction   = imp["direction"]
    swing_high  = imp["swing_high"]
    swing_low   = imp["swing_low"]
    force_atr   = imp["force_atr"]

    # ── 2. RETRACEMENT 50% ───────────────────────────────────
    in_zone, fib_pct, fib_zone = check_50_retracement(
        price, swing_high, swing_low, direction)
    if not in_zone:
        return None   # prix pas encore dans la zone → on attend

    zone_price = swing_low + (swing_high - swing_low) * 0.50

    # ── 3. FVG dans la zone ───────────────────────────────────
    fvg_ok, fvg_top, fvg_bot, fvg_fill = find_fvg_in_zone(
        highs, lows, opens, closes, zone_price, direction, atr)

    # ── 4. ORDER BLOCK dans la zone ───────────────────────────
    ob_ok, ob_top, ob_bot = find_ob_in_zone(
        opens, closes, highs, lows, zone_price, direction, atr)

    # ── 5. BOUGIE DE REJET ───────────────────────────────────
    rej_ok, rej_name = detect_rejection(opens, closes, highs, lows, direction)

    # ── 6. PRISE DE LIQUIDITÉ (Sweep) ────────────────────────
    sweep_ok = detect_liquidity_sweep(highs, lows, closes, direction, atr)

    # ── 7. TENDANCE STRUCTURELLE ──────────────────────────────
    struct_trend = detect_structural_trend(highs, lows, closes, n=TREND_LOOKBACK)

    # ── SCORING ──────────────────────────────────────────────
    score = 0
    score += 1                      # impulse présente
    if force_atr >= IMPULSE_STRONG_ATR:
        score += 1                  # impulse forte (bonus)
    if fvg_ok:
        score += 2                  # FVG comblée dans la zone
    if ob_ok:
        score += 1                  # OB confluent
    if rej_ok:
        score += 2                  # bougie de rejet
    if sweep_ok and LIQ_SWEEP_ENABLED:
        score += LIQ_SWEEP_SCORE    # prise de liquidité confirmée

    # ── FILTRES D'ENTRÉE OBLIGATOIRES ─────────────────────────
    # On n'entre JAMAIS sans rejet ET sans FVG ou OB
    if not rej_ok:
        return None   # pas de confirmation de retournement
    if not fvg_ok and not ob_ok:
        return None   # pas de structure Smart Money dans la zone

    # ── FILTRE TENDANCE DE FOND ───────────────────────────────
    # Si la tendance structurelle est opposée au signal ET score < override,
    # on rejette le signal (à contre-tendance = trop risqué)
    if TREND_FILTER_ENABLED and struct_trend != "NEUTRE":
        if struct_trend != direction and score < TREND_MIN_SCORE_OVERRIDE:
            return None   # signal à contre-tendance, pas assez fort

    if score < score_thresh:
        return None

    # ── SL BRUT (sous/sur la zone impulsion) ─────────────────
    if direction == "LONG":
        sl_raw = swing_low - atr * 0.3   # sous le swing low
    else:
        sl_raw = swing_high + atr * 0.3  # au-dessus du swing high

    # Sécurité : SL pas trop proche ni trop loin
    risk    = abs(price - sl_raw)
    min_risk = price * 0.0015  # 0.15% minimum
    max_risk = price * 0.05    # 5% maximum
    if risk < min_risk or risk > max_risk:
        return None

    # ── TAKE PROFITS (basés sur la distance SL) ──────────────
    tps = []
    for tp_def in TP_SPLIT:
        tp_price = (price + risk * tp_def["r"] if direction == "LONG"
                    else price - risk * tp_def["r"])
        tps.append({"r": tp_def["r"], "pct": tp_def["pct"],
                    "price": tp_price, "hit": False})

    # ── Construction résultat ─────────────────────────────────
    reason_parts = []
    if fvg_ok:
        reason_parts.append(f"FVG{fvg_fill*100:.0f}%")
    if ob_ok:
        reason_parts.append("OB")
    reason_parts.append(f"{fib_pct}%Fib")
    reason = "+".join(reason_parts)

    return {
        "direction" : direction,
        "entry"     : price,
        "sl_raw"    : sl_raw,
        "tps"       : tps,
        "risk"      : risk,
        "fib_pct"   : fib_pct,
        "fib_zone"  : fib_zone,
        "imb_fill"  : fvg_fill if fvg_ok else 0.0,
        "crt_name"  : rej_name,
        "score"     : score,
        "reason"    : reason,
        # Métadonnées pour le dashboard
        "swing_high"  : swing_high,
        "swing_low"   : swing_low,
        "force_atr"   : force_atr,
        "fvg_ok"      : fvg_ok,
        "ob_ok"       : ob_ok,
        "sweep_ok"    : sweep_ok,
        "struct_trend": struct_trend,
    }

# ═══════════════════════════════════════════════════════════════
#  📦  FETCH KLINES
# ═══════════════════════════════════════════════════════════════
def fetch_klines_parsed(symbol: str) -> Optional[tuple]:
    raw = get_klines(symbol, "1m", KLINES_LIMIT)
    if not isinstance(raw, list) or len(raw) < 60: return None
    return (
        [int(x[0])   for x in raw],
        [float(x[1]) for x in raw],
        [float(x[2]) for x in raw],
        [float(x[3]) for x in raw],
        [float(x[4]) for x in raw],
    )

# ═══════════════════════════════════════════════════════════════
#  📒  JOURNAL CSV
# ═══════════════════════════════════════════════════════════════
JOURNAL_FILE = f"journal_v2_{datetime.now().strftime('%Y%m%d')}.csv"
_HDR = ["time","symbol","direction","entry","sl","sl_source",
        "tp1","tp2","tp3","qty","notional","margin","fees_est",
        "risk_usd","risk_pct","score","crt","fib","reason",
        "vol","consecutive_sl_at_open","status"]

def _jw(row):
    hdr = not os.path.exists(JOURNAL_FILE)
    with open(JOURNAL_FILE, "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if hdr: w.writerow(_HDR)
        w.writerow(row)

def journal_open(t: dict, ss: SessionState):
    fees = t["qty"] * t["entry"] * FEE_RATE * 2
    _jw([datetime.now().isoformat(),
         t["symbol"], t["direction"], t["entry"], t["sl"], t.get("sl_source",""),
         t["tps"][0]["price"], t["tps"][1]["price"], t["tps"][2]["price"],
         t["qty"], round(t["qty"]*t["entry"],2),
         round(t["qty"]*t["entry"]/LEVERAGE,2), round(fees,4),
         t["risk_usd"], t["risk_pct"], t["score"],
         t["crt_name"], t["fib_zone"], t["reason"],
         t.get("vol_regime",""), ss.consecutive_sl, "OPEN"])

def journal_close(t: dict, pnl: float, reason: str):
    fees = t["qty"] * t["entry"] * FEE_RATE * 2
    _jw([datetime.now().isoformat(),
         t["symbol"], t["direction"], t["entry"], t["sl"], t.get("sl_source",""),
         t["tps"][0]["price"], t["tps"][1]["price"], t["tps"][2]["price"],
         t["qty"], round(t["qty"]*t["entry"],2),
         round(t["qty"]*t["entry"]/LEVERAGE,2), round(fees,4),
         t["risk_usd"], t["risk_pct"], t["score"],
         t["crt_name"], t["fib_zone"], t["reason"],
         t.get("vol_regime",""), "", f"CLOSE|{reason}|PNL:{round(pnl,4)}"])

# ═══════════════════════════════════════════════════════════════
#  🎯  ORDER MANAGER v2 — SL DYNAMIQUE + FRAIS
# ═══════════════════════════════════════════════════════════════
#  🎯  ORDER MANAGER v3 — SL STRUCTUREL + LOT ADAPTATIF
# ═══════════════════════════════════════════════════════════════
def open_trade(symbol: str, sig: dict, ss: SessionState,
               atr: float, vol_regime_str: str,
               highs: list = None, lows: list = None) -> Optional[dict]:
    """
    Place un trade avec SL basé sur la STRUCTURE du marché.
    Le lot s'adapte à la distance SL — jamais l'inverse.
    """
    info = _sym_info.get(symbol)
    if not info:
        log(f"{symbol}: infos symbole absentes", "WARN"); return None

    direction  = sig["direction"]
    entry      = sig["entry"]
    entry_side = "BUY"  if direction=="LONG" else "SELL"
    close_side = "SELL" if direction=="LONG" else "BUY"

    # ── SL STRUCTUREL (swing high/low) ───────────────────────
    if highs and lows:
        sl_final, sl_source = structural_sl(highs, lows, direction, entry, atr)
    else:
        sl_final, sl_source = dynamic_sl(entry, sig["sl_raw"], direction, atr)
    sl_final = round_tick(sl_final, info["tickSize"])

    # ── Sizing adaptatif (lot = risque / distance_SL) ─────────
    score      = sig.get("score", 5)
    risk_pct   = ss.adaptive_risk_pct(score=score)   # risque selon qualité signal
    balance    = ss.current_balance
    eff_lev    = get_effective_leverage(balance)   # levier adaptatif
    qty, notional, err = calc_position_size(
        symbol, balance, risk_pct, entry, sl_final)
    if err:
        log(f"  {symbol} sizing refusé: {err}", "WARN"); return None

    risk_usd = abs(entry - sl_final) / entry * notional
    margin   = notional / eff_lev
    sl_dist_pct = abs(entry - sl_final) / entry * 100

    log(
        f"  {symbol} {direction} | Entry≈{entry:.6f} "
        f"SL={sl_final:.6f}[{sl_source}] dist={sl_dist_pct:.3f}% | "
        f"Qty={fmt_qty(qty, info['stepSize'])} "
        f"Not=${notional:.2f} Marge=${margin:.2f}({eff_lev}x) "
        f"Risk={risk_pct*100:.1f}% (${risk_usd:.4f})",
        "TRADE",
    )

    # ── Margin ISOLATED + levier ADAPTATIF ────────────────────
    set_margin_isolated(symbol)
    set_leverage_api(symbol, eff_lev)   # levier adapté au capital

    # ── Entrée MARKET ─────────────────────────────────────────
    qty_str   = fmt_qty(qty, info["stepSize"])
    entry_ord = place_order(symbol, entry_side, "MARKET", qty_str)
    if not entry_ord or entry_ord.get("status") not in (
            "FILLED", "NEW", "PARTIALLY_FILLED"):
        log(f"  {symbol}: ordre entrée échoué → {entry_ord}", "ERROR")
        return None

    real_entry = float(entry_ord.get("avgPrice") or entry_ord.get("price") or entry)
    if real_entry < 1e-9: real_entry = entry

    # ── CORRECTION FIX#1 : conserver le SL STRUCTUREL (SwingHigh/Low)
    # On NE recalcule PAS avec dynamic_sl (ATR×1.5) qui donne un SL
    # trop serré et provoque des stop-hunts avec levier élevé.
    # On garde sl_final (structurel) et on l'ajuste juste sur le prix réel.
    sl_final2 = sl_final   # SL structurel calculé avant l'entrée
    sl_src2   = sl_source
    sl_final2 = round_tick(sl_final2, info["tickSize"])
    risk_actual = abs(real_entry - sl_final2)

    # ── Sécurité : SL minimum = 0.25% OU 2×ATR ─────────────
    # Si le SL calculé est trop proche (FEE_MIN ou spread),
    # on l'élargit au lieu de refuser le trade.
    # Un SL trop serré = stop-hunt garanti avec levier élevé.
    min_sl_dist = max(real_entry * 0.0025, atr * 2.0)   # 0.25% ou 2×ATR
    if risk_actual < min_sl_dist:
        sl_final2 = (real_entry - min_sl_dist
                     if direction == "LONG"
                     else real_entry + min_sl_dist)
        sl_final2   = round_tick(sl_final2, info["tickSize"])
        risk_actual = abs(real_entry - sl_final2)
        sl_src2     = "MIN_0.25pct"
        log(
            f"  {symbol}: SL élargi → {sl_final2:.6f} "
            f"({risk_actual/real_entry*100:.3f}%) [{sl_src2}]",
            "WARN",
        )

    if risk_actual < 1e-9:
        log(f"  {symbol}: risque nul après exécution — fermeture propre", "WARN")
        place_order(symbol, close_side, "MARKET", qty_str, reduce_only=True)
        return None


    # ── SL : STOP_MARKET avec closePosition (fix -4120) ─────────────────
    # closePosition=True ferme toute la position — pas de quantity nécessaire.
    # Corrige le -4120 sur comptes Portfolio Margin / modes spéciaux.
    # Binance annule auto les TP reduce-only restants quand SL se déclenche.
    sl_ord = place_order(
        symbol, close_side, "STOP_MARKET", qty_str,
        stop_price=fmt_px(sl_final2, info["tickSize"]),
        close_position=True,
    )
    # ── SL exchange posé ? ──────────────────────────────────────
    sl_on_exchange = sl_ord is not None
    if not sl_on_exchange:
        # SL exchange échoué — on ne ferme PAS la position.
        # Le bot prend en charge la surveillance du SL en logiciel :
        # chaque cycle, monitor_all() compare le mark price au niveau SL
        # et ferme la position via ordre MARKET si le seuil est atteint.
        log(
            f"  {symbol}: ⚠️ SL exchange non posé → GESTION SL LOGICIELLE activée "
            f"(surveille {sl_final2:.6f})",
            "WARN",
        )
        tg_send(
            f"⚠️ <b>{symbol}</b> SL exchange non posé\n"
            f"🤖 <b>SL logiciel activé</b> — bot surveille {sl_final2:.6f} en continu\n"
            f"Clôture auto MARKET si price touche ce niveau."
        )

    # ── 3× TAKE_PROFIT_MARKET ─────────────────────────────────
    tp_records    = []
    remaining     = qty
    tp_placed_cnt = 0   # compte les TPs posés avec succès

    for i, tp_def in enumerate(TP_SPLIT):
        tp_price_raw = (real_entry + risk_actual * tp_def["r"]
                        if direction=="LONG"
                        else real_entry - risk_actual * tp_def["r"])
        tp_px_str    = fmt_px(round_tick(tp_price_raw, info["tickSize"]),
                              info["tickSize"])

        if i < len(TP_SPLIT) - 1:
            part_qty = round_step(qty * tp_def["pct"], info["stepSize"])
        else:
            part_qty = remaining
        part_qty  = max(part_qty, info["minQty"])
        remaining = max(0.0, round_step(remaining - part_qty, info["stepSize"]))

        tp_ord = place_order(
            symbol, close_side, "TAKE_PROFIT_MARKET",
            fmt_qty(part_qty, info["stepSize"]),
            stop_price=tp_px_str, reduce_only=True,
        )
        if tp_ord:
            tp_placed_cnt += 1
        else:
            log(f"  {symbol}: ⚠️ TP{i+1} non posé — gestion logicielle", "WARN")

        tp_records.append({
            "r"       : tp_def["r"],
            "pct"     : tp_def["pct"],
            "price"   : float(tp_px_str),
            "qty"     : part_qty,
            "hit"     : False,
            "order_id": tp_ord.get("orderId") if tp_ord else None,
        })

    # Si aucun TP posé sur l'exchange → gestion logicielle complète
    tp_managed = (tp_placed_cnt == 0)
    if tp_managed:
        log(
            f"  {symbol}: 🤖 TPs exchange échoués → GESTION TP LOGICIELLE activée "
            f"(TP1={tp_records[0]['price']:.6f}  TP2={tp_records[1]['price']:.6f}  "
            f"TP3={tp_records[2]['price']:.6f})",
            "WARN",
        )

    trade = {
        "symbol"       : symbol,
        "direction"    : direction,
        "entry"        : real_entry,
        "sl"           : sl_final2,
        "sl_source"    : sl_src2,
        "qty"          : qty,
        "tps"          : tp_records,
        "score"        : sig["score"],
        "crt_name"     : sig.get("crt_name", "–"),
        "fib_zone"     : sig.get("fib_zone", "–"),
        "reason"       : sig.get("reason", "–"),
        "vol_regime"   : vol_regime_str,
        "risk_usd"     : round(risk_usd, 4),
        "risk_pct"     : risk_pct,
        "open_time"    : time.time(),
        "pnl"          : 0.0,
        # SL/TP logiciel — True si les ordres exchange n'ont pas pu être posés
        "sl_managed"    : not sl_on_exchange,
        "tp_managed"    : tp_managed,
        "remaining_qty" : qty,   # quantité restante (décroît au fil des TPs logiciels)
        "close_side"    : close_side,
    }

    journal_open(trade, ss)
    tg_trade_open(trade, ss)
    return trade

# ═══════════════════════════════════════════════════════════════
#  🔍  SURVEILLANCE POSITIONS
# ═══════════════════════════════════════════════════════════════
def is_position_open(symbol: str) -> Tuple[bool, float]:
    positions = get_open_positions()
    for p in positions:
        if p["symbol"] == symbol:
            return True, float(p.get("unRealizedProfit", 0))
    return False, 0.0

def estimate_pnl(trade: dict) -> float:
    try:
        mk = get_mark_price(trade["symbol"])
        if not mk: return 0.0
        mark = float(mk.get("markPrice", trade["entry"]))
        if trade["direction"]=="LONG":
            return (mark - trade["entry"]) * trade["qty"]
        return (trade["entry"] - mark) * trade["qty"]
    except Exception:
        return 0.0

# ═══════════════════════════════════════════════════════════════
#  🔄  GESTIONNAIRE DE POSITIONS
# ═══════════════════════════════════════════════════════════════
class LivePositionManager:
    def __init__(self):
        self.positions  : Dict[str, dict] = {}
        self.last_close : Dict[str, float] = {}

    def count(self) -> int: return len(self.positions)

    def can_open(self, symbol: str, ss: SessionState) -> Tuple[bool, str]:
        if self.count() >= MAX_POSITIONS:
            return False, f"max {MAX_POSITIONS} positions"
        if symbol in self.positions:
            return False, "paire déjà ouverte"
        elapsed = (time.time() - self.last_close.get(symbol, 0)) / 60
        if elapsed < COOLDOWN_MIN:
            return False, f"cooldown {round(COOLDOWN_MIN-elapsed,1)}min"
        paused, reason = ss.check_pause()
        if paused:
            return False, f"pause: {reason}"
        return True, "OK"

    def open(self, symbol: str, trade: dict):
        self.positions[symbol] = trade

    def close(self, symbol: str, skip_cooldown: bool = False):
        """
        Ferme une position.
        skip_cooldown=True : pas de cooldown (clôture manuelle détectée).
        Le bot peut immédiatement re-scanner ce symbole.
        """
        self.positions.pop(symbol, None)
        if not skip_cooldown:
            self.last_close[symbol] = time.time()

    # ──────────────────────────────────────────────────────────
    @staticmethod
    def _check_software_tps(sym: str, trade: dict, mark_px: float):
        """
        Vérifie et exécute les TPs logiciels niveau par niveau.
        Modifie trade en place : hit=True, remaining_qty décrémenté.
        """
        d          = trade["direction"]
        close_side = trade.get("close_side", "SELL" if d == "LONG" else "BUY")
        info       = _sym_info.get(sym, {})
        step       = info.get("stepSize", 1.0)
        tick       = info.get("tickSize", 0.0001)

        for i, tp in enumerate(trade.get("tps", [])):
            if tp.get("hit"):
                continue
            tp_price = tp["price"]
            triggered = (
                (d == "LONG"  and mark_px >= tp_price) or
                (d == "SHORT" and mark_px <= tp_price)
            )
            if not triggered:
                break   # TPs ordonnés — si ce niveau non atteint, les suivants non plus

            part_qty = tp["qty"]
            part_str = fmt_qty(part_qty, step)
            close_ord = place_order(
                sym, close_side, "MARKET", part_str, reduce_only=True
            )
            if close_ord:
                tp["hit"] = True
                trade["remaining_qty"] = max(
                    0.0,
                    round_step(
                        trade.get("remaining_qty", trade["qty"]) - part_qty, step
                    ),
                )
                pnl_partial = (
                    (mark_px - trade["entry"]) * part_qty if d == "LONG"
                    else (trade["entry"] - mark_px) * part_qty
                )
                log(
                    f"  {sym}: ✅ TP{i+1} LOGICIEL @ {mark_px:.6f} "
                    f"(cible {tp_price:.6f}) +${pnl_partial:.4f}  "
                    f"restant={trade['remaining_qty']:.4f}",
                    "TRADE",
                )
                tg_send(
                    f"✅ <b>{sym} TP{i+1} LOGICIEL</b>\n"
                    f"Prix mark  : <code>{mark_px:.6f}</code>\n"
                    f"Cible TP   : <code>{tp_price:.6f}</code>\n"
                    f"Gain part. : <code>+${pnl_partial:.4f}</code>\n"
                    f"Qty restant: <code>{trade['remaining_qty']:.4f}</code>"
                )
            else:
                log(f"  {sym}: ⚠️ TP{i+1} logiciel clôture MARKET échouée — retry", "ERROR")

    def monitor_all(self, ss: SessionState):
        """
        Surveillance des positions ouvertes.
        1. SL logiciel : si le SL exchange n'a pas pu être posé,
           vérifie le mark price et ferme via MARKET si SL touché.
        2. Détection clôture Binance (TP hit, liquidation, etc.).
        """
        to_close = []

        for sym, trade in list(self.positions.items()):

            # ── 1. SL LOGICIEL — vérification mark price ──────────
            if trade.get("sl_managed"):
                mk      = get_mark_price(sym)
                mark_px = float(mk.get("markPrice", 0)) if mk else 0.0
                sl_lvl  = trade["sl"]
                d       = trade["direction"]
                triggered = (
                    (d == "LONG"  and mark_px > 0 and mark_px <= sl_lvl) or
                    (d == "SHORT" and mark_px > 0 and mark_px >= sl_lvl)
                )
                if triggered:
                    log(
                        f"  {sym}: 🛑 SL LOGICIEL déclenché "
                        f"mark={mark_px:.6f} SL={sl_lvl:.6f}",
                        "TRADE",
                    )
                    tg_send(
                        f"🛑 <b>{sym} SL LOGICIEL</b>\n"
                        f"Prix mark : <code>{mark_px:.6f}</code>\n"
                        f"Niveau SL : <code>{sl_lvl:.6f}</code>\n"
                        f"→ Clôture MARKET en cours..."
                    )
                    info     = _sym_info.get(sym, {})
                    qty_str  = fmt_qty(trade["qty"], info.get("stepSize", 1.0))
                    c_side   = trade.get("close_side",
                                         "SELL" if d == "LONG" else "BUY")
                    close_ord = place_order(
                        sym, c_side, "MARKET", qty_str, reduce_only=True
                    )
                    cancel_all_orders(sym)
                    if close_ord:
                        pnl = (mark_px - trade["entry"]) * trade["qty"] if d == "LONG"                               else (trade["entry"] - mark_px) * trade["qty"]
                        to_close.append((sym, pnl, "SL_LOGICIEL", False))
                    else:
                        log(f"  {sym}: ⚠️ Clôture SL logiciel échouée — retry prochain cycle", "ERROR")
                    continue   # ne pas vérifier aussi is_position_open ce cycle

                # Afficher status SL logiciel
                if mark_px > 0:
                    dist_pct = abs(mark_px - sl_lvl) / mark_px * 100
                    col      = grn if (
                        (d == "LONG" and mark_px > trade["entry"]) or
                        (d == "SHORT" and mark_px < trade["entry"])
                    ) else red
                    dur      = round((time.time() - trade.get("open_time", time.time())) / 60, 1)
                    log(
                        f"  {sym} 🤖SL mark={col(f'{mark_px:.6f}')} "
                        f"SL={sl_lvl:.6f} dist={dist_pct:.2f}% | {dur}min",
                        "INFO",
                    )
                # Vérifier aussi les TPs logiciels si nécessaire
                if trade.get("tp_managed") and mark_px > 0:
                    self._check_software_tps(sym, trade, mark_px)
                    if trade.get("remaining_qty", 1) <= info_step(sym):
                        pnl_est = estimate_pnl(trade)
                        to_close.append((sym, pnl_est, "TP_LOGICIEL_COMPLET", False))
                continue   # pas besoin de vérifier is_position_open — SL géré localement

            # ── 2. TPs logiciels seuls (SL sur exchange) ──────────
            if trade.get("tp_managed"):
                mk2     = get_mark_price(sym)
                mark_p2 = float(mk2.get("markPrice", 0)) if mk2 else 0.0
                if mark_p2 > 0:
                    self._check_software_tps(sym, trade, mark_p2)
                    if trade.get("remaining_qty", 1) <= info_step(sym):
                        # Tous TPs touchés → position fermée, annuler SL exchange
                        cancel_all_orders(sym)
                        pnl_est = estimate_pnl(trade)
                        to_close.append((sym, pnl_est, "TP_LOGICIEL_COMPLET", False))
                        continue

            # ── 3. SL sur exchange — détecter clôture Binance ─────
            open_, upnl = is_position_open(sym)
            if not open_:
                pnl = estimate_pnl(trade)
                # ── Détection clôture manuelle ────────────────────
                # Si la position est fermée MAIS le SL et les TPs
                # sont encore sur l'exchange → c'était une clôture
                # manuelle. On ne pénalise pas avec un cooldown.
                open_orders = get_open_orders(sym)
                has_pending_sl_tp = len(open_orders) > 0
                manual_close = has_pending_sl_tp   # ordres encore là = pas déclenché

                if manual_close:
                    reason_close = "MANUAL_CLOSE"
                    cancel_all_orders(sym)
                    log(
                        f"{sym} CLÔTURÉ MANUELLEMENT | "
                        f"Ordres annulés | Pas de cooldown → re-scan immédiat",
                        "TRADE",
                    )
                    tg_send(
                        f"✋ <b>{sym} CLÔTURE MANUELLE détectée</b>\n"
                        f"Ordres SL/TP annulés automatiquement.\n"
                        f"🔍 Le bot continue de scanner ce symbole sans délai."
                    )
                else:
                    reason_close = "BINANCE_CLOSED"

                to_close.append((sym, pnl, reason_close, manual_close))
                result = "WIN" if pnl >= 0 else "LOSS"
                log(f"{sym} CLÔTURÉ | PnL≈${pnl:.4f} | {result}", "TRADE")
            else:
                col = grn if upnl >= 0 else red
                dur = round((time.time() - trade.get("open_time", time.time())) / 60, 1)
                log(f"  {sym} OPEN | uPnL: {col(f'${upnl:.4f}')} | {dur}min", "INFO")

        for sym, pnl, reason, is_manual in to_close:
            trade = self.positions.get(sym, {})

            # ── Annuler tous les ordres exchange ouverts ──────────
            # (déjà annulés si manual_close, mais on sécurise)
            cancel_all_orders(sym)

            journal_close(trade, pnl, reason)

            # Calcul R réalisé
            r_dist = abs(trade.get("entry", 0) - trade.get("sl", 0))
            r_real = round(abs(pnl) / (r_dist * trade.get("qty", 1)), 2) if r_dist > 0 else 0
            direction = trade.get("direction", "")

            if pnl >= 0:
                ss.record_win(pnl, direction=direction, rr=r_real)
            else:
                ss.record_loss(pnl, direction=direction, rr=-r_real)
            ss.current_balance = get_balance_usdt()

            tg_trade_close(trade, pnl, reason, ss)

            paused, reason_p = ss.check_pause()
            if paused and ss.consecutive_sl >= MAX_CONSEC_SL:
                log(f"⏸️  PAUSE — {reason_p}", "PAUSE")
                tg_pause(reason_p, ss)

            # Clôture manuelle → pas de cooldown (re-scan immédiat)
            self.close(sym, skip_cooldown=is_manual)

    def reconcile(self, ss: "SessionState"):
        """
        Adopte les positions ouvertes hors-bot (ouvertes manuellement
        ou lors d'un redémarrage).

        Pour chaque position trouvée :
          1. Analyse le marché (klines → ATR, structure)
          2. Calcule un SL structurel et 3 TPs réalistes
          3. Vérifie si des ordres SL/TP existent déjà sur l'exchange
          4. Pose SL + TP manquants (exchange ou logiciel en fallback)
          5. Enregistre la position dans le gestionnaire pour surveillance
        """
        for p in get_open_positions():
            sym = p["symbol"]

            if sym not in SYMBOLS or sym in self.positions:
                continue

            pos_amt   = float(p.get("positionAmt", 0))
            direction = "LONG" if pos_amt > 0 else "SHORT"
            qty       = abs(pos_amt)
            entry     = float(p.get("entryPrice", 0))
            close_side = "SELL" if direction == "LONG" else "BUY"

            if qty <= 0 or entry <= 0:
                continue

            log(f"📌 Position adoptée : {sym} {direction} qty={qty} @ {entry}", "WARN")

            # ── Infos symbole ─────────────────────────────────────
            info = _sym_info.get(sym)
            if not info:
                log(f"  {sym}: infos symbole absentes — adoption annulée", "WARN")
                continue

            qty_str = fmt_qty(qty, info["stepSize"])

            # ── Analyse marché ────────────────────────────────────
            parsed = fetch_klines_parsed(sym)
            if not parsed:
                log(f"  {sym}: klines indisponibles — SL logiciel uniquement", "WARN")
                atr       = entry * 0.003   # fallback 0.3%
                sl_calc   = (entry - atr * 2 if direction == "LONG"
                             else entry + atr * 2)
                sl_source = "ATR_FALLBACK"
                highs, lows = None, None
            else:
                _, opens, highs, lows, closes = parsed
                atr       = calc_atr(highs, lows, closes)
                sl_calc, sl_source = structural_sl(
                    highs, lows, direction, entry, atr
                )

            # ── SL minimum 0.25% / 2×ATR ─────────────────────────
            min_dist = max(entry * 0.0025, atr * 2.0)
            if abs(entry - sl_calc) < min_dist:
                sl_calc   = (entry - min_dist if direction == "LONG"
                             else entry + min_dist)
                sl_source = "MIN_0.25pct"

            sl_calc = round_tick(sl_calc, info["tickSize"])

            # ── SL du côté correct ? ──────────────────────────────
            if direction == "LONG"  and sl_calc >= entry:
                sl_calc = round_tick(entry - min_dist, info["tickSize"])
                sl_source = "FORCE_LONG"
            if direction == "SHORT" and sl_calc <= entry:
                sl_calc = round_tick(entry + min_dist, info["tickSize"])
                sl_source = "FORCE_SHORT"

            risk_actual = abs(entry - sl_calc)

            # ── Ordres déjà posés ? ───────────────────────────────
            existing_orders = get_open_orders(sym)
            has_sl = any(
                o.get("type") in ("STOP_MARKET", "STOP")
                for o in existing_orders
            )
            has_tp = any(
                o.get("type") in ("TAKE_PROFIT_MARKET", "TAKE_PROFIT")
                for o in existing_orders
            )

            # ── Poser SL si manquant ──────────────────────────────
            sl_on_exchange = has_sl
            if not has_sl:
                sl_px  = fmt_px(sl_calc, info["tickSize"])
                sl_ord = place_order(
                    sym, close_side, "STOP_MARKET", qty_str,
                    stop_price=sl_px, close_position=True,
                )
                sl_on_exchange = sl_ord is not None
                if sl_on_exchange:
                    log(f"  {sym}: ✅ SL posé @ {sl_px} [{sl_source}]", "TRADE")
                else:
                    log(f"  {sym}: ⚠️ SL exchange échoué → SL logiciel activé", "WARN")

            # ── Poser TPs si manquants ────────────────────────────
            tp_records = []
            remaining  = qty

            if not has_tp:
                for i, tp_def in enumerate(TP_SPLIT):
                    tp_raw = (entry + risk_actual * tp_def["r"]
                              if direction == "LONG"
                              else entry - risk_actual * tp_def["r"])
                    tp_px  = fmt_px(round_tick(tp_raw, info["tickSize"]),
                                    info["tickSize"])

                    part_qty = (round_step(qty * tp_def["pct"], info["stepSize"])
                                if i < len(TP_SPLIT) - 1 else remaining)
                    part_qty  = max(part_qty, info["minQty"])
                    remaining = max(0.0,
                                    round_step(remaining - part_qty,
                                               info["stepSize"]))

                    tp_ord = place_order(
                        sym, close_side, "TAKE_PROFIT_MARKET",
                        fmt_qty(part_qty, info["stepSize"]),
                        stop_price=tp_px, reduce_only=True,
                    )
                    if tp_ord:
                        log(f"  {sym}: ✅ TP{i+1} posé @ {tp_px}", "TRADE")
                    else:
                        log(f"  {sym}: ⚠️ TP{i+1} non posé", "WARN")

                    tp_records.append({
                        "r"       : tp_def["r"],
                        "pct"     : tp_def["pct"],
                        "price"   : float(tp_px),
                        "qty"     : part_qty,
                        "hit"     : False,
                        "order_id": tp_ord.get("orderId") if tp_ord else None,
                    })
            else:
                # TPs déjà présents — on les lit depuis l'exchange
                log(f"  {sym}: TPs déjà présents sur l'exchange", "INFO")
                for i, tp_def in enumerate(TP_SPLIT):
                    tp_raw = (entry + risk_actual * tp_def["r"]
                              if direction == "LONG"
                              else entry - risk_actual * tp_def["r"])
                    tp_records.append({
                        "r"    : tp_def["r"],
                        "pct"  : tp_def["pct"],
                        "price": round_tick(tp_raw, info["tickSize"]),
                        "qty"  : round_step(qty * tp_def["pct"], info["stepSize"]),
                        "hit"  : False,
                    })

            # ── Construire le dict trade ──────────────────────────
            mk        = get_mark_price(sym)
            mark_now  = float(mk.get("markPrice", entry)) if mk else entry
            upnl      = ((mark_now - entry) * qty if direction == "LONG"
                         else (entry - mark_now) * qty)

            trade = {
                "symbol"      : sym,
                "direction"   : direction,
                "entry"       : entry,
                "sl"          : sl_calc,
                "sl_source"   : sl_source,
                "qty"         : qty,
                "tps"         : tp_records,
                "score"       : 0,           # score inconnu (position externe)
                "crt_name"    : "EXTERNE",
                "fib_zone"    : "–",
                "reason"      : "Position adoptée au démarrage",
                "vol_regime"  : "–",
                "risk_usd"    : round(risk_actual * qty, 4),
                "risk_pct"    : 0.0,
                "open_time"   : time.time(),
                "pnl"         : round(upnl, 4),
                "sl_managed"   : not sl_on_exchange,
                "tp_managed"   : (len([t for t in tp_records if t.get("order_id")]) == 0),
                "remaining_qty": qty,
                "close_side"   : close_side,
                "adopted"      : True,       # flag : position adoptée (pas ouverte par le bot)
            }

            self.open(sym, trade)
            journal_open(trade, ss)

            # ── Rapport Telegram ──────────────────────────────────
            tp_lines = "".join(
                f"  TP{i+1} <code>{t['price']:.6f}</code>  @{t['r']}R\n"
                for i, t in enumerate(tp_records)
            )
            sl_mode = "🟢 Exchange" if sl_on_exchange else "🤖 Logiciel"

            tg_send(
                f"📌 <b>POSITION ADOPTÉE — {sym} {direction}</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━━━\n"
                f"🎯 Entrée    : <code>{entry:.6f}</code>\n"
                f"🛑 SL        : <code>{sl_calc:.6f}</code>  [{sl_source}]  {sl_mode}\n"
                f"━━━━━━━━━━━━━━━━━━━━━━\n"
                f"{tp_lines}"
                f"━━━━━━━━━━━━━━━━━━━━━━\n"
                f"📦 Qty       : <code>{qty}</code>\n"
                f"💹 uPnL      : <code>${upnl:+.4f}</code>\n"
                f"🤖 Gestion   : SL {sl_mode} | bot surveille en continu"
            )

            log(
                f"  ✅ {sym} {direction} adopté | "
                f"SL={sl_calc:.6f}[{sl_source}] "
                f"TP1={tp_records[0]['price']:.6f} "
                f"uPnL=${upnl:+.4f} "
                f"SL={'exchange' if sl_on_exchange else 'logiciel'}",
                "TRADE",
            )

# ═══════════════════════════════════════════════════════════════
#  🔭  SCANNER MULTI-MARCHÉS v3.0 — RANKING PAR SCORE
# ═══════════════════════════════════════════════════════════════
def scan_and_rank_symbols(
    pm: "LivePositionManager",
    ss: "SessionState",
) -> List[dict]:
    """
    Scanne les 21 marchés du pool et retourne une liste triée
    par score décroissant. Seuls les marchés avec signal valide
    et non exclus (cooldown, déjà ouvert, vol HIGH après SL)
    sont inclus.

    Retourne une liste de dicts :
    {
      "symbol"   : str,
      "sig"      : dict,          # résultat get_signal()
      "atr"      : float,
      "regime"   : str,           # "LOW" | "NORMAL" | "HIGH"
      "score"    : int,
      "skip_reason": str | None,  # raison d'exclusion si skippé
    }
    """
    results  : List[dict] = []
    skipped  : List[dict] = []

    log(f"🔭 Scan {len(SYMBOLS)} marchés...", "INFO")

    # ── Récupérer la tendance BTC une fois pour tout le cycle ─
    btc_trend = get_btc_trend()
    if BTC_CORRELATION:
        log(f"  📈 BTC tendance cycle: {btc_trend}", "INFO")

    for symbol in SYMBOLS:
        # ── Pré-filtres rapides (sans fetch) ──────────────────
        can, reason = pm.can_open(symbol, ss)
        if not can:
            skipped.append({"symbol": symbol, "skip_reason": reason})
            continue

        # ── Fetch klines ──────────────────────────────────────
        data = fetch_klines_parsed(symbol)
        if not data:
            skipped.append({"symbol": symbol,
                            "skip_reason": "fetch échoué"})
            continue

        _, opens, highs, lows, closes = data
        regime, atr_pct, thresh = vol_regime(highs, lows, closes)
        atr = calc_atr(highs, lows, closes)

        # ── Filtre vol HIGH après SL consécutif ───────────────
        if regime == "HIGH" and ss.consecutive_sl > 0:
            skipped.append({"symbol": symbol,
                            "skip_reason": f"vol HIGH + {ss.consecutive_sl} SL récent"})
            continue

        # ── Signal ────────────────────────────────────────────
        sig = get_signal(opens, highs, lows, closes, thresh)
        if not sig:
            skipped.append({"symbol": symbol,
                            "skip_reason": f"pas de signal [{regime}]"})
            continue

        # ── Filtre corrélation BTC ─────────────────────────────
        # On n'entre QUE si BTC confirme la direction (ou BTC neutre)
        # Exception : score élite (≥ TREND_MIN_SCORE_OVERRIDE)
        if (BTC_CORRELATION
                and btc_trend != "NEUTRE"
                and btc_trend != sig["direction"]
                and sig["score"] < TREND_MIN_SCORE_OVERRIDE):
            skipped.append({"symbol": symbol,
                            "skip_reason": f"BTC {btc_trend} ≠ signal {sig['direction']}"})
            log(
                f"  ⚡ {symbol}: signal {sig['direction']} rejeté "
                f"(BTC={btc_trend}, score={sig['score']})",
                "INFO",
            )
            continue

        results.append({
            "symbol" : symbol,
            "sig"    : sig,
            "atr"    : atr,
            "regime" : regime,
            "score"  : sig["score"],
            "highs"  : highs,   # pour SL structurel dans open_trade
            "lows"   : lows,
        })

        log(
            f"  ✅ {symbol:12s} {sig['direction']:5s} "
            f"Score:{sig['score']}/{SCORE_MAX} "
            f"Rejet:{sig['crt_name']:15s} "
            f"FVG:{'✅' if sig.get('fvg_ok') else '✖'}  "
            f"OB:{'✅' if sig.get('ob_ok') else '✖'}  "
            f"Sweep:{'✅' if sig.get('sweep_ok') else '✖'}  "
            f"Trend:{sig.get('struct_trend','?')}  "
            f"{sig.get('force_atr','?')}×ATR  "
            f"Fib:{sig['fib_zone']} [{regime}]",
            "TRADE",
        )

        time.sleep(0.3)   # anti-rate-limit léger entre fetches

    # ── Résumé console ────────────────────────────────────────
    log(
        f"  Résultat scan : {len(results)} signal(s) sur {len(SYMBOLS)} marchés "
        f"({len(skipped)} ignorés)",
        "INFO",
    )
    for sk in skipped:
        log(f"    ⏭  {sk['symbol']:12s} → {sk['skip_reason']}", "INFO")

    # ── Tri par score décroissant, puis TOP_N ─────────────────
    results.sort(key=lambda x: x["score"], reverse=True)
    top_n = results[:TOP_N_SYMBOLS]

    if top_n:
        log("  🏆 Classement (top):", "INFO")
        for i, r in enumerate(top_n, 1):
            log(
                f"    #{i} {r['symbol']:12s} Score:{r['score']} "
                f"[{r['regime']}] {r['sig']['direction']}",
                "INFO",
            )

    return top_n


def tg_scan_summary(ranked: List[dict], total: int):
    """Résumé scan Telegram — format v4 avec détails stratégie."""
    if not ranked:
        tg_send(
            f"🔭 <b>Scan {total} paires</b> — Aucun signal valide.\n"
            f"<i>Attente: impulse + retracement 50% + FVG + rejet</i>"
        )
        return
    lines = ""
    for i, r in enumerate(ranked):
        sig    = r["sig"]
        entry  = sig["entry"]
        sl_raw = sig["sl_raw"]
        sl_pct = round(abs(entry - sl_raw) / entry * 100, 3)
        tp1    = sig["tps"][0]["price"] if sig["tps"] else 0
        rr1    = round(abs(tp1 - entry) / abs(entry - sl_raw), 2) if abs(entry - sl_raw) > 0 else 0
        fvg_str  = f"FVG✅{sig.get('imb_fill',0)*100:.0f}%" if sig.get('fvg_ok') else "FVG✖"
        ob_str   = "OB✅" if sig.get('ob_ok') else "OB✖"
        sw_str   = "Sweep✅" if sig.get('sweep_ok') else ""
        trnd_str = f"Trend:{sig.get('struct_trend','?')}"
        lines += (
            f"\n#{i+1} <b>{r['symbol']}</b> — {sig['direction']} "
            f"Score:<b>{r['score']}/{SCORE_MAX}</b> [{r['regime']}]\n"
            f"   Entrée: <code>{entry:.5f}</code>  "
            f"SL: <code>{sl_raw:.5f}</code> ({sl_pct}%)\n"
            f"   TP1: <code>{tp1:.5f}</code>  R:R≈1:{rr1}\n"
            f"   {fvg_str}  {ob_str}  {sw_str}  "
            f"Rejet:{sig['crt_name']}  Fib:{sig['fib_zone']}  {trnd_str}\n"
            f"   Impulse: {sig.get('force_atr','?')}×ATR  "
            f"SwingH:{sig.get('swing_high',0):.5f}  SwingL:{sig.get('swing_low',0):.5f}\n"
        )
    tg_send(
        f"🔭 <b>Scan {total} marchés — {len(ranked)} signal(s) ICT</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━"
        f"{lines}"
    )


def tg_micro_account_alert(balance: float):
    """Alerte Telegram au démarrage si compte micro (<$10)."""
    eff_lev    = get_effective_leverage(balance)
    eff_margin = get_effective_margin_pct(balance)
    max_not    = balance * eff_margin * eff_lev
    _tg_raw(
        f"<b>🔬 MODE MICRO COMPTE ACTIVÉ</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"💰 Balance départ   : <code>${balance:.2f}</code> USDT\n"
        f"⚙️ Levier adaptatif : <b>{eff_lev}x</b> (ISOLATED)\n"
        f"🔐 Marge max/trade  : {eff_margin*100:.0f}%  →  <code>${balance*eff_margin:.2f}</code>\n"
        f"💵 Notionnel max    : <code>${max_not:.2f}</code>  (ok si ≥ $5)\n"
        f"📍 Max positions    : 1 (micro mode)\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"⚡ Le SL dynamique (SwingLow/High + ATR) protège le capital.\n"
        f"📈 Levier réduit automatiquement au fil de la croissance.\n"
        f"<i>🚀 Objectif : faire croître ${balance:.2f} en toute sécurité !</i>"
    )


# ═══════════════════════════════════════════════════════════════
#  📊  DASHBOARD CONSOLE
# ═══════════════════════════════════════════════════════════════
def print_dashboard(pm: "LivePositionManager", ss: SessionState, cycle: int):
    now      = datetime.now().strftime("%H:%M:%S")
    risk_pct = ss.adaptive_risk_pct(score=5) * 100
    pnl_col  = grn if ss.session_pnl >= 0 else red
    paused, pause_reason = ss.check_pause()
    pause_str = f" | {mag('PAUSE: '+pause_reason[:30])}" if paused else ""

    print(f"\n{sep('═')}")
    print(
        f"  {cyn(bld(f'CYCLE #{cycle}  {now}'))}  "
        f"Pos:{yel(str(pm.count()))}/{MAX_POSITIONS}  "
        f"Balance:{grn(f'${ss.current_balance:.2f}')}  "
        f"PnL:{pnl_col(f'${ss.session_pnl:+.4f}')}  "
        f"WR:{yel(f'{ss.win_rate}%')}  "
        f"Risk:{mag(f'{risk_pct:.1f}%')}"
        f"{pause_str}"
    )
    print(
        f"  Bilan: {grn(str(ss.wins))}W/{red(str(ss.losses))}L  "
        f"SL consec:{red(str(ss.consecutive_sl))}/{MAX_CONSEC_SL}  "
        f"Durée:{ss.session_duration()}  "
        f"Capital×:{yel(f'{ss.session_gain_mult:.2f}x')}"
    )
    print(sep('═'))

    if pm.positions:
        print(f"  {yel('POSITIONS ACTIVES :')}")
        for sym, t in pm.positions.items():
            mk_data = get_mark_price(sym)
            mark    = float(mk_data.get("markPrice", t["entry"])) if mk_data else t["entry"]
            upnl    = ((mark-t["entry"])*t["qty"] if t["direction"]=="LONG"
                       else (t["entry"]-mark)*t["qty"])
            col     = grn if upnl>=0 else red
            dur     = round((time.time()-t.get("open_time",time.time()))/60, 1)
            print(
                f"  [{yel(sym)}] {t['direction']}  "
                f"Entry:{t['entry']:.6f}  Mark:{mark:.6f}  "
                f"SL:{t['sl']:.6f}[{t.get('sl_source','–')}]  "
                f"uPnL:{col(f'${upnl:.4f}')}  {dur}min"
            )

# ═══════════════════════════════════════════════════════════════
#  🚀  BOUCLE PRINCIPALE
# ═══════════════════════════════════════════════════════════════
def main():
    print(cyn(bld("""
╔═══════════════════════════════════════════════════════════════╗
║   ALPHABOT FUTURES v4.0 — STRATÉGIE ICT PURE               ║
║   Impulse → 50% Retrace → FVG/OB → Rejet → Entrée          ║
╚═══════════════════════════════════════════════════════════════╝""")))

    # ── Vérif clés API ────────────────────────────────────────
    if not API_KEY or not API_SECRET or "COLLE" in (API_KEY or ""):
        log("⛔ API_KEY non renseignée. Configure les variables d'environnement et relance.", "ERROR")
        log("   export BINANCE_KEY='ta_clé'", "ERROR")
        log("   export BINANCE_SECRET='ton_secret'", "ERROR")
        return

    # ── Synchronisation horloge Binance (fix -1022) ───────────
    sync_server_time()

    # ── Initialisation ────────────────────────────────────────
    log("Chargement exchange info...", "INFO")
    if not load_symbol_info(): return

    balance = get_balance_usdt()
    if balance <= 0:
        log("Balance USDT = 0 ou clé API invalide.", "ERROR"); return
    if balance < MIN_BALANCE_USD:
        log(f"Balance ${balance:.2f} < seuil ${MIN_BALANCE_USD}.", "ERROR"); return

    log(f"💰 Balance: ${balance:.2f} USDT", "INFO")

    # ── Session state ─────────────────────────────────────────
    ss          = SessionState(start_balance=balance)
    ss.current_balance = balance

    # ── Telegram ─────────────────────────────────────────────
    tg_check()
    tg_startup(ss)
    if is_micro_account(balance):
        tg_micro_account_alert(balance)

    pm    = LivePositionManager()
    pm.reconcile(ss)   # adopte les positions existantes + pose SL/TP manquants

    cycle         = 0
    was_paused    = False

    # ── Boucle ───────────────────────────────────────────────
    while True:
        cycle += 1

        # Refresh balance
        bal = get_balance_usdt()
        if bal > 0: ss.current_balance = bal

        # ── Heartbeat log (toujours visible dans Render) ──────
        log(
            f"[CYCLE {cycle}] Balance=${ss.current_balance:.2f} "
            f"| Positions={pm.count()} "
            f"| {ss.wins}W/{ss.losses}L "
            f"| PnL=${ss.session_pnl:+.4f} "
            f"| SLconsec={ss.consecutive_sl}/{MAX_CONSEC_SL} "
            f"| Duree={ss.session_duration()}",
            "INFO"
        )

        print_dashboard(pm, ss, cycle)

        # ── Arrêt si balance sous le seuil ───────────────────
        if ss.current_balance < MIN_BALANCE_USD:
            log(f"⛔ Balance ${ss.current_balance:.2f} < ${MIN_BALANCE_USD}. Arrêt.", "ERROR")
            tg_send(f"⛔ Balance trop faible (${ss.current_balance:.4f}). Bot arrêté.\nSeuil minimum : ${MIN_BALANCE_USD}")
            break

        # ── Vérif pause ───────────────────────────────────────
        paused, pause_reason = ss.check_pause()
        if paused:
            if not was_paused:
                log(f"⏸️  PAUSE: {pause_reason}", "PAUSE")
            was_paused = True
            log(f"  En pause ({pause_reason}). Surveillance positions...", "PAUSE")
            if pm.positions:
                pm.monitor_all(ss)
            time.sleep(SCAN_INTERVAL_SEC)
            continue
        else:
            if was_paused:
                log("▶️  Reprise du bot", "INFO")
                tg_resume(ss)
                was_paused = False

        # ── 1. Surveiller positions ouvertes ──────────────────
        if pm.positions:
            pm.monitor_all(ss)
            bal = get_balance_usdt()
            if bal > 0: ss.current_balance = bal

        # ── 3. Scan et ranking multi-marchés ─────────────────
        max_pos = adaptive_max_positions(ss.current_balance)
        if pm.count() < max_pos:
            log(
                f"Scan pool {len(SYMBOLS)} marchés → top {TOP_N_SYMBOLS} "
                f"(risk={ss.adaptive_risk_pct(score=5)*100:.1f}% | maxPos={max_pos})",
                "INFO",
            )

            ranked = scan_and_rank_symbols(pm, ss)

            # Résumé TG scan (1 fois toutes les TG_SUMMARY_CYCLES)
            if cycle - ss.last_summary_cycle >= TG_SUMMARY_CYCLES:
                tg_scan_summary(ranked, len(SYMBOLS))
                tg_hourly_summary(ss, pm.positions)
                ss.last_summary_cycle = cycle

            # ── Ouvrir trades sur les meilleures paires ───────
            # Mode Sniper : vérif cooldown global 1 trade/heure
            sniper_ok, sniper_reason = ss.sniper_can_trade()
            if not sniper_ok:
                log(f"  🎯 Sniper: {sniper_reason} → attente", "INFO")
            else:
                # Filtre score sniper (plus strict que normal)
                if SNIPER_MODE:
                    ranked = [r for r in ranked
                              if r["score"] >= SNIPER_MIN_SCORE]
                    if ranked:
                        log(f"  🎯 Sniper: meilleur signal → {ranked[0]['symbol']} "
                            f"Score:{ranked[0]['score']}", "INFO")
                    else:
                        log(f"  🎯 Sniper: aucun signal ≥ {SNIPER_MIN_SCORE} → skip", "INFO")

                for candidate in ranked:
                    if pm.count() >= max_pos:
                        break

                    symbol = candidate["symbol"]
                    sig    = candidate["sig"]
                    atr    = candidate["atr"]
                    regime = candidate["regime"]
                    highs  = candidate.get("highs")
                    lows   = candidate.get("lows")

                    can, reason = pm.can_open(symbol, ss)
                    if not can:
                        log(f"  {symbol}: skip post-scan ({reason})", "INFO")
                        continue

                    log(
                        f"  {symbol}: TRADE {sig['direction']} "
                        f"Score:{sig['score']}/{SCORE_MAX} "
                        f"Rejet:{sig['crt_name']} "
                        f"FVG:{'✅' if sig.get('fvg_ok') else '✖'} "
                        f"OB:{'✅' if sig.get('ob_ok') else '✖'} "
                        f"Sweep:{'✅' if sig.get('sweep_ok') else '✖'} "
                        f"Trend:{sig.get('struct_trend','?')} "
                        f"{sig.get('force_atr','?')}×ATR [{regime}]",
                        "TRADE",
                    )

                    trade = open_trade(symbol, sig, ss, atr, regime,
                                       highs=highs, lows=lows)
                    if trade:
                        pm.open(symbol, trade)
                        ss.current_balance = get_balance_usdt()
                        ss.sniper_record_trade()   # enregistre timestamp sniper
                        log(f"  ✅ {symbol}: ouvert. Balance: ${ss.current_balance:.2f}", "TRADE")
                    else:
                        log(f"  ❌ {symbol}: ouverture échouée", "WARN")

                    time.sleep(2)
                    # Mode sniper : 1 seul trade par cycle
                    if SNIPER_MODE:
                        break

        else:
            log(f"Max positions ({max_pos}) atteint. Surveillance uniquement.", "INFO")
            # Résumé TG horaire même sans nouvelles positions
            if cycle - ss.last_summary_cycle >= TG_SUMMARY_CYCLES:
                tg_hourly_summary(ss, pm.positions)
                ss.last_summary_cycle = cycle

        log(f"Prochain cycle dans {SCAN_INTERVAL_SEC}s...", "INFO")
        time.sleep(SCAN_INTERVAL_SEC)


# ═══════════════════════════════════════════════════════════════
#  🌐  FLASK KEEPALIVE — VPS / Render / Railway
#  Flask tourne sur le thread PRINCIPAL (visible par Render).
#  Le bot tourne dans un thread daemon séparé.
# ═══════════════════════════════════════════════════════════════
import threading
import traceback

try:
    from flask import Flask, jsonify
    _flask_ok = True
except ImportError:
    _flask_ok = False

_bot_status = {"running": False, "cycle": 0, "started_at": None, "error": None}

if _flask_ok:
    _app = Flask(__name__)

    @_app.route("/")
    def index():
        return jsonify({
            "bot"       : "AlphaBot Futures v4.0",
            "status"    : "running" if _bot_status["running"] else "stopped",
            "cycle"     : _bot_status["cycle"],
            "started_at": _bot_status["started_at"],
            "error"     : _bot_status["error"],
            "symbols"   : len(SYMBOLS),
            "top_n"     : TOP_N_SYMBOLS,
        })

    @_app.route("/health")
    def health():
        return "OK", 200

# ── Bot loop — tourne dans un thread daemon ────────────────────
def _run_bot():
    _bot_status["running"]    = True
    _bot_status["started_at"] = datetime.now().isoformat()
    try:
        main()
    except KeyboardInterrupt:
        pass
    except Exception as e:
        tb = traceback.format_exc()
        _bot_status["error"] = str(e)
        log(f"ERREUR CRITIQUE: {e}", "ERROR")
        log(tb, "ERROR")
        # Envoie le traceback complet sur Telegram (tronqué à 3800 chars)
        tg_send(
            f"🚨 <b>AlphaBot v4.0 CRASH</b>\n"
            f"<code>{tb[-3800:]}</code>"
        )
    finally:
        _bot_status["running"] = False

_bot_thread = threading.Thread(target=_run_bot, daemon=True)
_bot_thread.start()

# ── Flask (ou HTTP minimal) sur le thread PRINCIPAL ───────────
# Render détecte le port dans les 90 premières secondes.
# Flask DOIT être sur le thread principal pour que Render le voie.
port = int(os.environ.get("PORT", 10000))

if _flask_ok:
    log(f"🌐 Flask démarré sur port {port}", "INFO")
    _app.run(host="0.0.0.0", port=port, use_reloader=False, threaded=True)
else:
    import http.server, socketserver
    class _H(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"AlphaBot OK")
        def log_message(self, *a): pass
    log(f"🌐 HTTP minimal démarré sur port {port}", "INFO")
    with socketserver.TCPServer(("0.0.0.0", port), _H) as httpd:
        httpd.serve_forever()


