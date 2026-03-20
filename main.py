
"""
╔══════════════════════════════════════════════════════════════╗
║   ALPHABOT v13 — FICHIER UNIQUE CORRIGÉ                    ║
║   + Fraîcheur données (max 15min)                           ║
║   + Expiration entrée dans le signal                        ║
║   + Mes Signaux = signaux réels du jour                     ║
║   + Parrainage = texte prêt à copier                        ║
║   + Groupe VIP → Rapports perf                              ║
║   + Fix doublon TOP PARRAINS                                ║
║   + [NEW] FVG / Fair Value Gap detection                    ║
║   + [NEW] BOS Pur / Continuation propre                     ║
╚══════════════════════════════════════════════════════════════╝
"""

import json, ssl, time, sqlite3, threading, urllib.request, urllib.parse, urllib.error
from datetime import datetime, timedelta, timezone
from queue    import Queue, Empty


# ═══════════════════════════════════════════════════════════════
#  ① CONFIG
# ═══════════════════════════════════════════════════════════════
BOT_TOKEN    = "6950706659:AAGXw-27ebhWLm2HfG7lzC7EckpwCPS_JFg"
BOT_USERNAME = "AlphaBotForexBot"
CHANNEL_ID   = "-1003757467015"
ADMIN_ID     = 6982051442

USDT_ADDRESS = "TJuPBihvzgb6ffGLw4WnqC33Av38kwU7XE"
BROKER_LINK  = "https://one.exnessonelink.com/a/nb3fx0bpnm"

PRO_PRICE    = 20
PRO_PROMO    = 10
REF_TARGET   = 30
REF_MONTHS   = 3
FREE_LIMIT   = 2
PRO_LIMIT    = 10
NB_AGENTS    = 20

SCAN_SEC     = 60
DAILY_HOUR   = 20
WEEKLY_DAY   = 6
WEEKLY_HOUR  = 21
DB_FILE      = "alphabot.db"

# Fraîcheur max des données Yahoo (en minutes)
DATA_MAX_AGE_MIN = 20

MARKETS = [
    # ── Métaux ───────────────────────────────────────────────
    {"sym":"GC=F",     "name":"XAUUSD","cat":"METALS", "pip":0.01,   "max_sp":70, "vol":5,"crypto":False},
    {"sym":"SI=F",     "name":"XAGUSD","cat":"METALS", "pip":0.001,  "max_sp":10, "vol":4,"crypto":False},
    {"sym":"PL=F",     "name":"XPTUSD","cat":"METALS", "pip":0.01,   "max_sp":20, "vol":3,"crypto":False},

    # ── Crypto : BTC uniquement ───────────────────────────────
    {"sym":"BTC-USD",  "name":"BTCUSD","cat":"CRYPTO", "pip":1.0,    "max_sp":100,"vol":5,"crypto":True},

    # ── Forex — 12 paires ─────────────────────────────────────
    {"sym":"EURUSD=X", "name":"EURUSD","cat":"FOREX",  "pip":0.0001, "max_sp":2,  "vol":5,"crypto":False},
    {"sym":"GBPUSD=X", "name":"GBPUSD","cat":"FOREX",  "pip":0.0001, "max_sp":3,  "vol":5,"crypto":False},
    {"sym":"USDJPY=X", "name":"USDJPY","cat":"FOREX",  "pip":0.01,   "max_sp":3,  "vol":5,"crypto":False},
    {"sym":"GBPJPY=X", "name":"GBPJPY","cat":"FOREX",  "pip":0.01,   "max_sp":6,  "vol":5,"crypto":False},
    {"sym":"EURJPY=X", "name":"EURJPY","cat":"FOREX",  "pip":0.01,   "max_sp":5,  "vol":4,"crypto":False},
    {"sym":"AUDUSD=X", "name":"AUDUSD","cat":"FOREX",  "pip":0.0001, "max_sp":3,  "vol":4,"crypto":False},
    {"sym":"AUDJPY=X", "name":"AUDJPY","cat":"FOREX",  "pip":0.01,   "max_sp":5,  "vol":4,"crypto":False},
    {"sym":"CADJPY=X", "name":"CADJPY","cat":"FOREX",  "pip":0.01,   "max_sp":5,  "vol":4,"crypto":False},
    {"sym":"CHFJPY=X", "name":"CHFJPY","cat":"FOREX",  "pip":0.01,   "max_sp":5,  "vol":4,"crypto":False},
    {"sym":"USDCHF=X", "name":"USDCHF","cat":"FOREX",  "pip":0.0001, "max_sp":3,  "vol":4,"crypto":False},
    {"sym":"NZDUSD=X", "name":"NZDUSD","cat":"FOREX",  "pip":0.0001, "max_sp":3,  "vol":3,"crypto":False},
    {"sym":"USDCAD=X", "name":"USDCAD","cat":"FOREX",  "pip":0.0001, "max_sp":3,  "vol":4,"crypto":False},

    # ── Indices US ────────────────────────────────────────────
    {"sym":"NQ=F",     "name":"NAS100","cat":"INDICES","pip":0.25,   "max_sp":5,  "vol":5,"crypto":False},
    {"sym":"ES=F",     "name":"SPX500","cat":"INDICES","pip":0.25,   "max_sp":3,  "vol":5,"crypto":False},
    {"sym":"YM=F",     "name":"US30",  "cat":"INDICES","pip":1.0,    "max_sp":5,  "vol":5,"crypto":False},

    # ── Pétrole ───────────────────────────────────────────────
    {"sym":"CL=F",     "name":"USOIL", "cat":"OIL",   "pip":0.01,   "max_sp":8,  "vol":4,"crypto":False},
]

CRYPTO_NAMES = [m["name"] for m in MARKETS if m.get("crypto")]
CAT_EMO  = {"FOREX":"\U0001f4b1","METALS":"\U0001f947","CRYPTO":"\u20bf",
            "INDICES":"\U0001f4c8","OIL":"\U0001f6e2"}
CAT_NAME = {"FOREX":"Forex","METALS":"Metaux","CRYPTO":"Crypto",
            "INDICES":"Indices","OIL":"Petrole"}


# ═══════════════════════════════════════════════════════════════
#  ② LOGGER
# ═══════════════════════════════════════════════════════════════
C = {
    "reset":   "\033[0m","bold":    "\033[1m","dim":     "\033[2m",
    "cyan":    "\033[96m","green":   "\033[92m","yellow":  "\033[93m",
    "red":     "\033[91m","white":   "\033[97m","magenta": "\033[95m",
}
TAGS = {
    "INFO":   lambda: clr(" INFO   ", "bold", "cyan"),
    "SIGNAL": lambda: clr(" SIGNAL ", "bold", "green"),
    "WARN":   lambda: clr(" WARN   ", "bold", "yellow"),
    "ERR":    lambda: clr(" ERROR  ", "bold", "red"),
    "PAY":    lambda: clr(" PAY    ", "bold", "magenta"),
}

def clr(text, *codes):
    return "".join(C[c] for c in codes) + str(text) + C["reset"]

def log(level, msg):
    ts  = clr("[{}]".format(datetime.now().strftime("%H:%M:%S")), "dim")
    tag = TAGS.get(level, lambda: clr(" LOG    ", "dim"))()
    print("{} {} {}".format(ts, tag, msg))

def print_banner():
    c = C["cyan"]; b = C["bold"]; r = C["reset"]
    d = C["dim"];  g = C["green"]; y = C["yellow"]
    print()
    print(b+c+"  ╔══════════════════════════════════════════════════╗"+r)
    print(b+c+"  ║   "+b+"██████ "+y+"ALPHABOT"+c+"  "+g+"v14"+c+"  ICT · SMC · M5+H1   ║"+r)
    print(b+c+"  ║  "+d+" 20 marchés  |  20 agents IA  |  Données LIVE  "+c+"║"+r)
    print(b+c+"  ║  "+d+" FREE 2/j  |  PRO max 10/j  |  Weekend BTC   "+c+" ║"+r)
    print(b+c+"  ╚══════════════════════════════════════════════════╝"+r)
    print()


# ═══════════════════════════════════════════════════════════════
#  ③ SESSION
# ═══════════════════════════════════════════════════════════════
def get_session():
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    h   = now.hour
    wd  = now.weekday()
    if wd >= 5:
        return "WEEKEND", 72, "\U0001f30d Week-end \u20bf Crypto only", True
    if 12 <= h < 16:
        return "OVERLAP", 63, "\U0001f1ec\U0001f1e7+\U0001f1fa\U0001f1f8 London+NY", False
    if 16 <= h < 21:
        return "NY",      65, "\U0001f1fa\U0001f1f8 New York",          False
    if 7  <= h < 12:
        return "LONDON",  61, "\U0001f1ec\U0001f1e7 Londres",           False
    if 0  <= h < 7:
        return "ASIAN",   68, "\U0001f30f Asiatique",                   False
    return     "OFF",     73, "\U0001f315 Hors session",                False

def score_min_for_market(m, base, atr_ratio):
    vol_adj = (m.get("vol", 3) - 3) * 2
    atr_adj = min(4, int(atr_ratio * 5))
    return base + vol_adj + atr_adj


# ═══════════════════════════════════════════════════════════════
#  ④ NETWORK
# ═══════════════════════════════════════════════════════════════
CTX = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
CTX.check_hostname = False
CTX.verify_mode    = ssl.CERT_NONE
CTX.set_ciphers("DEFAULT@SECLEVEL=0")

TG       = "https://api.telegram.org/bot{}/".format(BOT_TOKEN)
_tg_lock = threading.Lock()

def http_get(url, headers=None, timeout=15):
    hdrs = {
        "User-Agent": "Mozilla/5.0 (compatible; AlphaBot/8.5)",
        "Accept":     "application/json",
        **(headers or {})
    }
    for attempt in range(3):
        try:
            req    = urllib.request.Request(url, headers=hdrs)
            opener = urllib.request.build_opener(
                urllib.request.HTTPSHandler(context=CTX))
            with opener.open(req, timeout=timeout) as r:
                return r.read().decode("utf-8")
        except Exception:
            if attempt < 2: time.sleep(2)
            else: raise
    raise Exception("Max retries atteint")

def http_post(url, data, timeout=15):
    raw  = urllib.parse.urlencode(data).encode("utf-8")
    hdrs = {"Content-Type": "application/x-www-form-urlencoded"}
    for attempt in range(3):
        try:
            req    = urllib.request.Request(url, data=raw, headers=hdrs, method="POST")
            opener = urllib.request.build_opener(
                urllib.request.HTTPSHandler(context=CTX))
            with opener.open(req, timeout=timeout) as r:
                return json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            if e.code == 409: return {}
            if attempt < 2: time.sleep(2)
            else: return {}
        except Exception:
            if attempt < 2: time.sleep(2)
            else: return {}
    return {}

def tg_req(method, params):
    try:
        return http_post(TG + method, params)
    except Exception as e:
        print("  [TG] {}".format(e))
        return {}

def tg_send(chat_id, text, kb=None):
    p = {
        "chat_id":                  str(chat_id),
        "text":                     text,
        "parse_mode":               "HTML",
        "disable_web_page_preview": "true"
    }
    if kb:
        p["reply_markup"] = json.dumps(kb)
    with _tg_lock:
        return tg_req("sendMessage", p)

def tg_updates(offset):
    return tg_req("getUpdates", {
        "offset":  offset,
        "timeout": 2,
        "limit":   20
    }).get("result", [])

def tg_send_sticker(chat_id, sticker_id):
    """Envoie un sticker Telegram animé."""
    tg_req("sendSticker", {"chat_id": str(chat_id), "sticker": sticker_id})

# Stickers utilisés dans les messages
STK_SIGNAL  = "CAACAgIAAxkBAAIBhGWbNYA1IekbQLJgzf0HuBj0jYFnAAK3AQACB8OhCj1gMCxF9WqKNgQ"  # 🎯 bullseye
STK_MONEY   = "CAACAgIAAxkBAAIBhmWbNa7lp9yDhKRHx_7q2sDFGn0ZAAKFAQACvhiBC-VC2IuBbHH3NgQ"  # 💰 sac argent
STK_FIRE    = "CAACAgIAAxkBAAIBiGWbNcBL0k0ZGIPKHGWBq-fFxgG0AAJcAAMW0StFbJlMpSqAx3oNgQ"  # 🔥 feu
STK_CROWN   = "CAACAgIAAxkBAAIBimWbNeGxR0rp2J0m0eZ7nYJGq7cLAAKXAAMW0StFBtO28qLLMKgNgQ"  # 👑 couronne
STK_ROCKET  = "CAACAgIAAxkBAAIBjGWbNfNMiEkgPZrxgWMVBH1ycfP7AAIbAQACB8OhCsYm5NOoMByuNgQ"  # 🚀 fusée
STK_WELCOME = "CAACAgIAAxkBAAIBjmWbNgIkJ6opkKOd5P2tniQu7R2IAALiAAMW0StFqKjl9SqrXTUNgQ"  # 👋 bienvenue
STK_PRO     = "CAACAgIAAxkBAAIBkGWbNhPIhvNXV7yKp9c0wZIf-g2rAAJDAQACvhiBCxlh5gPVk7E_NgQ"  # 💎 diamant
STK_WIN     = "CAACAgIAAxkBAAIBkmWbNibdCvV2RRd7OjQbIRpQ7juvAAIlAQACB8OhCpNJ8K7ZqLyANgQ"  # 🏆 trophée


def tg_send_document(chat_id, data, filename, caption=""):
    boundary = "ABotBoundary85"
    body = b""
    def field(name, val):
        return (
            "--{}\r\nContent-Disposition: form-data; name=\"{}\"\r\n\r\n".format(boundary, name)
        ).encode() + str(val).encode() + b"\r\n"
    body += field("chat_id", chat_id)
    if caption:
        body += field("caption", caption)
        body += field("parse_mode", "HTML")
    body += (
        "--{}\r\nContent-Disposition: form-data; name=\"document\"; "
        "filename=\"{}\"\r\nContent-Type: application/octet-stream\r\n\r\n".format(boundary, filename)
    ).encode()
    body += data + b"\r\n" + ("--{}--\r\n".format(boundary)).encode()
    try:
        req = urllib.request.Request(
            TG + "sendDocument", data=body, method="POST",
            headers={"Content-Type": "multipart/form-data; boundary=" + boundary})
        opener = urllib.request.build_opener(urllib.request.HTTPSHandler(context=CTX))
        with opener.open(req, timeout=30) as r:
            return json.loads(r.read().decode())
    except Exception as e:
        print("  [DOC] {}".format(e))
        return {}


# ═══════════════════════════════════════════════════════════════
#  ⑤ DATABASE
# ═══════════════════════════════════════════════════════════════
_db_lock = threading.Lock()

def _conn():
    con = sqlite3.connect(DB_FILE, check_same_thread=False)
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("PRAGMA synchronous=NORMAL")
    return con

def db_setup():
    con = _conn(); cur = con.cursor()

    cur.execute("PRAGMA table_info(users)")
    u_cols = {r[1] for r in cur.fetchall()}
    GOOD_COLS = {"user_id","username","plan","ref_by","ref_count",
                 "joined","pro_expires","pro_source"}
    bad_cols  = u_cols - GOOD_COLS
    needs_rebuild = (
        not u_cols or ("id" in u_cols and "user_id" not in u_cols)
        or "telegram_id" in u_cols or (bad_cols - {"rowid"}))

    if needs_rebuild and u_cols:
        rows_info = cur.execute("PRAGMA table_info(users)").fetchall()
        pk_col = next((c for c in ["user_id","telegram_id","id"] if c in u_cols), rows_info[0][1])
        copy_map = [("username","username"),("plan","plan"),("ref_by","ref_by"),
                    ("ref_count","ref_count"),("joined","joined"),
                    ("pro_expires","pro_expires"),("pro_source","pro_source")]
        copy_cols = [(ins,sel) for ins,sel in copy_map if sel in u_cols]
        ins_part  = ",".join(["user_id"] + [p[0] for p in copy_cols])
        sel_part  = ",".join([pk_col]    + [p[1] for p in copy_cols])
        cur.execute("""CREATE TABLE users_new (
            user_id INTEGER PRIMARY KEY, username TEXT DEFAULT "",
            plan TEXT DEFAULT "FREE", ref_by INTEGER DEFAULT 0,
            ref_count INTEGER DEFAULT 0, joined TEXT DEFAULT "",
            pro_expires TEXT DEFAULT NULL, pro_source TEXT DEFAULT NULL)""")
        cur.execute("INSERT OR IGNORE INTO users_new ({}) SELECT {} FROM users".format(ins_part, sel_part))
        cur.execute("DROP TABLE users")
        cur.execute("ALTER TABLE users_new RENAME TO users")
        con.commit()
    elif not u_cols:
        cur.execute("""CREATE TABLE users (
            user_id INTEGER PRIMARY KEY, username TEXT DEFAULT "",
            plan TEXT DEFAULT "FREE", ref_by INTEGER DEFAULT 0,
            ref_count INTEGER DEFAULT 0, joined TEXT DEFAULT "",
            pro_expires TEXT DEFAULT NULL, pro_source TEXT DEFAULT NULL)""")

    for col_def in ['username TEXT DEFAULT ""','plan TEXT DEFAULT "FREE"',
                    "ref_by INTEGER DEFAULT 0","ref_count INTEGER DEFAULT 0",
                    'joined TEXT DEFAULT ""',"pro_expires TEXT DEFAULT NULL",
                    "pro_source TEXT DEFAULT NULL"]:
        try: cur.execute("ALTER TABLE users ADD COLUMN " + col_def)
        except: pass

    cur.execute("""CREATE TABLE IF NOT EXISTS payments (
        pay_id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, amount REAL,
        tx_hash TEXT, status TEXT DEFAULT "PENDING", created TEXT)""")

    cur.execute("""CREATE TABLE IF NOT EXISTS signals (
        sig_id INTEGER PRIMARY KEY AUTOINCREMENT, pair TEXT, side TEXT,
        entry REAL, tp REAL, sl REAL, rr REAL, score INTEGER,
        session TEXT DEFAULT "", g001 REAL DEFAULT 0, g1 REAL DEFAULT 0,
        l001 REAL DEFAULT 0, l1 REAL DEFAULT 0, sent_at TEXT)""")
    for col_def in ["g001 REAL DEFAULT 0","g1 REAL DEFAULT 0","l001 REAL DEFAULT 0",
                    "l1 REAL DEFAULT 0",'session TEXT DEFAULT ""',"sent_at TEXT"]:
        try: cur.execute("ALTER TABLE signals ADD COLUMN " + col_def)
        except: pass

    cur.execute("PRAGMA table_info(signal_counts)")
    sc_cols = {r[1] for r in cur.fetchall()}
    if not sc_cols or "user_id" not in sc_cols:
        cur.execute("DROP TABLE IF EXISTS signal_counts")
        cur.execute("""CREATE TABLE signal_counts (
            user_id INTEGER NOT NULL, date_str TEXT NOT NULL,
            count INTEGER NOT NULL DEFAULT 0, PRIMARY KEY (user_id, date_str))""")

    cur.execute("""CREATE TABLE IF NOT EXISTS daily_reports (
        report_id INTEGER PRIMARY KEY AUTOINCREMENT, report_date TEXT,
        sig_count INTEGER DEFAULT 0, win_count INTEGER DEFAULT 0,
        total_g001 REAL DEFAULT 0, total_g1 REAL DEFAULT 0, created TEXT)""")
    cur.execute("""CREATE TABLE IF NOT EXISTS weekly_reports (
        report_id INTEGER PRIMARY KEY AUTOINCREMENT, week_start TEXT,
        sig_count INTEGER DEFAULT 0, win_count INTEGER DEFAULT 0,
        total_g1 REAL DEFAULT 0, created TEXT)""")

    con.commit()
    cur.execute("PRAGMA table_info(users)")
    final = {r[1] for r in cur.fetchall()}
    missing = GOOD_COLS - final
    if missing: print("  [DB] COLONNES MANQUANTES: {}".format(missing))
    else:        print("  [DB] Schema OK")
    con.close()

def db_init():
    db_setup()

def db_register(uid, uname, ref_by=0, tg_send_fn=None):
    con = _conn(); cur = con.cursor()
    with _db_lock:
        cur.execute("SELECT user_id FROM users WHERE user_id=?", (uid,))
        is_new = cur.fetchone() is None
        if is_new:
            cur.execute(
                "INSERT OR IGNORE INTO users (user_id,username,ref_by,joined) VALUES (?,?,?,?)",
                (uid, uname or "", ref_by, datetime.now().isoformat()))
            con.commit()

    if is_new:
        # ── Notification admin : nouvel utilisateur ────────────
        if tg_send_fn and uid != ADMIN_ID:
            cur.execute("SELECT COUNT(*) FROM users")
            total_users = cur.fetchone()[0]
            fname = "@" + uname if uname else "ID:{}".format(uid)
            ref_info = " via parrainage de <code>{}</code>".format(ref_by) if ref_by else ""
            tg_send_fn(ADMIN_ID,
                "\U0001f195 <b>NOUVEL UTILISATEUR</b>{}\n\n"
                "\U0001f464 {} \u00b7 <code>{}</code>\n"
                "\U0001f465 Total membres : <b>{}</b>".format(ref_info, fname, uid, total_users),
                kb={"inline_keyboard": [[
                    {"text": "\U0001f4a0 Activer PRO", "callback_data": "adm_pro_{}".format(uid)},
                    {"text": "\U0001f6d1 Bloquer",     "callback_data": "adm_ban_{}".format(uid)},
                ]]})

        if ref_by and ref_by != uid:
            with _db_lock:
                cur.execute("UPDATE users SET ref_count=ref_count+1 WHERE user_id=?", (ref_by,))
                con.commit()
                cur.execute("SELECT ref_count,username FROM users WHERE user_id=?", (ref_by,))
                row = cur.fetchone()
            if row and tg_send_fn:
                count = row[0]
                fname = "@" + uname if uname else str(uid)
                tg_send_fn(ref_by,
                    "\U0001f389 <b>Nouveau filleul !</b>\n{} a rejoint.\n"
                    "\U0001f465 <b>{}/{}</b>  {}".format(
                        fname, count, REF_TARGET,
                        "\U0001f3c6 {} atteints ! PRO {} mois activé !".format(REF_TARGET, REF_MONTHS)
                        if count >= REF_TARGET else
                        "{} de plus = {} mois PRO !".format(REF_TARGET - count, REF_MONTHS)))
                if count >= REF_TARGET:
                    con.close()
                    db_activate_pro(ref_by, "PARRAINAGE_{}M".format(REF_MONTHS), days=REF_MONTHS * 30)
                    tg_send_fn(ref_by,
                        "\U0001f3c6 <b>FÉLICITATIONS !</b>\n\n"
                        "\U0001f929 <b>{} filleuls atteints !</b>\n"
                        "Ton PRO <b>{} MOIS</b> est activé ! \U0001f389\n\n"
                        "\u2705 Max {} signaux/j\n\u2705 24 paires + crypto week-end\n"
                        "\u2705 Rapport quotidien + hebdo\n\n"
                        "\U0001f4c5 Expire dans {} jours\n"
                        "\U0001f501 Renouvele en re-parrainant !".format(
                            REF_TARGET, REF_MONTHS, PRO_LIMIT, REF_MONTHS * 30))
                    return
    else:
        if uname:
            with _db_lock:
                cur.execute("UPDATE users SET username=? WHERE user_id=?", (uname, uid))
                con.commit()
    con.close()

def db_is_pro(uid):
    con = _conn(); cur = con.cursor()
    cur.execute("SELECT plan FROM users WHERE user_id=?", (uid,))
    row = cur.fetchone(); con.close()
    return row is not None and row[0] == "PRO"

def db_get_refs(uid):
    con = _conn(); cur = con.cursor()
    cur.execute("SELECT ref_count FROM users WHERE user_id=?", (uid,))
    row = cur.fetchone(); con.close()
    return row[0] if row else 0

def db_get_pro_info(uid):
    con = _conn(); cur = con.cursor()
    cur.execute("SELECT plan,pro_expires,pro_source FROM users WHERE user_id=?", (uid,))
    row = cur.fetchone(); con.close()
    return (row[0], row[1], row[2]) if row else ("FREE", None, None)

def db_get_pro_users():
    con = _conn(); cur = con.cursor()
    cur.execute("SELECT user_id FROM users WHERE plan='PRO'")
    r = cur.fetchall(); con.close()
    return [x[0] for x in r]

def db_get_free_users():
    con = _conn(); cur = con.cursor()
    cur.execute("SELECT user_id FROM users WHERE plan='FREE'")
    r = cur.fetchall(); con.close()
    return [x[0] for x in r]

def db_find_by_username(uname):
    uname = uname.lstrip("@").lower()
    con = _conn(); cur = con.cursor()
    cur.execute("SELECT user_id,username FROM users")
    rows = cur.fetchall(); con.close()
    for uid, un in rows:
        if un and un.lower() == uname:
            return uid
    return None

def db_activate_pro(uid, source="PAIEMENT", days=None):
    con = _conn(); cur = con.cursor()
    expires = (datetime.now() + timedelta(days=days)).strftime("%Y-%m-%d") if days else None
    with _db_lock:
        cur.execute(
            "UPDATE users SET plan='PRO',pro_expires=?,pro_source=? WHERE user_id=?",
            (expires, source, uid))
        cur.execute(
            "UPDATE payments SET status='CONFIRMED' WHERE user_id=? AND status='PENDING'", (uid,))
        con.commit()
    con.close()

def db_downgrade_pro(uid):
    con = _conn(); cur = con.cursor()
    with _db_lock:
        cur.execute(
            "UPDATE users SET plan='FREE',pro_expires=NULL,pro_source=NULL WHERE user_id=?", (uid,))
        con.commit()
    con.close()

def db_check_expiry():
    try:
        con = _conn(); cur = con.cursor()
        today = datetime.now().strftime("%Y-%m-%d")
        cur.execute(
            "SELECT user_id,username FROM users WHERE plan='PRO' AND pro_expires IS NOT NULL AND pro_expires<?",
            (today,))
        expired = cur.fetchall()
        for uid, uname in expired:
            with _db_lock:
                cur.execute("UPDATE users SET plan='FREE',pro_expires=NULL WHERE user_id=?", (uid,))
                con.commit()
        con.close()
        return expired
    except Exception as e:
        print("  [db_check_expiry] {}".format(e))
        return []

def db_save_payment(uid, tx_hash):
    con = _conn(); cur = con.cursor()
    with _db_lock:
        cur.execute(
            "INSERT INTO payments (user_id,amount,tx_hash,status,created) VALUES (?,?,?,?,?)",
            (uid, PRO_PROMO, tx_hash, "PENDING", datetime.now().isoformat()))
        con.commit()
    con.close()

def db_pending_payments():
    con = _conn(); cur = con.cursor()
    try:
        cur.execute(
            "SELECT p.pay_id,p.user_id,u.username,p.tx_hash,p.created "
            "FROM payments p LEFT JOIN users u ON p.user_id=u.user_id "
            "WHERE p.status='PENDING' ORDER BY p.created DESC LIMIT 10")
        r = cur.fetchall(); con.close(); return r
    except:
        con.close(); return []

def db_count_today(uid):
    ds = datetime.now().strftime("%Y-%m-%d")
    con = _conn(); cur = con.cursor()
    try:
        cur.execute("SELECT count FROM signal_counts WHERE user_id=? AND date_str=?", (uid, ds))
        row = cur.fetchone(); con.close()
        return row[0] if row else 0
    except:
        con.close(); return 0

def db_count_increment(uid):
    ds = datetime.now().strftime("%Y-%m-%d")
    con = _conn(); cur = con.cursor()
    try:
        cur.execute("SELECT count FROM signal_counts WHERE user_id=? AND date_str=?", (uid, ds))
        with _db_lock:
            if cur.fetchone():
                cur.execute("UPDATE signal_counts SET count=count+1 WHERE user_id=? AND date_str=?", (uid, ds))
            else:
                cur.execute("INSERT INTO signal_counts (user_id,date_str,count) VALUES (?,?,1)", (uid, ds))
            con.commit()
    except Exception as e:
        print("  [DB count] {}".format(e))
    con.close()

def db_count_reset(uid):
    ds = datetime.now().strftime("%Y-%m-%d")
    con = _conn(); cur = con.cursor()
    with _db_lock:
        cur.execute("DELETE FROM signal_counts WHERE user_id=? AND date_str=?", (uid, ds))
        con.commit()
    con.close()

def db_save_signal(s, session_name):
    con = _conn(); cur = con.cursor()
    with _db_lock:
        cur.execute(
            "INSERT INTO signals (pair,side,entry,tp,sl,rr,score,session,g001,g1,l001,l1,sent_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (s["name"], s["side"], s["entry"], s["tp"], s["sl"], s["rr"],
             s["score"], session_name, s.get("g001", 0), s.get("g1", 0),
             s.get("l001", 0), s.get("l1", 0), datetime.now().isoformat()))
        con.commit()
    con.close()

def db_daily_stats(date_str=None):
    if not date_str:
        date_str = datetime.now().strftime("%Y-%m-%d")
    con = _conn(); cur = con.cursor()
    cur.execute(
        "SELECT pair,side,rr,g001,g1,l001,l1,session,entry,tp,sl FROM signals "
        "WHERE sent_at LIKE ? ORDER BY sent_at",
        (date_str + "%",))
    rows = cur.fetchall(); con.close()
    wins   = sum(1 for r in rows if r[2] >= 3.0)
    losses = len(rows) - wins
    return {
        "date": date_str, "sig_count": len(rows), "wins": wins, "losses": losses,
        "total_g001": round(sum(r[3] for r in rows), 2),
        "total_g1":   round(sum(r[4] for r in rows), 2),
        "rows": rows
    }

def db_weekly_stats():
    con = _conn(); cur = con.cursor()
    week_start = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
    cur.execute(
        "SELECT pair,side,rr,g001,g1,session FROM signals WHERE sent_at>=? ORDER BY sent_at",
        (week_start + " 00:00",))
    rows = cur.fetchall(); con.close()
    wins = sum(1 for r in rows if r[2] >= 3.0)
    return {
        "week_start": week_start, "sig_count": len(rows), "wins": wins,
        "total_g001": round(sum(r[3] for r in rows), 2),
        "total_g1":   round(sum(r[4] for r in rows), 2),
        "rows": rows
    }

def db_report_sent(date_str, table="daily_reports", col="report_date"):
    con = _conn(); cur = con.cursor()
    cur.execute("SELECT 1 FROM {} WHERE {}=?".format(table, col), (date_str,))
    row = cur.fetchone(); con.close()
    return row is not None

def db_mark_report(stats, table="daily_reports"):
    con = _conn(); cur = con.cursor()
    with _db_lock:
        if table == "daily_reports":
            cur.execute(
                "INSERT INTO daily_reports (report_date,sig_count,win_count,total_g001,total_g1,created) "
                "VALUES (?,?,?,?,?,?)",
                (stats["date"], stats["sig_count"], stats["wins"],
                 stats.get("total_g001", 0), stats["total_g1"], datetime.now().isoformat()))
        else:
            cur.execute(
                "INSERT INTO weekly_reports (week_start,sig_count,win_count,total_g1,created) VALUES (?,?,?,?,?)",
                (stats["week_start"], stats["sig_count"], stats["wins"],
                 stats["total_g1"], datetime.now().isoformat()))
        con.commit()
    con.close()

def db_global_stats():
    con = _conn(); cur = con.cursor()
    cur.execute("SELECT COUNT(*) FROM users");                              total = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM users WHERE plan='PRO'");            pro   = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM signals");                           sigs  = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM payments WHERE status='CONFIRMED'"); pays  = cur.fetchone()[0]
    cur.execute("SELECT COALESCE(SUM(g1),0) FROM signals WHERE sent_at LIKE ?",
                (datetime.now().strftime("%Y-%m-%d") + "%",))
    g1d = cur.fetchone()[0]
    con.close()
    return total, pro, sigs, pays, round(g1d, 2)


# ═══════════════════════════════════════════════════════════════
#  ⑥ CLAVIERS TELEGRAM
# ═══════════════════════════════════════════════════════════════
def kb_reply():
    """Clavier principal — 4 lignes × 2 boutons."""
    return {"keyboard": [
        [{"text": "\U0001f4e1 Mes Signaux"}, {"text": "\U0001f4ca Mon Compte"}],
        [{"text": "\U0001f4b0 Devenir PRO"},  {"text": "\U0001f91d Parrainage"}],
        [{"text": "\U0001f4b8 Mes Gains"},    {"text": "\U0001f4d6 Guide ICT"}],
        [{"text": "\U0001f4c8 Rapports"},     {"text": "\U0001f3e6 Broker Exness"}],
    ], "resize_keyboard": True, "persistent": True,
       "input_field_placeholder": "Choisis une option..."}

def kb_main():
    return {"inline_keyboard": [
        [{"text": "\U0001f4e1 Signaux",    "callback_data": "signals"},
         {"text": "\U0001f4ca Compte",     "callback_data": "account"}],
        [{"text": "\U0001f4a0 Devenir PRO","callback_data": "pro"},
         {"text": "\U0001f4b0 Payer USDT", "callback_data": "pay"}],
        [{"text": "\U0001f91d Parrainage", "callback_data": "ref"},
         {"text": "\U0001f4c8 Rapports",   "callback_data": "rapports"}],
        [{"text": "\U0001f3e6 Broker",     "callback_data": "broker"}],
    ]}

def kb_back():
    return {"inline_keyboard": [[{"text": "\u25c0\ufe0f Menu", "callback_data": "main"}]]}

def kb_pro():
    return {"inline_keyboard": [
        [{"text": "\U0001f4b0 Payer {}$ USDT TRC20 \u2192 PRO IMMEDIAT".format(PRO_PROMO),
          "callback_data": "pay"}],
        [{"text": "\U0001f91d {} filleuls \u2192 {} mois PRO gratuit".format(REF_TARGET, REF_MONTHS),
          "callback_data": "ref"}],
        [{"text": "\u25c0\ufe0f Menu", "callback_data": "main"}],
    ]}


# ═══════════════════════════════════════════════════════════════
#  ⑦ MESSAGES UTILISATEURS
# ═══════════════════════════════════════════════════════════════
def send_welcome(uid, uname, ref_by=0):
    db_register(uid, uname, ref_by, tg_send_fn=tg_send)
    tg_send_sticker(uid, STK_WELCOME)
    is_pro = db_is_pro(uid)
    name_txt = "@" + uname if uname else "Trader"
    sn, sm, sl, wknd = get_session()
    wknd_note = "\n\U0001f30d <b>Week-end : crypto uniquement !</b>" if wknd else ""
    tg_send(uid,
        "\U0001f916 <b>AlphaBot PRO v8.5 \u2014 Bienvenue {} !</b>\n".format(name_txt) +
        "\u2550" * 22 + "\n\n"
        "\U0001f194 <b>ID :</b> <code>{}</code>\n"
        "\U0001f4cc <b>Plan :</b> {}\n"
        "\U0001f553 <b>Session :</b> {}  \u00b7  Score min : <b>{}</b>{}\n\n".format(
            uid,
            "\U0001f4a0 PRO actif \u2705" if is_pro else "\U0001f513 FREE \u2192 /pay",
            sl, sm, wknd_note) +
        "\u2550" * 22 + "\n"
        "\U0001f916 <b>20 agents IA</b> scannent en parallèle :\n"
        "  \U0001f947 Or · Argent · Platine  \u00b7  \u20bf BTC\n"
        "  \U0001f4b1 Forex : EURUSD · GBPUSD · USDJPY · GBPJPY · EURJPY\n"
        "           AUDUSD · AUDJPY · CADJPY · CHFJPY · USDCHF · NZDUSD · USDCAD\n"
        "  \U0001f4c8 Indices US : NAS100 \u00b7 SPX500 \u00b7 US30\n"
        "  \U0001f6e2 Pétrole : USOIL\n\n" +
        "\u2550" * 22 + "\n"
        "\U0001f513 FREE = {} sig/j  \u2014  \U0001f4a0 PRO = max {}/j\n"
        "\U0001f91d {} filleuls = {} mois PRO <b>GRATUIT</b>\n\n"
        "\U0001f4d6 Tape /guide ou choisis ci-dessous \u2193".format(
            FREE_LIMIT, PRO_LIMIT, REF_TARGET, REF_MONTHS),
        kb=kb_reply())

def send_account(uid, uname, forced_plan=None):
    """Mon Compte — affiche plan, filleuls, lien, gains du jour."""
    is_pro = (forced_plan == "PRO") if forced_plan else db_is_pro(uid)
    refs   = db_get_refs(uid)
    plan, exp, src = db_get_pro_info(uid)
    stats  = db_daily_stats()
    link   = "https://t.me/{}?start={}".format(BOT_USERNAME, uid)
    done   = min(refs, REF_TARGET)
    pct    = int(done / REF_TARGET * 100)
    fill   = int(done / REF_TARGET * 12)
    bar    = "\U0001f7e9" * fill + "\u2b1c" * (12 - fill)
    count  = db_count_today(uid)
    lim    = PRO_LIMIT if is_pro else FREE_LIMIT

    # Ligne plan + jours restants
    if is_pro:
        if exp:
            try:
                days_left = (datetime.strptime(exp, "%Y-%m-%d") - datetime.now()).days
                plan_line = "\U0001f4a0 <b>PRO</b> \u2705  Expire dans <b>{} jours</b> ({})".format(days_left, exp)
            except:
                plan_line = "\U0001f4a0 <b>PRO</b> \u2705  Expire le {}".format(exp)
        else:
            plan_line = "\U0001f4a0 <b>PRO À VIE</b> \u2705"
    else:
        plan_line = "\U0001f513 <b>FREE</b>  {}/{} sig aujourd'hui".format(count, lim)

    mode_banner = "\U0001f9ea <i>[Vue simulée — mode {}]</i>\n\n".format(forced_plan) if forced_plan else ""
    tg_send(uid,
        mode_banner +
        "\U0001f4ca <b>MON COMPTE</b>\n" + "\u2550" * 22 + "\n\n"
        "\U0001f464 @{}  <code>{}</code>\n"
        "\U0001f4cc {}\n\n"
        "\U0001f91d Parrainage : <b>{}/{}</b>  ({}%)\n{}\n\n"
        "\U0001f517 Mon lien de parrainage :\n<code>{}</code>\n\n"
        "\U0001f4e1 Signaux aujourd'hui : {}  \u00b7  Lot0.01 <b>+${}</b>  \u00b7  Lot1 <b>+${}</b>".format(
            uname or "?", uid, plan_line,
            done, REF_TARGET, pct, bar, link,
            stats["sig_count"], stats["total_g001"], stats["total_g1"]),
        kb=kb_back())

def send_signals_info(uid):
    """Mes Signaux — affiche les signaux réels du jour."""
    is_pro = db_is_pro(uid)
    stats  = db_daily_stats()
    rows   = stats["rows"]
    sn, sm, sl, wknd = get_session()
    count  = db_count_today(uid)
    lim    = PRO_LIMIT if is_pro else FREE_LIMIT
    remain = max(0, lim - count)
    today  = datetime.now().strftime("%d/%m/%Y")

    lines = [
        "\U0001f4e1 <b>SIGNAUX DU JOUR</b>",
        "\u2550" * 22,
        "\U0001f4c5 {}  \u00b7  {}".format(today, sl),
        "{} \u00b7  {}/{} signaux  \u00b7  Reste : <b>{}</b>".format(
            "\U0001f4a0 PRO" if is_pro else "\U0001f513 FREE", count, lim, remain),
        ""
    ]

    if rows:
        lines.append("\U0001f4cb <b>Signaux envoyés :</b>")
        lines.append("")
        for row in rows:
            pair, side, rr, g001, g1, l001, l1, session = row[0], row[1], row[2], row[3], row[4], row[5], row[6], row[7]
            arrow  = "\u2b06\ufe0f" if side == "BUY" else "\u2b07\ufe0f"
            icon   = "\u2705" if rr >= 3.0 else "\u26aa"
            gain   = "+${:.0f}".format(g1) if rr >= 3.0 else "---"
            lines.append("{} <b>{}</b>  {} {}  RR 1:{}  \U0001f4b0 {}".format(
                icon, pair, arrow, side, rr, gain))
        lines.append("")
        lines.append("\u2501" * 20)
        lines.append("\U0001f4b5 Total lot 0.01 : <b>+${}</b>".format(stats["total_g001"]))
        lines.append("\U0001f4b0 Total lot 1.00 : <b>+${}</b>".format(stats["total_g1"]))
        lines.append("\U0001f3af {}/{} gagnants".format(stats["wins"], stats["sig_count"]))
    else:
        lines.append("\u23f3 Aucun signal encore aujourd'hui.")
        lines.append("\U0001f504 Prochain scan dans quelques minutes...")
        lines.append("")
        if not is_pro:
            lines.append("\U0001f4a0 <b>Passe PRO pour max {}/j</b>\n/pay \u2014 {}$ USDT".format(
                PRO_LIMIT, PRO_PROMO))

    tg_send(uid, "\n".join(lines), kb=kb_back())

def send_pro(uid):
    is_pro = db_is_pro(uid)
    if is_pro:
        tg_send_sticker(uid, STK_CROWN)
        plan, exp, src = db_get_pro_info(uid)
        exp_txt = "À VIE" if not exp else "expire le {}".format(exp)
        tg_send(uid,
            "\U0001f4a0 <b>PRO actif !</b> \u2705\n\n"
            "Accès : <b>{}</b>\nSignaux : max {}/j\n\nMerci \U0001f64f".format(
                exp_txt, PRO_LIMIT),
            kb=kb_back())
        return
    refs = db_get_refs(uid)
    tg_send_sticker(uid, STK_PRO)
    tg_send(uid,
        "\U0001f4a0 <b>ALPHABOT PRO v8.5</b>\n" + "\u2550" * 22 + "\n\n"
        "\u2705 Max {} signaux/j (meilleurs seulement)\n"
        "\u2705 24 paires + crypto week-end\n"
        "\u2705 Lot 0.01, 0.10 et 1.00 dans chaque signal\n"
        "\u2705 20 agents IA en parallèle\n"
        "\u2705 Rapport scan + quotidien + hebdo\n"
        "\u2705 Support @leaderOdg\n\n" +
        "\u2501" * 20 + "\n"
        "\U0001f4b0 <b>Option 1 : {}$ USDT TRC20</b> \u2192 Accès immédiat\n\n"
        "\U0001f91d <b>Option 2 : Parrainage GRATUIT</b>\n"
        "{} filleuls = {} mois PRO (renouvelable)\n"
        "Tes filleuls : {}/{}\n\n/pay \u00b7 /ref".format(
            PRO_LIMIT, PRO_PROMO, REF_TARGET, REF_MONTHS, refs, REF_TARGET),
        kb=kb_pro())

def send_pay(uid):
    """Instructions de paiement USDT TRC20 + bouton J'ai payé."""
    msg = (
        "\U0001f4b0 <b>PAIEMENT PRO \u2014 {}$ USDT</b>\n".format(PRO_PROMO) +
        "\u2501" * 22 + "\n\n"
        "\u26a0\ufe0f <b>RÉSEAU : TRC20 UNIQUEMENT</b>\n"
        "Pas BEP20, pas ERC20 \u2014 sinon perdu !\n\n"
        "\U0001f447 <b>Adresse USDT TRC20 :</b>\n"
        "<code>{}</code>\n\n".format(USDT_ADDRESS) +
        "\u2501" * 22 + "\n"
        "1\ufe0f\u20e3 Ouvre Binance / Trust Wallet...\n"
        "2\ufe0f\u20e3 Envoie <b>{}$ USDT TRC20</b> à l'adresse\n"
        "3\ufe0f\u20e3 Clique <b>J'ai payé ✅</b> ci-dessous\n"
        "4\ufe0f\u20e3 Envoie ton <b>TX Hash</b> ou une <b>capture d'écran</b>\n\n"
        "\U0001f916 <b>Activation automatique sous 2 min !</b>".format(PRO_PROMO)
    )
    kb = {"inline_keyboard": [
        [{"text": "✅ J'ai payé — Soumettre ma preuve", "callback_data": "pay_submitted"}],
        [{"text": "◀️ Menu", "callback_data": "main"}],
    ]}
    tg_send(uid, msg, kb=kb)

def send_mes_gains(uid):
    stats = db_daily_stats(); rows = stats["rows"]
    if not rows:
        tg_send(uid, "\U0001f4b8 <b>MES GAINS</b>\n\nAucun signal aujourd'hui.", kb=kb_back())
        return
    lines = ["\U0001f4b8 <b>GAINS DU JOUR</b>", "\u2550" * 22, ""]
    for row in rows:
        pair, side, rr, g001, g1, l001, l1, session = row[0], row[1], row[2], row[3], row[4], row[5], row[6], row[7]
        ok = rr >= 3.0; icon = "\u2705" if ok else "\u274c"
        d  = "\u2b06\ufe0f" if side == "BUY" else "\u2b07\ufe0f"
        lines.append("{} <b>{}</b> {} {}  RR 1:{}".format(icon, pair, d, side, rr))
        if ok:
            lines.append("   0.01 \u2192 +${:.2f}   1.00 \u2192 +${:.0f}".format(g001, g1))
        else:
            lines.append("   ---")
    lines += ["", "\u2550" * 22,
              "\U0001f4b5 Lot 0.01 : <b>+${}</b>".format(stats["total_g001"]),
              "\U0001f4b0 Lot 1.00 : <b>+${}</b>".format(stats["total_g1"]),
              "({}/{} gagnants)".format(stats["wins"], stats["sig_count"]), "",
              "<i>Estimation TP atteint. Pas un conseil financier.</i>"]
    tg_send(uid, "\n".join(lines), kb=kb_back())

def send_rapports(uid):
    """📈 Rapports — performances journalières et hebdomadaires."""
    stats_day  = db_daily_stats()
    stats_week = db_weekly_stats()
    today      = datetime.now().strftime("%d/%m/%Y")

    sd = stats_day["sig_count"]; wd = stats_day["wins"]
    sw = stats_week["sig_count"]; ww = stats_week["wins"]
    wr_d = int(wd / sd * 100) if sd else 0
    wr_w = int(ww / sw * 100) if sw else 0

    perf_d = "\U0001f525" if stats_day["total_g1"] > 1000 else "\U0001f4b0" if sd > 0 else "\u23f3"
    perf_w = "\U0001f525\U0001f525" if stats_week["total_g1"] > 5000 else \
             "\U0001f525" if stats_week["total_g1"] > 2000 else "\U0001f4b0"

    lines = [
        "\U0001f4c8 <b>RAPPORTS DE PERFORMANCE</b>",
        "\u2550" * 22, "",
        "{} <b>AUJOURD'HUI — {}</b>".format(perf_d, today), ""
    ]

    if sd > 0:
        lines.append("\U0001f4e1 {} signaux  \u00b7  {} \u2705  \u00b7  {}% réussite".format(sd, wd, wr_d))
        lines.append("\U0001f4b5 Lot 0.01 : <b>+${}</b>".format(stats_day["total_g001"]))
        lines.append("\U0001f4b0 Lot 1.00 : <b>+${}</b>".format(stats_day["total_g1"]))
        lines.append("")
        lines.append("\U0001f4cb <b>Détail :</b>")
        for row in stats_day["rows"]:
            pair, side, rr, g001, g1, l001, l1, session = row[0], row[1], row[2], row[3], row[4], row[5], row[6], row[7]
            icon  = "\u2705" if rr >= 3.0 else "\u274c"
            arrow = "\u2b06\ufe0f" if side == "BUY" else "\u2b07\ufe0f"
            lines.append("  {} <b>{}</b> {} {}  RR 1:{}  \u2192 {}".format(
                icon, pair, arrow, side, rr,
                "+${:.0f}".format(g1) if rr >= 3.0 else "$0"))
    else:
        lines.append("\u23f3 Aucun signal encore aujourd'hui")

    lines += [
        "", "\u2501" * 20, "",
        "{} <b>CETTE SEMAINE</b>".format(perf_w),
        "Du {} \u00b7 7 derniers jours".format(stats_week["week_start"]), ""
    ]

    if sw > 0:
        lines.append("\U0001f4e1 {} signaux  \u00b7  {} \u2705  \u00b7  {}% réussite".format(sw, ww, wr_w))
        lines.append("\U0001f4b5 Lot 0.01 : <b>+${}</b>".format(stats_week["total_g001"]))
        lines.append("\U0001f4b0 Lot 1.00 : <b>+${}</b>".format(stats_week["total_g1"]))
    else:
        lines.append("\u23f3 Aucun signal cette semaine")

    lines += [
        "", "\u2550" * 22,
        "\u26a0\ufe0f Estimations si TP atteint. Pas un conseil financier.",
        "\U0001f916 AlphaBot PRO  \u00b7  @AlphaBotForexBot"
    ]
    tg_send(uid, "\n".join(lines), kb=kb_back())


# ═══════════════════════════════════════════════════════════════
#  ⑧ PARRAINAGE · BROKER · GUIDE + PDF
# ═══════════════════════════════════════════════════════════════
def send_affilie(uid, uname):
    """
    Parrainage — 2 messages :
    1) Texte promo DIRECT prêt à copier-coller
    2) Stats filleuls + progression
    """
    refs = db_get_refs(uid)
    link = "https://t.me/{}?start={}".format(BOT_USERNAME, uid)
    done = min(refs, REF_TARGET)
    pct  = int(done / REF_TARGET * 100)
    bar  = "\u2588" * int(done / REF_TARGET * 10) + "\u2591" * (10 - int(done / REF_TARGET * 10))

    # ── MESSAGE 1 : Texte promo direct prêt à partager ────────
    tg_send(uid,
        "\U0001f4cb <b>COPIE CE MESSAGE ET ENVOIE À TES AMIS :</b>\n\n"
        "\u2501" * 22 + "\n\n"
        "\U0001f916 <b>AlphaBot PRO</b> \u2014 Signaux trading GRATUITS !\n\n"
        "\U0001f4e1 <b>Forex, Or, BTC, ETH, Indices...</b>\n"
        "\U0001f3af Entrées directes avec SL \u0026 TP automatiques\n"
        "\U0001f4b0 Jusqu\u2019\u00e0 <b>+556$ par signal</b> (lot 1.00)\n"
        "\U0001f4ca Analyse ICT/SMC professionnelle \u2014 Score IA\n\n"
        "\u2705 <b>Gratuit</b> \u2014 2 signaux/jour\n"
        "\U0001f4a0 <b>PRO seulement 10$</b> \u2014 10 signaux/jour\n\n"
        "\U0001f449 <b>Clique ici pour rejoindre :</b>\n"
        "<code>{}</code>\n\n"
        "\u2501" * 22,
        kb={"inline_keyboard": [[
            {"text": "\U0001f91d Voir mes filleuls", "callback_data": "ref_stats"}
        ]]})

    # ── MESSAGE 2 : Stats filleuls ─────────────────────────────
    if refs >= REF_TARGET:
        rew = "\U0001f3c6 {} mois PRO actif ! Re-parraine pour renouveler !".format(REF_MONTHS)
    elif refs >= 20:
        rew = "\U0001f525 Plus que {} de plus \u2192 {} mois PRO !".format(REF_TARGET - refs, REF_MONTHS)
    else:
        rew = "\U0001f44b {} filleuls pour l\u2019instant. Continue !".format(refs)

    tg_send(uid,
        "\U0001f91d <b>MES FILLEULS</b>\n" + "\u2550" * 22 + "\n\n"
        "<b>{}/{}</b>  ({}%)\n[{}]\n\n"
        "{}\n\n"
        "\U0001f3c6 {} filleuls = <b>{} MOIS PRO GRATUIT</b>\n"
        "\U0001f501 Renouvelable à chaque tranche de {} filleuls !\n"
        "\u2705 <b>Activation automatique</b> dès {} atteints".format(
            done, REF_TARGET, pct, bar, rew,
            REF_TARGET, REF_MONTHS, REF_TARGET, REF_TARGET),
        kb=kb_back())

def send_broker(uid):
    tg_send(uid,
        "\U0001f3e6 <b>BROKER \u2014 EXNESS</b>\n\n"
        "\u2705 Spread 0 pip (Raw)\n"
        "\u2705 Dépôt minimum 10$\n"
        "\u2705 Réglementé FCA \u0026 CySEC\n"
        "\u2705 Exécution ultra-rapide\n"
        "\u2705 Crypto disponibles\n\n"
        "\U0001f449 <a href=\"{}\">\U0001f517 Ouvrir Exness maintenant</a>".format(BROKER_LINK),
        kb=kb_back())

def send_guide(uid):
    tg_send(uid,
        "\U0001f4d6 <b>GUIDE ALPHABOT PRO v8.5</b>\n" + "\u2550" * 22 + "\n\n"
        "\U0001f9e0 <b>Méthode ICT/SMC :</b>\n"
        "1\ufe0f\u20e3 <b>H1 Bias</b> (BOS/CHoCH) \u2192 détecte la tendance\n"
        "2\ufe0f\u20e3 <b>M5 Breaker Block</b> \u2192 zone d\u2019entrée précise\n"
        "3\ufe0f\u20e3 <b>Score dynamique</b> par session (0-100 pts)\n"
        "4\ufe0f\u20e3 <b>SL/TP auto</b> \u2014 RR minimum 1:2.5\n\n" +
        "\u2501" * 20 + "\n"
        "\U0001f553 <b>Score minimum par session :</b>\n"
        "  \U0001f1ec\U0001f1e7+\U0001f1fa\U0001f1f8 London+NY : <b>72</b>\n"
        "  \U0001f1fa\U0001f1f8 New York : <b>74</b>  \u00b7  \U0001f1ec\U0001f1e7 Londres : <b>70</b>\n"
        "  \U0001f30f Asiatique : <b>76</b>  \u00b7  \U0001f315 Hors session : <b>82</b>\n"
        "  \U0001f30d Week-end (crypto) : <b>80</b>\n\n" +
        "\u2501" * 20 + "\n"
        "\U0001f4ca <b>Score de confirmation (100 pts max) :</b>\n"
        "  +35 pts \u2192 Direction bougie (sens du bias)\n"
        "  +25 pts \u2192 Corps > 50% du range (displacement)\n"
        "  +20 pts \u2192 Rejet de wick (liquidité prise)\n"
        "  +10 pts \u2192 Momentum (bougie précédente)\n"
        "  +5+5 pts \u2192 Confirmation \u0026 englobante\n\n" +
        "\u2501" * 20 + "\n"
        "\U0001f513 FREE : {} sig/j\n"
        "\U0001f4a0 PRO  : max {}/j + rapports complets\n\n"
        "\u26a0\ufe0f Risk max 1-2% par trade. Not financial advice.\n\n"
        "\u2705 Suis chaque signal avec discipline \u2014 les TP arrivent !".format(FREE_LIMIT, PRO_LIMIT),
        kb=kb_back())

def _make_pdf_placeholder():
    pages = [
        [("ALPHABOT PRO v8.5 — GUIDE COMPLET", True),
         ("Bot de signaux trading — ICT/SMC — 24 marches — 20 agents IA", False),
         ("", False), ("="*46, False),
         ("1. QU'EST-CE QU'ALPHABOT ?", True), ("", False),
         ("AlphaBot est un bot Telegram automatique qui analyse", False),
         ("24 marches financiers en temps reel grace a 20 agents IA.", False),
         ("", False), ("Marches surveilles :", True),
         ("  Metaux    : XAUUSD (Or), XAGUSD (Argent)", False),
         ("  Crypto    : BTCUSD ETHUSD SOLUSD BNBUSD XRPUSD", False),
         ("  Forex     : EURUSD GBPUSD USDJPY GBPJPY + 6 autres", False),
         ("  Indices   : NAS100 SPX500 US30 UK100 GER40", False),
         ("  Energie   : USOIL NATGAS", False)],
        [("2. METHODE ICT / SMC", True), ("", False),
         ("ETAPE 1 : H1 BIAS (BOS / CHoCH)", True),
         ("  BOS = Break of Structure (continuation)", False),
         ("  CHoCH = Change of Character (retournement)", False),
         ("", False), ("ETAPE 2 : BREAKER BLOCK M5", True),
         ("  Zone d'entree issue d'une bougie invalidee.", False),
         ("", False), ("ETAPE 3 : SCORE (sur 100 pts)", True),
         ("  +35 pts : Direction bougie (sens du bias)", False),
         ("  +25 pts : Corps > 50% du range (displacement)", False),
         ("  +20 pts : Rejet de wick (liquidite prise)", False),
         ("  +10 pts : Momentum (bougie precedente)", False),
         ("  +5+5 pts : Confirmation & englobante", False),
         ("", False), ("ETAPE 4 : SL / TP AUTOMATIQUES", True),
         ("  SL = bas/haut du Breaker +/- ATR x 0.15", False),
         ("  TP = SL etendu au RR >= 2.5", False)],
        [("3. SIGNAUX EN DIRECT (LIVE)", True), ("", False),
         ("Les donnees sont verifiees en temps reel.", False),
         ("Si les donnees ont plus de 15 min, le signal est rejete.", False),
         ("Chaque signal affiche sa validite en minutes.", False),
         ("", False), ("4. PLANS FREE ET PRO", True), ("", False),
         ("Plan FREE : 2 signaux/jour, lot 0.01", False),
         ("Plan PRO : max 10/j, lots 0.01+0.10+1.00, rapports", False),
         ("", False), ("5. DEVENIR PRO", True), ("", False),
         ("Option 1 : 10$ USDT TRC20 -> Acces immediat", False),
         ("Option 2 : 30 filleuls = 3 mois PRO gratuit", False),
         ("Activation automatique dans les 2 minutes !", False)],
        [("6. GESTION DU RISQUE", True), ("", False),
         ("REGLE D'OR : Max 1-2% du capital par trade", False),
         ("  Capital 500$  : max 5-10$ par trade", False),
         ("  Capital 1000$ : max 10-20$ par trade", False),
         ("  Capital 5000$ : max 50-100$ par trade", False),
         ("", False), ("7. GLOSSAIRE ICT/SMC", True), ("", False),
         ("BOS  : Break of Structure — continuation", False),
         ("CHoCH: Change of Character — retournement", False),
         ("ATR  : Average True Range (volatilite)", False),
         ("RR   : Risque/Recompense — min 2.5", False),
         ("Breaker Block : Zone d'entree cle", False),
         ("Displacement : Bougie corps > 50% du range", False)],
        [("8. COMMANDES TELEGRAM", True), ("", False),
         ("  /start    : Menu principal + inscription", False),
         ("  /pay      : Paiement PRO (10$ USDT)", False),
         ("  /txhash   : Soumettre un TX Hash", False),
         ("  /ref      : Lien parrainage + texte promo", False),
         ("  /account  : Mon compte + statut PRO", False),
         ("  /guide    : Ce guide + PDF", False),
         ("  /broker   : Lien broker Exness", False),
         ("  /support  : Contacter l'admin @leaderOdg", False),
         ("", False), ("  --- Commandes Admin ---", True),
         ("  /activate /degrade /testfree /testpro", False),
         ("  /scan /debug /resetcount /monstatus", False),
         ("  /stats /membres /marches", False),
         ("", False), ("AlphaBot PRO v8.5 — @AlphaBotForexBot", True),
         ("Not financial advice — Risk 1-2% max par trade", False)],
    ]
    def build_page(lines_text):
        cl = ["BT"]; y = 780
        for text, bold in lines_text:
            if text == "":
                y -= 7; continue
            size = 11 if bold else 8
            safe = text.replace("\\","\\\\").replace("(","\\(").replace(")","\\)")
            safe = safe.encode("latin-1", errors="replace").decode("latin-1")
            cl.append("/F1 {} Tf".format(size))
            cl.append("30 {} Td".format(y))
            cl.append("({}) Tj".format(safe))
            cl.append("0 0 Td")
            y -= (13 if bold else 11)
            if y < 40: y = 780
        cl.append("ET")
        return "\n".join(cl).encode("latin-1", errors="replace")
    objects = []
    nb = len(pages)
    objects.append(b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n")
    kids = " ".join("{} 0 R".format(i * 3 + 3) for i in range(nb))
    objects.append("2 0 obj\n<< /Type /Pages /Kids [{}] /Count {} >>\nendobj\n".format(kids, nb).encode())
    for i, page_lines in enumerate(pages):
        pg_content = build_page(page_lines)
        pg_obj_id  = i * 3 + 3
        cont_id    = pg_obj_id + 1
        font_id    = pg_obj_id + 2
        objects.append(("{} 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] "
            "/Contents {} 0 R /Resources << /Font << /F1 {} 0 R >> >> >>\nendobj\n"
        ).format(pg_obj_id, cont_id, font_id).encode())
        stream = b"stream\n" + pg_content + b"\nendstream"
        objects.append(("{} 0 obj\n<< /Length {} >>\n".format(cont_id, len(pg_content))
        ).encode() + stream + b"\nendobj\n")
        objects.append(("{} 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica "
            "/Encoding /WinAnsiEncoding >>\nendobj\n").format(font_id).encode())
    pdf = b"%PDF-1.4\n"; offsets = []
    for obj in objects:
        offsets.append(len(pdf)); pdf += obj
    xref = len(pdf)
    pdf += "xref\n0 {}\n".format(len(objects) + 1).encode()
    pdf += b"0000000000 65535 f \n"
    for off in offsets:
        pdf += "{:010d} 00000 n \n".format(off).encode()
    pdf += "trailer\n<< /Size {} /Root 1 0 R >>\n".format(len(objects) + 1).encode()
    pdf += "startxref\n{}\n%%EOF".format(xref).encode()
    return pdf


# ═══════════════════════════════════════════════════════════════
#  ⑨ PAIEMENT USDT (TronScan)
# ═══════════════════════════════════════════════════════════════
def verify_tx(tx_hash):
    urls = [
        "https://apilist.tronscanapi.com/api/transaction-info?hash={}".format(tx_hash),
        "https://apilist2.tronscanapi.com/api/transaction-info?hash={}".format(tx_hash),
        "https://apilist3.tronscanapi.com/api/transaction-info?hash={}".format(tx_hash),
    ]
    network_errors = 0
    for url in urls:
        for attempt in range(2):
            try:
                body = json.loads(http_get(url, timeout=10))
                for t in body.get("trc20TransferInfo", []):
                    if (t.get("to_address", "").lower() == USDT_ADDRESS.lower()
                            and t.get("symbol", "").upper() == "USDT"):
                        amount = float(t.get("amount_str", "0")) / 1e6
                        if amount >= PRO_PROMO * 0.95:
                            return True, round(amount, 2)
                cd = body.get("contractData", {})
                if cd.get("to_address", "").lower() == USDT_ADDRESS.lower():
                    amount = float(cd.get("amount", 0)) / 1e6
                    if amount >= PRO_PROMO * 0.95:
                        return True, round(amount, 2)
                if body.get("hash") or body.get("txID"):
                    return False, 0
            except Exception as ex:
                err = str(ex)
                # Erreur réseau/DNS → inutile de réessayer les autres URLs
                if "No address associated" in err or "Name or service" in err or "Errno 7" in err:
                    network_errors += 1
                    log("WARN", clr("TronScan inaccessible (réseau) — vérification manuelle requise", "yellow"))
                    return None, 0  # None = erreur réseau (pas False = hash invalide)
                if attempt == 0: time.sleep(2)
    return False, 0

def handle_txhash(uid, uname, tx_hash):
    db_save_payment(uid, tx_hash)
    tg_send(uid,
        "\u2705 <b>Hash reçu !</b>\n\n"
        "\U0001f50d Vérification en cours...\n"
        "<code>{}</code>\n\n"
        "\u23f3 Vérification toutes les 60 sec (max 3 min)".format(tx_hash))
    tg_send(ADMIN_ID,
        "\U0001f4b0 <b>PAIEMENT EN ATTENTE</b>\n"
        "@{} <code>{}</code>\n<code>{}</code>\n"
        "/activate {} (si auto échoue)".format(uname or "?", uid, tx_hash, uid))
    delays = [5, 60, 120]
    for i, delay in enumerate(delays):
        time.sleep(delay)
        ok, amount = verify_tx(tx_hash)
        if ok:
            db_activate_pro(uid, "USDT_AUTO", days=None)
            tg_send_sticker(uid, STK_WIN)
            tg_send(uid,
                "\U0001f389 <b>PAIEMENT CONFIRMÉ !</b>\n\n"
                "\u2705 {}$ USDT reçu !\n\n"
                "\U0001f4a0 <b>PRO ACTIVÉ À VIE !</b>\n\n"
                "\u2705 Max {} signaux/j\n\u2705 24 paires + crypto week-end\n"
                "\u2705 Rapport quotidien + hebdo\n\u2705 Support @leaderOdg\n\n"
                "\U0001f680 Bienvenue dans AlphaBot PRO !".format(amount, PRO_LIMIT))
            tg_send(ADMIN_ID,
                "\U0001f7e2 <b>AUTO PRO OK</b>: @{} <code>{}</code>  {}$ \u2705".format(
                    uname or "?", uid, amount))
            log("PAY", clr("AUTO PRO: @{} {} — {}$".format(uname, uid, amount), "green"))
            return
        elif i < len(delays) - 1:
            log("INFO", clr("TX non confirmé (tentative {}/3)".format(i + 1), "yellow"))
    tg_send(uid,
        "\u23f3 <b>Vérification en attente</b>\n\n"
        "La transaction n'est pas encore confirmée.\n"
        "L'admin va activer manuellement dans 30 min.\n\n"
        "/support \u2192 @leaderOdg")
    tg_send(ADMIN_ID,
        "\u26a0\ufe0f <b>ACTIVATION MANUELLE REQUISE</b>\n"
        "@{} <code>{}</code>\nHash: <code>{}</code>\n\n"
        "\U0001f6e0 /activate {}".format(uname or "?", uid, tx_hash, uid))


# ═══════════════════════════════════════════════════════════════
#  ⑩ SCAN ICT / SMC — avec vérification fraîcheur données
# ═══════════════════════════════════════════════════════════════
_sent              = set()
_sent_lock         = threading.Lock()
_last_daily        = ""
_last_weekly       = ""
_scan_running = False  # verrou anti-doublon
_admin_test_mode   = ""

def cleanup_sent(date_str):
    global _sent
    with _sent_lock:
        _sent = {k for k in _sent if date_str in k}

def fetch_c(sym, interval, period):
    """
    Récupère les bougies OHLC via Yahoo Finance.
    NOUVEAU : vérifie que les données ont moins de DATA_MAX_AGE_MIN minutes.
    Retourne None si données trop vieilles (signal rejeté = pas de faux signal).
    """
    sym_enc = urllib.parse.quote(sym)
    urls = [
        "https://query1.finance.yahoo.com/v8/finance/chart/{}?interval={}&range={}&includePrePost=false".format(sym_enc, interval, period),
        "https://query2.finance.yahoo.com/v8/finance/chart/{}?interval={}&range={}&includePrePost=false".format(sym_enc, interval, period),
        "https://query1.finance.yahoo.com/v8/finance/chart/{}?interval={}&range={}&includePrePost=false&events=history".format(sym_enc, interval, period),
    ]
    for url in urls:
        try:
            body = json.loads(http_get(url, timeout=20))
            res  = body.get("chart", {}).get("result", [])
            if not res: continue

            # ── Vérification fraîcheur (NOUVEAU) ─────────────────
            timestamps = res[0].get("timestamp", [])
            if timestamps:
                last_ts   = timestamps[-1]
                age_min   = (time.time() - last_ts) / 60
                if age_min > DATA_MAX_AGE_MIN:
                    # Données trop vieilles — rejeter pour éviter faux signal
                    log("WARN", clr(
                        "{} {} données âgées de {:.0f}min — rejeté".format(sym, interval, age_min),
                        "yellow"))
                    return None
            # ─────────────────────────────────────────────────────

            q = res[0]["indicators"]["quote"][0]
            c = [
                {"o": float(o), "h": float(h), "l": float(l), "c": float(cv)}
                for o, h, l, cv in zip(
                    q.get("open", []), q.get("high", []),
                    q.get("low",  []), q.get("close", []))
                if None not in (o, h, l, cv)
            ]
            if len(c) >= 15:
                return c
        except:
            continue
    return None

def calc_atr(c, p=14):
    t = [max(c[i]["h"]-c[i]["l"], abs(c[i]["h"]-c[i-1]["c"]), abs(c[i]["l"]-c[i-1]["c"]))
         for i in range(1, len(c))]
    s = t[-p:] if len(t) >= p else t
    return sum(s) / len(s) if s else 0.001

def find_swings(c, n=5):
    H = []; L = []
    for i in range(n, len(c) - n):
        w = c[i-n:i+n+1]
        if c[i]["h"] == max(x["h"] for x in w): H.append((i, c[i]["h"]))
        if c[i]["l"] == min(x["l"] for x in w): L.append((i, c[i]["l"]))
    return H, L

def detect_fvg(c, bias, lookback=40):
    """
    FVG / Fair Value Gap : déséquilibre entre 3 bougies consécutives.
    Bullish FVG  : high[i-1] < low[i+1]  → gap non comblé → zone d'achat
    Bearish FVG  : low[i-1]  > high[i+1] → gap non comblé → zone de vente
    Retourne (fvg_bottom, fvg_top) si le prix revient dans la zone, sinon None.
    """
    if len(c) < 3: return None
    scan = c[-lookback:] if len(c) > lookback else c
    lp   = c[-1]["c"]
    best = None
    for i in range(1, len(scan) - 1):
        if bias == "BULLISH":
            fvg_lo = scan[i - 1]["h"]
            fvg_hi = scan[i + 1]["l"]
            if fvg_hi > fvg_lo:
                # Prix revient dans le gap (pullback dans le FVG)
                if fvg_lo * 0.998 <= lp <= fvg_hi * 1.002:
                    size = fvg_hi - fvg_lo
                    if best is None or size > (best[1] - best[0]):
                        best = (fvg_lo, fvg_hi)
        else:
            fvg_hi = scan[i - 1]["l"]
            fvg_lo = scan[i + 1]["h"]
            if fvg_hi > fvg_lo:
                if fvg_lo * 0.998 <= lp <= fvg_hi * 1.002:
                    size = fvg_hi - fvg_lo
                    if best is None or size > (best[1] - best[0]):
                        best = (fvg_lo, fvg_hi)
    return best  # (bottom, top) ou None

def is_clean_bos(c, bias):
    """
    BOS Pur / Continuation propre :
    - Bougie de cassure avec corps > 60% du range (forte)
    - Casse un swing high/low précédent clairement
    - Signe d'un momentum directionnel solide
    """
    if len(c) < 6: return False
    H, L = find_swings(c, n=3)
    if len(H) < 2 or len(L) < 2: return False
    # Analyser les 6 dernières bougies pour trouver la cassure propre
    for i in range(-6, -1):
        try:
            ci       = c[i]
            body     = abs(ci["c"] - ci["o"])
            rng      = ci["h"] - ci["l"]
            if rng == 0: continue
            body_pct = body / rng
            if bias == "BULLISH":
                # Grande bougie haussière qui casse un swing high
                if ci["c"] > ci["o"] and body_pct > 0.60:
                    if len(H) >= 2 and ci["c"] > H[-2][1]:
                        return True
            else:
                # Grande bougie baissière qui casse un swing low
                if ci["c"] < ci["o"] and body_pct > 0.60:
                    if len(L) >= 2 and ci["c"] < L[-2][1]:
                        return True
        except: continue
    return False


# ═══════════════════════════════════════════════════════════════
#  ICT v2 — EQH/EQL · CHoCH multiple · OTE 61.8% · M15
# ═══════════════════════════════════════════════════════════════

def detect_eqh_eql(c, tolerance=0.0003):
    """Détecte Equal Highs / Equal Lows — zones de liquidité ciblées en TP."""
    highs = [x["h"] for x in c[-40:]]
    lows  = [x["l"] for x in c[-40:]]
    eqh = eql = None
    for i in range(len(highs)-1):
        for j in range(i+1, len(highs)):
            if highs[i] and abs(highs[i]-highs[j])/highs[i] <= tolerance:
                eqh = max(highs[i], highs[j]); break
        if eqh: break
    for i in range(len(lows)-1):
        for j in range(i+1, len(lows)):
            if lows[i] and abs(lows[i]-lows[j])/lows[i] <= tolerance:
                eql = min(lows[i], lows[j]); break
        if eql: break
    return eqh, eql

def count_choch_sequence(c):
    """Compte les CHoCH consécutifs — CHoCH x2+ = retournement fort."""
    if len(c) < 20: return None, 0
    H, L = find_swings(c, n=3)
    if len(H) < 3 or len(L) < 3: return None, 0
    bear = bull = 0
    for k in range(min(3, len(H)-1)):
        if H[-(k+1)][1] < H[-(k+2)][1]: bear += 1
        else: break
    for k in range(min(3, len(L)-1)):
        if L[-(k+1)][1] > L[-(k+2)][1]: bull += 1
        else: break
    if bear >= 2: return "BEARISH", bear
    if bull >= 2: return "BULLISH", bull
    if bear == 1: return "BEARISH", 1
    if bull == 1: return "BULLISH", 1
    return None, 0

def get_ote_zone(swing_high, swing_low, bias):
    """Zone OTE 61.8%–78.6% de Fibonacci."""
    rng = swing_high - swing_low
    if rng <= 0: return None, None
    if bias == "BULLISH": return swing_high - rng*0.786, swing_high - rng*0.618
    return swing_low + rng*0.618, swing_low + rng*0.786

def is_in_discount_premium(price, swing_high, swing_low, bias):
    """Vérifie si le prix est en zone Discount (BUY) ou Premium (SELL)."""
    rng = swing_high - swing_low
    if rng <= 0: return True
    pct = (price - swing_low) / rng
    return pct <= 0.50 if bias == "BULLISH" else pct >= 0.50

def detect_bias(c):
    H, L   = find_swings(c, n=3)
    last   = c[-1]["c"]
    closes = [x["c"] for x in c]
    # CHoCH multiple = signal fort prioritaire
    choch_dir, choch_count = count_choch_sequence(c)
    if choch_count >= 2:
        if choch_dir == "BEARISH": return "BEARISH", min(x["l"] for x in c[-10:]), "CHoCHx{}".format(choch_count)
        if choch_dir == "BULLISH": return "BULLISH", max(x["h"] for x in c[-10:]), "CHoCHx{}".format(choch_count)
    if len(H) >= 2 and len(L) >= 2:
        sh1, sh2 = H[-1][1], H[-2][1]
        sl1, sl2 = L[-1][1], L[-2][1]
        if sh1 > sh2 and sl1 > sl2 and last > sh2: return "BULLISH", sh1, "BOS"
        if sh1 < sh2 and sl1 < sl2 and last < sl2: return "BEARISH", sl1, "BOS"
        if last > sh1 and sl1 > sl2:               return "BULLISH", sh1, "CHoCH"
        if last < sl1 and sh1 < sh2:               return "BEARISH", sl1, "CHoCH"
    eqh, eql = detect_eqh_eql(c)
    if eqh and last < eqh * 0.998: return "BEARISH", eqh, "EQH"
    if eql and last > eql * 1.002: return "BULLISH", eql, "EQL"
    ema20 = sum(closes[-20:]) / 20 if len(closes) >= 20 else closes[-1]
    ema50 = sum(closes[-50:]) / 50 if len(closes) >= 50 else closes[-1]
    if last > ema20 and ema20 > ema50: return "BULLISH", max(x["h"] for x in c[-10:]), "TREND"
    if last < ema20 and ema20 < ema50: return "BEARISH", min(x["l"] for x in c[-10:]), "TREND"
    if len(closes) >= 8:
        slope = (closes[-1] - closes[-8]) / closes[-8]
        if slope >  0.0005: return "BULLISH", max(x["h"] for x in c[-8:]), "TREND"
        if slope < -0.0005: return "BEARISH", min(x["l"] for x in c[-8:]), "TREND"
    if len(c) >= 3:
        bull = sum(1 for x in c[-3:] if x["c"] > x["o"])
        if bull >= 2: return "BULLISH", max(x["h"] for x in c[-5:]), "TREND"
        if bull == 0: return "BEARISH", min(x["l"] for x in c[-5:]), "TREND"
    return "NEUTRAL", None, None

def find_breakers(c, b, lookback=120):
    last = c[-1]["c"]; res = []; atr = calc_atr(c)
    scan = c[-lookback:] if len(c) > lookback else c
    for i in range(2, len(scan) - 2):
        ci = scan[i]; co = ci["o"]; cc = ci["c"]; fut = scan[i+1:]
        if b == "BULLISH":
            if cc >= co: continue
            if not any(f["c"] > co for f in fut): continue
            if cc - atr * 3 <= last <= co + atr * 3:
                res.append({"top": co, "bottom": cc, "strength": abs(co - cc),
                            "dist": abs(last - (co + cc) / 2)})
        else:
            if cc <= co: continue
            if not any(f["c"] < co for f in fut): continue
            if co - atr * 3 <= last <= cc + atr * 3:
                res.append({"top": cc, "bottom": co, "strength": abs(cc - co),
                            "dist": abs(last - (co + cc) / 2)})
    res.sort(key=lambda x: (-x["strength"], x["dist"]))
    return res

def check_conf(c, b):
    if len(c) < 3: return 0
    c1 = c[-1]; c2 = c[-2]; c3 = c[-3]
    o = c1["o"]; cc = c1["c"]; h = c1["h"]; l = c1["l"]
    body = abs(cc - o); rng = h - l
    if rng == 0: return 0
    ratio = body / rng; s = 0
    if b == "BULLISH":
        if cc > o:                       s += 35
        if ratio > 0.5:                  s += 25
        if min(o,cc) - l > body * 0.15: s += 20
        if c2["c"] < cc:                 s += 10
        if c3["c"] < c2["c"]:           s +=  5
        if cc > c2["h"]:                 s +=  5
    else:
        if cc < o:                        s += 35
        if ratio > 0.5:                   s += 25
        if h - max(o,cc) > body * 0.15:  s += 20
        if c2["c"] > cc:                  s += 10
        if c3["c"] > c2["c"]:            s +=  5
        if cc < c2["l"]:                  s +=  5
    # Bonus ICT v2
    choch_dir, choch_count = count_choch_sequence(c)
    if choch_count >= 2 and choch_dir == b: s += min(15, choch_count * 7)
    eqh, eql = detect_eqh_eql(c)
    lp = c[-1]["c"]
    if b == "BEARISH" and eqh and abs(lp-eqh)/eqh < 0.005: s += 10
    if b == "BULLISH" and eql and abs(lp-eql)/eql < 0.005: s += 10
    return min(s, 110)

def agent_analyze(m, score_min_base, news_ok, result_queue):
    try:
        h1 = fetch_c(m["sym"], "1h", "30d") or fetch_c(m["sym"], "4h", "60d")
        if not h1 or len(h1) < 10:
            result_queue.put({"name": m["name"], "cat": m["cat"],
                              "found": False, "reason": "H1 insuffisant"}); return
        b, bos, bt = detect_bias(h1)
        if b == "NEUTRAL":
            result_queue.put({"name": m["name"], "cat": m["cat"],
                              "found": False, "reason": "Marché neutre"}); return
        time.sleep(0.15)

        # M15 confirmation ICT v2
        m15_conf = False
        m15 = fetch_c(m["sym"], "15m", "10d")
        if m15 and len(m15) >= 10:
            m15_b, _, _ = detect_bias(m15)
            _, m15_choch = count_choch_sequence(m15)
            if m15_b != "NEUTRAL" and m15_b != b and m15_choch >= 2:
                result_queue.put({"name": m["name"], "cat": m["cat"],
                                  "found": False, "reason": "M15 CHoCHx{} contre H1".format(m15_choch)}); return
            m15_conf = (m15_b == b)
        time.sleep(0.10)

        # M5 avec vérification fraîcheur
        m5 = fetch_c(m["sym"], "5m", "5d") or fetch_c(m["sym"], "15m", "10d")
        if not m5 or len(m5) < 10:
            result_queue.put({"name": m["name"], "cat": m["cat"],
                              "found": False, "reason": "Données trop vieilles ou indispo"}); return

        # OTE / Discount-Premium
        sh_h1 = max(x["h"] for x in h1[-50:]); sl_h1 = min(x["l"] for x in h1[-50:])
        lp = m5[-1]["c"]
        in_zone = is_in_discount_premium(lp, sh_h1, sl_h1, b)
        ote_lo, ote_hi = get_ote_zone(sh_h1, sl_h1, b)
        in_ote = bool(ote_lo and ote_hi and ote_lo <= lp <= ote_hi)

        bbs = find_breakers(m5, b)
        if not bbs:
            result_queue.put({"name": m["name"], "cat": m["cat"],
                              "found": False, "reason": "Pas de Breaker"}); return

        sc = check_conf(m5, b)
        if in_ote:    sc = min(sc + 12, 115)
        elif in_zone: sc = min(sc + 5,  115)
        if m15_conf:  sc = min(sc + 8,  115)

        # ── FVG / Fair Value Gap ──────────────────────────────
        fvg_zone  = detect_fvg(m5, b)
        if fvg_zone:
            sc = min(sc + 15, 115)  # Fort bonus : prix revient dans le gap

        # ── BOS Pur (continuation propre) ────────────────────
        clean_bos = (bt == "BOS") and is_clean_bos(h1, b)
        if clean_bos:
            sc = min(sc + 10, 115)  # Bonus cassure propre avec momentum

        atr       = calc_atr(m5)
        atr_pct   = atr / (m5[-1]["c"] + 0.0001)
        atr_ratio = min(1.0, atr_pct * 100)
        score_min = score_min_for_market(m, score_min_base, atr_ratio)

        if sc < score_min:
            result_queue.put({"name": m["name"], "cat": m["cat"],
                              "found": False, "reason": "Score {}/{}".format(sc, score_min)}); return
        if not news_ok and sc < score_min + 8:
            result_queue.put({"name": m["name"], "cat": m["cat"],
                              "found": False, "reason": "News HIGH bloquée"}); return

        last5 = [abs(x["h"] - x["l"]) for x in m5[-5:] if x["h"] != x["l"]]
        sp    = round(min(last5) / m["pip"] * 0.03, 2) if last5 else 0.0
        if sp > m["max_sp"] * 1.5:
            result_queue.put({"name": m["name"], "cat": m["cat"],
                              "found": False, "reason": "Spread large {:.1f}p".format(sp)}); return

        bb = bbs[0]; e = lp; buf = atr * 0.15; sp_price = sp * m["pip"]
        eqh, eql = detect_eqh_eql(m5)
        if b == "BULLISH":
            sl   = bb["bottom"] - buf - sp_price
            risk = e - sl
            if risk <= 0 or risk > atr * 10:
                result_queue.put({"name": m["name"], "cat": m["cat"],
                                  "found": False, "reason": "Risque invalide"}); return
            tp = (eqh * 0.9995) if (eqh and e < eqh < e + risk*5) else (e + risk * 2.5)
        else:
            sl   = bb["top"] + buf + sp_price
            risk = sl - e
            if risk <= 0 or risk > atr * 10:
                result_queue.put({"name": m["name"], "cat": m["cat"],
                                  "found": False, "reason": "Risque invalide"}); return
            tp = (eql * 1.0005) if (eql and e - risk*5 < eql < e) else (e - risk * 2.5)

        gain_net = abs(tp - e) - sp_price
        rr       = round(gain_net / risk, 1)
        if rr < 2.5:
            result_queue.put({"name": m["name"], "cat": m["cat"],
                              "found": False,
                              "reason": "RR net 1:{} < 2.5 (spread {:.1f}p)".format(rr, sp)}); return

        dp  = 2 if e > 1000 else (3 if e > 10 else 5)
        f   = lambda v: round(v, dp)
        pip = m["pip"]
        ptp = gain_net / pip
        psl = abs(sl - e) / pip

        badges = []
        if in_ote:    badges.append("OTE 61.8%")
        if m15_conf:  badges.append("M15 ✓")
        if eqh or eql: badges.append("EQ Level")
        if fvg_zone:  badges.append("FVG ✓")
        if clean_bos: badges.append("BOS Pur ✓")
        sig = {
            "name": m["name"], "cat": m["cat"],
            "side": "BUY" if b == "BULLISH" else "SELL",
            "entry": f(e), "sl": f(sl), "tp": f(tp),
            "rr": rr, "score": sc, "score_min": score_min,
            "bias": b, "btype": bt, "bos": f(bos) if bos else 0,
            "bb_top": f(bb["top"]), "bb_bot": f(bb["bottom"]),
            "atr": round(atr, dp + 1), "sp": sp,
            "g001": round(ptp * 0.1,  2), "l001": round(psl * 0.1,  2),
            "g01":  round(ptp * 1.0,  2), "l01":  round(psl * 1.0,  2),
            "g1":   round(ptp * 10,   2), "l1":   round(psl * 10,   2),
            "time": datetime.now(timezone.utc).replace(tzinfo=None).strftime("%H:%M"),
            "ts":   time.time(),
            "badges": "  ".join(badges),
        }
        result_queue.put({"name": m["name"], "cat": m["cat"], "found": True, "signal": sig})

    except Exception as ex:
        result_queue.put({"name": m["name"], "cat": m["cat"],
                          "found": False, "reason": "Erreur: {}".format(str(ex)[:40])})

_ncache = []; _ntime = 0

def news_check():
    global _ncache, _ntime
    if time.time() - _ntime < 1800 and _ncache:
        return False, "\u26a0\ufe0f " + " | ".join(_ncache[:2])
    try:
        body   = json.loads(http_get("https://nfs.faireconomy.media/ff_calendar_thisweek.json"))
        now_dt = datetime.now(timezone.utc).replace(tzinfo=None)
        hi     = []
        for ev in body:
            if ev.get("impact", "").upper() != "HIGH": continue
            try:
                t = datetime.strptime(ev["date"], "%Y-%m-%dT%H:%M:%S%z").replace(tzinfo=None)
                if abs((t - now_dt).total_seconds()) < 7200:
                    hi.append(ev.get("title", ""))
            except: pass
        _ncache = hi; _ntime = time.time()
        if hi: return False, "\u26a0\ufe0f " + " | ".join(hi[:2])
    except: pass
    return True, "\u2705 Clear"

def _signal_validity(sig):
    """
    Calcule la validité restante du signal en minutes.
    Un signal M5 est valable ~3 bougies = 15 min.
    """
    age_sec  = time.time() - sig.get("ts", time.time())
    age_min  = age_sec / 60
    validity = max(0, int(DATA_MAX_AGE_MIN - age_min))
    return validity

def fmt_signal_free(s, news, sl):
    emo      = CAT_EMO.get(s["cat"], "\U0001f4ca")
    se       = "\U0001f7e2" if s["side"] == "BUY" else "\U0001f534"
    d        = "\u2b06\ufe0f" if s["side"] == "BUY" else "\u2b07\ufe0f"
    sf       = "ACHAT" if s["side"] == "BUY" else "VENTE"
    bar      = "\u2588" * (s["score"] // 10) + "\u2591" * (10 - s["score"] // 10)
    news_ok  = "\u2705" in news or "clear" in news.lower()
    validity = _signal_validity(s)
    valid_str = ("\u23f3 <b>Entrée valide ~{}min</b>".format(validity)
                 if validity > 0 else "\u274c <b>Entrée expirée \u2014 ne pas trader</b>")
    return (
        "{se} {d} <b>SIGNAL {sf} \u2014 {name}</b>  {emo}\n" +
        "\u2550" * 22 + "\n\n"
        "\U0001f553 {sl}  \u00b7  {time} UTC\n"
        "{valid}\n\n"
        "\U0001f3af <b>NIVEAUX DU TRADE</b>\n"
        "  \U0001f4cd Entrée   : <code>{entry}</code>\n"
        "  \u2705 Cible TP : <code>{tp}</code>  {d}  <b>+${g001}</b> (lot 0.01)\n"
        "  \u274c Stop SL  : <code>{sl_v}</code>  \u2014  -${l001} (lot 0.01)\n"
        "  \U0001f4ca RR ratio : <b>1:{rr}</b>\n\n"
        "\U0001f4ca Score IA : <b>{score}/100</b>  [{bar}]\n"
        "\U0001f9e0 {bias}  \u00b7  {btype}  \u00b7  News : {news_s}\n\n" +
        "\u2501" * 22 + "\n"
        "\U0001f4a0 <b>PASSE EN PRO \u2014 VOIS TOUT !</b>\n"
        "  \U0001f4b0 Lot 0.10 \u2192 <b>+${g01}</b> par TP  |  Lot 1.00 \u2192 <b>+${g1}</b> par TP\n"
        "  \u2705 Max {pro_lim} signaux/j  \u00b7  Analyse compl\u00e8te ICT v2\n"
        "  \u2705 Rapports quotidiens + hebdo  \u00b7  24 paires\n"
        "  \U0001f449 /pay \u2014 {}$ USDT seulement \u00b7  Not financial advice".format(
            PRO_PROMO)
    ).format(
        se=se, d=d, sf=sf, name=s["name"], emo=emo, sl=sl,
        time=s["time"], valid=valid_str,
        entry=s["entry"], tp=s["tp"], sl_v=s["sl"], rr=s["rr"],
        g001=s["g001"], l001=s["l001"], g01=s["g01"], g1=s["g1"],
        score=s["score"], bar=bar, bias=s["bias"], btype=s["btype"],
        pro_lim=PRO_LIMIT,
        news_s="\u2705 OK" if news_ok else "\u26a0\ufe0f Actif")

def fmt_signal_pro(s, news, sl):
    emo    = CAT_EMO.get(s["cat"], "\U0001f4ca")
    cname  = CAT_NAME.get(s["cat"], s["cat"])
    se     = "\U0001f7e2" if s["side"] == "BUY" else "\U0001f534"
    d      = "\u2b06\ufe0f" if s["side"] == "BUY" else "\u2b07\ufe0f"
    sf     = "ACHAT" if s["side"] == "BUY" else "VENTE"
    btype_fr = ("Continuation (BOS)" if s["btype"] == "BOS" else
                "Renversement (CHoCH)" if s["btype"] == "CHoCH" else "Tendance")
    news_ok  = "\u2705" in news or "clear" in news.lower()
    sp_ok    = s["sp"] < 3
    bar      = "\u2588" * (s["score"] // 10) + "\u2591" * (10 - s["score"] // 10)
    validity = _signal_validity(s)
    valid_str = ("\u23f3 <b>Entrée valide ~{}min</b>".format(validity)
                 if validity > 0 else "\u274c <b>Entrée expirée — ne pas trader</b>")
    return (
        "{se} {d} <b>SIGNAL {sf} \u2014 {name}</b>\n" +
        "\u2550" * 22 + "\n\n"
        "{emo} <b>{name}</b>  \u00b7  {cname}  \u00b7  {sl}  \u00b7  {time} UTC\n"
        "{valid}\n\n"
        "\U0001f3af <b>NIVEAUX</b>\n"
        "  Entrée   : <code>{entry}</code>\n"
        "  Cible TP : <code>{tp}</code>  {d}\n"
        "  Stop SL  : <code>{sl_v}</code>  \u274c\n"
        "  RR ratio : <b>1:{rr}</b>\n\n"
        "\U0001f4b5 <b>GAINS ESTIMÉS</b>\n"
        "  Lot 0.01 \u2192 <b>+${g001}</b>  /  -${l001}\n"
        "  Lot 0.10 \u2192 <b>+${g01}</b>   /  -${l01}\n"
        "  Lot 1.00 \u2192 <b>+${g1}</b>   /  -${l1}  \U0001f4b0\n\n"
        "\U0001f9e0 <b>ANALYSE ICT v2</b>\n"
        "  Tendance : <b>{bias}</b>  \u2014  {btype_fr}\n"
        "  Breaker  : <code>{bb_bot}</code> \u2014 <code>{bb_top}</code>\n"
        "  Score    : <b>{score}/100</b>  [{bar}]  (min {score_min})\n"
        "  ATR M5   : <code>{atr}</code>\n"
        "  {badges_s}\n\n"
        "\U0001f4cb Filtres : {news_s}  \u00b7  {sp_s}\n\n" +
        "\u2550" * 22 + "\n"
        "\u26a0\ufe0f Risk 1% max  \u00b7  Not financial advice\n"
        "\U0001f916 AlphaBot PRO  \u00b7  @AlphaBotForexBot"
    ).format(
        se=se, d=d, sf=sf, name=s["name"], emo=emo, cname=cname, sl=sl,
        time=s["time"], valid=valid_str,
        entry=s["entry"], tp=s["tp"], sl_v=s["sl"], rr=s["rr"],
        g001=s["g001"], l001=s["l001"], g01=s["g01"], l01=s["l01"],
        g1=s["g1"], l1=s["l1"], bias=s["bias"], btype_fr=btype_fr,
        bb_bot=s["bb_bot"], bb_top=s["bb_top"],
        score=s["score"], score_min=s.get("score_min", "?"), bar=bar, atr=s["atr"],
        news_s="\u2705 Pas de news" if news_ok else "\u26a0\ufe0f News actif",
        sp_s="\u2705 Spread OK" if sp_ok else "\u26a0\ufe0f Spread large",
        badges_s=s.get("badges", "") or "\u2014")

def _fmt_scan_report(results, news_lbl, scan_time, sl, score_min, nb_found):
    stats   = db_daily_stats()
    news_ok = "\u2705" in news_lbl or "clear" in news_lbl.lower()
    lines   = [
        "\U0001f50d <b>SCAN {} UTC</b>  \u00b7  {}  \u00b7  {} paires".format(
            scan_time, sl, len(results)),
        "\U0001f3af Score min : <b>{}</b>  \u00b7  News : {}  \u00b7  {} agents".format(
            score_min, "\u2705 OK" if news_ok else "\u26a0\ufe0f Actif", NB_AGENTS),
        "\U0001f4b5 Aujourd'hui : <b>+${}</b> lot1  \u00b7  {} sig  \u00b7  {} gagnants".format(
            stats["total_g1"], stats["sig_count"], stats["wins"]), ""]
    cats = {}
    for r in results:
        cats.setdefault(r.get("cat", "?"), []).append(r)
    for cat in ["METALS", "CRYPTO", "FOREX", "INDICES", "OIL"]:
        if cat not in cats: continue
        emo = CAT_EMO.get(cat, "\U0001f4ca")
        lines.append("{} <b>{}</b>".format(emo, cat))
        for r in cats[cat]:
            if r["found"]:
                s  = r["signal"]
                se = "\U0001f7e2" if s["side"] == "BUY" else "\U0001f534"
                sf = "ACHAT" if s["side"] == "BUY" else "VENTE"
                lines.append("  {} <b>{}</b>  {}  RR 1:{}  {}/100  +${} lot1".format(
                    se, r["name"], sf, s["rr"], s["score"], s.get("g1", 0)))
                lines.append("  \U0001f4cd <code>{}</code> \u2192 TP <code>{}</code>  SL <code>{}</code>".format(
                    s["entry"], s["tp"], s["sl"]))
            else:
                lines.append("  \u26aa <b>{}</b>  {}".format(r["name"], r.get("reason", "?")))
        lines.append("")
    lines.append("\u2550" * 22)
    lines.append("\U0001f7e2 <b>{} signal(s) envoyé(s) !</b>".format(nb_found) if nb_found
                 else "\U0001f7e1 Aucun signal ce cycle")
    lines.append("\U0001f504 Prochain scan dans ~4 min  \u00b7  AlphaBot PRO")
    return "\n".join(lines)

def _fmt_daily_report(stats):
    date_fr = datetime.strptime(stats["date"], "%Y-%m-%d").strftime("%d/%m/%Y")
    sc = stats["sig_count"]; w = stats["wins"]; l = stats.get("losses", sc - w)
    if sc == 0:
        return "\U0001f4ca <b>RAPPORT {}</b>\n\nAucun signal aujourd'hui.".format(date_fr)
    wr   = int(w / sc * 100)
    perf = "\U0001f525\U0001f525" if stats["total_g1"] > 2000 else \
           "\U0001f525" if stats["total_g1"] > 1000 else "\U0001f4b0"
    lines = [
        "\U0001f4af <b>RAPPORT DU JOUR \u2014 AlphaBot PRO</b> {}".format(perf),
        "\u2550" * 22,
        "\U0001f4c5 {}  \u00b7  Session fermée".format(date_fr), "",
        "\U0001f3af <b>RÉSULTATS</b>",
        "  \u2705 TP atteints : <b>{}</b>  |  \u274c SL touchés : <b>{}</b>  |  {}% réussite".format(w, l, wr),
        "  \U0001f4b5 Lot 0.01 : <b>+${}</b>  \u00b7  Lot 1.00 : <b>+${}</b>".format(
            stats["total_g001"], stats["total_g1"]),
        "", "\u2501" * 22,
        "\U0001f4cb <b>DÉTAIL DES TRADES</b>", ""]
    for row in stats["rows"]:
        pair, side, rr, g001, g1, l001, l1, session = row[0], row[1], row[2], row[3], row[4], row[5], row[6], row[7]
        entry = row[8] if len(row) > 8 else "—"
        tp    = row[9] if len(row) > 9 else "—"
        sl    = row[10] if len(row) > 10 else "—"
        ok    = rr >= 3.0
        icon  = "\u2705 TP" if ok else "\u274c SL"
        d     = "\u2b06\ufe0f" if side == "BUY" else "\u2b07\ufe0f"
        result = "+${:.0f}".format(g1) if ok else "-${:.0f}".format(l1)
        lines.append("{} <b>{}</b>  {} {}  RR 1:{}  \u2192 <b>{}</b>".format(
            icon, pair, d, side, rr, result))
        lines.append("   \U0001f4cd Entrée <code>{}</code>  \u2192  TP <code>{}</code>  SL <code>{}</code>".format(
            entry, tp, sl))
        lines.append("")
    lines += ["\u2550" * 22,
              "\U0001f4e9 Rejoins AlphaBot PRO \u2014 {}$ USDT".format(PRO_PROMO),
              "\U0001f449 @AlphaBotForexBot",
              "\u26a0\ufe0f Not financial advice  \u00b7  Risk 1% max"]
    return "\n".join(lines)

def _fmt_weekly_report(stats):
    sc = stats["sig_count"]; w = stats["wins"]
    if sc == 0:
        return "\U0001f4ca <b>RAPPORT HEBDO</b>\n\nAucun signal cette semaine."
    wr   = int(w / sc * 100) if sc else 0
    perf = "\U0001f525\U0001f525" if stats["total_g1"] > 10000 else \
           "\U0001f525" if stats["total_g1"] > 5000 else "\U0001f4b0"
    return (
        "\U0001f3c6 <b>RAPPORT HEBDOMADAIRE \u2014 AlphaBot PRO</b> {}\n".format(perf) +
        "\u2550" * 22 + "\n\n" +
        "\U0001f4c5 Semaine du {}\n\n"
        "\U0001f4b5 <b>LOT 0.01 : +${}</b>\n"
        "\U0001f4b0 <b>LOT 1.00 : +${}</b>\n\n"
        "\U0001f4ca {} signaux  \u00b7  {} gagnants  \u00b7  {}% réussite\n\n".format(
            stats["week_start"], stats["total_g001"], stats["total_g1"], sc, w, wr) +
        "\u2550" * 22 + "\n"
        "\U0001f4e9 Rejoins AlphaBot PRO\n"
        "\U0001f449 @AlphaBotForexBot \u2014 {}$ USDT\n\n"
        "\u26a0\ufe0f Not financial advice  \u00b7  Risk 1% max".format(PRO_PROMO)
    )

def scan_and_send():
    global _sent, _last_daily, _last_weekly, _last_scan_results, _scan_running
    if _scan_running:
        log("INFO", clr("Scan déjà en cours — ignoré.", "dim"))
        return
    _scan_running = True
    try:
        _scan_and_send_inner()
    finally:
        _scan_running = False

def _scan_and_send_inner():
    global _sent, _last_daily, _last_weekly, _last_scan_results

    now_dt    = datetime.now(timezone.utc).replace(tzinfo=None)
    scan_time = now_dt.strftime("%H:%M")
    date_str  = now_dt.strftime("%Y-%m-%d")
    hour_str  = now_dt.strftime("%H")
    wday      = now_dt.weekday()

    sn, sm, sl, wknd = get_session()
    log("INFO", clr("Scan {} — {} — Score ~{}  [{} marchés]".format(
        scan_time, sl, sm, len(MARKETS)), "dim"))
    news_ok, news_lbl = news_check()

    active_markets = [m for m in MARKETS if not wknd or m.get("crypto", False)]
    if wknd:
        log("INFO", clr("Week-end : {} marchés crypto".format(len(active_markets)), "yellow"))

    result_queue = Queue()
    threads = []
    for i in range(0, len(active_markets), NB_AGENTS):
        batch = active_markets[i:i + NB_AGENTS]
        for m in batch:
            t = threading.Thread(
                target=agent_analyze,
                args=(m, sm, news_ok, result_queue), daemon=True)
            t.start(); threads.append(t)
    for t in threads:
        t.join(timeout=12)

    raw = {}
    while not result_queue.empty():
        try: r = result_queue.get_nowait(); raw[r["name"]] = r
        except Empty: break
    results = [raw.get(m["name"], {"name": m["name"], "cat": m["cat"],
                "found": False, "reason": "Timeout"}) for m in active_markets]
    if wknd:
        for m in MARKETS:
            if not m.get("crypto", False):
                results.append({"name": m["name"], "cat": m["cat"],
                                "found": False, "reason": "Fermé le week-end"})

    _last_scan_results = results
    cleanup_sent(date_str)

    sigs_raw = [(r["signal"],
                 "{}-{}-{}-{}".format(r["signal"]["name"], r["signal"]["side"], date_str, hour_str))
                for r in results if r["found"]]
    with _sent_lock:
        sigs_raw = [(s, k) for s, k in sigs_raw if k not in _sent]
    sigs_raw.sort(key=lambda x: -x[0]["score"])

    pro_users  = db_get_pro_users()
    free_users = db_get_free_users()
    pro_users_eff  = [u for u in pro_users if not (u == ADMIN_ID and _admin_test_mode == "FREE")]
    free_users_eff = list(free_users) + (
        [ADMIN_ID] if _admin_test_mode == "FREE" and ADMIN_ID not in free_users else [])

    for sig, key in sigs_raw:
        msg_pro  = fmt_signal_pro(sig, news_lbl, sl)
        msg_free = fmt_signal_free(sig, news_lbl, sl)

        r = tg_send(CHANNEL_ID, msg_free)
        if r.get("ok"):
            with _sent_lock: _sent.add(key)
            db_save_signal(sig, sn)
            sc_txt = clr(sig["side"], "green") if sig["side"] == "BUY" else clr(sig["side"], "red")
            log("SIGNAL", "{} {}  RR 1:{}  Score {}/{}  G1 +${}".format(
                clr(sig["name"], "bold", "white"), sc_txt,
                sig["rr"], sig["score"], sig.get("score_min", "?"), sig["g1"]))

        for puid in pro_users_eff:
            if db_count_today(puid) < PRO_LIMIT:
                tg_send(puid, msg_pro)
                db_count_increment(puid)
                time.sleep(0.04)

        for fuid in free_users_eff:
            c = db_count_today(fuid)
            if c < FREE_LIMIT:
                tg_send(fuid, msg_free)
                db_count_increment(fuid)
                time.sleep(0.04)
            elif c == FREE_LIMIT:
                tg_send(fuid,
                    "\U0001f6d1 <b>Limite FREE : {}/{}</b>\n\n"
                    "Pour signaux illimités : /pay \u2014 {}$ USDT\n"
                    "Ou parraine {} amis = {} mois PRO !".format(
                        FREE_LIMIT, FREE_LIMIT, PRO_PROMO, REF_TARGET, REF_MONTHS))
                db_count_increment(fuid)
                time.sleep(0.04)

    if sigs_raw:
        report = _fmt_scan_report(results, news_lbl, scan_time, sl, sm, len(sigs_raw))
        tg_send(CHANNEL_ID, report)
        tg_send(ADMIN_ID, report)
        for puid in pro_users_eff:
            if puid != ADMIN_ID:
                tg_send(puid, report); time.sleep(0.04)
    else:
        log("INFO", clr("Aucun setup valide ce cycle.", "dim"))

    if int(hour_str) >= DAILY_HOUR and _last_daily != date_str and not db_report_sent(date_str):
        stats = db_daily_stats(date_str)
        if stats["sig_count"] > 0:
            daily = _fmt_daily_report(stats)
            tg_send(CHANNEL_ID, daily)
            for puid in pro_users:
                tg_send(puid, daily); time.sleep(0.04)
            db_mark_report(stats); _last_daily = date_str

    week_key = "{}-W{}".format(now_dt.year, now_dt.isocalendar()[1])
    if (wday == WEEKLY_DAY and int(hour_str) >= WEEKLY_HOUR
            and _last_weekly != week_key
            and not db_report_sent(week_key, "weekly_reports", "week_start")):
        ws = db_weekly_stats()
        if ws["sig_count"] > 0:
            weekly = _fmt_weekly_report(ws)
            tg_send(CHANNEL_ID, weekly)
            for puid in pro_users:
                tg_send(puid, weekly); time.sleep(0.04)
            db_mark_report(ws, "weekly_reports"); _last_weekly = week_key

    expired = db_check_expiry()
    for uid, uname in expired:
        tg_send(uid,
            "\u23f0 <b>PRO expiré</b>\n\n"
            "Renouveler :\n/pay \u2192 {}$ USDT\n"
            "/ref \u2192 {} filleuls = {} mois gratuit".format(PRO_PROMO, REF_TARGET, REF_MONTHS))
        tg_send(ADMIN_ID, "\u23f0 PRO expiré: @{} <code>{}</code>".format(uname or "?", uid))
    if expired:
        log("WARN", clr("{} PRO expiré(s) → FREE".format(len(expired)), "yellow"))


# ═══════════════════════════════════════════════════════════════
#  ⑪ ADMIN
# ═══════════════════════════════════════════════════════════════
def _admin_only(uid):
    if uid != ADMIN_ID:
        tg_send(uid, "\u274c Accès refusé.")
        return False
    return True

def handle_activate(uid, target):
    if not _admin_only(uid): return
    if not target:
        tg_send(uid,
            "\U0001f6e0 <b>ADMIN v8.5</b>\n\n"
            "/activate ID    \u2192 Toggle PRO\u21d4FREE\n"
            "/degrade ID     \u2192 Forcer FREE\n"
            "/testfree       \u2192 Simuler vue FREE\n"
            "/testpro        \u2192 Retour vue PRO\n"
            "/scan           \u2192 Forcer scan immédiat\n"
            "/debug          \u2192 Raisons dernier scan\n"
            "/resetcount [ID]\u2192 Reset compteur signaux\n"
            "/monstatus      \u2192 Statut admin complet\n"
            "/stats          \u2192 Stats + paiements\n"
            "/membres [n]    \u2192 Liste membres paginée")
        return
    try:
        t_uid = int(target) if target.lstrip("@").isdigit() else db_find_by_username(target)
        if not t_uid:
            tg_send(uid, "\u274c Utilisateur introuvable."); return
        plan, exp, src = db_get_pro_info(t_uid)
        con = _conn(); cur = con.cursor()
        cur.execute("SELECT username FROM users WHERE user_id=?", (t_uid,))
        row = cur.fetchone(); con.close()
        uc  = "@" + (row[0] if row and row[0] else str(t_uid))
        if plan == "PRO":
            db_downgrade_pro(t_uid)
            tg_send(t_uid, "\U0001f512 PRO désactivé. Plan : FREE.\n/pay pour revenir PRO.")
            tg_send(uid, "\u2705 {} \u2192 FREE  <code>{}</code>".format(uc, t_uid))
        else:
            db_activate_pro(t_uid, "ADMIN", days=None)
            tg_send(t_uid,
                "\U0001f389 <b>PRO activé !</b>\n\n"
                "\u2705 Max {} signaux/j\n\u2705 24 paires + crypto week-end\n"
                "\u2705 Rapports inclus\n\U0001f680 Bienvenue !".format(PRO_LIMIT))
            tg_send(uid, "\u2705 PRO : {} <code>{}</code>  À VIE".format(uc, t_uid))
    except Exception as ex:
        tg_send(uid, "\u274c {}".format(ex))

def handle_degrade(uid, target):
    if not _admin_only(uid): return
    if not target:
        tg_send(uid, "Usage : /degrade ID"); return
    try:
        t_uid = int(target) if target.lstrip("@").isdigit() else db_find_by_username(target)
        if not t_uid:
            tg_send(uid, "\u274c Introuvable."); return
        db_downgrade_pro(t_uid)
        tg_send(t_uid, "\U0001f512 PRO désactivé. /pay pour revenir.")
        tg_send(uid, "\u2705 FREE : <code>{}</code>".format(t_uid))
    except Exception as ex:
        tg_send(uid, "\u274c {}".format(ex))

def handle_testfree(uid):
    if not _admin_only(uid): return
    global _admin_test_mode
    _admin_test_mode = "FREE"
    tg_send(uid,
        "\U0001f9ea <b>MODE TEST FREE ACTIVÉ</b>\n\n"
        "Tu vois maintenant exactement ce que voit un utilisateur FREE.\n\n"
        "\U0001f513 Limite : <b>{}/j</b>\n"
        "\u26a0\ufe0f Tes vraies données PRO sont préservées.\n\n"
        "Pour tester :\n"
        "\u2022 Clique <b>Mes Signaux</b>\n"
        "\u2022 Clique <b>Mon Compte</b>\n"
        "\u2022 Clique <b>Devenir PRO</b>\n\n"
        "/testpro \u2192 revenir en vue PRO".format(FREE_LIMIT))
    # Montrer directement la vue FREE
    send_account(uid, "leaderOdg", forced_plan="FREE")

def handle_testpro(uid):
    if not _admin_only(uid): return
    global _admin_test_mode
    _admin_test_mode = ""
    tg_send(uid,
        "\U0001f4a0 <b>MODE TEST PRO</b>\n\nVue PRO normale restaurée.\n\n"
        "/testfree \u2192 retester la vue FREE")
    send_account(uid, "leaderOdg", forced_plan="PRO")

def handle_scan(uid):
    if not _admin_only(uid): return
    tg_send(uid, "\U0001f50d <b>Scan forcé lancé...</b>")
    scan_and_send()

def handle_debug(uid):
    if not _admin_only(uid): return
    try:
        results = _last_scan_results
        if not results:
            tg_send(uid, "\U0001f50d Aucun scan encore. Lance /scan d'abord."); return
        lines     = ["\U0001f50d <b>DEBUG — Dernier scan</b>\n"]
        found     = [r for r in results if r.get("found")]
        not_found = [r for r in results if not r.get("found")]
        if found:
            lines.append("\u2705 <b>SIGNAUX ({}):</b>".format(len(found)))
            for r in found:
                s = r["signal"]
                lines.append("  \U0001f7e2 {} {} RR 1:{} Score {}".format(
                    r["name"], s["side"], s["rr"], s["score"]))
            lines.append("")
        lines.append("\u26aa <b>REJETÉS ({}):</b>".format(len(not_found)))
        reasons = {}
        for r in not_found:
            reason = r.get("reason", "?")
            if "insuffisant" in reason or "vieilles" in reason: key = "Données indisponibles/vieilles"
            elif "neutre" in reason.lower():   key = "Marché neutre"
            elif "Breaker" in reason:          key = "Pas de Breaker Block"
            elif "Score" in reason:            key = reason
            elif "Spread" in reason:           key = "Spread trop large"
            elif "Risque" in reason:           key = "Risque invalide"
            elif "RR" in reason:               key = reason
            elif "week" in reason.lower() or "ferme" in reason.lower(): key = "Fermé (week-end)"
            elif "News" in reason:             key = "News HIGH bloquée"
            else:                              key = reason
            reasons.setdefault(key, []).append(r["name"])
        for reason, names in sorted(reasons.items(), key=lambda x: -len(x[1])):
            lines.append("  <b>{}</b> ({}x): {}{}".format(
                reason, len(names), ", ".join(names[:6]),
                "..." if len(names) > 6 else ""))
        msg = "\n".join(lines)
        if len(msg) > 4000: msg = msg[:3900] + "\n...(tronqué)"
        tg_send(uid, msg)
    except Exception as ex:
        tg_send(uid, "\u274c Erreur /debug : {}".format(str(ex)[:100]))

def handle_resetcount(uid, target):
    if not _admin_only(uid): return
    try:
        t_uid = uid if not target else (
            int(target) if target.lstrip("@").isdigit() else db_find_by_username(target))
        if not t_uid:
            tg_send(uid, "\u274c Introuvable."); return
        db_count_reset(t_uid)
        tg_send(uid, "\u2705 Compteur remis à 0 pour <code>{}</code>.".format(t_uid))
    except Exception as ex:
        tg_send(uid, "\u274c {}".format(ex))

def handle_monstatus(uid):
    if not _admin_only(uid): return
    try:
        plan, exp, src      = db_get_pro_info(uid)
        total, pro, sigs, pays, g1d = db_global_stats()
        sn, sm, sl, wknd    = get_session()
        stats               = db_daily_stats()
        ws                  = db_weekly_stats()
        count_today         = db_count_today(uid)
        pending             = db_pending_payments()
        refs                = db_get_refs(uid)
        plan_icon  = "\U0001f4a0" if plan == "PRO" else "\U0001f513"
        exp_str    = "À VIE" if not exp else "Expire le {}".format(exp)
        wknd_str   = "\n\U0001f30d <b>Week-end : crypto uniquement</b>" if wknd else ""
        free_total = total - pro
        win_pct    = int(stats["wins"] / stats["sig_count"] * 100) if stats["sig_count"] > 0 else 0
        test_banner= "\U0001f9ea <b>Mode test : {}</b>\n".format(_admin_test_mode) if _admin_test_mode else ""
        pend_str   = "\n\u23f3 <b>{} paiement(s) en attente !</b> /stats".format(
            len(pending)) if pending else ""
        tg_send(uid,
            test_banner +
            "\U0001f6e1 <b>MON STATUT ADMIN</b>\n" + "\u2550" * 22 + "\n\n"
            "\U0001f194 ID : <code>{}</code>  \u00b7  @leaderOdg\n"
            "{} <b>Plan : {}</b>  \u2014  {}\n\n".format(uid, plan_icon, plan, exp_str) +
            "\u2501" * 20 + "\n"
            "\U0001f553 Session : <b>{}</b>  \u00b7  Score min : <b>{}</b>{}\n\n".format(sl, sm, wknd_str) +
            "\u2501" * 20 + "\n"
            "\U0001f465 <b>MEMBRES</b>  {} total  \u00b7  <b>{} PRO</b>  \u00b7  {} FREE\n"
            "\U0001f4b0 Payés : {}  \u00b7  En attente : {}{}\n"
            "\U0001f4e1 Signaux total : {}\n\n".format(
                total, pro, free_total, pays, len(pending), pend_str, sigs) +
            "\u2501" * 20 + "\n"
            "\U0001f4c5 <b>AUJOURD'HUI</b>\n"
            "  {} sig  \u00b7  {} gagnants ({}%)\n"
            "  Lot 0.01 : +${}  \u00b7  Lot 1.00 : +${}\n\n"
            "\U0001f4c6 <b>CETTE SEMAINE</b>\n"
            "  {} sig  \u00b7  {} gagnants  \u00b7  Lot1 +${}\n\n".format(
                stats["sig_count"], stats["wins"], win_pct,
                stats["total_g001"], stats["total_g1"],
                ws["sig_count"], ws["wins"], ws["total_g1"]) +
            "\u2501" * 20 + "\n"
            "\U0001f6e0 /activate {}  /testfree  /testpro\n"
            "/stats  /membres  /scan  /debug".format(uid))
    except Exception as ex:
        tg_send(uid, "\u274c Erreur /monstatus : {}".format(str(ex)[:100]))

def handle_stats(uid):
    if not _admin_only(uid): return
    try:
        total, pro, sigs, pays, g1d = db_global_stats()
        stats   = db_daily_stats()
        ws      = db_weekly_stats()
        con     = _conn(); cur = con.cursor()
        # FIX: DISTINCT sur user_id pour éviter les doublons
        cur.execute(
            "SELECT user_id, username, ref_count FROM users "
            "GROUP BY user_id ORDER BY ref_count DESC LIMIT 5")
        top = cur.fetchall(); con.close()
        pending = db_pending_payments()
        msg = (
            "\U0001f4ca <b>STATS ALPHABOT PRO v8.5</b>\n" + "\u2550" * 22 + "\n"
            "\U0001f465 Total:{} PRO:{}\n"
            "\U0001f4e1 Signaux:{} Payés:{}\n\n" +
            "\u2501" * 20 + "\n"
            "\U0001f4c5 <b>AUJOURD'HUI</b>\n"
            "{} sig  {} gagnants\nLot0.01:+${}  Lot1:+${}\n\n"
            "\U0001f4c6 <b>CETTE SEMAINE</b>\n"
            "{} sig  {} gagnants  Lot1:+${}\n\n"
        ).format(
            total, pro, sigs, pays,
            stats["sig_count"], stats["wins"], stats["total_g001"], stats["total_g1"],
            ws["sig_count"], ws["wins"], ws["total_g1"])
        if top:
            msg += "\U0001f91d <b>TOP PARRAINS</b>\n"
            seen = set()
            for t_uid, uname, rc in top:
                if t_uid not in seen:
                    seen.add(t_uid)
                    msg += "{}. @{}  {} filleuls\n".format(len(seen), uname or "?", rc)
        if pending:
            msg += "\n\u23f3 <b>ATTENTE PAIEMENT</b>\n"
            for _, p_uid, uname, tx, _ in pending:
                tx_short = (tx or "")[:16] + "..."
                msg += "\u2022 @{} <code>{}</code>  <code>{}</code>\n  /activate {}\n".format(
                    uname or "?", p_uid, tx_short, p_uid)
        tg_send(uid, msg)
    except Exception as ex:
        tg_send(uid, "\u274c Erreur /stats : {}".format(str(ex)[:100]))

def handle_membres(uid, page=1):
    if not _admin_only(uid): return
    try:
        PAGE = 20
        con  = _conn(); cur = con.cursor()
        cur.execute("SELECT COUNT(*) FROM users")
        total = cur.fetchone()[0]
        cur.execute(
            "SELECT user_id,username,plan,ref_count,joined,pro_expires "
            "FROM users ORDER BY joined DESC LIMIT ? OFFSET ?",
            (PAGE, (page - 1) * PAGE))
        rows = cur.fetchall(); con.close()
        tp   = max(1, (total + PAGE - 1) // PAGE)
        if total == 0:
            tg_send(uid, "\U0001f465 <b>MEMBRES</b>\n\nAucun membre enregistré."); return
        msg = "\U0001f465 <b>MEMBRES {}/{}</b> ({} total)\n".format(page, tp, total)
        msg += "\u2550" * 22 + "\n"
        for row_uid, uname, plan, rc, joined, exp in rows:
            icon = "\U0001f4a0" if plan == "PRO" else "\U0001f513"
            j    = (joined or "")[:10]
            e    = "  exp:" + exp[:10] if exp else ""
            msg += "{} @{}  <code>{}</code>  \U0001f91d{}  {}{}\n".format(
                icon, uname or "?", row_uid, rc, j, e)
        msg += "\u2550" * 22 + "\n"
        if page > 1:  msg += "\u2b05\ufe0f /membres {}  ".format(page - 1)
        if page < tp: msg += "\u27a1\ufe0f /membres {}".format(page + 1)
        tg_send(uid, msg)
    except Exception as ex:
        tg_send(uid, "\u274c Erreur /membres : {}".format(str(ex)[:100]))

def handle_marches(uid):
    try:
        db_register(uid, "")
        sn, sm, sl, wknd = get_session()
        tg_send(uid,
            "\U0001f4e1 <b>SCAN EN COURS...</b>\n"
            "\U0001f553 {} \u00b7 Score min : <b>{}</b>\n"
            "\u23f3 Analyse de {} marchés...".format(sl, sm, len(MARKETS)))
        active_markets = [m for m in MARKETS if not wknd or m.get("crypto", False)]
        news_ok, news_lbl = news_check()
        result_queue = Queue()
        threads = []
        for m in active_markets:
            t = threading.Thread(
                target=agent_analyze, args=(m, sm, news_ok, result_queue), daemon=True)
            t.start(); threads.append(t)
        for t in threads:
            t.join(timeout=10)
        results = {}
        while not result_queue.empty():
            try: r = result_queue.get_nowait(); results[r["name"]] = r
            except Empty: break
        cats = {}
        for m in MARKETS:
            r = results.get(m["name"], {"name": m["name"], "cat": m["cat"],
                                        "found": False, "reason": "Timeout"})
            cats.setdefault(m["cat"], []).append(r)
        lines = ["\U0001f50d <b>ÉTAT DES MARCHÉS</b> \u2014 {} \u00b7 {}\n".format(
            sl, datetime.now().strftime("%H:%M"))]
        signals_found = []
        for cat in ["METALS", "CRYPTO", "FOREX", "INDICES", "OIL"]:
            mlist = cats.get(cat, [])
            if not mlist: continue
            lines.append("{} <b>{}</b>".format(CAT_EMO.get(cat, "\U0001f4ca"), CAT_NAME.get(cat, cat)))
            for r in mlist:
                if r.get("found"):
                    s = r["signal"]
                    arrow = "\u2b06\ufe0f" if s["side"] == "BUY" else "\u2b07\ufe0f"
                    validity = _signal_validity(s)
                    lines.append("  \U0001f7e2 <b>{}</b> {} {}  RR 1:{}  Score {}  \u23f3{}min".format(
                        r["name"], arrow, s["side"], s["rr"], s["score"], validity))
                    lines.append("    \U0001f4cd <code>{}</code> \u2192 TP <code>{}</code>  SL <code>{}</code>".format(
                        s["entry"], s["tp"], s["sl"]))
                    signals_found.append(r["name"])
                else:
                    reason = r.get("reason", "?")
                    ico = ("\u26aa" if "insuffisant" in reason or "Timeout" in reason or "vieilles" in reason else
                           "\U0001f7e1" if "neutre" in reason.lower() else
                           "\U0001f7e0" if "Score" in reason else
                           "\U0001f535" if "Breaker" in reason else
                           "\U0001f534" if "RR" in reason or "Spread" in reason else "\u23f8\ufe0f")
                    lines.append("  {} <b>{}</b>  <i>{}</i>".format(ico, r["name"], reason))
            lines.append("")
        if signals_found:
            lines.append("\U0001f7e2 <b>{} signal(s) détecté(s) !</b>".format(len(signals_found)))
        else:
            lines.append("\U0001f7e1 Aucun signal ce cycle")
        msg = "\n".join(lines)
        if len(msg) > 4000: msg = msg[:3900] + "\n...(tronqué)"
        tg_send(uid, msg)
    except Exception as ex:
        tg_send(uid, "\u274c Erreur /marches : {}".format(str(ex)[:100]))



# ═══════════════════════════════════════════════════════════════
#  PANEL ADMIN — /admin  (réservé à l'administrateur)
# ═══════════════════════════════════════════════════════════════

_broadcast_pending = {}   # uid → {"target": "ALL"|"PRO", "step": "waiting_text"}

# ── État paiement en attente de confirmation ──────────────────
# uid → {"tx": "hash_ou_None", "photo_id": "file_id_ou_None", "step": "waiting_proof"|"waiting_confirm"}
_payment_state = {}

def kb_admin():
    return {"inline_keyboard": [
        [{"text": "👥 Membres",          "callback_data": "adm_membres_1"},
         {"text": "📊 Stats globales",   "callback_data": "adm_stats"}],
        [{"text": "💰 Paiements",         "callback_data": "adm_payments"},
         {"text": "📈 Rapports",          "callback_data": "adm_rapports"}],
        [{"text": "📡 Forcer scan",        "callback_data": "adm_scan"},
         {"text": "🔍 Debug scan",         "callback_data": "adm_debug"}],
        [{"text": "✉️ Message → TOUS",    "callback_data": "adm_bcast_all"},
         {"text": "✉️ Message → PRO",    "callback_data": "adm_bcast_pro"}],
        [{"text": "📢 Messages Promo",    "callback_data": "adm_promo_list"}],
        [{"text": "🔧 Recommandations",   "callback_data": "adm_reco"},
         {"text": "🌐 État marchés",      "callback_data": "adm_marches"}],
    ]}

def kb_admin_back():
    return {"inline_keyboard": [[{"text": "◀️ Panel Admin", "callback_data": "adm_panel"}]]}

def send_admin_panel(uid):
    if uid != ADMIN_ID: tg_send(uid, "❌ Accès refusé."); return
    total, pro, sigs, pays, g1d = db_global_stats()
    sn, sm, sl, wknd = get_session()
    stats  = db_daily_stats()
    pend   = db_pending_payments()
    free   = total - pro
    tg_send_sticker(uid, STK_CROWN)
    tg_send(uid,
        "🛡 <b>PANEL ADMIN — AlphaBot v8.5</b>\n" + "═" * 22 + "\n\n"
        "👥 Membres : <b>{}</b>  ·  PRO : <b>{}</b>  ·  FREE : <b>{}</b>\n"
        "📡 Signaux aujourd'hui : <b>{}</b>  ·  Gains : <b>+${}</b>\n"
        "💰 Paiements confirmés : <b>{}</b>\n"
        "⏳ En attente paiement : <b>{}</b>{}\n\n"
        "🕐 Session : <b>{}</b>  ·  Score min : <b>{}</b>\n\n"
        "Sélectionne une action ↓".format(
            total, pro, free,
            stats["sig_count"], stats["total_g1"],
            pays, len(pend),
            "  ⚠️ À valider !" if pend else "",
            sl, sm),
        kb=kb_admin())

def send_admin_stats(uid):
    if uid != ADMIN_ID: return
    total, pro, sigs, pays, g1d = db_global_stats()
    stats = db_daily_stats(); ws = db_weekly_stats()
    con = _conn(); cur = con.cursor()
    cur.execute("SELECT user_id,username,ref_count FROM users GROUP BY user_id ORDER BY ref_count DESC LIMIT 5")
    top = cur.fetchall()
    cur.execute("SELECT COUNT(*) FROM users WHERE joined >= date('now','-1 day')")
    new1 = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM users WHERE joined >= date('now','-7 days')")
    new7 = cur.fetchone()[0]
    con.close()
    wr_d = int(stats["wins"]/stats["sig_count"]*100) if stats["sig_count"] else 0
    wr_w = int(ws["wins"]/ws["sig_count"]*100) if ws["sig_count"] else 0
    msg = (
        "📊 <b>STATS COMPLÈTES</b>\n" + "═"*22 + "\n\n"
        "👥 Total : <b>{}</b>  ·  PRO : <b>{}</b>  ·  FREE : <b>{}</b>\n"
        "🆕 Nouveaux 24h : <b>{}</b>  ·  7j : <b>{}</b>\n"
        "📡 Signaux total : <b>{}</b>  ·  Payés : <b>{}</b>\n\n"
        "📅 <b>AUJOURD'HUI</b>\n"
        "  {} signaux  ·  {} gagnants  ·  {}% winrate\n"
        "  Lot 0.01 : +${}  ·  Lot 1.00 : +${}\n\n"
        "📆 <b>CETTE SEMAINE</b>\n"
        "  {} signaux  ·  {} gagnants  ·  {}% winrate\n"
        "  Lot 1.00 : +${}\n\n"
    ).format(total, pro, total-pro, new1, new7, sigs, pays,
             stats["sig_count"], stats["wins"], wr_d,
             stats["total_g001"], stats["total_g1"],
             ws["sig_count"], ws["wins"], wr_w, ws["total_g1"])
    if top:
        msg += "🤝 <b>TOP PARRAINS</b>\n"
        seen = set()
        for t_uid, uname, rc in top:
            if t_uid not in seen:
                seen.add(t_uid)
                msg += "  @{}  <b>{}</b> filleuls\n".format(uname or "?", rc)
    tg_send(uid, msg, kb=kb_admin_back())

def send_admin_payments(uid):
    if uid != ADMIN_ID: return
    pend = db_pending_payments()
    if not pend:
        tg_send(uid, "💰 <b>PAIEMENTS</b>\n\nAucun paiement en attente. ✅", kb=kb_admin_back())
        return
    msg = "💰 <b>PAIEMENTS EN ATTENTE ({})</b>\n".format(len(pend)) + "═"*22 + "\n\n"
    btns = []
    for pay_id, p_uid, uname, tx, created in pend:
        tx_s = (tx or "")[:20] + "..."
        msg += "• @{}  <code>{}</code>\n  Hash : <code>{}</code>\n\n".format(
            uname or "?", p_uid, tx_s)
        btns.append([
            {"text": "✅ Activer @{}".format(uname or p_uid), "callback_data": "adm_pro_{}".format(p_uid)},
            {"text": "❌ Refuser",                             "callback_data": "adm_ban_{}".format(p_uid)},
        ])
    btns.append([{"text": "◀️ Panel Admin", "callback_data": "adm_panel"}])
    tg_send(uid, msg, kb={"inline_keyboard": btns})

def send_admin_reco(uid):
    if uid != ADMIN_ID: return
    total, pro, sigs, pays, g1d = db_global_stats()
    stats = db_daily_stats()
    wr = int(stats["wins"]/stats["sig_count"]*100) if stats["sig_count"] else 0
    recs = []
    if stats["sig_count"] == 0:
        recs.append("📭 Aucun signal aujourd'hui — Lance /scan pour vérifier, puis /debug pour les raisons.")
    if wr < 50 and stats["sig_count"] >= 3:
        recs.append("📉 Winrate {}% — Envisage d'augmenter temporairement le score minimum (SCAN_SEC).".format(wr))
    if (total - pro) > pro * 4:
        recs.append("💡 {} FREE vs {} PRO — Lance un broadcast de motivation avec /admin → Message à tous.".format(total-pro, pro))
    if pays < 5:
        recs.append("💰 Seulement {} paiements — Envoie un message promo à tous les FREE.".format(pays))
    if stats["total_g1"] > 500:
        recs.append("🔥 Excellente journée +${} ! Partage les résultats avec un broadcast pour motiver.".format(stats["total_g1"]))
    if not recs:
        recs.append("✅ Tout fonctionne bien. Continue !")
    msg = "🔧 <b>RECOMMANDATIONS ADMIN</b>\n" + "═"*22 + "\n\n"
    for i, r in enumerate(recs, 1):
        msg += "{}. {}\n\n".format(i, r)
    tg_send(uid, msg, kb=kb_admin_back())

def handle_pay_submitted(uid, uname):
    """Étape 1 — L'utilisateur a cliqué 'J'ai payé' → demander le TX Hash uniquement."""
    _payment_state[uid] = {"tx": None, "photo_id": None, "step": "waiting_proof"}
    tg_send(uid,
        "\U0001f4cb <b>COLLE TON TX HASH ICI</b>\n\n"
        "Après ton virement USDT TRC20,\n"
        "copie l'identifiant de transaction et envoie-le ici.\n\n"
        "\U0001f4cc <i>Exemple :</i>\n"
        "<code>a1b2c3d4e5f6789abc123def456789abc123def456789abc123def4567890ab</code>\n\n"
        "\u2705 Le bot vérifie automatiquement sur la blockchain\n"
        "et active ton PRO en moins de 2 minutes !",
        kb={"inline_keyboard": [[
            {"text": "\u274c Annuler", "callback_data": "pay_cancel"}
        ]]}
    )

def handle_payment_proof_received(uid, uname, tx=None, photo_id=None):
    """Étape 2 — TX Hash reçu → afficher dans un cadre + bouton Vérifier."""
    if uid not in _payment_state or _payment_state[uid].get("step") != "waiting_proof":
        return False
    if not tx:
        return False  # on ignore les photos désormais

    _payment_state[uid]["tx"]   = tx
    _payment_state[uid]["step"] = "waiting_confirm"

    tg_send(uid,
        "\U0001f4cb <b>TX HASH REÇU</b>\n\n"
        "\u2500" * 20 + "\n"
        "<code>{}</code>\n".format(tx) +
        "\u2500" * 20 + "\n\n"
        "Vérifie que c'est le bon hash puis clique sur\n"
        "<b>🔍 Vérifier mon paiement</b> pour lancer la vérification.",
        kb={"inline_keyboard": [
            [{"text": "🔍 Vérifier mon paiement", "callback_data": "pay_confirm"}],
            [{"text": "🔄 Changer le hash",        "callback_data": "pay_submitted"}],
            [{"text": "❌ Annuler",                 "callback_data": "pay_cancel"}],
        ]}
    )
    return True

def handle_pay_confirm(uid, uname):
    """Étape 3 — Clic sur Vérifier → vérification blockchain + activation."""
    state = _payment_state.pop(uid, None)
    if not state or not state.get("tx"):
        tg_send(uid,
            "\u274c Aucun hash en attente.\n\n"
            "Recommence avec le bouton \U0001f4b0 Devenir PRO.")
        return

    tx = state["tx"]
    db_save_payment(uid, tx)

    tg_send(uid,
        "\U0001f50d <b>Vérification en cours...</b>\n\n"
        "Hash : <code>{}</code>\n\n"
        "\u23f3 Consultation de la blockchain TRC20...\n"
        "Activation automatique sous <b>2 minutes</b> si confirmé.".format(tx))

    tg_send(ADMIN_ID,
        "\U0001f4b0 <b>PAIEMENT À VÉRIFIER</b>\n"
        "@{} <code>{}</code>\n"
        "Hash : <code>{}</code>\n"
        "\U0001f6e0 /activate {} (si auto échoue)".format(uname or "?", uid, tx, uid))

    threading.Thread(target=_auto_verify_and_activate, args=(uid, uname, tx), daemon=True).start()

def _auto_verify_and_activate(uid, uname, tx_hash):
    """Vérification auto TronScan + activation si OK."""
    delays = [10, 60, 120]
    for i, delay in enumerate(delays):
        time.sleep(delay)
        result, amount = verify_tx(tx_hash)
        if result is None:
            # Réseau TronScan inaccessible → activation manuelle directe
            tg_send(uid,
                "\u26a0\ufe0f <b>Vérification impossible</b>\n\n"
                "Le réseau TronScan est inaccessible depuis le serveur.\n"
                "L'admin va activer ton PRO <b>manuellement dans 5 min</b>.\n\n"
                "\U0001f4e9 @leaderOdg")
            tg_send(ADMIN_ID,
                "\U0001f534 <b>RÉSEAU TRONSCAN INDISPONIBLE</b>\n"
                "@{} <code>{}</code>\n"
                "Hash : <code>{}</code>\n\n"
                "\u26a0\ufe0f Vérification auto impossible — active manuellement :\n"
                "\U0001f6e0 /activate {}".format(uname or "?", uid, tx_hash, uid))
            return
        if result:
            db_activate_pro(uid, "USDT_AUTO", days=None)
            tg_send_sticker(uid, STK_WIN)
            tg_send(uid,
                "\U0001f389 <b>PAIEMENT CONFIRMÉ !</b>\n\n"
                "\u2705 {}$ USDT reçu !\n\n"
                "\U0001f4a0 <b>PRO ACTIVÉ À VIE !</b>\n\n"
                "\u2705 Max {} signaux/j\n"
                "\u2705 24 paires + crypto week-end\n"
                "\u2705 Rapports quotidien + hebdo\n"
                "\u2705 Support @leaderOdg\n\n"
                "\U0001f680 Bienvenue dans AlphaBot PRO !".format(amount, PRO_LIMIT))
            tg_send(ADMIN_ID,
                "\U0001f7e2 <b>AUTO PRO OK</b> : @{} <code>{}</code>  {}$ \u2705".format(
                    uname or "?", uid, amount))
            log("PAY", clr("AUTO PRO: @{} {} — {}$".format(uname, uid, amount), "green"))
            return
        elif i < len(delays) - 1:
            log("INFO", clr("TX non confirmé (tentative {}/3)".format(i + 1), "yellow"))
    # Toutes tentatives échouées → activation manuelle
    tg_send(uid,
        "\u23f3 <b>Vérification en cours côté admin</b>\n\n"
        "Ta transaction n'est pas encore visible sur la blockchain.\n"
        "L'admin va activer manuellement dans 30 min.\n\n"
        "\U0001f4e9 @leaderOdg")
    tg_send(ADMIN_ID,
        "\u26a0\ufe0f <b>ACTIVATION MANUELLE REQUISE</b>\n"
        "@{} <code>{}</code>\n"
        "Hash : <code>{}</code>\n\n"
        "\U0001f6e0 /activate {}".format(uname or "?", uid, tx_hash, uid))


# ═══════════════════════════════════════════════════════════════
#  MESSAGES PROMO — Templates marketing intégrés
# ═══════════════════════════════════════════════════════════════
PROMO_MESSAGES = [
    {
        "id": "promo_1", "label": "📡 Accroche générale",
        "text": (
            "📡 <b>SIGNAUX TRADING EN TEMPS RÉEL</b> 📡\n\n"
            "Tu rates des trades parce que tu ne sais pas quand entrer ? ↗️\n\n"
            "Entrée précise, Stop Loss et Take Profit automatiques 🎯\n"
            "Une IA qui analyse le marché à ta place, 24h/24 🤖\n\n"
            "📩 Rejoins AlphaBot maintenant\n➡️ @AlphaBotForexBot\n\n"
            "🌍 <b>DES RÉSULTATS QUI CHANGENT TOUT</b> ✈️\n\n"
            "Karim a suivi les signaux avec discipline pendant 3 semaines 📊\n"
            "Résultat : <b>+340$ sur un capital de 500$</b> avec des lots 0.10 💰\n\n"
            "Le trading, ce n'est pas du hasard…\nc'est de la méthode et les bons outils 💫\n\n"
            "📩 Envoie <b>START</b> ici\n➡️ @AlphaBotForexBot"
        )
    },
    {
        "id": "promo_2", "label": "💰 Preuve sociale",
        "text": (
            "💰 <b>ILS GAGNENT. ET TOI ?</b> 💰\n\n"
            "Pendant que tu hésites, d'autres exécutent 🚀\n\n"
            "Or · Forex · BTC · Indices US\n"
            "Analyse ICT/SMC professionnelle à portée de main 📲\n\n"
            "✅ Signal reçu\n✅ Entrée placée\n✅ TP atteint\n\n"
            "C'est aussi simple que ça 🎯\n\n"
            "📩 Commence <b>GRATUIT</b> aujourd'hui\n➡️ @AlphaBotForexBot"
        )
    },
    {
        "id": "promo_3", "label": "⏰ Urgence / Opportunité",
        "text": (
            "⏰ <b>LE MARCHÉ N'ATTEND PAS</b> ⏰\n\n"
            "Chaque bougie est une opportunité… ou une perte évitée 📉📈\n\n"
            "AlphaBot scanne <b>EURUSD · GBPJPY · XAUUSD · NAS100</b>\n"
            "et t'envoie le signal avec l'entrée exacte 🎯\n\n"
            "Tu n'as qu'à exécuter 💪\n\n"
            "🆓 2 signaux gratuits par jour\n"
            "💎 Plan PRO = jusqu'à 10 signaux/jour\n\n"
            "📩 Lance-toi maintenant\n➡️ @AlphaBotForexBot"
        )
    },
    {
        "id": "promo_4", "label": "📊 Résultats du jour",
        "text": None  # Généré dynamiquement
    },
    {
        "id": "promo_5", "label": "🆓 FREE vs 💎 PRO",
        "text": (
            "🆓 <b>GRATUIT</b> ou 💎 <b>PRO ?</b>\n\n"
            "Les deux donnent des signaux avec entrée, TP et SL 📲\n\n"
            "La différence ?\n\n"
            "🆓 FREE → 2 signaux par jour\n"
            "💎 PRO  → jusqu'à 10 signaux/jour\n"
            "         + analyse ICT complète\n"
            "         + rapports quotidiens et hebdo\n\n"
            "Tout ça pour seulement <b>10$ USDT</b> 💵\n"
            "Ou <b>30 filleuls = 3 mois PRO GRATUIT</b> 🤝\n\n"
            "📩 Commence dès maintenant\n➡️ @AlphaBotForexBot"
        )
    },
]

def _build_promo_text(promo_id):
    """Construit le texte du message promo (gère le cas dynamique)."""
    promo = next((p for p in PROMO_MESSAGES if p["id"] == promo_id), None)
    if not promo: return None
    if promo_id != "promo_4":
        return promo["text"]
    stats = db_daily_stats(); rows = stats["rows"]
    if not rows: return None
    lines = ["📊 <b>RÉSULTATS D'AUJOURD'HUI</b> 📊\n"]
    for row in rows:
        pair,side,rr,g001,g1,l001,l1,session = row[0],row[1],row[2],row[3],row[4],row[5],row[6],row[7]
        ok=rr>=3.0; icon="🟢" if ok else "🔴"
        d="ACHAT" if side=="BUY" else "VENTE"
        res="✅ TP → <b>+${:.0f}</b>".format(g1) if ok else "❌ SL → <b>-${:.0f}</b>".format(l1)
        lines.append("{} <b>{}</b> {}  {} (lot 0.01)".format(icon,pair,d,res))
    lines += ["",
        "💰 <b>Total : +${}</b> lot 0.01  ·  +${} lot 1.00 🔥".format(stats["total_g001"],stats["total_g1"]),
        "","Et toi tu étais où pendant ces moves ? 👀","",
        "📩 Rejoins la communauté\n➡️ @AlphaBotForexBot"]
    return "\n".join(lines)

def send_admin_promo_list(uid):
    """Panel de sélection des messages promo."""
    if uid != ADMIN_ID: return
    stats = db_daily_stats()
    btns  = [[{"text": p["label"], "callback_data": "adm_promo_{}".format(p["id"])}]
             for p in PROMO_MESSAGES]
    btns.append([{"text": "◀️ Panel Admin", "callback_data": "adm_panel"}])
    tg_send(uid,
        "📢 <b>MESSAGES PROMO</b>\n" + "═"*22 + "\n\n"
        "Sélectionne un message à envoyer à <b>TOUS</b> les membres.\n\n"
        "📊 Résultats d'aujourd'hui : "
        "<b>{} signaux · {} TP · +${} lot1</b>".format(
            stats["sig_count"], stats["wins"], stats["total_g1"]),
        kb={"inline_keyboard": btns})

def send_promo_preview(uid, promo_id):
    """Aperçu du message promo + bouton d'envoi."""
    if uid != ADMIN_ID: return
    promo = next((p for p in PROMO_MESSAGES if p["id"] == promo_id), None)
    if not promo: return
    text = _build_promo_text(promo_id)
    if not text:
        tg_send(uid, "⚠️ Aucun signal aujourd'hui — le message résultats n'est pas disponible.",
                kb={"inline_keyboard": [[{"text": "◀️ Retour", "callback_data": "adm_promo_list"}]]}); return
    total = len(set(db_get_pro_users() + db_get_free_users()))
    tg_send(uid,
        "👁 <b>APERÇU</b> — {}\n".format(promo["label"]) + "─"*22 + "\n\n" + text +
        "\n\n" + "─"*22 + "\n📤 Envoyer à <b>{}</b> membres ?".format(total),
        kb={"inline_keyboard": [
            [{"text": "✅ Envoyer à TOUS maintenant", "callback_data": "adm_promo_send_{}".format(promo_id)}],
            [{"text": "◀️ Choisir un autre message",  "callback_data": "adm_promo_list"}],
        ]})

def broadcast_promo(uid, promo_id):
    """Envoie le message promo à tous les membres."""
    if uid != ADMIN_ID: return
    text = _build_promo_text(promo_id)
    if not text: tg_send(uid, "⚠️ Impossible de générer ce message."); return
    users = list(set(db_get_pro_users() + db_get_free_users()))
    tg_send(uid, "📤 Envoi en cours à <b>{}</b> membres...".format(len(users)))
    sent = fail = 0
    for u in users:
        if u == uid: continue
        r = tg_send(u, text)
        if r.get("ok"): sent += 1
        else:           fail += 1
        time.sleep(0.05)
    tg_send_sticker(uid, STK_ROCKET)
    tg_send(uid,
        "✅ <b>Broadcast terminé !</b>\n\n"
        "✉️ Envoyés : <b>{}</b>  ·  ❌ Échoués : <b>{}</b>".format(sent, fail),
        kb=kb_admin_back())


def handle_admin_broadcast_start(uid, target):
    nb = len(db_get_pro_users()) + len(db_get_free_users()) if target == "ALL" else len(db_get_pro_users())
    tg_send(uid,
        "✉️ <b>BROADCAST → {}</b>\n\n"
        "Envoie maintenant le message à diffuser à <b>{} membres</b>.\n\n"
        "💡 Tu peux utiliser du HTML : <b>gras</b>, <i>italique</i>, <code>code</code>\n\n"
        "/annuler pour annuler.".format(target, nb),
        kb={"inline_keyboard": [[{"text": "❌ Annuler", "callback_data": "adm_panel"}]]})

def handle_broadcast_message(uid, text):
    """Retourne True si le message a été traité comme un broadcast."""
    if uid not in _broadcast_pending: return False
    state = _broadcast_pending.pop(uid)
    target = state["target"]
    users = list(set(db_get_pro_users() + db_get_free_users())) if target == "ALL" else db_get_pro_users()
    tg_send(uid, "📤 Envoi en cours à <b>{}</b> membres...".format(len(users)))
    sent = fail = 0
    for u in users:
        if u == uid: continue
        r = tg_send(u,
            "📢 <b>Message de l'équipe AlphaBot :</b>\n\n" + text +
            "\n\n— <i>@leaderOdg · AlphaBot PRO</i>")
        if r.get("ok"): sent += 1
        else:           fail += 1
        time.sleep(0.05)
    tg_send_sticker(uid, STK_ROCKET)
    tg_send(uid,
        "✅ <b>Broadcast terminé !</b>\n\n"
        "✉️ Envoyés : <b>{}</b>  ·  ❌ Échoués : <b>{}</b>".format(sent, fail),
        kb=kb_admin_back())
    return True


# ═══════════════════════════════════════════════════════════════
#  ⑫ DISPATCHER — Tous les boutons et commandes
# ═══════════════════════════════════════════════════════════════
def dispatch_message(uid, uname, txt):
    # /start
    if txt.startswith("/start"):
        args   = txt.split()[1:]
        ref_by = int(args[0]) if args and args[0].isdigit() else 0
        send_welcome(uid, uname, ref_by)

    # ── Boutons clavier principal ─────────────────────────────
    elif txt == "\U0001f4e1 Mes Signaux":
        db_register(uid, uname)
        tg_req("sendChatAction", {"chat_id": str(uid), "action": "typing"})
        threading.Thread(target=send_signals_info, args=(uid,), daemon=True).start()
    elif txt == "\U0001f4ca Mon Compte":
        db_register(uid, uname)
        tg_req("sendChatAction", {"chat_id": str(uid), "action": "typing"})
        forced = _admin_test_mode if uid == ADMIN_ID and _admin_test_mode else None
        threading.Thread(target=send_account, args=(uid, uname, forced), daemon=True).start()
    elif txt == "\U0001f4b0 Devenir PRO":
        db_register(uid, uname)
        tg_req("sendChatAction", {"chat_id": str(uid), "action": "typing"})
        threading.Thread(target=send_pro, args=(uid,), daemon=True).start()
    elif txt == "\U0001f91d Parrainage":
        db_register(uid, uname)
        tg_req("sendChatAction", {"chat_id": str(uid), "action": "typing"})
        threading.Thread(target=send_affilie, args=(uid, uname), daemon=True).start()
    elif txt == "\U0001f4b8 Mes Gains":
        db_register(uid, uname)
        tg_req("sendChatAction", {"chat_id": str(uid), "action": "typing"})
        threading.Thread(target=send_mes_gains, args=(uid,), daemon=True).start()
    elif txt == "\U0001f4d6 Guide ICT":
        db_register(uid, uname)
        tg_req("sendChatAction", {"chat_id": str(uid), "action": "typing"})
        threading.Thread(target=send_guide, args=(uid,), daemon=True).start()
    elif txt == "\U0001f4c8 Rapports":
        db_register(uid, uname)
        tg_req("sendChatAction", {"chat_id": str(uid), "action": "typing"})
        threading.Thread(target=send_rapports, args=(uid,), daemon=True).start()
    elif txt == "\U0001f3e6 Broker Exness":
        db_register(uid, uname)
        threading.Thread(target=send_broker, args=(uid,), daemon=True).start()

    # ── Alias anciens boutons (rétrocompatibilité) ────────────
    elif txt in ("\U0001f91d Devenir Affilié", "\U0001f4e1 Parrainage",
                 "\U0001f381 Partager et Récompenses"):
        db_register(uid, uname); send_affilie(uid, uname)
    elif txt in ("\U0001f4ca Mon Tableau de Bord", "\U0001f4ca Mon compte"):
        db_register(uid, uname)
        threading.Thread(target=send_account, args=(uid, uname), daemon=True).start()
    elif txt in ("\U0001f4b0 Mes Gains", "\U0001f4c8 Mes Gains"):
        db_register(uid, uname); send_mes_gains(uid)
    elif txt in ("\u2753 Comment ça marche ?", "\U0001f4d6 Guide AlphaBot"):
        db_register(uid, uname)
        threading.Thread(target=send_guide, args=(uid,), daemon=True).start()
    elif txt in ("\U0001f4b0 Paiement USDT", "\U0001f4a0 Devenir PRO"):
        db_register(uid, uname); send_pay(uid)
    elif txt == "\U0001f465 Groupe VIP":
        # Ancien bouton — redirige vers rapports
        db_register(uid, uname); send_rapports(uid)

    # ── Commandes texte ───────────────────────────────────────
    elif txt in ("/menu", "menu"):
        db_register(uid, uname)
        tg_send(uid, "\U0001f4cb Menu :", kb=kb_main())
    elif txt.startswith("/pay"):
        db_register(uid, uname); send_pay(uid)
    elif txt.startswith("/pro"):
        db_register(uid, uname); send_pro(uid)
    elif txt.startswith("/ref"):
        db_register(uid, uname); send_affilie(uid, uname)
    elif txt.startswith("/broker"):
        db_register(uid, uname); send_broker(uid)
    elif txt.startswith("/rapports") or txt.startswith("/report"):
        db_register(uid, uname); send_rapports(uid)
    elif txt.startswith("/guide") or txt.startswith("/pdf"):
        db_register(uid, uname)
        threading.Thread(target=send_guide, args=(uid,), daemon=True).start()
    elif txt.startswith("/account"):
        db_register(uid, uname)
        threading.Thread(target=send_account, args=(uid, uname), daemon=True).start()
    elif txt.startswith("/support"):
        db_register(uid, uname)
        tg_send(uid,
            "\U0001f4e9 <b>Support</b>\n"
            "ID : <code>{}</code>\n\U0001f449 @leaderOdg".format(uid))
    elif txt.startswith("/txhash"):
        parts = txt.split()
        if len(parts) >= 2:
            db_register(uid, uname)
            threading.Thread(
                target=handle_txhash, args=(uid, uname, parts[1]), daemon=True).start()
        else:
            tg_send(uid, "Usage :\n<code>/txhash COLLE_TON_HASH</code>")

    # ── Commandes admin ───────────────────────────────────────
    elif txt in ("/admin", "/panel") and uid == ADMIN_ID:
        threading.Thread(target=send_admin_panel, args=(uid,), daemon=True).start()

    elif txt == "/annuler" and uid == ADMIN_ID:
        _broadcast_pending.pop(uid, None)
        tg_send(uid, "❌ Broadcast annulé.", kb=kb_reply())

    elif uid == ADMIN_ID and txt and not txt.startswith("/") and handle_broadcast_message(uid, txt):
        pass  # broadcast géré

    elif txt.startswith("/activate"):
        parts = txt.split()
        handle_activate(uid, parts[1] if len(parts) >= 2 else "")
    elif txt.startswith("/degrade"):
        parts = txt.split()
        handle_degrade(uid, parts[1] if len(parts) >= 2 else "")
    elif txt.startswith("/testfree"):
        handle_testfree(uid)
    elif txt.startswith("/testpro"):
        handle_testpro(uid)
    elif txt.startswith("/monstatus"):
        threading.Thread(target=handle_monstatus, args=(uid,), daemon=True).start()
    elif txt.startswith("/marches"):
        threading.Thread(target=handle_marches, args=(uid,), daemon=True).start()
    elif txt.startswith("/scan"):
        threading.Thread(target=handle_scan, args=(uid,), daemon=True).start()
    elif txt.startswith("/debug"):
        threading.Thread(target=handle_debug, args=(uid,), daemon=True).start()
    elif txt.startswith("/resetcount"):
        parts = txt.split()
        handle_resetcount(uid, parts[1] if len(parts) >= 2 else "")
    elif txt.startswith("/membres"):
        parts = txt.split()
        pg    = int(parts[1]) if len(parts) >= 2 and parts[1].isdigit() else 1
        threading.Thread(target=handle_membres, args=(uid, pg), daemon=True).start()
    elif txt.startswith("/stats"):
        threading.Thread(target=handle_stats, args=(uid,), daemon=True).start()
    elif txt.startswith("/stop") and uid == ADMIN_ID:
        tg_send(uid, "\U0001f6d1 Bot arrêté.")
        raise KeyboardInterrupt

    # ── Fallback ──────────────────────────────────────────────
    else:
        db_register(uid, uname)
        tg_send(uid, "\U0001f916 Choisis une option :", kb=kb_reply())


def dispatch_callback(cb):
    """Route les boutons inline — tous les callback_data gérés."""
    uid   = cb["from"]["id"]
    uname = cb["from"].get("username", "")
    data  = cb.get("data", "")
    tg_req("answerCallbackQuery", {"callback_query_id": cb["id"]})
    db_register(uid, uname)

    if   data == "main":
        tg_send(uid, "\U0001f4cb Menu :", kb=kb_main())
    elif data == "signals":
        send_signals_info(uid)
    elif data == "pro":
        send_pro(uid)
    elif data == "pay":
        send_pay(uid)

    # ── Flux paiement interactif ──────────────────────────────
    elif data == "pay_submitted":
        handle_pay_submitted(uid, uname)
    elif data == "pay_confirm":
        threading.Thread(target=handle_pay_confirm, args=(uid, uname), daemon=True).start()
    elif data == "pay_cancel":
        _payment_state.pop(uid, None)
        tg_send(uid,
            "\u274c <b>Paiement annulé.</b>\n\n"
            "Reviens quand tu veux avec /pay ou le bouton \U0001f4b0 Devenir PRO.",
            kb=kb_reply())
    elif data == "broker":
        send_broker(uid)
    elif data == "ref":
        send_affilie(uid, uname)
    elif data == "ref_stats":
        # Bouton "Voir mes filleuls" depuis le message promo
        refs = db_get_refs(uid)
        link = "https://t.me/{}?start={}".format(BOT_USERNAME, uid)
        done = min(refs, REF_TARGET)
        pct  = int(done / REF_TARGET * 100)
        bar  = "\u2588" * int(done / REF_TARGET * 10) + "\u2591" * (10 - int(done / REF_TARGET * 10))
        tg_send(uid,
            "\U0001f91d <b>MES FILLEULS</b>\n" + "\u2550" * 22 + "\n\n"
            "\U0001f517 Lien : <code>{}</code>\n\n"
            "<b>{}/{}</b>  ({}%)\n[{}]\n\n"
            "\U0001f3c6 {} filleuls = <b>{} MOIS PRO GRATUIT</b>\n"
            "\u2705 Activation automatique".format(
                link, done, REF_TARGET, pct, bar, REF_TARGET, REF_MONTHS),
            kb=kb_back())
    elif data == "rapports":
        send_rapports(uid)
    elif data == "guide":
        threading.Thread(target=send_guide, args=(uid,), daemon=True).start()
    elif data == "account":
        threading.Thread(target=send_account, args=(uid, uname), daemon=True).start()

    # ── Boutons admin inline (notifs nouveaux users) ──────────
    elif data.startswith("adm_pro_") and uid == ADMIN_ID:
        try:
            t_uid = int(data.split("_")[2])
            db_activate_pro(t_uid, "ADMIN", days=None)
            con = _conn(); cur = con.cursor()
            cur.execute("SELECT username FROM users WHERE user_id=?", (t_uid,))
            row = cur.fetchone(); con.close()
            uname_t = "@" + (row[0] if row and row[0] else str(t_uid))
            tg_send(ADMIN_ID, "\u2705 PRO activé : {} <code>{}</code>".format(uname_t, t_uid))
            tg_send(t_uid,
                "\U0001f389 <b>PRO activé !</b>\n\n"
                "\u2705 Max {} signaux/j\n\u2705 24 paires + crypto week-end\n"
                "\U0001f680 Bienvenue dans AlphaBot PRO !".format(PRO_LIMIT))
        except Exception as ex:
            tg_send(ADMIN_ID, "\u274c Erreur activation : {}".format(ex))

    elif data.startswith("adm_ban_") and uid == ADMIN_ID:
        try:
            t_uid = int(data.split("_")[2])
            db_downgrade_pro(t_uid)
            tg_send(ADMIN_ID, "\U0001f6d1 Utilisateur <code>{}</code> repassé en FREE.".format(t_uid))
        except Exception as ex:
            tg_send(ADMIN_ID, "\u274c Erreur : {}".format(ex))

    elif data == "adm_panel" and uid == ADMIN_ID:
        threading.Thread(target=send_admin_panel, args=(uid,), daemon=True).start()
    elif data == "adm_stats" and uid == ADMIN_ID:
        threading.Thread(target=send_admin_stats, args=(uid,), daemon=True).start()
    elif data == "adm_payments" and uid == ADMIN_ID:
        threading.Thread(target=send_admin_payments, args=(uid,), daemon=True).start()
    elif data == "adm_reco" and uid == ADMIN_ID:
        threading.Thread(target=send_admin_reco, args=(uid,), daemon=True).start()
    elif data == "adm_rapports" and uid == ADMIN_ID:
        threading.Thread(target=send_rapports, args=(uid,), daemon=True).start()
    elif data == "adm_scan" and uid == ADMIN_ID:
        tg_send(uid, "📡 Scan forcé lancé !", kb=kb_admin_back())
        threading.Thread(target=scan_and_send, daemon=True).start()
    elif data == "adm_debug" and uid == ADMIN_ID:
        threading.Thread(target=handle_debug, args=(uid,), daemon=True).start()
    elif data == "adm_marches" and uid == ADMIN_ID:
        threading.Thread(target=handle_marches, args=(uid,), daemon=True).start()
    elif data.startswith("adm_membres_") and uid == ADMIN_ID:
        pg = int(data.split("_")[-1])
        threading.Thread(target=handle_membres, args=(uid, pg), daemon=True).start()
    elif data == "adm_promo_list" and uid == ADMIN_ID:
        threading.Thread(target=send_admin_promo_list, args=(uid,), daemon=True).start()
    elif data.startswith("adm_promo_send_") and uid == ADMIN_ID:
        promo_id = data.replace("adm_promo_send_", "")
        threading.Thread(target=broadcast_promo, args=(uid, promo_id), daemon=True).start()
    elif data.startswith("adm_promo_") and uid == ADMIN_ID:
        promo_id = data.replace("adm_promo_", "")
        threading.Thread(target=send_promo_preview, args=(uid, promo_id), daemon=True).start()
    elif data == "adm_bcast_all" and uid == ADMIN_ID:
        handle_admin_broadcast_start(uid, "ALL")
    elif data == "adm_bcast_pro" and uid == ADMIN_ID:
        handle_admin_broadcast_start(uid, "PRO")
    else:
        tg_send(uid, "\U0001f916 Choisis une option :", kb=kb_reply())


# ═══════════════════════════════════════════════════════════════
#  ⑬ DÉMARRAGE
# ═══════════════════════════════════════════════════════════════
def startup():
    print_banner()
    db_init()
    log("INFO", clr("DB", "white") + "  " + clr("OK", "bold", "green"))

    db_register(ADMIN_ID, "leaderOdg")
    db_activate_pro(ADMIN_ID, source="ADMIN_AUTO", days=None)
    print(clr("  Admin {} : PRO actif.".format(ADMIN_ID), "bold", "green"))

    tg_req("deleteWebhook", {"drop_pending_updates": "true"})
    time.sleep(1)
    old = tg_req("getUpdates", {"offset": -1, "timeout": 1}).get("result", [])
    skip_offset = 0
    if old:
        skip_offset = old[-1]["update_id"] + 1
        tg_req("getUpdates", {"offset": skip_offset, "timeout": 1})
        print(clr("  {} anciens messages ignorés".format(len(old)), "dim"))
    time.sleep(1)
    log("INFO", clr("Webhook", "white") + "  " + clr("OK", "bold", "green"))

    sn, sm, sl, wknd = get_session()
    ok = tg_send(ADMIN_ID,
        "\U0001f916 <b>AlphaBot v8.5 \u2014 Démarré !</b>\n\n"
        "\U0001f553 {}  \U0001f3af Score min : {}\n"
        "{}"
        "\U0001f916 20 agents IA  \u00b7  Données LIVE (max {}min)\n"
        "\U0001f4e1 FREE {}/j  \u00b7  PRO max {}/j\n"
        "\U0001f4b0 Paiement USDT auto  \u00b7  {} filleuls = {} mois\n\n"
        "\U0001f6e0 <b>/admin</b> \u2014 Panel complet\n/monstatus /stats /marches /scan /debug /membres".format(
            sl, sm,
            "\U0001f30d <b>Week-end : crypto uniquement !</b>\n" if wknd else "",
            DATA_MAX_AGE_MIN, FREE_LIMIT, PRO_LIMIT, REF_TARGET, REF_MONTHS))

    if not ok.get("ok"):
        log("ERR", clr("Connexion Telegram échouée — vérifie BOT_TOKEN", "red"))
        return None

    log("INFO", clr("Telegram OK — Bot actif", "bold", "green"))
    print()
    return skip_offset


# ═══════════════════════════════════════════════════════════════
#  ⑭ BOUCLE PRINCIPALE
# ═══════════════════════════════════════════════════════════════
def main():
    skip_offset = startup()
    if skip_offset is None:
        return

    offset    = skip_offset
    last_scan = 0

    while True:
        try:
            for upd in tg_updates(offset):
                offset = upd["update_id"] + 1

                if "message" in upd:
                    msg   = upd["message"]
                    uid   = msg["from"]["id"]
                    uname = msg["from"].get("username", "")
                    txt   = msg.get("text", "").strip()

                    if txt:
                        # TX Hash collé pendant le flux paiement
                        if uid in _payment_state and _payment_state[uid].get("step") == "waiting_proof":
                            cleaned = txt.strip()
                            if len(cleaned) >= 20 and not cleaned.startswith("/"):
                                handle_payment_proof_received(uid, uname, tx=cleaned)
                            else:
                                dispatch_message(uid, uname, txt)
                        else:
                            dispatch_message(uid, uname, txt)

                elif "callback_query" in upd:
                    dispatch_callback(upd["callback_query"])

            now = time.time()
            if now - last_scan >= SCAN_SEC:
                last_scan = now
                threading.Thread(target=scan_and_send, daemon=True).start()

            time.sleep(0.2)

        except KeyboardInterrupt:
            print()
            log("WARN", clr("Bot arrêté manuellement.", "yellow"))
            tg_send(ADMIN_ID, "\U0001f6d1 Bot arrêté.")
            break
        except Exception as ex:
            log("ERR", str(ex))
            time.sleep(5)


if __name__ == "__main__":
    main()
