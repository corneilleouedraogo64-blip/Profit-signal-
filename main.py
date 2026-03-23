
#!/usr/bin/env python3
"""
AlphaBot PRO v10 — Agent IA Adaptatif
• Bot Telegram FREE/PRO/VIP + paiement USDT auto
• 20 marchés Forex/Métaux/Crypto/Indices/Pétrole
• Cerveau ICT/SMC v2 + Mode IMPROVISATION
• Si pas de setup parfait → l'agent allège les critères
  si tendance de fond + session + broker sont valides
• Challenge IA 5$→500$ (Binance simulation)
• pip install requests
"""
import json, ssl, time, sqlite3, threading, math, random, logging
import urllib.request, urllib.parse, urllib.error, os
from datetime import datetime, timedelta, timezone
from queue import Queue, Empty
from http.server import HTTPServer, BaseHTTPRequestHandler
from collections import defaultdict, deque

# ══════════════════════════════════════════════════════
#  CONFIG
# ══════════════════════════════════════════════════════
TG_TOKEN     = os.getenv("TG_TOKEN",  "6950706659:AAGXw-27ebhWLm2HfG7lzC7EckpwCPS_JFg")
BOT_USER     = "leaderodg_bot"
CHANNEL_ID   = os.getenv("TG_GROUP", "-1003757467015")
VIP_CH       = os.getenv("TG_VIP",   "-1003771736496")
ADMIN_ID     = int(os.getenv("ADMIN_ID", "6982051442"))
USDT_ADDR    = "TJuPBihvzgb6ffGLw4WnqC33Av38kwU7XE"
BROKER_LINK  = "https://one.exnessonelink.com/a/nb3fx0bpnm"
DB_FILE      = "ab10.db"
BINANCE_BASE = "https://fapi.binance.com/fapi/v1"

PRO_PRICE  = 10;  REF_TARGET = 30;  REF_MONTHS = 3
FREE_LIMIT = 2;   PRO_LIMIT  = 10;  NB_AGENTS  = 20
TRIAL_DAYS = 3;   SCAN_SEC   = 60;  DATA_MAX_AGE = 30
DAILY_HOUR = 20;  WEEKLY_DAY = 6;   WEEKLY_HOUR = 21
FEE_TAKER  = 0.0004
CHALLENGE_START = float(os.getenv("CHALLENGE_START", "5.0"))
MAX_OPEN   = 3;  COOLDOWN_MIN = 25
FLOOR_USD  = 2.0; DD_LIMIT = 0.35
AM_MULT    = 1.30; AM_MAX = 4

MARKETS = [
    {"sym":"GC=F",     "name":"XAUUSD","cat":"METALS","pip":0.01,  "max_sp":70,"vol":5,"crypto":False},
    {"sym":"SI=F",     "name":"XAGUSD","cat":"METALS","pip":0.001, "max_sp":10,"vol":4,"crypto":False},
    {"sym":"BTC-USD",  "name":"BTCUSD","cat":"CRYPTO","pip":1.0,   "max_sp":100,"vol":5,"crypto":True},
    {"sym":"EURUSD=X", "name":"EURUSD","cat":"FOREX", "pip":0.0001,"max_sp":2, "vol":5,"crypto":False},
    {"sym":"GBPUSD=X", "name":"GBPUSD","cat":"FOREX", "pip":0.0001,"max_sp":3, "vol":5,"crypto":False},
    {"sym":"USDJPY=X", "name":"USDJPY","cat":"FOREX", "pip":0.01,  "max_sp":3, "vol":5,"crypto":False},
    {"sym":"GBPJPY=X", "name":"GBPJPY","cat":"FOREX", "pip":0.01,  "max_sp":6, "vol":5,"crypto":False},
    {"sym":"EURJPY=X", "name":"EURJPY","cat":"FOREX", "pip":0.01,  "max_sp":5, "vol":4,"crypto":False},
    {"sym":"AUDUSD=X", "name":"AUDUSD","cat":"FOREX", "pip":0.0001,"max_sp":3, "vol":4,"crypto":False},
    {"sym":"AUDJPY=X", "name":"AUDJPY","cat":"FOREX", "pip":0.01,  "max_sp":5, "vol":4,"crypto":False},
    {"sym":"CADJPY=X", "name":"CADJPY","cat":"FOREX", "pip":0.01,  "max_sp":5, "vol":4,"crypto":False},
    {"sym":"USDCHF=X", "name":"USDCHF","cat":"FOREX", "pip":0.0001,"max_sp":3, "vol":4,"crypto":False},
    {"sym":"NZDUSD=X", "name":"NZDUSD","cat":"FOREX", "pip":0.0001,"max_sp":3, "vol":3,"crypto":False},
    {"sym":"USDCAD=X", "name":"USDCAD","cat":"FOREX", "pip":0.0001,"max_sp":3, "vol":4,"crypto":False},
    {"sym":"NQ=F",     "name":"NAS100","cat":"INDICES","pip":0.25, "max_sp":5, "vol":5,"crypto":False},
    {"sym":"ES=F",     "name":"SPX500","cat":"INDICES","pip":0.25, "max_sp":3, "vol":5,"crypto":False},
    {"sym":"YM=F",     "name":"US30",  "cat":"INDICES","pip":1.0,  "max_sp":5, "vol":5,"crypto":False},
    {"sym":"CL=F",     "name":"USOIL", "cat":"OIL",   "pip":0.01, "max_sp":8, "vol":4,"crypto":False},
]
CAT_EMO = {"FOREX":"💱","METALS":"🥇","CRYPTO":"₿","INDICES":"📈","OIL":"🛢"}
PAIR_MAX_LEV = {"BTCUSDT":125,"ETHUSDT":100,"SOLUSDT":50,"BNBUSDT":75,"XRPUSDT":50}
# ── Alias constantes v13 (rétrocompatibilité) ─────────────────────
INACTIF_DAYS     = 3
DATA_MAX_AGE_MIN = DATA_MAX_AGE
BOT_USERNAME     = BOT_USER
PRO_PROMO        = PRO_PRICE
NB_AGENTS        = 20
VIP_CHANNEL      = VIP_CH       # alias v13


# ══════════════════════════════════════════════════════
#  LOGGER
# ══════════════════════════════════════════════════════
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S", handlers=[logging.StreamHandler(),
    logging.FileHandler("ab10.log", encoding="utf-8")])
L = logging.getLogger("AB10")
C = {"r":"\033[0m","b":"\033[1m","d":"\033[2m","c":"\033[96m","g":"\033[92m","y":"\033[93m","red":"\033[91m","m":"\033[95m"}
def clr(t,*c): return "".join(C[x] for x in c)+str(t)+C["r"]
def log(lv,msg):
    tags={"INFO":clr(" INFO ","b","c"),"SIG":clr(" SIGNAL","b","g"),"WARN":clr(" WARN ","b","y"),
          "ERR":clr(" ERR  ","b","red"),"PAY":clr(" PAY  ","b","m"),"AI":clr(" AI   ","b","m")}
    print("[{}] {} {}".format(datetime.now().strftime("%H:%M:%S"),tags.get(lv,lv),msg))

# ══════════════════════════════════════════════════════
#  RÉSEAU
# ══════════════════════════════════════════════════════
CTX = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
CTX.check_hostname = False; CTX.verify_mode = ssl.CERT_NONE
CTX.set_ciphers("DEFAULT@SECLEVEL=0")
TG = "https://api.telegram.org/bot{}/".format(TG_TOKEN)
_tg_lock = threading.Lock()

def http_get(url, timeout=15):
    hdrs = {"User-Agent":"Mozilla/5.0","Accept":"application/json"}
    for i in range(3):
        try:
            req = urllib.request.Request(url, headers=hdrs)
            opener = urllib.request.build_opener(urllib.request.HTTPSHandler(context=CTX))
            with opener.open(req, timeout=timeout) as r: return r.read().decode()
        except Exception:
            if i < 2: time.sleep(2)
    raise Exception("Max retries: "+url[:60])

def http_post(url, data, timeout=15):
    raw = urllib.parse.urlencode(data).encode()
    for i in range(3):
        try:
            req = urllib.request.Request(url, data=raw, method="POST",
                headers={"Content-Type":"application/x-www-form-urlencoded"})
            opener = urllib.request.build_opener(urllib.request.HTTPSHandler(context=CTX))
            with opener.open(req, timeout=timeout) as r: return json.loads(r.read().decode())
        except urllib.error.HTTPError as e:
            if e.code == 409: return {}
            if i < 2: time.sleep(2)
            else: return {}
        except Exception:
            if i < 2: time.sleep(2)
            else: return {}
    return {}

def tg_req(m, p):
    try: return http_post(TG+m, p)
    except Exception as e: print("  [TG]", e); return {}

def tg_send(cid, text, kb=None):
    p = {"chat_id":str(cid),"text":text,"parse_mode":"HTML","disable_web_page_preview":"true"}
    if kb: p["reply_markup"] = json.dumps(kb)
    with _tg_lock: return tg_req("sendMessage", p)

def tg_doc(cid, data, fname, caption=""):
    bd = "AB10B"
    body = b""
    def f(n,v): return ("--{}\r\nContent-Disposition: form-data; name=\"{}\"\r\n\r\n".format(bd,n)).encode()+str(v).encode()+b"\r\n"
    body += f("chat_id",cid)
    if caption: body += f("caption",caption); body += f("parse_mode","HTML")
    body += ("--{}\r\nContent-Disposition: form-data; name=\"document\"; filename=\"{}\"\r\nContent-Type: application/octet-stream\r\n\r\n".format(bd,fname)).encode()
    body += data+b"\r\n"+("--{}--\r\n".format(bd)).encode()
    try:
        req = urllib.request.Request(TG+"sendDocument", data=body, method="POST",
            headers={"Content-Type":"multipart/form-data; boundary="+bd})
        opener = urllib.request.build_opener(urllib.request.HTTPSHandler(context=CTX))
        with opener.open(req, timeout=30) as r: return json.loads(r.read().decode())
    except: return {}

STK_W = "CAACAgIAAxkBAAIBjmWbNgIkJ6opkKOd5P2tniQu7R2IAALiAAMW0StFqKjl9SqrXTUNgQ"
STK_WIN = "CAACAgIAAxkBAAIBkmWbNibdCvV2RRd7OjQbIRpQ7juvAAIlAQACB8OhCpNJ8K7ZqLyANgQ"
STK_PRO = "CAACAgIAAxkBAAIBkGWbNhPIhvNXV7yKp9c0wZIf-g2rAAJDAQACvhiBCxlh5gPVk7E_NgQ"
STK_WELCOME = "CAACAgIAAxkBAAIBjmWbNgIkJ6opkKOd5P2tniQu7R2IAALiAAMW0StFqKjl9SqrXTUNgQ"
STK_SIGNAL  = "CAACAgIAAxkBAAIBhGWbNYA1IekbQLJgzf0HuBj0jYFnAAK3AQACB8OhCj1gMCxF9WqKNgQ"
STK_MONEY   = "CAACAgIAAxkBAAIBhmWbNa7lp9yDhKRHx_7q2sDFGn0ZAAKFAQACvhiBC-VC2IuBbHH3NgQ"
STK_FIRE    = "CAACAgIAAxkBAAIBiGWbNcBL0k0ZGIPKHGWBq-fFxgG0AAJcAAMW0StFbJlMpSqAx3oNgQ"
STK_CROWN   = "CAACAgIAAxkBAAIBimWbNeGxR0rp2J0m0eZ7nYJGq7cLAAKXAAMW0StFBtO28qLLMKgNgQ"
STK_ROCKET  = "CAACAgIAAxkBAAIBjGWbNfNMiEkgPZrxgWMVBH1ycfP7AAIbAQACB8OhCsYm5NOoMByuNgQ"
def tg_send_sticker(chat_id, sticker_id): tg_req("sendSticker", {"chat_id": str(chat_id), "sticker": sticker_id})
def tg_sticker(cid, sid): tg_req("sendSticker",{"chat_id":str(cid),"sticker":sid})

# ══════════════════════════════════════════════════════
#  BASE DE DONNÉES
# ══════════════════════════════════════════════════════
_dbl = threading.RLock()  # RLock: réentrant, évite deadlock db_register→db_pro
def _conn():
    c = sqlite3.connect(DB_FILE, check_same_thread=False)
    c.execute("PRAGMA journal_mode=WAL"); c.execute("PRAGMA synchronous=NORMAL")
    return c

def db_init():
    con = _conn(); cur = con.cursor()
    cur.execute("""CREATE TABLE IF NOT EXISTS users(
        user_id INTEGER PRIMARY KEY, username TEXT DEFAULT '',
        plan TEXT DEFAULT 'FREE', ref_by INTEGER DEFAULT 0,
        ref_count INTEGER DEFAULT 0, joined TEXT DEFAULT '',
        pro_expires TEXT, pro_source TEXT, trial_used INTEGER DEFAULT 0,
        last_seen TEXT)""")
    cur.execute("""CREATE TABLE IF NOT EXISTS payments(
        id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER,
        amount REAL, tx_hash TEXT, status TEXT DEFAULT 'PENDING', created TEXT)""")
    cur.execute("""CREATE TABLE IF NOT EXISTS signals(
        id INTEGER PRIMARY KEY AUTOINCREMENT, pair TEXT, side TEXT,
        entry REAL, tp REAL, sl REAL, rr REAL, score INTEGER,
        mode TEXT DEFAULT 'NORMAL', session TEXT DEFAULT '', g001 REAL DEFAULT 0,
        g1 REAL DEFAULT 0, l001 REAL DEFAULT 0, l1 REAL DEFAULT 0, sent_at TEXT)""")
    cur.execute("""CREATE TABLE IF NOT EXISTS sig_counts(
        user_id INTEGER, date_str TEXT, count INTEGER DEFAULT 0,
        PRIMARY KEY(user_id, date_str))""")
    cur.execute("""CREATE TABLE IF NOT EXISTS sig_track(
        id INTEGER PRIMARY KEY AUTOINCREMENT, sig_id INTEGER,
        pair TEXT, entry REAL, tp REAL, sl REAL, side TEXT,
        status TEXT DEFAULT 'OPEN', created TEXT, closed_at TEXT)""")
    cur.execute("""CREATE TABLE IF NOT EXISTS daily_rep(
        id INTEGER PRIMARY KEY AUTOINCREMENT, rep_date TEXT,
        sig_count INTEGER DEFAULT 0, wins INTEGER DEFAULT 0,
        g001 REAL DEFAULT 0, g1 REAL DEFAULT 0, created TEXT)""")
    cur.execute("""CREATE TABLE IF NOT EXISTS weekly_rep(
        id INTEGER PRIMARY KEY AUTOINCREMENT, week_start TEXT,
        sig_count INTEGER DEFAULT 0, wins INTEGER DEFAULT 0,
        g1 REAL DEFAULT 0, created TEXT)""")
    cur.execute("""CREATE TABLE IF NOT EXISTS ai_mem(
        key TEXT PRIMARY KEY, wins INTEGER DEFAULT 0,
        losses INTEGER DEFAULT 0, pnl REAL DEFAULT 0, updated TEXT)""")
    cur.execute("""CREATE TABLE IF NOT EXISTS challenge(
        id INTEGER PRIMARY KEY, balance REAL DEFAULT 5, start_bal REAL DEFAULT 5,
        today_pnl REAL DEFAULT 0, today_w INTEGER DEFAULT 0, today_l INTEGER DEFAULT 0,
        best_rr REAL DEFAULT 0, peak REAL DEFAULT 5, am_cycle INTEGER DEFAULT 0,
        w_streak INTEGER DEFAULT 0, l_streak INTEGER DEFAULT 0,
        day_open REAL DEFAULT 5, day_start TEXT DEFAULT '')""")
    cur.execute("INSERT OR IGNORE INTO challenge(id,balance,start_bal,peak,day_open) VALUES(1,?,?,?,?)",
        (CHALLENGE_START,)*4)
    con.commit(); con.close()
    log("INFO", clr("DB v10 OK","b","g"))

# ── Helpers DB ─────────────────────────────────────────
def db_one(sql, args=()):
    con=_conn(); cur=con.cursor(); cur.execute(sql,args); r=cur.fetchone(); con.close(); return r

def db_all(sql, args=()):
    con=_conn(); cur=con.cursor(); cur.execute(sql,args); r=cur.fetchall(); con.close(); return r

def db_run(sql, args=()):
    con=_conn(); cur=con.cursor()
    with _dbl: cur.execute(sql,args); con.commit()
    con.close()

def db_register(uid, uname, ref_by=0, tg_fn=None):
    con=_conn(); cur=con.cursor()
    with _dbl:
        cur.execute("SELECT user_id FROM users WHERE user_id=?",(uid,))
        if not cur.fetchone():
            now=datetime.now().strftime("%Y-%m-%d")
            cur.execute("INSERT INTO users(user_id,username,plan,ref_by,joined) VALUES(?,?,?,?,?)",(uid,uname or "","FREE",ref_by,now))
            con.commit()
            if ref_by and ref_by!=uid:
                cur.execute("UPDATE users SET ref_count=ref_count+1 WHERE user_id=?",(ref_by,))
                cur.execute("SELECT ref_count FROM users WHERE user_id=?",(ref_by,))
                row=cur.fetchone(); con.commit()
                if row and tg_fn:
                    count=row[0]
                    tg_fn(ref_by,"🎉 <b>Nouveau filleul!</b>\n@{} a rejoint.\n👥 <b>{}/{}</b>".format(uname or "?",count,REF_TARGET))
                    if count>=REF_TARGET:
                        con.close(); db_pro(ref_by,"PARRAINAGE",days=REF_MONTHS*30)
                        tg_fn(ref_by,"🏆 {} filleuls → {} MOIS PRO!".format(REF_TARGET,REF_MONTHS)); return
            # Essai PRO
            cur.execute("SELECT trial_used FROM users WHERE user_id=?",(uid,))
            row=cur.fetchone()
            if row and not row[0]:
                con.close(); db_pro(uid,"TRIAL_{}J".format(TRIAL_DAYS),days=TRIAL_DAYS)
                if tg_fn: tg_fn(uid,"🎁 <b>Essai PRO {} jours!</b>".format(TRIAL_DAYS))
                return
        else:
            if uname:
                cur.execute("UPDATE users SET username=?,last_seen=? WHERE user_id=?",(uname,datetime.now().isoformat(),uid))
                con.commit()
    con.close()

def db_pro(uid, src="PAY", days=None):
    con=_conn(); cur=con.cursor()
    exp=(datetime.now()+timedelta(days=days)).strftime("%Y-%m-%d") if days else None
    with _dbl:
        cur.execute("UPDATE users SET plan='PRO',pro_expires=?,pro_source=? WHERE user_id=?",(exp,src,uid))
        cur.execute("UPDATE payments SET status='CONFIRMED' WHERE user_id=? AND status='PENDING'",(uid,))
        con.commit()
    con.close()

def db_free(uid):
    db_run("UPDATE users SET plan='FREE',pro_expires=NULL,pro_source=NULL WHERE user_id=?",(uid,))

def is_pro(uid):
    r=db_one("SELECT plan FROM users WHERE user_id=?",(uid,))
    return r is not None and r[0] in ("PRO","VIP")

def get_plan(uid):
    r=db_one("SELECT plan FROM users WHERE user_id=?",(uid,)); return r[0] if r else "FREE"

def get_refs(uid):
    r=db_one("SELECT ref_count FROM users WHERE user_id=?",(uid,)); return r[0] if r else 0

def get_pro_info(uid):
    r=db_one("SELECT plan,pro_expires,pro_source FROM users WHERE user_id=?",(uid,))
    return (r[0],r[1],r[2]) if r else ("FREE",None,None)

def pro_users(): return [r[0] for r in db_all("SELECT user_id FROM users WHERE plan IN ('PRO','VIP')")]
def free_users(): return [r[0] for r in db_all("SELECT user_id FROM users WHERE plan='FREE'")]

def find_user(uname):
    uname=uname.lstrip("@").lower()
    for uid,un in db_all("SELECT user_id,username FROM users"):
        if un and un.lower()==uname: return uid
    return None

def count_today(uid):
    ds=datetime.now().strftime("%Y-%m-%d")
    r=db_one("SELECT count FROM sig_counts WHERE user_id=? AND date_str=?",(uid,ds))
    return r[0] if r else 0

def count_incr(uid):
    ds=datetime.now().strftime("%Y-%m-%d"); con=_conn(); cur=con.cursor()
    with _dbl:
        r=cur.execute("SELECT count FROM sig_counts WHERE user_id=? AND date_str=?",(uid,ds)).fetchone()
        if r: cur.execute("UPDATE sig_counts SET count=count+1 WHERE user_id=? AND date_str=?",(uid,ds))
        else: cur.execute("INSERT INTO sig_counts(user_id,date_str,count) VALUES(?,?,1)",(uid,ds))
        con.commit()
    con.close()

def check_expiry():
    today=datetime.now().strftime("%Y-%m-%d")
    expired=db_all("SELECT user_id,username FROM users WHERE plan='PRO' AND pro_expires IS NOT NULL AND pro_expires<?",(today,))
    for uid,_ in expired: db_run("UPDATE users SET plan='FREE',pro_expires=NULL WHERE user_id=?",(uid,))
    return expired

def save_signal(s, sn):
    con=_conn(); cur=con.cursor()
    with _dbl:
        cur.execute("INSERT INTO signals(pair,side,entry,tp,sl,rr,score,mode,session,g001,g1,l001,l1,sent_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (s["name"],s["side"],s["entry"],s["tp"],s["sl"],s["rr"],s["score"],
             s.get("mode","NORMAL"),sn,s.get("g001",0),s.get("g1",0),s.get("l001",0),s.get("l1",0),
             datetime.now().isoformat()))
        lid=cur.lastrowid
        cur.execute("INSERT OR IGNORE INTO sig_track(sig_id,pair,entry,tp,sl,side,created) VALUES(?,?,?,?,?,?,?)",
            (lid,s["name"],s["entry"],s["tp"],s["sl"],s["side"],datetime.now().isoformat()))
        con.commit()
    con.close()

def daily_stats(ds=None):
    ds = ds or datetime.now().strftime("%Y-%m-%d")
    con = _conn(); cur = con.cursor()
    # Récupère les signaux du jour avec leur résultat réel depuis sig_track
    cur.execute("""
        SELECT s.pair, s.side, s.rr, s.g001, s.g1, s.l001, s.l1, s.session, s.mode,
               COALESCE(st.status, 'OPEN') as result
        FROM signals s
        LEFT JOIN sig_track st ON st.sig_id = s.id
        WHERE s.sent_at LIKE ?
        ORDER BY s.sent_at
    """, (ds + "%",))
    rows = cur.fetchall(); con.close()
    # Compter uniquement les vrais TP confirmés (pas estimés)
    confirmed_tp   = [r for r in rows if r[9] == "TP"]
    confirmed_sl   = [r for r in rows if r[9] == "SL"]
    open_signals   = [r for r in rows if r[9] == "OPEN"]
    # Gains réels = uniquement les TP confirmés ; gains estimés = signaux ouverts
    real_g1   = round(sum(r[4] for r in confirmed_tp), 2)
    real_g001 = round(sum(r[3] for r in confirmed_tp), 2)
    pot_g1    = round(sum(r[4] for r in open_signals), 2)   # potentiel si TP
    pot_g001  = round(sum(r[3] for r in open_signals), 2)
    return {
        "date":   ds,
        "n":      len(rows),
        "wins":   len(confirmed_tp),
        "losses": len(confirmed_sl),
        "open":   len(open_signals),
        "g001":   real_g001,
        "g1":     real_g1,
        "pot_g001": pot_g001,
        "pot_g1":   pot_g1,
        "rows":   rows,
    }

def weekly_stats():
    ws=(datetime.now()-timedelta(days=7)).strftime("%Y-%m-%d")
    rows=db_all("SELECT pair,side,rr,g001,g1 FROM signals WHERE sent_at>=? ORDER BY sent_at",(ws+" 00:00",))
    w=sum(1 for r in rows if r[2]>=2.5)
    return {"ws":ws,"n":len(rows),"wins":w,"g001":round(sum(r[3] for r in rows),2),"g1":round(sum(r[4] for r in rows),2)}

def global_stats():
    total=db_one("SELECT COUNT(*) FROM users")[0]; pro=db_one("SELECT COUNT(*) FROM users WHERE plan='PRO'")[0]
    sigs=db_one("SELECT COUNT(*) FROM signals")[0]; pays=db_one("SELECT COUNT(*) FROM payments WHERE status='CONFIRMED'")[0]
    g1d=db_one("SELECT COALESCE(SUM(g1),0) FROM signals WHERE sent_at LIKE ?",(datetime.now().strftime("%Y-%m-%d")+"%",))[0]
    return total,pro,sigs,pays,round(g1d,2)

def rep_sent(ds, tbl="daily_rep", col="rep_date"):
    r=db_one("SELECT 1 FROM {} WHERE {}=?".format(tbl,col),(ds,)); return r is not None

def mark_rep(stats, tbl="daily_rep"):
    if tbl=="daily_rep":
        db_run("INSERT INTO daily_rep(rep_date,sig_count,wins,g001,g1,created) VALUES(?,?,?,?,?,?)",
            (stats["date"],stats["n"],stats["wins"],stats["g001"],stats["g1"],datetime.now().isoformat()))
    else:
        db_run("INSERT INTO weekly_rep(week_start,sig_count,wins,g1,created) VALUES(?,?,?,?,?)",
            (stats["ws"],stats["n"],stats["wins"],stats["g1"],datetime.now().isoformat()))

def save_pay(uid, tx): db_run("INSERT INTO payments(user_id,amount,tx_hash,status,created) VALUES(?,?,?,?,?)",(uid,PRO_PRICE,tx,"PENDING",datetime.now().isoformat()))
def pending_pays(): return db_all("SELECT p.id,p.user_id,u.username,p.tx_hash,p.created FROM payments p LEFT JOIN users u ON p.user_id=u.user_id WHERE p.status='PENDING' ORDER BY p.created DESC LIMIT 10")

def open_signals():
    try: return db_all("SELECT id,pair,entry,tp,sl,side,created FROM sig_track WHERE status='OPEN'")
    except: return []

def close_track(tid, status): db_run("UPDATE sig_track SET status=?,closed_at=? WHERE id=?",(status,datetime.now().isoformat(),tid))

def inactive_users(days=3):
    cutoff=(datetime.now()-timedelta(days=days)).isoformat()
    return db_all("SELECT user_id,username FROM users WHERE plan='FREE' AND (last_seen<? OR last_seen IS NULL) AND joined<?",(cutoff,cutoff))

def chal_get():
    _def = {"balance":CHALLENGE_START,"start_bal":CHALLENGE_START,"today_pnl":0,
            "today_w":0,"today_l":0,"best_rr":0,"peak":CHALLENGE_START,
            "am_cycle":0,"w_streak":0,"l_streak":0,"day_open":CHALLENGE_START,"day_start":""}
    try:
        r = db_one("SELECT balance,start_bal,today_pnl,today_w,today_l,best_rr,"
                   "peak,am_cycle,w_streak,l_streak,day_open,day_start FROM challenge WHERE id=1")
    except Exception:
        return _def
    if not r:
        return _def
    k = ["balance","start_bal","today_pnl","today_w","today_l","best_rr",
         "peak","am_cycle","w_streak","l_streak","day_open","day_start"]
    return dict(zip(k, r))

def chal_save(c):
    today=datetime.now(timezone.utc).strftime("%Y-%m-%d")
    if c.get("day_start")!=today:
        c["day_open"]=c["balance"]; c["today_pnl"]=0; c["today_w"]=0; c["today_l"]=0; c["day_start"]=today
    db_run("UPDATE challenge SET balance=?,today_pnl=?,today_w=?,today_l=?,best_rr=?,peak=?,am_cycle=?,w_streak=?,l_streak=?,day_open=?,day_start=? WHERE id=1",
        (c["balance"],c["today_pnl"],c["today_w"],c["today_l"],c["best_rr"],c["peak"],c["am_cycle"],c["w_streak"],c["l_streak"],c["day_open"],c.get("day_start",today)))

def mem_query(key):
    r=db_one("SELECT wins,losses,pnl FROM ai_mem WHERE key=?",(key,)); return r or (0,0,0.0)

def mem_record(key, result, pnl):
    w,l,p=mem_query(key)
    w+=(1 if result=="WIN" else 0); l+=(0 if result=="WIN" else 1); p=round(p+pnl,4)
    db_run("INSERT OR REPLACE INTO ai_mem(key,wins,losses,pnl,updated) VALUES(?,?,?,?,?)",(key,w,l,p,datetime.now().isoformat()))

# ══════════════════════════════════════════════════════
#  SESSIONS
# ══════════════════════════════════════════════════════
def get_session():
    h=datetime.now(timezone.utc).hour; wd=datetime.now(timezone.utc).weekday()
    if wd>=5: return "WEEKEND",72,"🌍 Week-end ₿",True
    if 7<=h<10:  return "LONDON_KZ",61,"🇬🇧 London Kill Zone 🔥",False
    if 12<=h<16: return "OVERLAP",63,"🇬🇧+🇺🇸 London+NY",False
    if 16<=h<21: return "NY",65,"🇺🇸 New York",False
    if 10<=h<12: return "LONDON",63,"🇬🇧 Londres",False
    if 0<=h<7:   return "ASIAN",68,"🌏 Asiatique",False
    return "OFF",73,"🌑 Hors session",False

def sess_bonus(sn):
    return {"LONDON_KZ":15,"OVERLAP":10,"NY":8,"LONDON":5,"ASIAN":0,"WEEKEND":5,"OFF":-20}.get(sn,0)

# ══════════════════════════════════════════════════════
#  FETCH DONNÉES YAHOO
# ══════════════════════════════════════════════════════
def fetch_c(sym, interval, period):
    sym_e=urllib.parse.quote(sym)
    for base in ["https://query1.finance.yahoo.com","https://query2.finance.yahoo.com"]:
        try:
            url="{}/v8/finance/chart/{}?interval={}&range={}&includePrePost=false".format(base,sym_e,interval,period)
            body=json.loads(http_get(url,timeout=20))
            res=body.get("chart",{}).get("result",[])
            if not res: continue
            ts=res[0].get("timestamp",[])
            if ts and (time.time()-ts[-1])/60>DATA_MAX_AGE:
                log("WARN",clr("{} {} trop vieux — ignoré".format(sym,interval),"y")); return None
            q=res[0]["indicators"]["quote"][0]
            c=[{"o":float(o),"h":float(h),"l":float(l),"c":float(cv)}
               for o,h,l,cv in zip(q.get("open",[]),q.get("high",[]),q.get("low",[]),q.get("close",[]))
               if None not in (o,h,l,cv)]
            if len(c)>=10: return c
        except: continue
    return None

# ══════════════════════════════════════════════════════
#  ANALYSE TECHNIQUE
# ══════════════════════════════════════════════════════
def atr(c,p=14):
    t=[max(c[i]["h"]-c[i]["l"],abs(c[i]["h"]-c[i-1]["c"]),abs(c[i]["l"]-c[i-1]["c"])) for i in range(1,len(c))]
    s=t[-p:] if len(t)>=p else t; return sum(s)/len(s) if s else 0.001

def swings(c,n=5):
    H,L=[],[]
    for i in range(n,len(c)-n):
        w=c[i-n:i+n+1]
        if c[i]["h"]==max(x["h"] for x in w): H.append((i,c[i]["h"]))
        if c[i]["l"]==min(x["l"] for x in w): L.append((i,c[i]["l"]))
    return H,L

def eqh_eql(c,tol=0.0003):
    hi=[x["h"] for x in c[-40:]]; lo=[x["l"] for x in c[-40:]]
    eqh=eql=None
    for i in range(len(hi)-1):
        for j in range(i+1,len(hi)):
            if hi[i] and abs(hi[i]-hi[j])/hi[i]<=tol: eqh=max(hi[i],hi[j]); break
        if eqh: break
    for i in range(len(lo)-1):
        for j in range(i+1,len(lo)):
            if lo[i] and abs(lo[i]-lo[j])/lo[i]<=tol: eql=min(lo[i],lo[j]); break
        if eql: break
    return eqh,eql

def choch_seq(c):
    if len(c)<20: return None,0
    H,L=swings(c,n=3)
    if len(H)<3 or len(L)<3: return None,0
    bear=bull=0
    for k in range(min(3,len(H)-1)):
        if H[-(k+1)][1]<H[-(k+2)][1]: bear+=1
        else: break
    for k in range(min(3,len(L)-1)):
        if L[-(k+1)][1]>L[-(k+2)][1]: bull+=1
        else: break
    if bear>=2: return "BEARISH",bear
    if bull>=2: return "BULLISH",bull
    if bear==1: return "BEARISH",1
    if bull==1: return "BULLISH",1
    return None,0

def detect_bias(c):
    H,L=swings(c,n=3); last=c[-1]["c"]; closes=[x["c"] for x in c]
    cd,cc=choch_seq(c)
    if cc>=2:
        if cd=="BEARISH": return "BEARISH",min(x["l"] for x in c[-10:]),"CHoCHx{}".format(cc)
        if cd=="BULLISH": return "BULLISH",max(x["h"] for x in c[-10:]),"CHoCHx{}".format(cc)
    if len(H)>=2 and len(L)>=2:
        sh1,sh2=H[-1][1],H[-2][1]; sl1,sl2=L[-1][1],L[-2][1]
        if sh1>sh2 and sl1>sl2 and last>sh2: return "BULLISH",sh1,"BOS"
        if sh1<sh2 and sl1<sl2 and last<sl2: return "BEARISH",sl1,"BOS"
        if last>sh1 and sl1>sl2: return "BULLISH",sh1,"CHoCH"
        if last<sl1 and sh1<sh2: return "BEARISH",sl1,"CHoCH"
    ema20=sum(closes[-20:])/20 if len(closes)>=20 else closes[-1]
    ema50=sum(closes[-50:])/50 if len(closes)>=50 else closes[-1]
    if last>ema20 and ema20>ema50: return "BULLISH",max(x["h"] for x in c[-10:]),"TREND"
    if last<ema20 and ema20<ema50: return "BEARISH",min(x["l"] for x in c[-10:]),"TREND"
    if len(closes)>=8:
        slope=(closes[-1]-closes[-8])/closes[-8]
        if slope>0.0005: return "BULLISH",max(x["h"] for x in c[-8:]),"TREND"
        if slope<-0.0005: return "BEARISH",min(x["l"] for x in c[-8:]),"TREND"
    return "NEUTRAL",None,None

def breakers(c,b,lookback=100):
    last=c[-1]["c"]; res=[]; a=atr(c)
    scan=c[-lookback:] if len(c)>lookback else c
    for i in range(2,len(scan)-2):
        ci=scan[i]; co=ci["o"]; cc=ci["c"]; fut=scan[i+1:]
        if b=="BULLISH":
            if cc>=co: continue
            if not any(f["c"]>co for f in fut): continue
            if cc-a*3<=last<=co+a*3: res.append({"top":co,"bottom":cc,"strength":abs(co-cc),"dist":abs(last-(co+cc)/2)})
        else:
            if cc<=co: continue
            if not any(f["c"]<co for f in fut): continue
            if co-a*3<=last<=cc+a*3: res.append({"top":cc,"bottom":co,"strength":abs(cc-co),"dist":abs(last-(co+cc)/2)})
    res.sort(key=lambda x:(-x["strength"],x["dist"]))
    return res

def conf_score(c,b):
    if len(c)<3: return 0
    c1,c2,c3=c[-1],c[-2],c[-3]; o,cc,h,l=c1["o"],c1["c"],c1["h"],c1["l"]
    body=abs(cc-o); rng=h-l
    if rng==0: return 0
    r=body/rng; s=0
    if b=="BULLISH":
        if cc>o: s+=35
        if r>0.5: s+=25
        if min(o,cc)-l>body*0.15: s+=20
        if c2["c"]<cc: s+=10
        if c3["c"]<c2["c"]: s+=5
        if cc>c2["h"]: s+=5
    else:
        if cc<o: s+=35
        if r>0.5: s+=25
        if h-max(o,cc)>body*0.15: s+=20
        if c2["c"]>cc: s+=10
        if c3["c"]>c2["c"]: s+=5
        if cc<c2["l"]: s+=5
    cd,cc2=choch_seq(c)
    if cc2>=2 and cd==b: s+=min(15,cc2*7)
    eq_h,eq_l=eqh_eql(c)
    lp=c[-1]["c"]
    if b=="BEARISH" and eq_h and abs(lp-eq_h)/eq_h<0.005: s+=10
    if b=="BULLISH" and eq_l and abs(lp-eq_l)/eq_l<0.005: s+=10
    return min(s,110)

def fvg(c,bias,look=40):
    if len(c)<3: return None
    scan=c[-look:] if len(c)>look else c; lp=c[-1]["c"]; best=None
    for i in range(1,len(scan)-1):
        if bias=="BULLISH":
            fl,fh=scan[i-1]["h"],scan[i+1]["l"]
            if fh>fl and fl*0.998<=lp<=fh*1.002:
                sz=fh-fl
                if best is None or sz>(best[1]-best[0]): best=(fl,fh)
        else:
            fh2,fl2=scan[i-1]["l"],scan[i+1]["h"]
            if fh2>fl2 and fl2*0.998<=lp<=fh2*1.002:
                sz=fh2-fl2
                if best is None or sz>(best[1]-best[0]): best=(fl2,fh2)
    return best

def ote_zone(sh,sl,bias):
    rng=sh-sl
    if rng<=0: return None,None
    if bias=="BULLISH": return sh-rng*0.786,sh-rng*0.618
    return sl+rng*0.618,sl+rng*0.786

# ══════════════════════════════════════════════════════
#  🧠 MODE IMPROVISATION — Le cœur du v10
# ══════════════════════════════════════════════════════
# Quand il n'y a pas de setup ICT parfait, l'agent improvise :
# il allège les critères si 3 conditions fondamentales sont réunies :
# 1. TENDANCE DE FOND valide (H1 bias clair)
# 2. SESSION active (pas hors marché)
# 3. BROKER OK (pas de spread trop large, pas de news)
# → Il entre sur un setup "simplifié" avec risque réduit

IMPROV_MODES = [
    # (nom, description, risk_mult, score_required)
    ("TREND_FOLLOW",  "Trend Following pur",    0.6, 40),
    ("EMA_BOUNCE",    "Rebond EMA20",            0.5, 35),
    ("RANGE_BREAK",   "Cassure de range",        0.5, 38),
    ("MOMENTUM",      "Momentum directionnel",   0.55,36),
    ("STRUCTURE_PLAY","Structure H1 simple",     0.65,42),
]

def improv_analyze(m, b, h1, m5, sn, news_ok):
    """
    Mode improvisation : génère un signal allégé si la tendance + session
    sont valides, même sans setup ICT complet.
    Retourne un signal ou None.
    """
    if b == "NEUTRAL": return None
    if not news_ok: return None  # jamais sans news ok

    last = m5[-1]["c"]
    a    = atr(m5)
    closes = [x["c"] for x in m5[-20:]]

    # ── EMA 20 / 50 sur M5 ───────────────────────────
    ema20 = sum(closes[-20:])/20 if len(closes)>=20 else closes[-1]
    ema8  = sum(closes[-8:])/8   if len(closes)>=8  else closes[-1]
    ema50 = sum([x["c"] for x in m5][-50:])/50 if len(m5)>=50 else ema20

    # Broker check : spread et fraîcheur (déjà filtrés en amont)
    # Session check
    sess_qual = {"LONDON_KZ":1.0,"OVERLAP":1.0,"NY":0.9,"LONDON":0.8,"ASIAN":0.5,"WEEKEND":0.6,"OFF":0.0}.get(sn,0.5)
    if sess_qual < 0.5: return None

    mode_name = None; side = None; entry = last; sl = 0; tp = 0; sc = 0

    if b == "BULLISH":
        # EMA Bounce : prix au-dessus EMA20 qui rebondit dessus
        if ema8 > ema20 and abs(last - ema20) / ema20 < 0.003:
            mode_name = "EMA_BOUNCE"; side = "BUY"
            sl = ema20 - a * 1.2; tp = last + (last - sl) * 3.0; sc = 72
        # Momentum : 3 bougies vertes consécutives + volume
        elif all(m5[-i]["c"]>m5[-i]["o"] for i in range(1,4)):
            mode_name = "MOMENTUM"; side = "BUY"
            sl = min(x["l"] for x in m5[-5:]) * 0.999
            tp = last + (last - sl) * 3.0; sc = 68
        # Structure H1 : prix au-dessus de la dernière clôture H1
        elif h1[-1]["c"] > h1[-2]["c"] and last > h1[-1]["c"] * 0.999:
            mode_name = "STRUCTURE_PLAY"; side = "BUY"
            sl = h1[-1]["l"] * 0.999; tp = last + (last - sl) * 3.0; sc = 70

    elif b == "BEARISH":
        if ema8 < ema20 and abs(last - ema20) / ema20 < 0.003:
            mode_name = "EMA_BOUNCE"; side = "SELL"
            sl = ema20 + a * 1.2; tp = last - (sl - last) * 3.0; sc = 72
        elif all(m5[-i]["c"]<m5[-i]["o"] for i in range(1,4)):
            mode_name = "MOMENTUM"; side = "SELL"
            sl = max(x["h"] for x in m5[-5:]) * 1.001
            tp = last - (sl - last) * 3.0; sc = 68
        elif h1[-1]["c"] < h1[-2]["c"] and last < h1[-1]["c"] * 1.001:
            mode_name = "STRUCTURE_PLAY"; side = "SELL"
            sl = h1[-1]["h"] * 1.001; tp = last - (sl - last) * 3.0; sc = 70

    if not mode_name or not side: return None

    risk = abs(entry - sl)
    gain = abs(tp - entry)
    if risk <= 0 or gain / risk < 2.5: return None  # RR min 2.5 pour improv

    # Bonus session (+0 à +10)
    sc += int(sess_qual * 10)

    # Score minimum 55 — improvisation très agressive
    if sc < 55: return None

    return {"improv": True, "mode": mode_name, "side": side,
            "entry": entry, "sl": sl, "tp": tp,
            "rr": round(gain/risk,1), "score": sc,
            "risk_mult": 0.5}  # risque réduit de 50% en mode improv

# ══════════════════════════════════════════════════════
#  AGENT ANALYZE PRINCIPAL
# ══════════════════════════════════════════════════════
def news_check():
    try:
        body=json.loads(http_get("https://nfs.faireconomy.media/ff_calendar_thisweek.json",timeout=8))
        now=datetime.utcnow()
        for evt in body:
            if evt.get("impact","")!="High": continue
            try:
                et=datetime.strptime(evt["date"],"%Y-%m-%dT%H:%M:%S%z").replace(tzinfo=None)
                if abs((et-now).total_seconds())<1800: return False,"⚠️ News HIGH: {}".format(evt.get("title","?")[:30])
            except: pass
        return True,"✅ OK"
    except: return True,"✅ OK"


# ══════════════════════════════════════════════════════
#  🌊 AGENT LIQUIDITÉ — Condition OBLIGATOIRE
# ══════════════════════════════════════════════════════
# Avant tout signal, on vérifie que le prix a PRIS de la liquidité.
# Sans ça = signal refusé. Aucune exception.
#
# 3 types de prise de liquidité détectés :
#   1. SWEEP      : franchissement d'un swing high/low récent + retour
#   2. STOP_HUNT  : spike rapide + rejet violent (wick > 2×corps)
#   3. EQH_EQL    : Equal Highs ou Equal Lows touchés (pool de liquidité)

def agent_liquidity(candles, bias, lookback=40):
    """
    Retourne un dict décrivant la prise de liquidité ou None si pas détectée.
    {
      "type"  : "SWEEP" | "STOP_HUNT" | "EQH_EQL",
      "level" : float,        # niveau de liquidité touché
      "score" : int,          # bonus score (+10 à +25)
      "label" : str,          # texte affiché dans le message signal
    }
    """
    if not candles or len(candles) < 10:
        return None

    c     = candles[-lookback:] if len(candles) > lookback else candles
    last  = c[-1]
    lp    = last["c"]
    a     = atr(candles)

    # ── 1. SWEEP : franchissement swing récent + retour dans le range ──
    highs = [x["h"] for x in c[:-3]]
    lows  = [x["l"] for x in c[:-3]]
    if highs and lows:
        prev_hh = max(highs)  # plus haut récent
        prev_ll = min(lows)   # plus bas récent
        cur_h   = last["h"]; cur_l = last["l"]

        if bias == "BULLISH" and cur_l < prev_ll and lp > prev_ll:
            # Prix a cassé le plus bas → swept les longs stops → remonte
            return {"type":"SWEEP", "level":round(prev_ll,5),
                    "score":20, "label":"Sweep LL ✓"}

        if bias == "BEARISH" and cur_h > prev_hh and lp < prev_hh:
            # Prix a cassé le plus haut → swept les short stops → redescend
            return {"type":"SWEEP", "level":round(prev_hh,5),
                    "score":20, "label":"Sweep HH ✓"}

    # ── 2. STOP HUNT : spike + rejet violent (wick long = 2× corps min) ─
    for i in range(-1, -min(5, len(c)), -1):
        cv = c[i]
        body   = abs(cv["c"] - cv["o"])
        if body < a * 0.05:
            continue  # doji, ignorer
        if bias == "BULLISH":
            lower_wick = cv["o"] - cv["l"] if cv["c"] >= cv["o"] else cv["c"] - cv["l"]
            if lower_wick > body * 2.0 and cv["c"] > cv["o"]:
                return {"type":"STOP_HUNT", "level":round(cv["l"], 5),
                        "score":18, "label":"Stop Hunt bas ✓"}
        else:
            upper_wick = cv["h"] - cv["o"] if cv["c"] <= cv["o"] else cv["h"] - cv["c"]
            if upper_wick > body * 2.0 and cv["c"] < cv["o"]:
                return {"type":"STOP_HUNT", "level":round(cv["h"], 5),
                        "score":18, "label":"Stop Hunt haut ✓"}

    # ── 3. EQH / EQL : pool de liquidité externe touché ─────────────────
    tol   = 0.0004
    highs2 = [x["h"] for x in c]
    lows2  = [x["l"] for x in c]
    # Chercher deux highs très proches (Equal Highs) touchés par la bougie actuelle
    if bias == "BEARISH":
        eq_highs = []
        for i in range(len(highs2) - 2):
            for j in range(i + 1, len(highs2) - 1):
                if highs2[i] > 0 and abs(highs2[i] - highs2[j]) / highs2[i] <= tol:
                    eq_highs.append(max(highs2[i], highs2[j]))
        if eq_highs:
            eqh = max(eq_highs)
            if last["h"] >= eqh * (1 - tol) and lp < eqh:
                return {"type":"EQH_EQL", "level":round(eqh, 5),
                        "score":15, "label":"EQH prise ✓"}

    if bias == "BULLISH":
        eq_lows = []
        for i in range(len(lows2) - 2):
            for j in range(i + 1, len(lows2) - 1):
                if lows2[i] > 0 and abs(lows2[i] - lows2[j]) / lows2[i] <= tol:
                    eq_lows.append(min(lows2[i], lows2[j]))
        if eq_lows:
            eql = min(eq_lows)
            if last["l"] <= eql * (1 + tol) and lp > eql:
                return {"type":"EQH_EQL", "level":round(eql, 5),
                        "score":15, "label":"EQL prise ✓"}

    return None  # Pas de prise de liquidité détectée → signal refusé

def agent_analyze(m, score_min, news_ok, q, improv_unlocked=False):
    try:
        sn,_,_,_=get_session()
        h1=fetch_c(m["sym"],"1h","30d") or fetch_c(m["sym"],"4h","60d")
        if not h1 or len(h1)<10:
            q.put({"name":m["name"],"cat":m["cat"],"found":False,"reason":"H1 insuffisant","improv":False}); return
        b,bos,bt=detect_bias(h1)
        if b=="NEUTRAL":
            q.put({"name":m["name"],"cat":m["cat"],"found":False,"reason":"Neutre","improv":False}); return
        time.sleep(0.1)
        m5=fetch_c(m["sym"],"15m","10d") or fetch_c(m["sym"],"5m","5d")
        if not m5 or len(m5)<10:
            q.put({"name":m["name"],"cat":m["cat"],"found":False,"reason":"M15 indispo","improv":False}); return

        # ── Vérif spread ─────────────────────────────
        last5=[abs(x["h"]-x["l"]) for x in m5[-5:] if x["h"]!=x["l"]]
        sp=round(min(last5)/m["pip"]*0.03,2) if last5 else 0
        if sp>m["max_sp"]*1.5:
            q.put({"name":m["name"],"cat":m["cat"],"found":False,"reason":"Spread large","improv":False}); return

        # ── OTE + FVG + CHoCH ────────────────────────
        sh_h1=max(x["h"] for x in h1[-50:]); sl_h1=min(x["l"] for x in h1[-50:])
        lp=m5[-1]["c"]
        ote_lo,ote_hi=ote_zone(sh_h1,sl_h1,b)
        in_ote=bool(ote_lo and ote_hi and ote_lo<=lp<=ote_hi)
        fvg_z=fvg(m5,b)
        cd2,cc2=choch_seq(h1)
        bbs=breakers(m5,b)
        sc=conf_score(m5,b)
        if in_ote:  sc=min(sc+12,115)
        if fvg_z:   sc=min(sc+15,115)
        if cc2>=2:  sc=min(sc+10,115)

        # ── AGENT LIQUIDITÉ — condition OBLIGATOIRE ───
        liq = agent_liquidity(m5, b)
        if not liq:
            # Pas de prise de liquidité → signal refusé, même si score OK
            q.put({"name":m["name"],"cat":m["cat"],"found":False,
                   "reason":"No liquidity sweep","improv":False}); return
        # Bonus score si liquidité confirmée
        sc = min(sc + liq["score"], 115)

        a=atr(m5); a_pct=a/(m5[-1]["c"]+0.0001)
        s_min=score_min+(m.get("vol",3)-3)*2+min(4,int(a_pct*100*5))

        sig = None

        # ── MODE NORMAL : setup ICT complet ──────────
        if bbs and sc>=s_min and (news_ok or sc>=s_min+8):
            bb=bbs[0]; e=lp; buf=a*0.15; sp_p=sp*m["pip"]
            eq_h,eq_l=eqh_eql(m5)
            if b=="BULLISH":
                sl=bb["bottom"]-buf-sp_p; risk=e-sl
                if risk<=0 or risk>a*10: pass
                else:
                    tp=(eq_h*0.9995) if (eq_h and e<eq_h<e+risk*5) else e+risk*2.5
                    gain_brut=abs(tp-e); gain_net=gain_brut-sp_p
                    # RR net : spread déduit du gain ET ajouté au risque
                    rr=round(gain_net/(risk+sp_p),1) if (risk+sp_p)>0 else 0
                    if rr>=2.0:  # seuil 2.0 (2.5 avec spread inclus ≈ 2.0 net)
                        badges=[]
                        if in_ote: badges.append("OTE ✓")
                        if fvg_z: badges.append("FVG ✓")
                        if cc2>=2: badges.append("CHoCHx{} ✓".format(cc2))
                        dp=2 if e>1000 else (3 if e>10 else 5); f=lambda v:round(v,dp); pip=m["pip"]
                        ptp=gain_net/pip; psl=(risk+sp_p)/pip  # pips nets
                        badges_full = badges[:]
                        if liq: badges_full.insert(0, liq["label"])
                        sig={"name":m["name"],"cat":m["cat"],"side":"BUY","entry":f(e),"tp":f(tp),"sl":f(sl),"rr":rr,
                             "score":sc,"score_min":s_min,"atr":f(a),"sp":sp,"bias":b,"btype":bt,
                             "g001":round(ptp*0.01,2),"g01":round(ptp*0.1,2),"g1":round(ptp,2),
                             "l001":round(psl*0.01,2),"l01":round(psl*0.1,2),"l1":round(psl,2),
                             "badges":" · ".join(badges_full),"time":datetime.now(timezone.utc).strftime("%H:%M"),
                             "liq":liq,"mode":"NORMAL","risk_mult":1.0}
            else:
                sl=bb["top"]+buf+sp_p; risk=sl-e
                if risk<=0 or risk>a*10: pass
                else:
                    tp=(eq_l*1.0005) if (eq_l and e-risk*5<eq_l<e) else e-risk*2.5
                    gain_brut=abs(tp-e); gain_net=gain_brut-sp_p
                    rr=round(gain_net/(risk+sp_p),1) if (risk+sp_p)>0 else 0
                    if rr>=2.0:
                        badges=[]
                        if in_ote: badges.append("OTE ✓")
                        if fvg_z: badges.append("FVG ✓")
                        if cc2>=2: badges.append("CHoCHx{} ✓".format(cc2))
                        dp=2 if e>1000 else (3 if e>10 else 5); f=lambda v:round(v,dp); pip=m["pip"]
                        ptp=gain_net/pip; psl=(risk+sp_p)/pip
                        badges_full = badges[:]
                        if liq: badges_full.insert(0, liq["label"])
                        sig={"name":m["name"],"cat":m["cat"],"side":"SELL","entry":f(e),"tp":f(tp),"sl":f(sl),"rr":rr,
                             "score":sc,"score_min":s_min,"atr":f(a),"sp":sp,"bias":b,"btype":bt,
                             "g001":round(ptp*0.01,2),"g01":round(ptp*0.1,2),"g1":round(ptp,2),
                             "l001":round(psl*0.01,2),"l01":round(psl*0.1,2),"l1":round(psl,2),
                             "badges":" · ".join(badges_full),"time":datetime.now(timezone.utc).strftime("%H:%M"),
                             "liq":liq,"mode":"NORMAL","risk_mult":1.0}

        # ── MODE IMPROVISATION : uniquement après 500 cycles sans signal ICT ──
        if not sig and improv_unlocked:
            # Cooldown par paire : 4h minimum entre deux improv sur la même paire
            last_improv_ts = _improv_cd.get(m["name"], 0)
            if time.time() - last_improv_ts < 1 * 3600:
                # Cooldown actif → pas d'improv
                pass
            else:
                improv = improv_analyze(m, b, h1, m5, sn, news_ok)
                if improv and improv["rr"] >= 2.5:   # RR minimum 2.5 pour improv
                    e = improv["entry"]; tp = improv["tp"]; sl_v = improv["sl"]
                    dp = 2 if e > 1000 else (3 if e > 10 else 5)
                    f  = lambda v: round(v, dp); pip = m["pip"]
                    gain = abs(tp - e); risk = abs(e - sl_v)
                    ptp  = gain / pip;  psl  = risk / pip
                    sig  = {"name":m["name"],"cat":m["cat"],"side":improv["side"],
                            "entry":f(e),"tp":f(tp),"sl":f(sl_v),"rr":improv["rr"],
                            "score":improv["score"],"score_min":s_min,"atr":f(a),"sp":sp,
                            "bias":b,"btype":bt,
                            "g001":round(ptp*0.01,2),"g01":round(ptp*0.1,2),"g1":round(ptp,2),
                            "l001":round(psl*0.01,2),"l01":round(psl*0.1,2),"l1":round(psl,2),
                            "badges":"Mode: {}".format(improv["mode"]),
                            "time":datetime.now(timezone.utc).strftime("%H:%M"),
                            "mode":improv["mode"],"risk_mult":improv["risk_mult"],
                            "improv":True,
                            "improv_cycles":_cycles_no_signal}  # info cycles pour le message

        if sig:
            q.put({"name":m["name"],"cat":m["cat"],"found":True,"signal":sig,
                   "improv":sig.get("improv",False)})
        else:
            q.put({"name":m["name"],"cat":m["cat"],"found":False,
                   "reason":"Score {}/{}{}".format(sc,s_min," — improv impossible" if not news_ok else ""),
                   "improv":False})
    except Exception as ex:
        q.put({"name":m["name"],"cat":m["cat"],"found":False,"reason":str(ex)[:40],"improv":False})

# ══════════════════════════════════════════════════════
#  BINANCE IA (Crypto futures)
# ══════════════════════════════════════════════════════
AI_C   = defaultdict(lambda: defaultdict(deque))
AI_P   = {}
AI_PRS = []
AI_REG = {"regime":"RANGING","min_score":72,"risk_mult":1.0,"lev_cap":15,"label":"Init"}
AI_OT  = {}
AI_TC  = 0
AI_CD  = {}
_ai_lk = threading.Lock()
EXCH   = {}; EXCH_TS = 0

def b_get(ep, p=None):
    try:
        url="{}{}?{}".format(BINANCE_BASE,ep,urllib.parse.urlencode(p or {}))
        return json.loads(http_get(url,timeout=8))
    except: return None

def bn_price(sym):
    d=b_get("/ticker/price",{"symbol":sym}); return float(d["price"]) if d and "price" in d else None

def bn_klines(sym,tf="5m",lim=60):
    d=b_get("/klines",{"symbol":sym,"interval":tf,"limit":lim})
    if not d or not isinstance(d,list): return None
    return [{"ts":int(k[0]),"open":float(k[1]),"high":float(k[2]),"low":float(k[3]),"close":float(k[4]),"vol":float(k[5])} for k in d]

def bn_fund(sym):
    d=b_get("/premiumIndex",{"symbol":sym}); return float(d["lastFundingRate"])*100 if d and "lastFundingRate" in d else None

def refresh_exch():
    global EXCH_TS
    try:
        d=json.loads(http_get("{}/exchangeInfo".format(BINANCE_BASE),timeout=12))
        for s in d.get("symbols",[]):
            nm=s["symbol"]; info={"step":1.0,"minQty":0.0,"minNot":5.0,"tick":0.01}
            for f in s.get("filters",[]):
                if f["filterType"]=="LOT_SIZE": info["step"]=float(f["stepSize"]); info["minQty"]=float(f["minQty"])
                elif f["filterType"]=="MIN_NOTIONAL": info["minNot"]=float(f.get("notional",5.0))
                elif f["filterType"]=="PRICE_FILTER": info["tick"]=float(f["tickSize"])
            EXCH[nm]=info
        EXCH_TS=time.time(); log("AI",clr("Exchange info OK ({})".format(len(EXCH)),"g"))
    except Exception as e: log("WARN","[EXCH] {}".format(e))

def lot_calc(sym,risk,sld,entry,lev):
    info=EXCH.get(sym,{"step":0.001,"minQty":0.001,"minNot":5.0})
    step=info["step"]; minq=info["minQty"]; minn=info["minNot"]
    p=max(0,round(-math.log10(step))) if step>0 else 3
    qty=round(math.floor((risk/sld if sld>0 else 0)/step)*step,p); qty=max(qty,minq)
    not_=qty*entry
    if not_<minn: qty=round(math.floor(minn/entry*1.02/step)*step,p); qty=max(qty,minq); not_=qty*entry
    ft=not_*FEE_TAKER*2
    return {"qty":qty,"not":round(not_,4),"ft":round(ft,6),"rr":round(qty*sld+ft,4)}

def regime_detect():
    global AI_REG
    c4=list(AI_C["BTCUSDT"].get("4h",deque()))
    if len(c4)<20: return
    recent=c4[-20:]
    cl=[c["close"] for c in recent]; hi=[c["high"] for c in recent]; lo=[c["low"] for c in recent]
    a_raw=sum(h-l for h,l in zip(hi,lo))/len(recent)
    a_pct=a_raw/cl[-1]*100 if cl[-1]>0 else 0
    mom=(cl[-1]-cl[0])/cl[0]*100 if cl[0]>0 else 0
    mv=max(abs(c["close"]-c["open"])/c["open"]*100 for c in recent[-5:] if c["open"]>0)
    if a_pct>5 or mv>8:    r="CRISIS";  ms=95; rm=0.3; lc=3
    elif a_pct>3:           r="VOLATILE";ms=85; rm=0.6; lc=7
    elif abs(mom)>3:        r="TRENDING";ms=70; rm=1.2; lc=20
    elif (max(hi)-min(lo))/sum(cl)*len(cl)*100<3: r="ACCUM"; ms=76; rm=1.0; lc=15
    else:                   r="RANGING"; ms=78; rm=0.8; lc=10
    AI_REG={"regime":r,"min_score":ms,"risk_mult":rm,"lev_cap":lc,
             "atr_pct":round(a_pct,2),"mom":round(mom,2),"label":r}
    log("AI",clr("Régime: {} ATR:{:.1f}% Mom:{:.1f}%".format(r,a_pct,mom),"c"))

def refresh_ai():
    global AI_PRS
    try:
        d=b_get("/ticker/24hr")
        if d and isinstance(d,list):
            u=[t for t in d if t["symbol"].endswith("USDT") and "_" not in t["symbol"]]
            u.sort(key=lambda t:float(t.get("quoteVolume",0)),reverse=True)
            AI_PRS=[t["symbol"] for t in u[:25]]
    except: pass
    for sym in AI_PRS[:20]:
        for tf,lim in [("5m",60),("15m",40),("1h",48),("4h",50)]:
            c=bn_klines(sym,tf,lim)
            if c: AI_C[sym][tf]=deque(c,maxlen=lim)
            if tf=="5m" and c: AI_P[sym]=c[-1]["close"]
        time.sleep(0.07)
    regime_detect()
    log("AI",clr("Binance {} paires OK".format(len(AI_PRS)),"g"))

def ai_btc_bias():
    s={"BULL":0,"BEAR":0}
    for tf,w in [("5m",1),("1h",2),("4h",3)]:
        c=list(AI_C["BTCUSDT"].get(tf,deque()))
        if len(c)<5: continue
        cl=[x["close"] for x in c[-10:]]
        d=(cl[-1]-cl[0])/cl[0]*100 if cl[0]>0 else 0
        if d>0.3: s["BULL"]+=w
        elif d<-0.3: s["BEAR"]+=w
    if s["BULL"]>s["BEAR"]+1: return "BULL"
    if s["BEAR"]>s["BULL"]+1: return "BEAR"
    return "RANGE"

def ai_risk(bal,sc,am,sess):
    if bal<15: b=0.10
    elif bal<30: b=0.09
    elif bal<75: b=0.08
    else: b=0.06
    if sc>=90: b*=1.2
    elif sc>=80: b*=1.1
    b*=AI_REG.get("risk_mult",1.0)
    if "KZ" in sess or "OVERLAP" in sess: b*=1.1
    b*=(AM_MULT**am)
    return round(min(bal*b, bal*0.20),4)

def ai_lev(sym,bal,sc):
    if bal<15: base=5
    elif bal<30: base=7
    elif bal<75: base=10
    else: base=15
    if sc>=88: base=min(base+2,25)
    return min(base,AI_REG.get("lev_cap",15),PAIR_MAX_LEV.get(sym,20))

def ai_scan_sym(sym,bias,bal):
    c5=list(AI_C[sym].get("5m",deque()))
    c15=list(AI_C[sym].get("15m",deque()))
    if len(c5)<12: return None
    ch=chal_get()
    if ch["balance"]<FLOOR_USD: return None
    dop=ch.get("day_open",ch["balance"])
    if dop>0 and (dop-ch["balance"])/dop>=DD_LIMIT: return None
    sn,_,_,_=get_session()
    if sn=="OFF": return None
    reg=AI_REG
    cd=AI_CD.get(sym)
    if cd and datetime.now(timezone.utc)<cd: return None
    with _ai_lk:
        if any(t["symbol"]==sym and t["status"]=="open" for t in AI_OT.values()): return None
    a=max(c5[-1]["close"]-c5[-1]["open"] for _ in [1]); price=c5[-1]["close"]

    # ── Détection OB simple ───────────────────────────
    n=len(c5); a_v=sum(abs(x["close"]-x["open"]) for x in c5[-14:])/14 if len(c5)>=14 else 0.01
    sig=None; strat="OB"

    for i in range(n-3,max(n-12,2),-1):
        c0,c1,c2=c5[i-2],c5[i-1],c5[i]
        b2=abs(c1["close"]-c1["open"]); r=c1["high"]-c1["low"]
        if r==0: continue
        bull_i=c2["close"]>c2["open"] and (c2["close"]-c2["open"])>b2*1.0
        bear_i=c2["close"]<c2["open"] and (c2["open"]-c2["close"])>b2*1.0
        if c1["close"]<c1["open"] and bull_i and bias!="BEAR" and c1["low"]<=price<=c1["high"]*1.004:
            sl=c1["low"]*0.998; sld=price-sl
            if 0<sld<=a_v*4:
                sig={"side":"BUY","entry":price,"sl":sl,"tp1":price+sld*2.5,"tp2":price+sld*5,"sc":68}; break
        if c1["close"]>c1["open"] and bear_i and bias!="BULL" and c1["low"]*0.996<=price<=c1["high"]:
            sl=c1["high"]*1.002; sld=sl-price
            if 0<sld<=a_v*4:
                sig={"side":"SELL","entry":price,"sl":sl,"tp1":price-sld*2.5,"tp2":price-sld*5,"sc":68}; break

    # ── Liq sweep simple ─────────────────────────────
    if not sig:
        rec=c5[n-15:n-3] if n>=15 else c5
        sh=max(x["high"] for x in rec); sl2=min(x["low"] for x in rec)
        if any(x["high"]>sh for x in c5[n-5:n-1]) and price<sh and bias!="BULL":
            sl_v=max(x["high"] for x in c5[n-5:n])*1.002; sld=sl_v-price
            if 0<sld<=a_v*4:
                sig={"side":"SELL","entry":price,"sl":sl_v,"tp1":price-sld*3,"tp2":price-sld*6,"sc":72}; strat="LIQ"
        if not sig and any(x["low"]<sl2 for x in c5[n-5:n-1]) and price>sl2 and bias!="BEAR":
            sl_v=min(x["low"] for x in c5[n-5:n])*0.998; sld=price-sl_v
            if 0<sld<=a_v*4:
                sig={"side":"BUY","entry":price,"sl":sl_v,"tp1":price+sld*3,"tp2":price+sld*6,"sc":72}; strat="LIQ"

    if not sig: return None

    sld=abs(sig["entry"]-sig["sl"])
    sc=sig["sc"]+sess_bonus(sn)

    # Mémoire
    w,l,_=mem_query("{}|{}|{}".format(strat,sn,reg.get("regime","?")))
    t=w+l
    if t>=3:
        wr=w/t
        if wr>0.85: sc+=8
        elif wr<0.45: sc-=12

    min_sc=reg.get("min_score",72)
    if sc<min_sc: return None

    risk=ai_risk(bal,sc,ch["am_cycle"],sn)
    lev=ai_lev(sym,bal,sc)
    lot=lot_calc(sym,risk,sld,sig["entry"],lev)
    if not lot["qty"]: return None

    return {"sym":sym,"side":sig["side"],"entry":sig["entry"],"sl":sig["sl"],
            "tp1":sig["tp1"],"tp2":sig["tp2"],"sc":sc,"rr":round(abs(sig["tp1"]-sig["entry"])/sld,1),
            "risk":risk,"lev":lev,"qty":lot["qty"],"not":lot["not"],
            "ft":lot["ft"],"rr_real":lot["rr"],
            "strat":strat,"sess":sn,"regime":reg.get("regime","?"),
            "am":ch["am_cycle"]}

def ai_full_scan():
    bias=ai_btc_bias(); ch=chal_get(); bal=ch["balance"]
    res=[]
    for sym in AI_PRS[:20]:
        s=ai_scan_sym(sym,bias,bal)
        if s: res.append(s)
    res.sort(key=lambda x:(-x["sc"],-x["rr"]))
    return res

def ai_open(setup):
    global AI_TC
    AI_TC+=1; tid=AI_TC; sym=setup["sym"]
    trade={"id":tid,"symbol":sym,"side":setup["side"],
           "entry":setup["entry"],"sl":setup["sl"],"sl0":setup["sl"],
           "tp1":setup["tp1"],"tp2":setup["tp2"],
           "risk":setup["risk"],"rr":setup["rr"],"lev":setup["lev"],
           "qty":setup["qty"],"not":setup["not"],"ft":setup["ft"],
           "strat":setup["strat"],"sc":setup["sc"],"am":setup["am"],
           "sess":setup["sess"],"regime":setup["regime"],
           "status":"open","be":False,"tp1_hit":False,
           "open_ts":datetime.now(timezone.utc).isoformat()}
    with _ai_lk:
        AI_OT[tid]=trade
        AI_CD[sym]=datetime.now(timezone.utc)+timedelta(minutes=COOLDOWN_MIN)
    ch=chal_get(); bal=ch["balance"]
    d="🟢 LONG" if setup["side"]=="BUY" else "🔴 SHORT"
    prog=chal_prog(ch)
    tg_send(ADMIN_ID,
        "<b>━━━ TRADE IA #{} ━━━</b>\n{} <b>{}</b>\n"
        "🎯 Score:{}/100  RR:1:{}\n"
        "📍 {:.5f}  🛑 {:.5f}\n"
        "✅ TP1:{:.5f}  🏆 TP2:{:.5f}\n"
        "📦 Qty:{}  {}$  Lev:{}x\n"
        "💸 Frais:{:.5f}$  Risk:{:.4f}$\n"
        "🕐 {}  🌍 {}  📊 {}\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "{}\n<b>@leaderOdg</b>".format(
            tid,d,sym,setup["sc"],setup["rr"],
            setup["entry"],setup["sl"],setup["tp1"],setup["tp2"],
            setup["qty"],round(setup["not"],2),setup["lev"],
            setup["ft"],setup["risk"],
            setup["sess"],setup["regime"],setup["strat"],prog))
    if setup["sc"]>=78:
        for puid in pro_users(): tg_send(puid,"<b>📊 Signal IA #{} — {} {}</b>\n{} Score:{}/100 RR:1:{}\n📍 {:.5f} → TP:{:.5f} SL:{:.5f}\n<b>@leaderOdg</b>".format(tid,sym,d,setup["strat"],setup["sc"],setup["rr"],setup["entry"],setup["tp1"],setup["sl"])); time.sleep(0.04)
    log("AI",clr("#{} {} {} Sc:{} Qty:{} Risk:{:.4f}$".format(tid,sym,"L" if setup["side"]=="BUY" else "S",setup["sc"],setup["qty"],setup["risk"]),"g"))
    return tid

def ai_check():
    with _ai_lk: trades=list(AI_OT.values())
    ch=chal_get()
    for t in trades:
        if t["status"]!="open": continue
        price=bn_price(t["symbol"])
        if price is None: continue
        side=t["side"]; entry=t["entry"]; sl=t["sl"]; tp1=t["tp1"]; tp2=t["tp2"]
        sld0=abs(entry-t["sl0"])
        rrc=((price-entry)/sld0 if side=="BUY" else (entry-price)/sld0) if sld0>0 else 0
        if rrc>=1.0 and not t["be"]:
            be=entry*1.0002 if side=="BUY" else entry*0.9998
            with _ai_lk: t["sl"]=be; t["be"]=True
            tg_send(ADMIN_ID,"<b>🔒 BE #{} — {}</b>\nRR:{:.2f} SL→{:.5f}\n<b>@leaderOdg</b>".format(t["id"],t["symbol"],rrc,be))
        hit_tp1=(price>=tp1 if side=="BUY" else price<=tp1)
        if hit_tp1 and not t["tp1_hit"]:
            p=round(t["risk"]*rrc-t["ft"],4)
            with _ai_lk: t["tp1_hit"]=True; t["sl"]=tp1
            tg_send(ADMIN_ID,"<b>✅ TP1 #{} — {}</b>\n+{:.4f}$ SL→TP2:{:.5f}\n<b>@leaderOdg</b>".format(t["id"],t["symbol"],p,tp2))
        hit_sl=(price<=sl if side=="BUY" else price>=sl)
        hit_tp2=(price>=tp2 if side=="BUY" else price<=tp2)
        if hit_sl or hit_tp2:
            gross=t["risk"]*(rrc if (hit_tp2 or t["tp1_hit"]) else -1)
            net=round(gross-t["ft"],4)
            result="WIN" if (hit_tp2 or (t["tp1_hit"] and hit_sl)) else ("BE" if t["be"] else "LOSS")
            with _ai_lk: t.update({"status":"closed","exit":price,"pnl":net,"result":result,"close_ts":datetime.now(timezone.utc).isoformat()})
            dur=""
            try:
                od=datetime.fromisoformat(t.get("open_ts",""))
                dur="{}min".format(int((datetime.now(timezone.utc)-od).total_seconds()/60))
            except: pass
            am_old=ch["am_cycle"]
            if result=="WIN": ch["w_streak"]=ch.get("w_streak",0)+1; ch["l_streak"]=0; ch["am_cycle"]=0 if ch["w_streak"]>=AM_MAX else min(ch["am_cycle"]+1,AM_MAX)
            else: ch["l_streak"]=ch.get("l_streak",0)+1; ch["am_cycle"]=0; ch["w_streak"]=0
            ch["balance"]=round(ch["balance"]+net,4); ch["today_pnl"]=round(ch.get("today_pnl",0)+net,4)
            if net>0: ch["today_w"]=ch.get("today_w",0)+1
            else: ch["today_l"]=ch.get("today_l",0)+1
            ch["best_rr"]=max(ch.get("best_rr",0),float(t["rr"])); ch["peak"]=max(ch.get("peak",ch["balance"]),ch["balance"])
            chal_save(ch)
            mem_record("{}|{}|{}".format(t.get("strat","?"),t.get("sess","?"),t.get("regime","?")),result,net)
            hdr={"WIN":"✅ GAGNANT","BE":"🔒 BE","LOSS":"❌ PERDANT"}[result]
            tg_send(ADMIN_ID,"<b>━━━ {} #{} ━━━</b>\n{} <b>{}</b>\n📍{:.5f}→<b>{:.5f}</b>\n💵 {:+.4f}$  Frais:-{:.5f}$\n📐 RR:{:.2f}  ⏱{}\n🔄 AM:{}→{}\n{}\n<b>@leaderOdg</b>".format(
                hdr,t["id"],"🟢" if side=="BUY" else "🔴",t["symbol"],
                entry,price,net,t["ft"],rrc,dur,am_old,ch["am_cycle"],chal_prog(ch)))
            if result=="WIN": tg_send(CHANNEL_ID,"<b>✅ WIN IA #{} — {}</b>\n+{:.4f}$ RR:{:.2f}\nSolde:{:.4f}$\n<b>@leaderOdg</b>".format(t["id"],t["symbol"],net,rrc,ch["balance"]))

def chal_prog(c):
    bal=c["balance"]; start=c["start_bal"]; target=start*100
    prog=min(100,bal/target*100) if target>0 else 0
    bar="█"*int(prog/5)+"░"*(20-int(prog/5))
    return "[{}] {:.1f}%\n{:.4f}$ → {:.0f}$".format(bar,prog,bal,target)

# ══════════════════════════════════════════════════════
#  FORMATAGE SIGNAUX
# ══════════════════════════════════════════════════════
MODE_LABELS = {
    "NORMAL":"ICT/SMC ✓","EMA_BOUNCE":"EMA Bounce 📊",
    "MOMENTUM":"Momentum 🚀","STRUCTURE_PLAY":"Structure H1 🏗",
    "RANGE_BREAK":"Cassure Range 📐","TREND_FOLLOW":"Trend Following 📈",
    "OB":"Order Block","LIQ":"Liquidity Sweep",
}

def _score_label(sc):
    """Retourne une évaluation textuelle du score de confiance."""
    if sc >= 90: return "🔥 ÉLITE"
    if sc >= 80: return "💎 PREMIUM"
    if sc >= 70: return "✅ SOLIDE"
    if sc >= 60: return "📊 CORRECT"
    return "⚠️ FAIBLE"

def _confidence_bar(sc):
    filled = sc // 10
    return "█" * filled + "░" * (10 - filled) + f"  {sc}/100"

def fmt_pro(s, news, sl_label):
    se       = "🟢" if s["side"] == "BUY" else "🔴"
    arrow    = "📈" if s["side"] == "BUY" else "📉"
    sf       = "ACHAT" if s["side"] == "BUY" else "VENTE"
    emo      = CAT_EMO.get(s["cat"], "📊")
    mode_lbl = MODE_LABELS.get(s["mode"], "?")
    liq      = s.get("liq") or {}
    liq_line = f'💧 Liquidité : <b>{liq.get("label","—")}</b>  (niveau {liq.get("level","—")})' if liq else ""
    is_improv= s.get("improv", False)
    bar      = _confidence_bar(s["score"])
    sc_lbl   = _score_label(s["score"])
    news_lbl = "✅ Calme" if "✅" in news else "⚠️ Actif"
    sp_s     = "✅ OK" if s["sp"] < 3 else "⚠️ Large"
    sep      = "═" * 24

    # ── Phrase d'accroche selon le score ────────────────────────────
    if s["score"] >= 85:
        hook = "🔥 <b>Setup PREMIUM — Confluence maximale</b>"
    elif s["score"] >= 75:
        hook = "💎 <b>Setup de haute qualité — ICT confirmé</b>"
    else:
        hook = "📊 <b>Setup valide — Conditions réunies</b>"
    if is_improv:
        hook = "⚡ <b>Mode Improvisation — Setup allégé</b>"

    lines = [
        f"{arrow} {se} <b>SIGNAL PRO {sf} · {s['name']}</b>  {emo}",
        sep,
        hook,
        liq_line,
        f"🕐 {s['time']} UTC  ·  {sl_label}",
        "",
        "┌─ <b>NIVEAUX</b> ──────────────────",
        f"│  📍 Entrée : <code>{s['entry']}</code>",
        f"│  ✅ TP     : <code>{s['tp']}</code>",
        f"│  ❌ SL     : <code>{s['sl']}</code>",
        f"│  📐 RR     : <b>1:{s['rr']}</b>",
        "└───────────────────────────",
        "",
        f"💵 Lot 0.01 : <b>+${s['g001']}</b> TP  /  <b>-${s['l001']}</b> SL",
        f"💰 Lot 1.00 : <b>+${s['g1']}</b> TP  /  <b>-${s['l1']}</b> SL",
        "",
        "┌─ <b>ANALYSE IA</b> ─────────────────",
        f"│  {sc_lbl}  [{bar}]",
        f"│  Tendance : <b>{s['bias']}</b>  ({s['btype']})",
        f"│  Mode     : <b>{mode_lbl}</b>",
        f"│  {s.get('badges', '—')}",
        "└───────────────────────────",
        "",
        f"📰 News: {news_lbl}  ·  Spread: {sp_s}",
        sep,
        "⚠️ Risk 1-2% max  ·  Not financial advice",
        "🤖 <b>AlphaBot PRO</b>  ·  @leaderodg_bot",
    ]
    return "\n".join(l for l in lines if l is not None)

def fmt_free(s, news, sl_label):
    se    = "🟢" if s["side"] == "BUY" else "🔴"
    sf    = "ACHAT" if s["side"] == "BUY" else "VENTE"
    emo   = CAT_EMO.get(s["cat"], "📊")
    sep   = "═" * 22
    arrow = "📈" if s["side"] == "BUY" else "📉"
    liq   = s.get("liq") or {}

    if s["score"] >= 85:
        hook = "🔥 <b>Setup PREMIUM — Score élite</b>"
    elif s["score"] >= 75:
        hook = "💎 <b>Setup ICT confirmé — Haute confiance</b>"
    elif s.get("improv"):
        hook = "⚡ <b>Setup allégé — Mode Improvisation</b>"
    else:
        hook = "📊 <b>Setup valide — Conditions réunies</b>"

    lines = [
        f"{arrow} {se} <b>{s['name']} — {sf}</b>  {emo}",
        sep,
        hook,
        f"💧 <b>{liq.get('label', 'Liquidité ✓')}</b>" if liq else "💧 Liquidité confirmée ✓",
        "",
        f"📍 Entrée : <code>{s['entry']}</code>",
        f"✅ TP     : <code>{s['tp']}</code>",
        f"❌ SL     : <code>{s['sl']}</code>",
        f"📐 RR     : <b>1:{s['rr']}</b>  ·  🎯 Score : <b>{s['score']}/100</b>",
        "",
        f"💵 Lot 0.01 : <b>+${s['g001']}</b>  /  💰 Lot 1.00 : <b>+${s['g1']}</b>",
        "",
        sep,
        "🚨 <b>Tu vois ce signal FREE ?</b>",
        f"Les membres PRO en reçoivent <b>10/jour</b> comme ça.",
        f"Toi tu en as droit à <b>{FREE_LIMIT} seulement.</b> 😬",
        "",
        "⏳ Pendant que tu attends ton prochain signal,",
        "<b>les PRO exécutent déjà les suivants.</b>",
        "",
        f"💎 <b>Passe PRO — seulement {PRO_PRICE}$ USDT</b>",
        "👉 @leaderodg_bot  →  /pay",
        sep,
        "🤖 AlphaBot PRO  ·  @leaderodg_bot",
    ]
    return "\n".join(l for l in lines if l is not None)

def fmt_scan(results,news,scan_t,sl_l,sm,nb):
    st=daily_stats(); ch=chal_get(); reg=AI_REG
    improv_count=sum(1 for r in results if r.get("improv"))
    lines=["🔍 <b>SCAN {} UTC</b>  ·  {}".format(scan_t,sl_l),
           "🎯 Score min:<b>{}</b>  ·  News:{}".format(sm,"✅" if "✅" in news else "⚠️"),
           "💵 Confirmés: <b>+${}</b>  ·  {}✅ {}❌ {}🔄 ({} signaux)".format(st["g1"],st["wins"],st["losses"],st.get("open",0),st["n"]),
           "🤖 IA: <b>{:.4f}$</b>  ·  Régime: {}".format(ch["balance"],reg.get("regime","?")),
           "⚡ Improv: {} signal(s) allégé(s)".format(improv_count) if improv_count else "",""]
    cats={}
    for r in results: cats.setdefault(r.get("cat","?"),[]).append(r)
    for cat in ["METALS","CRYPTO","FOREX","INDICES","OIL"]:
        if cat not in cats: continue
        lines.append("{} <b>{}</b>".format(CAT_EMO.get(cat,"📊"),cat))
        for r in cats[cat]:
            if r["found"]:
                s=r["signal"]; se="🟢" if s["side"]=="BUY" else "🔴"
                tag=" ⚡" if r.get("improv") else ""
                lines.append("  {} <b>{}</b>  {}{}  RR 1:{}  {}/100".format(se,r["name"],s["side"],tag,s["rr"],s["score"]))
                lines.append("  📍<code>{}</code>→TP<code>{}</code> SL<code>{}</code>".format(s["entry"],s["tp"],s["sl"]))
            else:
                lines.append("  ⚪ <b>{}</b>  {}".format(r["name"],r.get("reason","?")))
        lines.append("")
    lines+=["═"*22,"🟢 <b>{} signal(s)</b>".format(nb) if nb else "🟡 Aucun signal","🔄 Prochain scan ~{}s".format(SCAN_SEC)]
    return "\n".join(lines)

def fmt_daily(st):
    if st["n"] == 0:
        return "📊 <b>RAPPORT {}</b>\n\nAucun signal.".format(st["date"])
    closed = st["wins"] + st["losses"]
    wr = int(st["wins"] / closed * 100) if closed > 0 else 0
    ch = chal_get()
    improv_sigs = db_all("SELECT COUNT(*) FROM signals WHERE sent_at LIKE ? AND mode!='NORMAL'", (st["date"] + "%",))
    improv_count = improv_sigs[0][0] if improv_sigs else 0
    perf = "🔥🔥" if st["g1"] > 2000 else "🔥" if st["g1"] > 1000 else "💰"
    sep = "═" * 22
    lines = [
        f"📯 <b>RAPPORT DU JOUR — AlphaBot PRO</b> {perf}",
        sep,
        f"📅 {st['date']}  ·  {st['n']} signaux envoyés",
        f"✅ TP confirmés : <b>{st['wins']}</b>  ·  ❌ SL : <b>{st['losses']}</b>  ·  🔄 En cours : <b>{st['open']}</b>",
        f"📊 Win rate réel : <b>{wr}%</b>" if closed > 0 else "📊 Win rate : <b>En attente résultats</b>",
        f"💵 Lot 0.01 confirmé : <b>+${st['g001']}</b>  · potentiel +${st['pot_g001']}",
        f"💰 Lot 1.00 confirmé : <b>+${st['g1']}</b>  · potentiel +${st['pot_g1']}",
        "⚡ Dont {} signal(s) improvisation".format(improv_count) if improv_count else "",
        "",
        f"🤖 <b>IA Challenge: {ch['balance']:.4f}$</b>  AM:{ch['am_cycle']}/4",
        "",
        "━" * 20,
        "",
    ]
    for row in st["rows"]:
        pair, side, rr, g001, g1, l001, l1, sess, mode, result = row
        d = "⬆️" if side == "BUY" else "⬇️"
        improv_tag = " ⚡" if mode != "NORMAL" else ""
        if result == "TP":
            icon = "✅"; detail = f"+${g1:.0f} (lot 1)"
        elif result == "SL":
            icon = "❌"; detail = f"-${l1:.0f} (lot 1)"
        else:
            icon = "🔄"; detail = "en cours..."
        lines.append(f"{icon} <b>{pair}</b>{improv_tag} {d} {'ACHAT' if side=='BUY' else 'VENTE'} — RR <b>1:{rr}</b>  {detail}")
    lines += [
        "",
        sep,
        f"💰 Total confirmé lot 1.00 : <b>+${st['g1']}</b>",
        f"🔄 Potentiel en cours      : <b>+${st['pot_g1']}</b>",
        f"📩 @leaderodg_bot  ·  {PRO_PRICE}$ USDT",
        "⚠️ Gains confirmés = TP atteints réels. Not financial advice.",
    ]
    return "\n".join(l for l in lines if l is not None)

# ══════════════════════════════════════════════════════
#  BOUCLE SCAN
# ══════════════════════════════════════════════════════
_sent=set(); _sent_lk=threading.Lock()
_last_d=""; _last_w=""; _scan_run=False; _test_mode=""
_last_results=[]; _pay_state={}
# ── Compteur improv ──────────────────────────────────────────────────
_cycles_no_signal = 0          # cycles consécutifs sans aucun signal ICT
IMPROV_UNLOCK_CYCLES = 0       # ⚡ Improvisation TOUJOURS active (seuil = 0)
_improv_cd = {}                # {pair_name: timestamp} cooldown par paire
# v13 compat aliases
_sent_lock         = _sent_lk
_last_daily        = _last_d
_last_weekly       = _last_w
_scan_running      = False
_admin_test_mode   = ""
_last_scan_results = []
_payment_state     = _pay_state
_broadcast_pending = {}    # partagé avec _bcast_pending

def cleanup_sent(ds):
    global _sent
    with _sent_lk: _sent={k for k in _sent if ds in k}


# ══════════════════════════════════════════════════════
#  RAPPORT DE FIN DE SESSION
# ══════════════════════════════════════════════════════
_last_session_reported = ""

def check_session_end_report():
    """
    Détecte la fin d'une session et envoie un rapport.
    Sessions avec rapport : LONDON_KZ (fin 10h), NY (fin 21h), OVERLAP (fin 16h)
    """
    global _last_session_reported
    now = datetime.now(timezone.utc)
    h, m = now.hour, now.minute
    # Fin de session = première minute après la fin
    session_ends = {
        10: ("LONDON_KZ", "🇬🇧 London Kill Zone"),
        12: ("LONDON",    "🇬🇧 Londres AM"),
        16: ("OVERLAP",   "🇬🇧+🇺🇸 London+NY"),
        21: ("NY",        "🇺🇸 New York"),
    }
    if h in session_ends and m == 0:
        sess_key = session_ends[h][0]
        sess_lbl = session_ends[h][1]
        report_key = "{}-{}-{}".format(
            now.strftime("%Y-%m-%d"), h, sess_key)
        if report_key == _last_session_reported:
            return
        _last_session_reported = report_key
        threading.Thread(
            target=_send_session_report,
            args=(sess_lbl, h),
            daemon=True
        ).start()

def _send_session_report(sess_label, end_hour):
    """Envoie le rapport de performance d'une session terminée."""
    try:
        # Signaux des 4 dernières heures (durée d'une session)
        now = datetime.now(timezone.utc)
        since = (now - timedelta(hours=4)).strftime("%Y-%m-%dT%H:%M")
        con = _conn(); cur = con.cursor()
        cur.execute(
            "SELECT pair,side,rr,g001,g1,l001,l1,mode FROM signals "
            "WHERE sent_at >= ? ORDER BY sent_at",
            (since,))
        rows = cur.fetchall(); con.close()
        if not rows:
            return  # Pas de signaux cette session → pas de rapport
        wins = sum(1 for r in rows if r[2] >= 2.5)
        losses = len(rows) - wins
        wr = round(wins / len(rows) * 100) if rows else 0
        total_g001 = round(sum(r[3] for r in rows), 2)
        total_g1   = round(sum(r[4] for r in rows), 2)
        improv = sum(1 for r in rows if r[7] != "NORMAL")
        perf = "🔥" if total_g1 > 500 else "💰" if total_g1 > 100 else "📊"
        sep = "=" * 22
        msg = (
            "📊 <b>RAPPORT SESSION — {}</b> {}\n" + sep + "\n\n"
            "⏱ Session terminée à {}h UTC\n\n"
            "📡 <b>{}</b> signaux  ·  {} ✅  ·  {} ❌  ·  <b>{}%</b> WR\n"
            "💵 Lot 0.01 : <b>+${}</b>\n"
            "💰 Lot 1.00 : <b>+${}</b>\n"
            "{}\n\n"
        ).format(
            sess_label, perf, end_hour,
            len(rows), wins, losses, wr,
            total_g001, total_g1,
            "⚡ {} signal(s) improvisation".format(improv) if improv else ""
        )
        # Détail trades
        sep2 = "=" * 22
        for row in rows:
            pair, side, rr, g001, g1, l001, l1, mode = row
            ok  = rr >= 2.5
            d   = "UP" if side == "BUY" else "DOWN"
            tag = " IMPROV" if mode != "NORMAL" else ""
            res = "+${:.0f}".format(g1) if ok else "-${:.0f}".format(l1)
            msg += "{} {} {} {} {} RR 1:{} {}\n".format(
                "OK" if ok else "SL", pair, tag, d, side, rr, res)
        msg += "\n" + sep2 + "\n"
        msg += "AlphaBot PRO · @leaderodg_bot"
        tg_send(CHANNEL_ID, msg)
        for puid in pro_users():
            tg_send(puid, msg)
            time.sleep(0.04)
        log("INFO", clr("Rapport session {} envoyé ({} signaux)".format(
            sess_label, len(rows)), "g"))
    except Exception as e:
        log("WARN", "session_report: {}".format(e))

def scan_and_send():
    global _scan_run
    if _scan_run: return
    _scan_run=True
    try: _scan_inner()
    finally: _scan_run=False

def _scan_inner():
    global _last_d, _last_w, _last_results, _cycles_no_signal
    now    = datetime.now(timezone.utc).replace(tzinfo=None)
    scan_t = now.strftime("%H:%M"); ds = now.strftime("%Y-%m-%d")
    hs     = now.strftime("%H");    wd = now.weekday()
    sn, sm, sl_l, wknd = get_session()
    sm = get_adaptive_score_min()
    # Improv autorisé seulement après IMPROV_UNLOCK_CYCLES cycles sans signal ICT
    improv_unlocked = (_cycles_no_signal >= IMPROV_UNLOCK_CYCLES)
    log("INFO", clr("Scan {} — {} — Score~{} | No-sig cycles: {}/{}{}".format(
        scan_t, sl_l, sm, _cycles_no_signal, IMPROV_UNLOCK_CYCLES,
        " ⚡IMPROV OK" if improv_unlocked else ""), "d"))
    news_ok, news_lbl = news_check()
    active = [m for m in MARKETS if not wknd or m.get("crypto", False)]
    q = Queue(); threads = []
    for m in active:
        # On passe improv_unlocked à agent_analyze
        t = threading.Thread(target=agent_analyze,
                             args=(m, sm, news_ok, q, improv_unlocked), daemon=True)
        t.start(); threads.append(t)
    for t in threads: t.join(timeout=15)
    raw = {}
    while not q.empty():
        try: r = q.get_nowait(); raw[r["name"]] = r
        except Empty: break
    results = [raw.get(m["name"], {"name":m["name"],"cat":m["cat"],"found":False,
               "reason":"Timeout","improv":False}) for m in active]
    _last_results = results; cleanup_sent(ds)
    sigs = [(r["signal"], "{}-{}-{}-{}".format(r["signal"]["name"], r["signal"]["side"], ds, hs))
            for r in results if r["found"]]
    with _sent_lk: sigs = [(s, k) for s, k in sigs if k not in _sent]
    sigs.sort(key=lambda x: -x[0]["score"])

    # ── Mise à jour compteur cycles ────────────────────────────────
    # On compte uniquement les signaux ICT vrais (non improv)
    ict_sigs = [s for s, k in sigs if not s.get("improv")]
    if ict_sigs:
        _cycles_no_signal = 0   # reset : un vrai signal ICT trouvé
    else:
        _cycles_no_signal += 1  # aucun signal ICT → on incrémente

    pru     = pro_users(); fru = free_users()
    pru_eff = [u for u in pru if not (u == ADMIN_ID and _test_mode == "FREE")]
    fru_eff = list(fru) + ([ADMIN_ID] if _test_mode == "FREE" and ADMIN_ID not in fru else [])
    for sig, key in sigs:
        msg_p = fmt_pro(sig, news_lbl, sl_l)
        msg_f = fmt_free(sig, news_lbl, sl_l)
        # ── Sticker adapté au score et à la direction ───────────────
        if sig.get("improv"):
            stk = STK_FIRE if sig["side"] == "SELL" else STK_ROCKET
        elif sig.get("score", 0) >= 85:
            stk = STK_CROWN   # setup élite
        elif sig.get("score", 0) >= 75:
            stk = STK_MONEY if sig["side"] == "BUY" else STK_FIRE
        else:
            stk = STK_SIGNAL
        tg_req("sendSticker", {"chat_id": str(CHANNEL_ID), "sticker": stk})
        time.sleep(0.3)
        r = tg_send(CHANNEL_ID, msg_f)
        if r.get("ok"):
            with _sent_lk: _sent.add(key)
            save_signal(sig, sn)
            if sig.get("improv"):
                _improv_cd[sig["name"]] = time.time()  # cooldown 4h par paire
            mode_tag = " ⚡IMPROV" if sig.get("improv") else ""
            log("SIG", "{} {} RR:1:{} Sc:{}{} G1:+${}".format(
                clr(sig["name"], "b", "c"), sig["side"], sig["rr"],
                sig["score"], mode_tag, sig["g1"]))
        for puid in pru_eff:
            if count_today(puid) < PRO_LIMIT:
                tg_send(puid, msg_p); count_incr(puid); time.sleep(0.04)
        for fuid in fru_eff:
            c = count_today(fuid)
            if c < FREE_LIMIT:
                tg_send(fuid, msg_f); count_incr(fuid); time.sleep(0.04)
            elif c == FREE_LIMIT:
                tg_send(fuid, "🛑 <b>Limite FREE {}/{}</b>\n\n/pay — {}$ USDT\n{} filleuls = {} mois PRO!".format(
                    FREE_LIMIT, FREE_LIMIT, PRO_PRICE, REF_TARGET, REF_MONTHS))
                count_incr(fuid)
    # Scan summary supprimé — disponible uniquement via /scan ou /debug
    # Rapport quotidien
    if int(hs)>=DAILY_HOUR and _last_d!=ds and not rep_sent(ds):
        st=daily_stats(ds)
        if st["n"]>0:
            d=fmt_daily(st); tg_send(CHANNEL_ID,d)
            for puid in pru: tg_send(puid,d); time.sleep(0.04)
            mark_rep(st); _last_d=ds
    # Rapport hebdo
    wk="{}-W{}".format(now.year,now.isocalendar()[1])
    if wd==WEEKLY_DAY and int(hs)>=WEEKLY_HOUR and _last_w!=wk and not rep_sent(wk,"weekly_rep","week_start"):
        ws=weekly_stats()
        if ws["n"]>0:
            wmsg="🏆 <b>RAPPORT HEBDO AlphaBot PRO</b>\n═"*1+"═"*21+"\n\n📅 Semaine du {}\n\n💵 Lot 0.01: +${}\n💰 Lot 1.00: +${}\n\n📡 {} signaux  ·  {} wins  ·  {}%\n\n📩 @leaderodg_bot  ·  {}$ USDT".format(ws["ws"],ws["g001"],ws["g1"],ws["n"],ws["wins"],int(ws["wins"]/ws["n"]*100) if ws["n"] else 0,PRO_PRICE)
            tg_send(CHANNEL_ID,wmsg)
            for puid in pru: tg_send(puid,wmsg); time.sleep(0.04)
            mark_rep(ws,"weekly_rep"); _last_w=wk
    # Expirations
    for uid,uname in check_expiry():
        _,_,src=get_pro_info(uid)
        msg="⏰ <b>Essai {} jours terminé!</b>\n/pay → {}$ USDT".format(TRIAL_DAYS,PRO_PRICE) if src and "TRIAL" in (src or "") else "⏰ <b>PRO expiré</b>\n/pay → {}$ USDT\n/ref → {} filleuls = {} mois".format(PRO_PRICE,REF_TARGET,REF_MONTHS)
        tg_send(uid,msg)
    # Backup + relance + suivi TP/SL + scan IA
    if int(hs)==DAILY_HOUR and ds!=getattr(_scan_inner,"_lb",""):
        _scan_inner._lb=ds; threading.Thread(target=do_backup,daemon=True).start()
    if int(hs)%6==0 and ds+hs!=getattr(_scan_inner,"_lr",""):
        _scan_inner._lr=ds+hs; threading.Thread(target=relance_inactifs,daemon=True).start()
    threading.Thread(target=check_open_sigs,daemon=True).start()
    threading.Thread(target=ai_scan_cycle,daemon=True).start()
    # Vérifier fin de session → rapport automatique
    # Session end reports désactivés — rapport soir uniquement

def ai_scan_cycle():
    try:
        setups=ai_full_scan()
        if setups:
            best=setups[0]
            log("AI",clr("Setup {} {} Sc:{} RR:{}".format(best["sym"],"L" if best["side"]=="BUY" else "S",best["sc"],best["rr"]),"g"))
            ai_open(best)
    except Exception as e: log("WARN","[AI] {}".format(e))

def do_backup():
    try:
        import shutil; bp="/tmp/ab10_{}.db".format(datetime.now().strftime("%Y%m%d_%H%M"))
        shutil.copy2(DB_FILE,bp)
        with open(bp,"rb") as f: data=f.read()
        tg_doc(ADMIN_ID,data,"ab10_backup_{}.db".format(datetime.now().strftime("%Y%m%d")),"💾 <b>Backup v10</b> — {}".format(datetime.now().strftime("%d/%m/%Y %H:%M")))
    except Exception as e: log("WARN","Backup: {}".format(e))

def relance_inactifs():
    try:
        inactifs=inactive_users()
        if not inactifs: return
        st=daily_stats()
        for uid,uname in inactifs[:20]:
            try:
                tg_send(uid,"👋 <b>Hey {}!</b>\n\n📡 {} signaux aujourd'hui\n+${} de gains estimés\n\n✅ {} TP  ·  {}% réussite\n\n@leaderodg_bot".format(
                    "@"+uname if uname else "Trader",st["n"],st["g1"],st["wins"],
                    int(st["wins"]/st["n"]*100) if st["n"] else 0))
                time.sleep(0.1)
            except: pass
    except Exception as e: log("WARN","Relance: {}".format(e))

def check_open_sigs():
    try:
        for tid,pair,entry,tp,sl,side,created in open_signals():
            try:
                age=(datetime.now()-datetime.fromisoformat(created)).total_seconds()/3600
                if age>4: close_track(tid,"EXPIRED"); continue
            except: continue
            m=next((x for x in MARKETS if x["name"]==pair),None)
            if not m: continue
            try:
                c=fetch_c(m["sym"],"5m","1d")
                if not c: continue
                cur=c[-1]["c"]
                if side=="BUY":
                    if cur>=tp: close_track(tid,"TP"); notify_result(pair,side,entry,tp,sl,"TP",cur)
                    elif cur<=sl: close_track(tid,"SL"); notify_result(pair,side,entry,tp,sl,"SL",cur)
                else:
                    if cur<=tp: close_track(tid,"TP"); notify_result(pair,side,entry,tp,sl,"TP",cur)
                    elif cur>=sl: close_track(tid,"SL"); notify_result(pair,side,entry,tp,sl,"SL",cur)
            except: continue
    except Exception as e: log("WARN","check_open: {}".format(e))

def notify_result(pair, side, entry, tp, sl, result, cur):
    icon  = "✅" if result == "TP" else "❌"
    label = "TP ATTEINT 💰" if result == "TP" else "SL TOUCHÉ ⚠️"
    d     = "⬆️" if side == "BUY" else "⬇️"
    sep   = "━" * 20
    # NOTE: parenthèses obligatoires pour que .format() couvre TOUT le template
    msg = (
        f"{icon} <b>RÉSULTAT — {pair}</b>  {d}\n"
        f"{sep}\n"
        f"<b>{label}</b>\n"
        f"📍 Entrée : <code>{entry}</code>\n"
        f"📌 Prix   : <code>{cur}</code>\n"
        f"✅ TP     : <code>{tp}</code>\n"
        f"❌ SL     : <code>{sl}</code>\n"
        f"🤖 AlphaBot  ·  @leaderodg_bot"
    )
    tg_send(CHANNEL_ID, msg)
    for puid in pro_users(): tg_send(puid, msg); time.sleep(0.04)

# ══════════════════════════════════════════════════════
#  PAIEMENT USDT
# ══════════════════════════════════════════════════════
def verify_tx(tx):
    for url in ["https://apilist.tronscan.org/api/transaction-info?hash={}".format(tx),"https://api.trongrid.io/v1/transactions/{}".format(tx)]:
        for attempt in range(2):
            try:
                body=json.loads(http_get(url,timeout=10))
                for t in body.get("trc20TransferInfo",[]):
                    if t.get("to_address","").lower()==USDT_ADDR.lower() and t.get("symbol","").upper()=="USDT":
                        amt=float(t.get("amount_str","0"))/1e6
                        if amt>=PRO_PRICE*0.95: return True,round(amt,2)
                cd=body.get("contractData",{})
                if cd.get("to_address","").lower()==USDT_ADDR.lower():
                    amt=float(cd.get("amount",0))/1e6
                    if amt>=PRO_PRICE*0.95: return True,round(amt,2)
                if body.get("hash") or body.get("txID"): return False,0
            except Exception as ex:
                if any(e in str(ex) for e in ["No address","Name or service","Errno 7"]): return None,0
                if attempt==0: time.sleep(2)
    return False,0

def handle_pay_submitted(uid, uname, plan_key="PRO"):
    _pay_state[uid]={"tx":None,"step":"waiting","plan":plan_key}
    price = {"FREE":0,"STARTER":5,"PRO":10,"VIP":25}.get(plan_key, PRO_PRICE)
    tg_send(uid,
        "📋 <b>COLLE TON TX HASH</b>\n\n"
        "Plan: <b>{}</b> — {}$ USDT TRC20\n\n"
        "Après virement, envoie l'ID de transaction ici.\n\n"
        "<code>exemple: a1b2c3d4e5f6789abc...</code>\n\n"
        "✅ Vérification automatique blockchain!".format(plan_key, price),
        kb={"inline_keyboard":[[{"text":"❌ Annuler","callback_data":"pay_cancel"}]]})

def handle_proof(uid,uname,tx):
    if uid not in _pay_state or _pay_state[uid].get("step")!="waiting": return False
    _pay_state[uid]["tx"]=tx; _pay_state[uid]["step"]="confirm"
    tg_send(uid,"📋 <b>TX HASH REÇU</b>\n\n<code>{}</code>\n\nClique sur <b>🔍 Vérifier</b>".format(tx),
        kb={"inline_keyboard":[[{"text":"🔍 Vérifier mon paiement","callback_data":"pay_confirm"}],[{"text":"🔄 Changer","callback_data":"pay_submitted"}],[{"text":"❌ Annuler","callback_data":"pay_cancel"}]]})
    return True

def handle_pay_confirm(uid,uname):
    state=_pay_state.pop(uid,None)
    if not state or not state.get("tx"): tg_send(uid,"❌ Aucun hash. Recommence avec /pay"); return
    tx=state["tx"]; save_pay(uid,tx)
    tg_send(uid,"🔍 <b>Vérification...</b>\n\nHash: <code>{}</code>\n\n⏳ Blockchain TRC20 — 2 min max".format(tx))
    tg_send(ADMIN_ID,"💰 <b>PAIEMENT EN ATTENTE</b>\n@{} <code>{}</code>\n<code>{}</code>\n/activate {}".format(uname or "?",uid,tx,uid))
    def _v():
        for i,delay in enumerate([5,60,120]):
            time.sleep(delay); ok,amt=verify_tx(tx)
            if ok:
                db_pro(uid,"USDT_AUTO",days=None); tg_sticker(uid,STK_WIN)
                tg_send(uid,"🎉 <b>PAIEMENT CONFIRMÉ!</b>\n\n✅ {}$ USDT reçu!\n💎 <b>PRO À VIE!</b>\n✅ Max {} signaux/j\n✅ Agent IA Binance inclus!".format(amt,PRO_LIMIT))
                tg_send(ADMIN_ID,"🟢 AUTO PRO: @{} <code>{}</code> {}$ ✅".format(uname or "?",uid,amt))
                log("PAY",clr("AUTO PRO: @{} {}$".format(uname,amt),"g")); return
            if i<2: log("INFO",clr("TX non confirmé {}/3".format(i+1),"y"))
        tg_send(uid,"⏳ <b>En attente</b>\n\nL'admin activera sous 30 min.\n@leaderOdg"); tg_send(ADMIN_ID,"⚠️ MANUELLE\n@{} <code>{}</code>\n<code>{}</code>\n/activate {}".format(uname or "?",uid,tx,uid))
    threading.Thread(target=_v,daemon=True).start()

# ══════════════════════════════════════════════════════
#  CLAVIERS & COMMANDES
# ══════════════════════════════════════════════════════
def kb_main(pro=False): return {"inline_keyboard":[
    [{"text":"📡 Signaux","callback_data":"signals"},{"text":"📈 Rapports","callback_data":"rapports"}],
    [{"text":"👤 Mon Compte","callback_data":"account"},{"text":"🏆 Challenge IA","callback_data":"challenge"}],
    [{"text":"💎 Devenir PRO","callback_data":"pay"} if not pro else {"text":"✅ PRO Actif","callback_data":"account"},{"text":"🤝 Parrainage","callback_data":"ref"}],
    [{"text":"🏦 Broker","callback_data":"broker"},{"text":"📖 Guide","callback_data":"guide"}],
]}
def kb_back(): return {"inline_keyboard":[[{"text":"◀️ Retour","callback_data":"start"}]]}

def send_welcome(uid,uname):
    db_register(uid,uname,tg_fn=tg_send)
    p=is_pro(uid); ch=chal_get()
    tg_sticker(uid,STK_W)
    tg_send(uid,"🤖 <b>AlphaBot PRO v10 — Agent IA Adaptatif</b>\n"+"═"*22+"\n\n"
        "📡 20 marchés : Forex · Or · BTC · Indices · Pétrole\n"
        "🧠 ICT/SMC v2 + <b>Mode Improvisation</b> ⚡\n"
        "🌍 Régime: <b>{}</b>  ·  Challenge: <b>{:.4f}$</b>\n\n"
        "✅ Plan: <b>{}</b>\n\nSélectionne une option ↓".format(
            AI_REG.get("regime","?"),ch["balance"],get_plan(uid)),
        kb=kb_main(p))

def send_account(uid,uname,forced=None):
    plan=forced or get_plan(uid); _,exp,_=get_pro_info(uid)
    refs=get_refs(uid); td=count_today(uid); lim={"FREE":FREE_LIMIT,"PRO":PRO_LIMIT,"VIP":999}.get(plan,FREE_LIMIT)
    tg_send(uid,"👤 <b>MON COMPTE</b>\n"+"═"*22+"\n\n🆔 <code>{}</code>\n👤 @{}\n💎 Plan: <b>{}</b>{}\n"
        "📡 Signaux: <b>{}/{}</b>\n🤝 Filleuls: <b>{}/{}</b>\n\n"
        "{}" "📩 Support: @leaderOdg".format(uid,uname or "?",plan,"\n📅 Expire: {}".format(exp) if exp else "",td,lim,refs,REF_TARGET,
        "✅ Accès PRO + Agent IA\n" if plan in ("PRO","VIP") else "🔒 /pay pour PRO complet\n"),kb=kb_main(plan in ("PRO","VIP")))

def send_pay(uid):
    tg_send(uid,"💎 <b>PASSER EN PRO</b>\n"+"═"*22+"\n\n✅ {} signaux/jour\n✅ 20 marchés + crypto\n✅ Mode Improvisation ⚡\n✅ Agent IA Binance\n✅ Challenge 5$→500$\n\n💵 <b>PRIX: {}$ USDT TRC20</b>\n\n📤 Envoie sur:\n<code>{}</code>\n\nPuis clique <b>J'ai payé ✅</b>".format(PRO_LIMIT,PRO_PRICE,USDT_ADDR),
        kb={"inline_keyboard":[[{"text":"✅ J'ai payé","callback_data":"pay_submitted"}],[{"text":"❓ Aide @leaderOdg","url":"https://t.me/leaderOdg"}],[{"text":"◀️ Retour","callback_data":"start"}]]})

def send_challenge(uid):
    ch=chal_get(); reg=AI_REG
    w=ch.get("today_w",0); l=ch.get("today_l",0); tot=w+l
    wr=round(w/tot*100) if tot>0 else 0
    open_t=sum(1 for t in AI_OT.values() if t["status"]=="open")
    tg_send(uid,"🏆 <b>CHALLENGE IA — Agent Alpha v10</b>\n"+"═"*22+"\n\n"
        "{}\n\n"
        "📊 Aujourd'hui: W:{} L:{} WR:{}%\n"
        "📈 PnL jour: {:+.4f}$\n"
        "🔄 AM Cycle: {}/4\n"
        "📂 Positions: {}/{}\n\n"
        "🌍 Régime: <b>{}</b> — {}\n"
        "⚡ Mode Improvisation: actif\n\n"
        "⚠️ Simulation — aucun ordre réel".format(
            chal_prog(ch),w,l,wr,ch.get("today_pnl",0),ch["am_cycle"],open_t,MAX_OPEN,
            reg.get("regime","?"),reg.get("label","?")),kb=kb_back())

def send_rapports(uid):
    st=daily_stats(); ws=weekly_stats()
    sd=st["n"]; wd_=st["wins"]; wr_d=int(wd_/sd*100) if sd else 0
    sw=ws["n"]; ww=ws["wins"]; wr_w=int(ww/sw*100) if sw else 0
    improv_today=db_all("SELECT COUNT(*) FROM signals WHERE sent_at LIKE ? AND mode!='NORMAL'",(datetime.now().strftime("%Y-%m-%d")+"%",))
    improv_cnt=improv_today[0][0] if improv_today else 0
    lines=["📈 <b>RAPPORTS DE PERFORMANCE</b>","═"*22,"","🔥 <b>AUJOURD'HUI</b>",""]
    if sd>0:
        lines+=["📡 {} signaux  ·  {} ✅  ·  {}% réussite".format(sd,wd_,wr_d),
                "💵 Lot 0.01: <b>+${}</b>".format(st["g001"]),
                "💰 Lot 1.00: <b>+${}</b>".format(st["g1"]),
                "⚡ {} signal(s) improvisation".format(improv_cnt) if improv_cnt else "",""]
    else: lines.append("⏳ Aucun signal aujourd'hui")
    lines+=["","━"*20,"","🔥🔥 <b>CETTE SEMAINE</b>",""]
    if sw>0: lines+=["📡 {} signaux  ·  {} ✅  ·  {}% réussite".format(sw,ww,wr_w),"💵 +${}  ·  💰 +${}".format(ws["g001"],ws["g1"])]
    else: lines.append("⏳ Aucun signal cette semaine")
    lines+=["","═"*22,"⚠️ Estimations si TP atteint. Not financial advice.","🤖 AlphaBot PRO  ·  @leaderodg_bot"]
    tg_send(uid,"\n".join(l for l in lines if l is not None),kb=kb_back())

def send_admin_full(uid):
    if uid!=ADMIN_ID: tg_send(uid,"❌ Accès refusé."); return
    total,pro,sigs,pays,g1d=global_stats(); sn,sm,sl_l,_=get_session()
    st=daily_stats(); pend=pending_pays(); ch=chal_get(); reg=AI_REG
    tg_sticker(uid,STK_PRO)
    tg_send(uid,"🛡 <b>ADMIN — AlphaBot v10</b>\n"+"═"*22+"\n\n"
        "👥 Membres: <b>{}</b>  ·  PRO: <b>{}</b>  ·  FREE: <b>{}</b>\n"
        "📡 Signaux: <b>{}</b>  ·  Gains: <b>+${}</b>  ·  Payés: <b>{}</b>\n"
        "⏳ En attente: <b>{}</b>{}\n\n"
        "🤖 <b>IA:</b> {:.4f}$ AM:{}/4 W:{} L:{}\n"
        "🌍 Régime: <b>{}</b>  Positions: {}/{}\n\n"
        "🕐 Session: {}  Score min: {}\n\n"
        "/activate /degrade /scan /debug /stats /membres".format(
            total,pro,total-pro,st["n"],st["g1"],pays,len(pend),
            "  ⚠️ À valider!" if pend else "",
            ch["balance"],ch["am_cycle"],ch.get("today_w",0),ch.get("today_l",0),
            reg.get("regime","?"),sum(1 for t in AI_OT.values() if t["status"]=="open"),MAX_OPEN,sl_l,sm),
        kb={"inline_keyboard":[
            [{"text":"💰 Paiements","callback_data":"adm_pays"},{"text":"📡 Scan forcé","callback_data":"adm_scan"}],
            [{"text":"🏆 Challenge IA","callback_data":"challenge"},{"text":"📈 Rapports","callback_data":"rapports"}],
            [{"text":"🌍 État marchés","callback_data":"adm_markets"}],
        ]})

def send_guide(uid):
    tg_send(uid,"📖 <b>GUIDE AlphaBot PRO v10</b>\n"+"═"*22+"\n\n"
        "🧠 <b>Méthode ICT/SMC :</b>\n"
        "1️⃣ H1 Bias (BOS/CHoCH) → tendance\n"
        "2️⃣ M5 Breaker Block → zone d'entrée\n"
        "3️⃣ Score dynamique 0-100 pts\n"
        "4️⃣ SL/TP auto — RR min 1:2.5\n"
        "5️⃣ OTE 61.8% + FVG + CHoCHx2\n\n"
        "━"*20+"\n"
        "⚡ <b>Mode Improvisation (NOUVEAU) :</b>\n"
        "Si pas de setup ICT parfait mais que :\n"
        "• Tendance de fond valide (H1)\n"
        "• Session active (London/NY/Overlap)\n"
        "• Pas de news High Impact\n\n"
        "→ L'agent entre en mode allégé :\n"
        "  EMA Bounce / Momentum / Structure H1\n"
        "  Risque réduit 50% · Signal marqué ⚡\n\n"
        "━"*20+"\n"
        "🤖 <b>Agent IA Binance :</b>\n"
        "• Régime marché auto (6 régimes)\n"
        "• Mémoire épisodique + apprentissage\n"
        "• Challenge 5$→500$ auto-géré\n\n"
        "🔓 FREE: {}/j\n💎 PRO: {}/j + IA\n\n"
        "⚠️ Risk 1-2% max. Not financial advice.".format(FREE_LIMIT,PRO_LIMIT),kb=kb_back())

def send_broker(uid):
    tg_send(uid,"🏦 <b>BROKER — EXNESS</b>\n\n✅ Spread 0 pip (Raw)\n✅ Dépôt min 10$\n✅ FCA & CySEC\n✅ Crypto disponibles\n\n👉 <a href=\"{}\">🔗 Ouvrir Exness</a>".format(BROKER_LINK),kb=kb_back())

def send_ref(uid,uname):
    refs=get_refs(uid); link="https://t.me/{}?start={}".format(BOT_USER,uid)
    done=min(refs,REF_TARGET); bar="█"*int(done/REF_TARGET*10)+"░"*(10-int(done/REF_TARGET*10))
    tg_send(uid,"🤝 <b>PARRAINAGE</b>\n"+"═"*22+"\n\n<b>{}/{}</b>  ({}%)\n[{}]\n\n🏆 {} filleuls = {} MOIS PRO\n\n🔗 <code>{}</code>".format(done,REF_TARGET,int(done/REF_TARGET*100),bar,REF_TARGET,REF_MONTHS,link),kb=kb_back())

# ══════════════════════════════════════════════════════
#  DISPATCH
# ══════════════════════════════════════════════════════

# ══════════════════════════════════════════════════════
#  FONCTIONS ORIGINALES v13 — INTÉGRÉES COMPLÈTES
# ══════════════════════════════════════════════════════

def _admin_only(uid):
    if uid != ADMIN_ID:
        tg_send(uid, "\u274c Accès refusé.")
        return False
    return True


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
        "📩 Rejoins la communauté\n➡️ @leaderodg_bot"]
    return "\n".join(lines)


def _check_open_signals():
    """Vérifie si les signaux ouverts ont atteint TP ou SL."""
    try:
        open_sigs = db_get_open_signals()
        if not open_sigs: return
        for track_id, pair, entry, tp, sl, side, created in open_sigs:
            # Vérifier si le signal a moins de 4h (sinon on abandonne)
            try:
                age = (datetime.now() - datetime.fromisoformat(created)).total_seconds() / 3600
                if age > 4:
                    db_close_signal_tracking(track_id, "EXPIRED")
                    continue
            except: continue
            # Récupérer le prix actuel
            mkt = next((m for m in MARKETS if m["name"] == pair), None)
            if not mkt: continue
            try:
                c = fetch_c(mkt["sym"], "5m", "1d")
                if not c: continue
                current = c[-1]["c"]
                if side == "BUY":
                    if current >= tp:
                        db_close_signal_tracking(track_id, "TP")
                        _notify_result(pair, side, entry, tp, sl, "TP", current)
                    elif current <= sl:
                        db_close_signal_tracking(track_id, "SL")
                        _notify_result(pair, side, entry, tp, sl, "SL", current)
                else:
                    if current <= tp:
                        db_close_signal_tracking(track_id, "TP")
                        _notify_result(pair, side, entry, tp, sl, "TP", current)
                    elif current >= sl:
                        db_close_signal_tracking(track_id, "SL")
                        _notify_result(pair, side, entry, tp, sl, "SL", current)
            except: continue
    except Exception as e:
        log("WARN", clr("Suivi signal échoué: {}".format(e), "yellow"))


def _do_backup():
    """Envoie une copie de la DB à l'admin sur Telegram."""
    try:
        import shutil
        backup_path = "/tmp/alphabot_backup_{}.db".format(
            datetime.now().strftime("%Y%m%d_%H%M"))
        shutil.copy2(DB_FILE, backup_path)
        with open(backup_path, "rb") as f:
            data = f.read()
        tg_send_document(ADMIN_ID, data,
            "alphabot_backup_{}.db".format(datetime.now().strftime("%Y%m%d")),
            "\U0001f4be <b>Backup quotidien</b> \u2014 {}\n"
            "Conserve ce fichier en lieu sûr.".format(
                datetime.now().strftime("%d/%m/%Y %H:%M")))
        log("INFO", clr("Backup DB envoyé à l'admin.", "green"))
    except Exception as e:
        log("WARN", clr("Backup échoué: {}".format(e), "yellow"))


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
        "\U0001f3af <b>BILAN GLOBAL</b>",
        "  \u2705 TP atteints : <b>{}</b>  |  \u274c SL touchés : <b>{}</b>  |  <b>{}%</b> réussite".format(w, l, wr),
        "  \U0001f4b5 Lot 0.01 : <b>+${}</b>  \u00b7  Lot 1.00 : <b>+${}</b>".format(
            stats["total_g001"], stats["total_g1"]),
        "", "\u2501" * 22,
        "\U0001f4cb <b>DÉTAIL DES TRADES</b>", ""
    ]

    for row in stats["rows"]:
        pair    = row[0]; side = row[1]; rr   = row[2]
        g001    = row[3]; g1   = row[4]; l001 = row[5]; l1 = row[6]
        entry   = row[8]  if len(row) > 8  else "—"
        tp      = row[9]  if len(row) > 9  else "—"
        sl      = row[10] if len(row) > 10 else "—"
        ok      = rr >= 3.0
        d       = "\u2b06\ufe0f" if side == "BUY" else "\u2b07\ufe0f"
        sf      = "ACHAT" if side == "BUY" else "VENTE"
        outcome = "\u2705 TP ATTEINT" if ok else "\u274c SL TOUCHÉ"
        gain_lot001 = "+${:.2f}".format(g001) if ok else "-${:.2f}".format(l001)
        gain_lot1   = "+${:.0f}".format(g1)   if ok else "-${:.0f}".format(l1)

        lines.append("{} <b>{}</b>  {} {}  \u2014  RR <b>1:{}</b>".format(
            "\U0001f7e2" if ok else "\U0001f534", pair, d, sf, rr))
        lines.append("  {} {}".format(outcome, gain_lot1 + " (lot 1.00)"))
        lines.append("  \U0001f4cd Entrée : <code>{}</code>".format(entry))
        lines.append("  \u2705 TP     : <code>{}</code>".format(tp))
        lines.append("  \u274c SL     : <code>{}</code>".format(sl))
        lines.append("  \U0001f4b5 Lot 0.01 : <b>{}</b>  \u00b7  Lot 1.00 : <b>{}</b>".format(
            gain_lot001, gain_lot1))
        lines.append("")

    lines += [
        "\u2550" * 22,
        "\U0001f4b0 Total lot 0.01 : <b>+${}</b>  \u00b7  Lot 1.00 : <b>+${}</b>".format(
            stats["total_g001"], stats["total_g1"]),
        "",
        "\U0001f4e9 Rejoins AlphaBot PRO \u2014 {}$ USDT".format(PRO_PROMO),
        "\U0001f449 @leaderodg_bot",
        "\u26a0\ufe0f Not financial advice  \u00b7  Risk 1% max"
    ]
    return "\n".join(lines)


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
        "\U0001f449 @leaderodg_bot \u2014 {}$ USDT\n\n"
        "\u26a0\ufe0f Not financial advice  \u00b7  Risk 1% max".format(PRO_PROMO)
    )


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
         ("", False), ("AlphaBot PRO v8.5 — @leaderodg_bot", True),
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



def _notify_result(pair, side, entry, tp, sl, result, current):
    """Notifie tous les utilisateurs du résultat d'un signal."""
    icon   = "\u2705" if result == "TP" else "\u274c"
    label  = "TP ATTEINT \U0001f4b0" if result == "TP" else "SL TOUCHÉ \u26a0\ufe0f"
    d      = "\u2b06\ufe0f" if side == "BUY" else "\u2b07\ufe0f"
    sf     = "ACHAT" if side == "BUY" else "VENTE"
    msg    = (
        "{} <b>RÉSULTAT \u2014 {}</b>  {}\n".format(icon, pair, d) +
        "\u2501" * 20 + "\n\n"
        "<b>{}</b>\n\n"
        "\U0001f4cd Entrée : <code>{}</code>\n"
        "\U0001f3af Prix actuel : <code>{}</code>\n"
        "\u2705 TP : <code>{}</code>  \u274c SL : <code>{}</code>\n\n"
        "\U0001f916 AlphaBot PRO \u00b7 @leaderodg_bot"
    ).format(label, entry, current, tp, sl)
    # Envoyer au canal et à tous les users
    tg_send(CHANNEL_ID, msg)
    for puid in db_get_pro_users():
        tg_send(puid, msg); time.sleep(0.04)
    for fuid in db_get_free_users():
        tg_send(fuid, msg); time.sleep(0.04)
    log("SIGNAL", clr("Résultat {} : {} {} → {}".format(pair, sf, entry, result), "green"))



def _relance_inactifs():
    """Envoie un message de relance aux utilisateurs FREE inactifs."""
    try:
        inactifs = db_get_inactive_users(days=INACTIF_DAYS)
        if not inactifs: return
        stats = db_daily_stats()
        for uid, uname in inactifs[:20]:  # max 20 par cycle
            try:
                fname = "@" + uname if uname else "Trader"
                tg_send(uid,
                    "\U0001f44b <b>Hey {} !</b>\n\n".format(fname) +
                    "\U0001f4ca AlphaBot a envoyé <b>{} signaux</b> aujourd'hui\n"
                    "avec <b>+${}</b> de gains estimés (lot 1.00)\n\n".format(
                        stats["sig_count"], stats["total_g1"]) +
                    "\u2705 {} TP atteints  \u00b7  {}% réussite\n\n".format(
                        stats["wins"],
                        int(stats["wins"]/stats["sig_count"]*100) if stats["sig_count"] else 0) +
                    "Tu rates ces opportunités !\n\n"
                    "\U0001f916 Reviens voir tes signaux :\n"
                    "\U0001f449 @leaderodg_bot",
                    kb=kb_reply())
                time.sleep(0.1)
            except: pass
        log("INFO", clr("Relance envoyée à {} inactifs.".format(len(inactifs[:20])), "dim"))
    except Exception as e:
        log("WARN", clr("Relance échouée: {}".format(e), "yellow"))


def _scan_and_send_inner():
    global _sent, _last_daily, _last_weekly, _last_scan_results

    now_dt    = datetime.now(timezone.utc).replace(tzinfo=None)
    scan_time = now_dt.strftime("%H:%M")
    date_str  = now_dt.strftime("%Y-%m-%d")
    hour_str  = now_dt.strftime("%H")
    wday      = now_dt.weekday()

    sn, sm, sl, wknd = get_session()
    # Score minimum adaptatif (session + régime marché)
    sm = get_adaptive_score_min()
    log("INFO", clr("Scan {} — {} — Score min:{}  [{} marchés]".format(
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

    if not sigs_raw:
        log("INFO", clr("Aucun setup valide ce cycle.", "dim"))
    # Scan summary supprimé — admin peut voir via /scan

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
        # Ne pas downgrader si c'était un essai → message spécifique
        plan, exp, src = db_get_pro_info(uid)
        if src and "TRIAL" in (src or ""):
            tg_send(uid,
                "\u23f0 <b>Ton essai PRO de {} jours est terminé !</b>\n\n"
                "Tu as pu voir la puissance des signaux AlphaBot.\n\n"
                "\U0001f4a0 Continue avec le <b>Plan PRO à {}$ USDT</b>\n"
                "et garde accès à tous les signaux !\n\n"
                "\U0001f449 /pay \u2014 Activation immédiate".format(TRIAL_DAYS, PRO_PROMO))
        else:
            tg_send(uid,
                "\u23f0 <b>PRO expiré</b>\n\n"
                "Renouveler :\n/pay \u2192 {}$ USDT\n"
                "/ref \u2192 {} filleuls = {} mois gratuit".format(PRO_PROMO, REF_TARGET, REF_MONTHS))
        tg_send(ADMIN_ID, "\u23f0 PRO expiré: @{} <code>{}</code>".format(uname or "?", uid))
    if expired:
        log("WARN", clr("{} PRO expiré(s) → FREE".format(len(expired)), "yellow"))

    # ── Backup quotidien à DAILY_HOUR ─────────────────────────
    if int(hour_str) == DAILY_HOUR and date_str != getattr(_scan_and_send_inner, "_last_backup", ""):
        _scan_and_send_inner._last_backup = date_str
        threading.Thread(target=_do_backup, daemon=True).start()

    # ── Relance utilisateurs inactifs (toutes les 6h) ─────────
    if int(hour_str) % 6 == 0 and date_str + hour_str != getattr(_scan_and_send_inner, "_last_relance", ""):
        _scan_and_send_inner._last_relance = date_str + hour_str
        threading.Thread(target=_relance_inactifs, daemon=True).start()

    # ── Suivi TP/SL des signaux ouverts ───────────────────────
    threading.Thread(target=_check_open_signals, daemon=True).start()



def _signal_validity(sig):
    """
    Calcule la validité restante du signal en minutes.
    Un signal M5 est valable ~3 bougies = 15 min.
    """
    age_sec  = time.time() - sig.get("ts", time.time())
    age_min  = age_sec / 60
    validity = max(0, int(DATA_MAX_AGE_MIN - age_min))
    return validity


def calc_atr(c, p=14):
    t = [max(c[i]["h"]-c[i]["l"], abs(c[i]["h"]-c[i-1]["c"]), abs(c[i]["l"]-c[i-1]["c"]))
         for i in range(1, len(c))]
    s = t[-p:] if len(t) >= p else t
    return sum(s) / len(s) if s else 0.001


def check_conf(c, b):
    """
    Score de confirmation ICT — 100 points maximum.

    CONFIRMATIONS REQUISES (par ordre d'importance) :
    ┌─────────────────────────────────────────┬──────┐
    │ Bougie dans le sens du bias             │ +35  │
    │ Corps > 50% du range (displacement)     │ +25  │
    │ Rejet de wick (liquidité prise)          │ +20  │
    │ Momentum (bougie précédente confirme)    │ +10  │
    │ Bougie -2 confirme (série directionnelle)│ +5   │
    │ Englobante (dépasse high/low précédent) │ +5   │
    ├─────────────────────────────────────────┼──────┤
    │ BONUS ICT v2 :                          │      │
    │ CHoCH consécutifs (2+ = fort signal)    │ +5→15│
    │ Equal High/Low touché (pool liquidité)  │ +10  │
    │ OTE Zone 61.8-78.6% Fibonacci           │ +12  │
    │ FVG (Fair Value Gap) en retest          │ +15  │
    │ BOS pur avec momentum fort              │ +10  │
    └─────────────────────────────────────────┴──────┘
    Score minimum pour signal : 61-82 selon session
    """
    if len(c) < 3: return 0
    c1 = c[-1]; c2 = c[-2]; c3 = c[-3]
    o = c1["o"]; cc = c1["c"]; h = c1["h"]; l = c1["l"]
    body = abs(cc - o); rng = h - l
    if rng == 0: return 0
    ratio = body / rng; s = 0

    if b == "BULLISH":
        if cc > o:                        s += 35   # Direction correcte
        if ratio > 0.5:                   s += 25   # Displacement fort
        if min(o,cc) - l > body * 0.15:  s += 20   # Rejet bas (wick)
        if c2["c"] < cc:                  s += 10   # Momentum M-1
        if c3["c"] < c2["c"]:            s +=  5   # Série haussière
        if cc > c2["h"]:                  s +=  5   # Englobante haussière
        # Pénalités
        if ratio < 0.3:                   s -= 10   # Corps trop faible
        if h - max(o,cc) > body * 0.5:   s -=  5   # Wick haut trop long
    else:
        if cc < o:                         s += 35
        if ratio > 0.5:                    s += 25
        if h - max(o,cc) > body * 0.15:   s += 20
        if c2["c"] > cc:                   s += 10
        if c3["c"] > c2["c"]:             s +=  5
        if cc < c2["l"]:                   s +=  5
        # Pénalités
        if ratio < 0.3:                    s -= 10
        if min(o,cc) - l > body * 0.5:    s -=  5

    # ── Bonus ICT v2 ─────────────────────────────────────────
    choch_dir, choch_count = count_choch_sequence(c)
    if choch_count >= 2 and choch_dir == b:
        s += min(15, choch_count * 7)   # CHoCH x2 = +14, x3 = +15

    eqh, eql = detect_eqh_eql(c)
    lp = c[-1]["c"]
    if b == "BEARISH" and eqh and abs(lp-eqh)/eqh < 0.005: s += 10  # EQH touché
    if b == "BULLISH" and eql and abs(lp-eql)/eql < 0.005: s += 10  # EQL touché

    return min(max(s, 0), 110)


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


def db_close_signal_track(track_id, status):
    try:
        con = _conn(); cur = con.cursor()
        with _db_lock:
            cur.execute("UPDATE signal_tracking SET status=? WHERE track_id=?", (status, track_id))
            con.commit()
        con.close()
    except: pass


def db_close_signal_tracking(track_id, status):
    con = _conn(); cur = con.cursor()
    with _db_lock:
        cur.execute("UPDATE signal_tracking SET status=?,closed_at=? WHERE track_id=?",
                    (status, datetime.now().isoformat(), track_id))
        con.commit()
    con.close()



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


def db_count_today(uid):
    ds = datetime.now().strftime("%Y-%m-%d")
    con = _conn(); cur = con.cursor()
    try:
        cur.execute("SELECT count FROM signal_counts WHERE user_id=? AND date_str=?", (uid, ds))
        row = cur.fetchone(); con.close()
        return row[0] if row else 0
    except:
        con.close(); return 0


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


def db_downgrade_pro(uid):
    con = _conn(); cur = con.cursor()
    with _db_lock:
        cur.execute(
            "UPDATE users SET plan='FREE',pro_expires=NULL,pro_source=NULL WHERE user_id=?", (uid,))
        con.commit()
    con.close()


def db_find_by_username(uname):
    uname = uname.lstrip("@").lower()
    con = _conn(); cur = con.cursor()
    cur.execute("SELECT user_id,username FROM users")
    rows = cur.fetchall(); con.close()
    for uid, un in rows:
        if un and un.lower() == uname:
            return uid
    return None


def db_get_free_users():
    con = _conn(); cur = con.cursor()
    cur.execute("SELECT user_id FROM users WHERE plan='FREE'")
    r = cur.fetchall(); con.close()
    return [x[0] for x in r]


def db_get_inactive_users(days=INACTIF_DAYS):
    """Retourne les users FREE sans activité depuis X jours."""
    try:
        con = _conn(); cur = con.cursor()
        cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
        # Users FREE dont le dernier comptage date est vieux ou inexistant
        cur.execute("""
            SELECT u.user_id, u.username FROM users u
            WHERE u.plan='FREE'
            AND u.user_id != ?
            AND (
                NOT EXISTS (
                    SELECT 1 FROM signal_counts sc
                    WHERE sc.user_id = u.user_id
                    AND sc.date_str >= ?
                )
            )
        """, (ADMIN_ID, cutoff))
        rows = cur.fetchall(); con.close()
        return rows
    except Exception as e:
        print("  [db_get_inactive] {}".format(e))
        return []


def db_get_open_signals():
    """Retourne les signaux ouverts à surveiller."""
    try:
        con = _conn(); cur = con.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='signal_tracking'")
        if not cur.fetchone():
            con.close(); return []
        cur.execute(
            "SELECT track_id,sig_id,pair,entry,tp,sl,side FROM signal_tracking "
            "WHERE status='OPEN' AND sent_at >= datetime('now','-24 hours')")
        rows = cur.fetchall(); con.close()
        return rows
    except:
        return []


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


def db_get_refs(uid):
    con = _conn(); cur = con.cursor()
    cur.execute("SELECT ref_count FROM users WHERE user_id=?", (uid,))
    row = cur.fetchone(); con.close()
    return row[0] if row else 0


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


def db_is_pro(uid):
    con = _conn(); cur = con.cursor()
    cur.execute("SELECT plan FROM users WHERE user_id=?", (uid,))
    row = cur.fetchone(); con.close()
    return row is not None and row[0] == "PRO"


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


def db_report_sent(date_str, table="daily_reports", col="report_date"):
    con = _conn(); cur = con.cursor()
    cur.execute("SELECT 1 FROM {} WHERE {}=?".format(table, col), (date_str,))
    row = cur.fetchone(); con.close()
    return row is not None


def db_save_payment(uid, tx_hash):
    con = _conn(); cur = con.cursor()
    with _db_lock:
        cur.execute(
            "INSERT INTO payments (user_id,amount,tx_hash,status,created) VALUES (?,?,?,?,?)",
            (uid, PRO_PROMO, tx_hash, "PENDING", datetime.now().isoformat()))
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


def db_save_signal_track(sig_id, pair, entry, tp, sl, side):
    """Enregistre un signal pour suivi TP/SL automatique."""
    try:
        con = _conn(); cur = con.cursor()
        with _db_lock:
            cur.execute("""CREATE TABLE IF NOT EXISTS signal_tracking (
                track_id INTEGER PRIMARY KEY AUTOINCREMENT,
                sig_id INTEGER, pair TEXT, entry REAL, tp REAL, sl REAL,
                side TEXT, status TEXT DEFAULT 'OPEN', sent_at TEXT)""")
            cur.execute(
                "INSERT INTO signal_tracking (sig_id,pair,entry,tp,sl,side,sent_at) VALUES (?,?,?,?,?,?,?)",
                (sig_id, pair, entry, tp, sl, side, datetime.now().isoformat()))
            con.commit()
        con.close()
    except Exception as e:
        print("  [db_save_track] {}".format(e))


def db_save_signal_tracking(sig_id, pair, entry, tp, sl, side):
    """Enregistre un signal pour suivi TP/SL automatique."""
    con = _conn(); cur = con.cursor()
    with _db_lock:
        cur.execute("""CREATE TABLE IF NOT EXISTS signal_tracking (
            track_id INTEGER PRIMARY KEY AUTOINCREMENT,
            sig_id INTEGER, pair TEXT, entry REAL, tp REAL, sl REAL,
            side TEXT, status TEXT DEFAULT 'OPEN',
            created TEXT, closed_at TEXT)""")
        cur.execute(
            "INSERT INTO signal_tracking (sig_id,pair,entry,tp,sl,side,created) VALUES (?,?,?,?,?,?,?)",
            (sig_id, pair, entry, tp, sl, side, datetime.now().isoformat()))
        con.commit()
    con.close()


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
                    "pro_source TEXT DEFAULT NULL",
                    'trial_used INTEGER DEFAULT 0',
                    'last_seen TEXT DEFAULT NULL',
                    'plan_tier TEXT DEFAULT "FREE"']:
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


def db_update_last_seen(uid):
    """Met à jour la date de dernière activité de l'utilisateur."""
    con = _conn(); cur = con.cursor()
    with _db_lock:
        cur.execute("UPDATE users SET last_seen=? WHERE user_id=?",
                    (datetime.now().isoformat(), uid))
        con.commit()
    con.close()


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


def find_swings(c, n=5):
    H = []; L = []
    for i in range(n, len(c) - n):
        w = c[i-n:i+n+1]
        if c[i]["h"] == max(x["h"] for x in w): H.append((i, c[i]["h"]))
        if c[i]["l"] == min(x["l"] for x in w): L.append((i, c[i]["l"]))
    return H, L


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
        "\U0001f916 AlphaBot PRO  \u00b7  @leaderodg_bot"
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


def get_ote_zone(swing_high, swing_low, bias):
    """Zone OTE 61.8%–78.6% de Fibonacci."""
    rng = swing_high - swing_low
    if rng <= 0: return None, None
    if bias == "BULLISH": return swing_high - rng*0.786, swing_high - rng*0.618
    return swing_low + rng*0.618, swing_low + rng*0.786


def handle_activate(uid, target):
    if not _admin_only(uid): return
    if not target:
        tg_send(uid,
            "🛠 <b>COMMANDES ADMIN</b>\n\n"
            "/activate ID    → Toggle PRO ↔ FREE\n"
            "/activate @user → Par username\n"
            "/degrade ID     → Forcer FREE\n"
            "/testfree       → Simuler vue FREE\n"
            "/testpro        → Retour vue PRO\n"
            "/scan           → Forcer scan immédiat\n"
            "/debug          → Raisons dernier scan\n"
            "/resetcount [ID]→ Reset compteur signaux\n"
            "/monstatus      → Statut admin complet\n"
            "/stats          → Stats + paiements\n"
            "/membres [n]    → Liste membres paginée\n\n"
            "<b>Toggle rapide ↓</b>",
            kb={"inline_keyboard": [
                [{"text": "📋 Liste membres", "callback_data": "adm_membres_1"},
                 {"text": "📊 Stats",          "callback_data": "adm_stats"}],
                [{"text": "💰 Paiements",       "callback_data": "adm_payments"}],
            ]})
        return
    try:
        t_uid = int(target) if target.lstrip("@").isdigit() else db_find_by_username(target)
        if not t_uid:
            tg_send(uid, "❌ Utilisateur introuvable : {}".format(target)); return
        plan, exp, src = db_get_pro_info(t_uid)
        con = _conn(); cur = con.cursor()
        cur.execute("SELECT username FROM users WHERE user_id=?", (t_uid,))
        row = cur.fetchone(); con.close()
        uc = "@" + (row[0] if row and row[0] else str(t_uid))
        if plan == "PRO":
            # ── DÉSACTIVER PRO ───────────────────────────────────
            db_downgrade_pro(t_uid)
            tg_send(t_uid,
                "🔒 <b>Accès PRO désactivé</b>\n\n"
                "Ton plan est maintenant : <b>FREE</b>\n"
                "Limite : {} signaux/jour\n\n"
                "Pour revenir PRO : /pay".format(FREE_LIMIT))
            tg_send(uid,
                "✅ PRO → FREE\n"
                "{} <code>{}</code>\n\n"
                "Plan actuel : <b>FREE</b>".format(uc, t_uid),
                kb={"inline_keyboard": [[
                    {"text": "🔄 Réactiver PRO", "callback_data": "adm_pro_{}".format(t_uid)},
                ]]})
            log("INFO", clr("Admin: {} {} → FREE".format(uc, t_uid), "y"))
        else:
            # ── ACTIVER PRO ─────────────────────────────────────
            db_activate_pro(t_uid, "ADMIN", days=None)
            tg_send(t_uid,
                "🎉 <b>PRO activé !</b>\n\n"
                "✅ Max {} signaux/jour\n"
                "✅ Tous les marchés + crypto week-end\n"
                "✅ Rapports quotidiens + hebdo\n"
                "⚡ Mode Improvisation inclus\n"
                "🤖 Agent IA Binance inclus\n\n"
                "🚀 Bienvenue dans AlphaBot PRO !".format(PRO_LIMIT))
            tg_send(uid,
                "✅ FREE → PRO\n"
                "{} <code>{}</code>  À VIE\n\n"
                "Plan actuel : <b>PRO ✅</b>".format(uc, t_uid),
                kb={"inline_keyboard": [[
                    {"text": "🔒 Désactiver PRO", "callback_data": "adm_ban_{}".format(t_uid)},
                ]]})
            log("INFO", clr("Admin: {} {} → PRO".format(uc, t_uid), "g"))
    except Exception as ex:
        tg_send(uid, "❌ Erreur : {}".format(ex))


def handle_admin_broadcast_start(uid, target):
    nb = len(db_get_pro_users()) + len(db_get_free_users()) if target == "ALL" else len(db_get_pro_users())
    # Enregistrer l'état en attente de message
    _broadcast_pending[uid] = {"target": target, "step": "waiting"}
    _bcast_pending[uid] = {"target": target, "step": "waiting"}
    tg_send(uid,
        "✉️ <b>BROADCAST → {}</b>\n\n"
        "📝 <b>Tape maintenant ton message</b> et envoie-le.\n\n"
        "👥 Sera envoyé à <b>{} membres</b>\n\n"
        "💡 HTML supporté :\n"
        "  <code>&lt;b&gt;gras&lt;/b&gt;</code>\n"
        "  <code>&lt;i&gt;italique&lt;/i&gt;</code>\n"
        "  <code>&lt;code&gt;code&lt;/code&gt;</code>\n\n"
        "/annuler pour annuler.".format(target, nb),
        kb={"inline_keyboard": [[
            {"text": "❌ Annuler", "callback_data": "adm_panel"}
        ]]})


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


def handle_scan(uid):
    if not _admin_only(uid): return
    tg_send(uid, "\U0001f50d <b>Scan forcé lancé...</b>")
    scan_and_send()


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



def is_in_discount_premium(price, swing_high, swing_low, bias):
    """Vérifie si le prix est en zone Discount (BUY) ou Premium (SELL)."""
    rng = swing_high - swing_low
    if rng <= 0: return True
    pct = (price - swing_low) / rng
    return pct <= 0.50 if bias == "BULLISH" else pct >= 0.50


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


def kb_pro():
    return {"inline_keyboard": [
        [{"text": "\U0001f4b0 Payer {}$ USDT TRC20 \u2192 PRO IMMEDIAT".format(PRO_PROMO),
          "callback_data": "pay"}],
        [{"text": "\U0001f91d {} filleuls \u2192 {} mois PRO gratuit".format(REF_TARGET, REF_MONTHS),
          "callback_data": "ref"}],
        [{"text": "\u25c0\ufe0f Menu", "callback_data": "main"}],
    ]}



def make_webhook_handler(scan_state):
    """Crée le handler HTTP pour recevoir les updates Telegram via webhook."""
    class WebhookHandler(BaseHTTPRequestHandler):
        def do_POST(self):
            try:
                length = int(self.headers.get("Content-Length", 0))
                body   = self.rfile.read(length)
                upd    = json.loads(body.decode("utf-8"))
                # Répondre immédiatement 200 OK à Telegram
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b"OK")
                # Traiter l'update dans un thread
                threading.Thread(target=process_update, args=(upd,), daemon=True).start()
            except Exception as ex:
                log("ERR", "WebhookHandler: {}".format(ex))
                try:
                    self.send_response(200)
                    self.end_headers()
                except: pass

        def do_GET(self):
            # Health check pour Render
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"AlphaBot OK")

        def log_message(self, *a): pass  # silence les logs HTTP

    return WebhookHandler



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



def score_min_for_market(m, base, atr_ratio):
    """Score minimum adaptatif selon la qualité de la session et la volatilité."""
    vol_adj = (m.get("vol", 3) - 3) * 2
    atr_adj = min(4, int(atr_ratio * 5))
    return base + vol_adj + atr_adj

def get_adaptive_score_min():
    """
    Score minimum intelligent :
    - Kill Zone Londres/NY     → score min BAISSÉ  (meilleure session)
    - Session hors marché/nuit → score min MONTÉ   (moins de setups)
    - Week-end                 → score min MONTÉ   (crypto only, volatilité)
    - Régime VOLATILE/CRISIS   → score min MONTÉ   (risque élevé)
    - Régime TRENDING          → score min BAISSÉ  (tendance claire)
    """
    sn, sm, sl, wknd = get_session()
    reg  = AI_REG.get("regime", "RANGING")
    base = sm  # score de base de la session

    # Ajustement selon la qualité de la session
    session_adj = {
        "LONDON_KZ": -5,   # Kill Zone = meilleure probabilité
        "OVERLAP":   -3,   # London+NY = très liquide
        "NY_KZ":     -5,   # Kill Zone NY
        "NY":        -2,   # NY normal
        "LONDON":    -1,   # Londres normal
        "ASIAN":     +5,   # Asie = moins fiable
        "OFF":       +10,  # Hors session = éviter
        "WEEKEND":   +8,   # Week-end = volatile
    }.get(sn, 0)

    # Ajustement selon le régime de marché
    regime_adj = {
        "TRENDING_BULL": -3,  # Tendance claire → plus facile
        "TRENDING_BEAR": -3,
        "ACCUMULATION":  -1,
        "RANGING":       +2,  # Range → plus de faux signaux
        "VOLATILE":      +8,  # Volatile → exiger plus de confirmations
        "CRISIS":        +20, # Crise → quasi stop
    }.get(reg, 0)

    final = base + session_adj + regime_adj
    log("INFO", clr("Score min adaptatif: {} (base:{} sess:{:+d} regime:{:+d})".format(
        final, base, session_adj, regime_adj), "d"))
    return max(72, min(95, final))



def send_admin_panel(uid):
    if uid != ADMIN_ID: tg_send(uid, "❌ Accès refusé."); return
    total, pro, sigs, pays, g1d = db_global_stats()
    sn, sm, sl, wknd = get_session()
    stats  = db_daily_stats()
    pend   = db_pending_payments()
    free   = total - pro
    tg_send_sticker(uid, STK_CROWN)
    tg_send(uid,
        "🛡 <b>PANEL ADMIN — AlphaBot v10</b>\n" + "═" * 22 + "\n\n"
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


def send_pro(uid):
    is_pro = db_is_pro(uid)
    if is_pro:
        tg_send_sticker(uid, STK_CROWN)
        plan, exp, src = db_get_pro_info(uid)
        exp_txt = "À VIE" if not exp else "expire le {}".format(exp)
        tg_send(uid,
            "\U0001f4a0 <b>Plan {} actif !</b> \u2705\n\n"
            "Accès : <b>{}</b>\nSignaux : max {}/j\n\nMerci \U0001f64f".format(
                plan, exp_txt, PRO_LIMIT),
            kb=kb_back())
        return
    refs = db_get_refs(uid)
    tg_send_sticker(uid, STK_PRO)
    tg_send(uid,
        "\U0001f4a0 <b>PASSE AU NIVEAU SUPÉRIEUR</b>\n" + "\u2550" * 22 + "\n\n"
        "\U0001f513 <b>FREE</b>  \u2014  2 signaux/jour  \u2014  Gratuit\n\n"
        "\U0001f680 <b>STARTER</b>  \u2014  5 signaux/jour\n"
        "  \u2022 Analyse ICT/SMC complète\n"
        "  \u2022 Entrée + TP + SL + RR\n"
        "  \u2022 <b>5$ USDT/mois</b>\n\n"
        "\U0001f4a0 <b>PRO</b>  \u2014  10 signaux/jour\n"
        "  \u2022 Tout STARTER +\n"
        "  \u2022 Rapports quotidiens + hebdo\n"
        "  \u2022 Suivi TP/SL automatique\n"
        "  \u2022 <b>10$ USDT/mois</b>\n\n"
        "\U0001f451 <b>VIP</b>  \u2014  Signaux illimités\n"
        "  \u2022 Tout PRO +\n"
        "  \u2022 Accès prioritaire aux meilleurs setups\n"
        "  \u2022 Support direct @leaderOdg\n"
        "  \u2022 <b>25$ USDT/mois</b>\n\n" +
        "\u2501" * 22 + "\n"
        "\U0001f91d <b>Parrainage GRATUIT</b>\n"
        "{} filleuls = {} mois PRO (renouvelable)\n"
        "Tes filleuls : {}/{}\n\n"
        "\U0001f449 /pay pour payer et choisir ton plan".format(
            REF_TARGET, REF_MONTHS, refs, REF_TARGET),
        kb={"inline_keyboard": [
            [{"text": "🚀 STARTER — 5$/mois",  "callback_data": "pay_plan_STARTER"}],
            [{"text": "💠 PRO — 10$/mois",      "callback_data": "pay_plan_PRO"}],
            [{"text": "👑 VIP — 25$/mois",      "callback_data": "pay_plan_VIP"}],
            [{"text": "🤝 Parrainage gratuit",   "callback_data": "ref"}],
        ]})


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



def tg_send_sticker(chat_id, sticker_id):
    """Envoie un sticker Telegram animé."""
    tg_req("sendSticker", {"chat_id": str(chat_id), "sticker": sticker_id})


def tg_updates(offset):
    return tg_req("getUpdates", {
        "offset":  offset,
        "timeout": 0,
        "limit":   100
    }).get("result", [])


# ══════════════════════════════════════════════════════
#  CLAVIERS COMPLETS
# ══════════════════════════════════════════════════════
def kb_reply():
    return {"keyboard": [
        [{"text":"📡 Mes Signaux"},   {"text":"📊 Mon Compte"}],
        [{"text":"💰 Devenir PRO"},   {"text":"🤝 Parrainage"}],
        [{"text":"💸 Mes Gains"},     {"text":"📖 Guide ICT"}],
        [{"text":"📈 Rapports"},      {"text":"🏦 Broker Exness"}],
    ], "resize_keyboard":True, "persistent":True,
       "input_field_placeholder":"Choisis une option..."}

def kb_pro_plans():
    return {"inline_keyboard":[
        [{"text":"🚀 STARTER — 5$/mois",  "callback_data":"pay_plan_STARTER"}],
        [{"text":"💠 PRO — 10$/mois",     "callback_data":"pay_plan_PRO"}],
        [{"text":"👑 VIP — 25$/mois",     "callback_data":"pay_plan_VIP"}],
        [{"text":"🤝 Parrainage gratuit", "callback_data":"ref"}],
    ]}

def kb_admin_back(): return {"inline_keyboard":[[{"text":"◀️ Panel Admin","callback_data":"adm_panel"}]]}

# ══════════════════════════════════════════════════════
#  MESSAGES UTILISATEURS COMPLETS
# ══════════════════════════════════════════════════════
def send_welcome(uid, uname, ref_by=0):
    db_register(uid, uname, ref_by, tg_fn=tg_send)
    tg_sticker(uid, STK_W)
    p = is_pro(uid); sn,sm,sl_l,wknd = get_session()
    plan_line = ("🎁 <b>ESSAI PRO {} JOURS OFFERT !</b> ✅".format(TRIAL_DAYS) if p
                 else "🔓 FREE → /pay")
    wknd_note = "\n🌍 <b>Week-end : crypto uniquement !</b>" if wknd else ""
    tg_send(uid,
        "🤖 <b>AlphaBot PRO v10 — Bienvenue {} !</b>\n".format("@"+uname if uname else "Trader") +
        "═"*22 + "\n\n"
        "🆔 <b>ID :</b> <code>{}</code>\n"
        "📌 <b>Plan :</b> {}\n"
        "🕐 <b>Session :</b> {}  ·  Score min : <b>{}</b>{}\n\n".format(uid,plan_line,sl_l,sm,wknd_note)+
        "═"*22+"\n"
        "🤖 <b>20 agents IA</b> scannent en parallèle :\n"
        "  🥇 Or · Argent  ·  ₿ BTC\n"
        "  💱 Forex : EURUSD · GBPUSD · USDJPY · GBPJPY · EURJPY\n"
        "           AUDUSD · AUDJPY · CADJPY · USDCHF · NZDUSD · USDCAD\n"
        "  📈 Indices : NAS100 · SPX500 · US30  ·  🛢 USOIL\n\n"
        "⚡ <b>Mode Improvisation actif</b> — signal même sans setup ICT parfait !\n\n"
        "═"*22+"\n"
        "🎁 Essai PRO {} jours GRATUIT !\n"
        "💠 PRO = max {}/j  ·  🤝 {} filleuls = {} mois PRO\n\n"
        "📖 /guide ou choisis ci-dessous ↓".format(TRIAL_DAYS,PRO_LIMIT,REF_TARGET,REF_MONTHS),
        kb=kb_reply())    # ← clavier physique persistant

def send_start(uid, uname, ref_by=0):
    """Alias for send_welcome."""
    send_welcome(uid, uname)

def send_signals_info(uid):
    p = is_pro(uid); st = daily_stats(); rows = st["rows"]
    sn,sm,sl_l,wknd = get_session()
    cnt = count_today(uid); lim = PRO_LIMIT if p else FREE_LIMIT
    today = datetime.now().strftime("%d/%m/%Y")
    lines = ["📡 <b>SIGNAUX DU JOUR</b>","═"*22,
             "📅 {}  ·  {}".format(today,sl_l),
             "{} ·  {}/{} signaux  ·  Reste : <b>{}</b>".format(
                 "💠 PRO" if p else "🔓 FREE",cnt,lim,max(0,lim-cnt)),""]
    if rows:
        lines.append("📋 <b>Signaux envoyés :</b>"); lines.append("")
        for row in rows:
            pair,side,rr,g001,g1,l001,l1,sess,mode = row
            arrow = "⬆️" if side=="BUY" else "⬇️"
            icon = "✅" if rr>=2.5 else "⚪"
            gain = "+${:.0f}".format(g1) if rr>=2.5 else "---"
            tag = " ⚡" if mode!="NORMAL" else ""
            lines.append("{} <b>{}</b>{} {} {}  RR 1:{}  💰 {}".format(icon,pair,tag,arrow,side,rr,gain))
        lines += ["","━"*20,
                  "💵 Total lot 0.01 : <b>+${}</b>".format(st["g001"]),
                  "💰 Total lot 1.00 : <b>+${}</b>".format(st["g1"]),
                  "🎯 {}/{} gagnants".format(st["wins"],st["n"])]
    else:
        lines += ["⏳ Aucun signal encore aujourd\'hui.",
                  "🔄 Prochain scan dans quelques minutes...",
                  "","💠 <b>Passe PRO pour max {}/j</b>\n/pay — {}$ USDT".format(PRO_LIMIT,PRO_PRICE) if not p else ""]
    tg_send(uid, "\n".join(l for l in lines if l is not None), kb=kb_back())

def send_pro_page(uid):
    p = is_pro(uid)
    if p:
        tg_sticker(uid, STK_PRO)
        plan,exp,_ = get_pro_info(uid)
        tg_send(uid,"💠 <b>Plan {} actif !</b> ✅\n\nAccès : {}\nSignaux : max {}/j\n\nMerci 🙏".format(
            plan,"À VIE" if not exp else "expire le {}".format(exp),PRO_LIMIT),kb=kb_back())
        return
    refs = get_refs(uid)
    tg_sticker(uid, STK_PRO)
    tg_send(uid,
        "💠 <b>PASSE AU NIVEAU SUPÉRIEUR</b>\n"+"═"*22+"\n\n"
        "🔓 <b>FREE</b>  —  2 signaux/jour  —  Gratuit\n\n"
        "🚀 <b>STARTER</b>  —  5 signaux/jour\n"
        "  • Analyse ICT/SMC complète\n"
        "  • Entrée + TP + SL + RR\n"
        "  • ⚡ Mode Improvisation\n"
        "  • <b>5$ USDT/mois</b>\n\n"
        "💠 <b>PRO</b>  —  10 signaux/jour\n"
        "  • Tout STARTER +\n"
        "  • Rapports quotidiens + hebdo\n"
        "  • Suivi TP/SL automatique\n"
        "  • Agent IA Binance (Challenge 5$→500$)\n"
        "  • <b>10$ USDT/mois</b>\n\n"
        "👑 <b>VIP</b>  —  Signaux illimités\n"
        "  • Tout PRO + Support @leaderOdg\n"
        "  • <b>25$ USDT/mois</b>\n\n"
        "━"*22+"\n"
        "🤝 <b>Parrainage GRATUIT</b>\n"
        "{} filleuls = {} mois PRO (renouvelable)\n"
        "Tes filleuls : {}/{}\n\n"
        "👉 /pay pour payer et choisir ton plan".format(REF_TARGET,REF_MONTHS,refs,REF_TARGET),
        kb=kb_pro_plans())

def send_pay_plan(uid, plan_key="PRO"):
    plans = {"FREE":{"price":0,"label":"FREE"},"STARTER":{"price":5,"label":"STARTER"},
             "PRO":{"price":10,"label":"PRO"},"VIP":{"price":25,"label":"VIP"}}
    plan = plans.get(plan_key, plans["PRO"])
    price = plan["price"]; label = plan["label"]
    tg_send(uid,
        "💰 <b>PAIEMENT {} — {}$ USDT/mois</b>\n"+"━"*22+"\n\n"
        "⚠️ <b>RÉSEAU : TRC20 UNIQUEMENT</b>\n"
        "Pas BEP20, pas ERC20 — sinon perdu !\n\n"
        "👇 <b>Adresse USDT TRC20 :</b>\n"
        "<code>{}</code>\n\n"+"━"*22+"\n"
        "1️⃣ Ouvre Binance / Trust Wallet\n"
        "2️⃣ Envoie <b>{}$ USDT TRC20</b>\n"
        "3️⃣ Clique <b>J\'ai payé ✅</b>\n"
        "4️⃣ Envoie ton <b>TX Hash</b>\n\n"
        "🤖 <b>Activation automatique sous 2 min !</b>".format(label,price,USDT_ADDR,price),
        kb={"inline_keyboard":[
            [{"text":"✅ J\'ai payé — Soumettre TX Hash","callback_data":"pay_submitted_{}".format(plan_key)}],
            [{"text":"◀️ Voir les plans","callback_data":"pro"}],
        ]})

def send_mes_gains(uid):
    st = daily_stats()
    if not st["n"]: tg_send(uid,"💸 <b>MES GAINS</b>\n\nAucun signal aujourd\'hui.",kb=kb_back()); return
    lines = ["💸 <b>GAINS DU JOUR</b>","═"*22,""]
    for row in st["rows"]:
        pair,side,rr,g001,g1,l001,l1,sess,mode = row
        ok=rr>=2.5; icon="✅" if ok else "❌"; d="⬆️" if side=="BUY" else "⬇️"
        tag=" ⚡" if mode!="NORMAL" else ""
        lines.append("{} <b>{}</b>{} {} {}  RR 1:{}".format(icon,pair,tag,d,side,rr))
        if ok: lines.append("   0.01 → +${:.2f}   1.00 → +${:.0f}".format(g001,g1))
        else:  lines.append("   ---")
    lines += ["","═"*22,
              "💵 Lot 0.01 : <b>+${}</b>".format(st["g001"]),
              "💰 Lot 1.00 : <b>+${}</b>".format(st["g1"]),
              "({}/{} gagnants)".format(st["wins"],st["n"]),"",
              "<i>Estimation TP atteint. Pas un conseil financier.</i>"]
    tg_send(uid,"\n".join(lines),kb=kb_back())

def send_affilie(uid, uname):
    refs=get_refs(uid); link="https://t.me/{}?start={}".format(BOT_USER,uid)
    done=min(refs,REF_TARGET); pct=int(done/REF_TARGET*100)
    fill=int(done/REF_TARGET*12); bar="🟩"*fill+"⬛"*(12-fill)
    tg_send(uid,
        "📋 <b>COPIE CE MESSAGE ET ENVOIE À TES AMIS :</b>\n\n"+"━"*22+"\n\n"
        "🤖 <b>AlphaBot PRO</b> — Signaux trading GRATUITS !\n\n"
        "📡 <b>Forex, Or, BTC, Indices...</b>\n"
        "🎯 Entrées directes avec SL & TP automatiques\n"
        "💰 Jusqu\'à <b>+$500+ par signal</b> (lot 1.00)\n"
        "📊 Analyse ICT/SMC + <b>Mode Improvisation ⚡</b>\n\n"
        "✅ <b>Gratuit</b> — 2 signaux/jour\n"
        "💠 <b>PRO seulement 10$</b> — 10 signaux/jour\n\n"
        "👉 <b>Clique ici :</b>\n<code>{}</code>\n\n"+"━"*22,
        kb={"inline_keyboard":[[{"text":"🤝 Voir mes filleuls","callback_data":"ref_stats"}]]})
    rew = ("🏆 {} mois PRO actif ! Re-parraine pour renouveler !".format(REF_MONTHS) if refs>=REF_TARGET
           else "🔥 Plus que {} de plus → {} mois PRO !".format(REF_TARGET-refs,REF_MONTHS) if refs>=20
           else "👋 {} filleuls pour l\'instant. Continue !".format(refs))
    tg_send(uid,
        "🤝 <b>MES FILLEULS</b>\n"+"═"*22+"\n\n"
        "<b>{}/{}</b>  ({}%)\n{}\n\n"
        "{}\n\n"
        "🏆 {} filleuls = <b>{} MOIS PRO GRATUIT</b>\n"
        "✅ <b>Activation automatique</b> dès {} atteints".format(
            done,REF_TARGET,pct,bar,rew,REF_TARGET,REF_MONTHS,REF_TARGET),
        kb=kb_back())

# ══════════════════════════════════════════════════════
#  ADMIN COMPLET
# ══════════════════════════════════════════════════════
_bcast_pending = _broadcast_pending  # même dict, deux noms
STK_ROCKET = "CAACAgIAAxkBAAIBjGWbNfNMiEkgPZrxgWMVBH1ycfP7AAIbAQACB8OhCsYm5NOoMByuNgQ"

def kb_admin_full():
    return {"inline_keyboard":[
        [{"text":"🙏 Excuses membres","callback_data":"adm_promo_send_promo_excuse"}],
        [{"text":"👥 Membres","callback_data":"adm_membres_1"},{"text":"📊 Stats","callback_data":"adm_stats"}],
        [{"text":"💰 Paiements","callback_data":"adm_payments"},{"text":"📈 Rapports","callback_data":"adm_rapports"}],
        [{"text":"📡 Forcer scan","callback_data":"adm_scan"},{"text":"🔍 Debug scan","callback_data":"adm_debug"}],
        [{"text":"✉️ Message → TOUS","callback_data":"adm_bcast_all"},{"text":"✉️ Message → PRO","callback_data":"adm_bcast_pro"}],
        [{"text":"📢 Messages Promo","callback_data":"adm_promo_list"},{"text":"🌍 État marchés","callback_data":"adm_marches"}],
        [{"text":"🏆 Challenge IA","callback_data":"challenge"},{"text":"🔧 Recommandations","callback_data":"adm_reco"}],
    ]}

def send_admin_full(uid):
    if uid!=ADMIN_ID: tg_send(uid,"❌ Accès refusé."); return
    total,pro,sigs,pays,g1d=global_stats(); sn,sm,sl_l,_=get_session()
    st=daily_stats(); pend=pending_pays(); ch=chal_get(); reg=AI_REG
    improv=db_all("SELECT COUNT(*) FROM signals WHERE sent_at LIKE ? AND mode!='NORMAL'",(datetime.now().strftime("%Y-%m-%d")+"%",))
    improv_cnt=improv[0][0] if improv else 0
    tg_sticker(uid,STK_PRO)
    tg_send(uid,
        "🛡 <b>PANEL ADMIN — AlphaBot v10</b>\n"+"═"*22+"\n\n"
        "👥 Membres: <b>{}</b>  ·  PRO: <b>{}</b>  ·  FREE: <b>{}</b>\n"
        "📡 Signaux: <b>{}</b>  ·  Gains: <b>+${}</b>\n"
        "⚡ Dont {} improvisation\n"
        "💰 Payés: <b>{}</b>  ·  En attente: <b>{}</b>{}\n\n"
        "🤖 <b>IA:</b> {:.4f}$ AM:{}/4 W:{} L:{}\n"
        "🌍 Régime: <b>{}</b>  Positions: {}/{}\n\n"
        "🕐 Session: {}  Score min: {}\n\n"
        "/activate /degrade /scan /debug /stats /membres /marches".format(
            total,pro,total-pro,st["n"],st["g1"],improv_cnt,pays,len(pend),
            "  ⚠️ À valider!" if pend else "",
            ch["balance"],ch["am_cycle"],ch.get("today_w",0),ch.get("today_l",0),
            reg.get("regime","?"),sum(1 for t in AI_OT.values() if t["status"]=="open"),MAX_OPEN,sl_l,sm),
        kb=kb_admin_full())

def send_admin_stats_full(uid):
    if uid!=ADMIN_ID: return
    total,pro,sigs,pays,g1d=global_stats(); st=daily_stats(); ws=weekly_stats()
    con=_conn(); cur=con.cursor()
    cur.execute("SELECT user_id,username,ref_count FROM users GROUP BY user_id ORDER BY ref_count DESC LIMIT 5")
    top=cur.fetchall()
    cur.execute("SELECT COUNT(*) FROM users WHERE joined>=date(\'now\',\'-1 day\')")
    new1=cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM users WHERE joined>=date(\'now\',\'-7 days\')")
    new7=cur.fetchone()[0]; con.close()
    pend=pending_pays()
    wr_d=int(st["wins"]/st["n"]*100) if st["n"] else 0
    wr_w=int(ws["wins"]/ws["n"]*100) if ws["n"] else 0
    msg=("📊 <b>STATS ALPHABOT PRO v10</b>\n"+"═"*22+"\n"
         "👥 Total:{} PRO:{} FREE:{}\n"
         "🆕 Nouveaux 24h:{} · 7j:{}\n"
         "📡 Signaux:{} · Payés:{}\n\n"
         "━"*20+"\n"
         "📅 <b>AUJOURD\'HUI</b>\n"
         "  {} sig · {} gagnants · {}% winrate\n"
         "  Lot 0.01:+${}  Lot 1.00:+${}\n\n"
         "📆 <b>CETTE SEMAINE</b>\n"
         "  {} sig · {} gagnants · {}% winrate\n"
         "  Lot 1.00:+${}\n\n").format(total,pro,total-pro,new1,new7,sigs,pays,
             st["n"],st["wins"],wr_d,st["g001"],st["g1"],ws["n"],ws["wins"],wr_w,ws["g1"])
    if top:
        msg += "🤝 <b>TOP PARRAINS</b>\n"
        seen=set()
        for t_uid,uname,rc in top:
            if t_uid not in seen:
                seen.add(t_uid); msg += "  @{}  <b>{}</b> filleuls\n".format(uname or "?",rc)
    if pend:
        msg += "\n⏳ <b>ATTENTE PAIEMENT</b>\n"
        for _,p_uid,un,tx,_ in pend:
            msg += "• @{} <code>{}</code>  <code>{}</code>\n  /activate {}\n".format(un or "?",p_uid,(tx or "")[:16]+"...",p_uid)
    tg_send(uid,msg,kb=kb_admin_back())

def send_admin_payments_full(uid):
    if uid!=ADMIN_ID: return
    pend=pending_pays()
    if not pend: tg_send(uid,"💰 Aucun paiement en attente. ✅",kb=kb_admin_back()); return
    msg="💰 <b>PAIEMENTS EN ATTENTE ({})</b>\n".format(len(pend))+"═"*22+"\n\n"
    btns=[]
    for pid,p_uid,un,tx,created in pend:
        msg+="• @{}  <code>{}</code>\n  Hash: <code>{}</code>\n\n".format(un or "?",p_uid,(tx or "")[:30]+"...")
        btns.append([{"text":"✅ Activer @{}".format(un or p_uid),"callback_data":"adm_pro_{}".format(p_uid)},{"text":"❌ Refuser","callback_data":"adm_ban_{}".format(p_uid)}])
    btns.append([{"text":"◀️ Panel Admin","callback_data":"adm_panel"}])
    tg_send(uid,msg,kb={"inline_keyboard":btns})

def send_admin_reco(uid):
    if uid!=ADMIN_ID: return
    total,pro,sigs,pays,g1d=global_stats(); st=daily_stats()
    wr=int(st["wins"]/st["n"]*100) if st["n"]>=3 else 0
    recs=[]
    if st["n"]==0: recs.append("📭 Aucun signal — Lance /scan puis /debug pour voir les raisons.")
    if wr<50 and st["n"]>=3: recs.append("📉 Winrate {}% faible — Mode Improvisation actif pour combler.".format(wr))
    if (total-pro)>pro*4: recs.append("💡 {} FREE vs {} PRO — Lance un broadcast de motivation.".format(total-pro,pro))
    if pays<5: recs.append("💰 Seulement {} paiements — Envoie un message promo.".format(pays))
    if st["g1"]>500: recs.append("🔥 Excellente journée +${} ! Partage les résultats.".format(st["g1"]))
    improv=db_all("SELECT COUNT(*) FROM signals WHERE sent_at LIKE ? AND mode!='NORMAL'",(datetime.now().strftime("%Y-%m-%d")+"%",))
    if improv and improv[0][0]>0: recs.append("⚡ {} signal(s) improvisation envoyés aujourd\'hui.".format(improv[0][0]))
    if not recs: recs.append("✅ Tout fonctionne bien. Continue !")
    msg="🔧 <b>RECOMMANDATIONS ADMIN</b>\n"+"═"*22+"\n\n"
    for i,r in enumerate(recs,1): msg+="{}. {}\n\n".format(i,r)
    tg_send(uid,msg,kb=kb_admin_back())

def handle_monstatus_full(uid):
    if uid!=ADMIN_ID: return
    plan,exp,src=get_pro_info(uid); total,pro,sigs,pays,g1d=global_stats()
    sn,sm,sl_l,wknd=get_session(); st=daily_stats(); ws=weekly_stats()
    cnt=count_today(uid); pend=pending_pays(); refs=get_refs(uid)
    ch=chal_get(); reg=AI_REG
    win_pct=int(st["wins"]/st["n"]*100) if st["n"] else 0
    pend_str="\n⏳ <b>{} paiement(s) en attente !</b>".format(len(pend)) if pend else ""
    tg_send(uid,
        "🛡 <b>MON STATUT ADMIN</b>\n"+"═"*22+"\n\n"
        "🆔 ID: <code>{}</code>  · @leaderOdg\n"
        "💠 Plan: <b>{}</b>  —  {}\n\n"
        "━"*20+"\n"
        "🕐 Session: <b>{}</b>  ·  Score min: <b>{}</b>\n\n"
        "━"*20+"\n"
        "👥 <b>MEMBRES</b>  {} total  ·  <b>{} PRO</b>  ·  {} FREE\n"
        "💰 Payés: {}  ·  En attente: {}{}\n"
        "📡 Signaux total: {}\n\n"
        "━"*20+"\n"
        "📅 <b>AUJOURD\'HUI</b>\n"
        "  {} sig  ·  {} gagnants ({}%)\n"
        "  Lot 0.01: +${}  ·  Lot 1.00: +${}\n\n"
        "📆 <b>CETTE SEMAINE</b>\n"
        "  {} sig  ·  {} gagnants  ·  Lot1 +${}\n\n"
        "🤖 <b>IA:</b> {:.4f}$ AM:{}/4  Régime:{}\n\n"
        "━"*20+"\n"
        "/activate {} /testfree /testpro\n/stats /membres /scan /debug".format(
            uid,plan,"À VIE" if not exp else "expire le {}".format(exp),sl_l,sm,
            total,pro,total-pro,pays,len(pend),pend_str,sigs,
            st["n"],st["wins"],win_pct,st["g001"],st["g1"],
            ws["n"],ws["wins"],ws["g1"],
            ch["balance"],ch["am_cycle"],reg.get("regime","?"),uid))

def handle_marches_full(uid):
    sn,sm,sl_l,wknd=get_session()
    tg_send(uid,"📡 <b>SCAN EN COURS...</b>\n🕐 {}  ·  Score min: <b>{}</b>\n⏳ Analyse {} marchés...".format(sl_l,sm,len(MARKETS)))
    active=[m for m in MARKETS if not wknd or m.get("crypto",False)]
    news_ok,news_lbl=news_check(); q=Queue(); threads=[]
    for m in active:
        t=threading.Thread(target=agent_analyze,args=(m,sm,news_ok,q),daemon=True); t.start(); threads.append(t)
    for t in threads: t.join(timeout=10)
    results={}
    while not q.empty():
        try: r=q.get_nowait(); results[r["name"]]=r
        except Empty: break
    cats={}
    for m in MARKETS:
        r=results.get(m["name"],{"name":m["name"],"cat":m["cat"],"found":False,"reason":"Timeout"})
        cats.setdefault(m["cat"],[]).append(r)
    lines=["🔍 <b>ÉTAT DES MARCHÉS</b> — {}  {}\n".format(sl_l,datetime.now().strftime("%H:%M"))]
    found=[]
    for cat in ["METALS","CRYPTO","FOREX","INDICES","OIL"]:
        mlist=cats.get(cat,[])
        if not mlist: continue
        lines.append("{} <b>{}</b>".format(CAT_EMO.get(cat,"📊"),cat))
        for r in mlist:
            if r.get("found"):
                s=r["signal"]; arrow="⬆️" if s["side"]=="BUY" else "⬇️"
                tag=" ⚡" if r.get("improv") else ""
                lines.append("  🟢 <b>{}</b>{} {} {}  RR 1:{}  Score {}".format(r["name"],tag,arrow,s["side"],s["rr"],s["score"]))
                lines.append("    📍<code>{}</code>→TP<code>{}</code> SL<code>{}</code>".format(s["entry"],s["tp"],s["sl"]))
                found.append(r["name"])
            else:
                reason=r.get("reason","?")
                ico=("⚪" if "insuffisant" in reason or "Timeout" in reason else
                     "🟡" if "neutre" in reason.lower() else
                     "🟠" if "Score" in reason else
                     "🔵" if "Breaker" in reason else "🔴" if "RR" in reason or "Spread" in reason else "⏸")
                lines.append("  {} <b>{}</b>  <i>{}</i>".format(ico,r["name"],reason))
        lines.append("")
    lines.append("🟢 <b>{} signal(s) détecté(s) !</b>".format(len(found)) if found else "🟡 Aucun signal ce cycle")
    msg="\n".join(lines)
    if len(msg)>4000: msg=msg[:3900]+"\n...(tronqué)"
    tg_send(uid,msg)

def handle_resetcount(uid, target):
    if uid!=ADMIN_ID: tg_send(uid,"❌ Accès refusé."); return
    try:
        t=int(target) if target and target.lstrip("@").isdigit() else (find_user(target) if target else uid)
        if not t: tg_send(uid,"❌ Introuvable."); return
        ds=datetime.now().strftime("%Y-%m-%d"); db_run("DELETE FROM sig_counts WHERE user_id=? AND date_str=?",(t,ds))
        tg_send(uid,"✅ Compteur remis à 0 pour <code>{}</code>.".format(t))
    except Exception as e: tg_send(uid,"❌ {}".format(e))

# ── Messages Promo ───────────────────────────────────────────────
PROMO_MSGS = [
    {"id":"promo_excuse","label":"🙏 Excuses membres (messages)",
     "text":"🙏 <b>Un mot de l\'équipe AlphaBot</b>\n\nCher(e) membre,\n\nNous tenons à nous excuser sincèrement pour le <b>volume important de messages</b> que vous avez reçu ces derniers jours.\n\nNous avons ajusté notre système pour vous envoyer <b>uniquement les signaux essentiels</b> — plus de bruit, plus de clarté.\n\n📡 Désormais vous recevrez :\n✅ Les signaux de trading directement\n✅ Les rapports journaliers/hebdomadaires\n✅ Les résultats TP/SL en temps réel\n\nMerci pour votre confiance et votre patience. 🙏\n\n<i>— @leaderOdg · Équipe AlphaBot PRO</i>"},
    {"id":"promo_1","label":"📡 Accroche générale",
     "text":"📡 <b>SIGNAUX TRADING EN TEMPS RÉEL</b>\n\nTu rates des trades faute d\'entrée précise ?\n\n🎯 Entrée + Stop Loss + Take Profit automatiques\n🤖 IA qui analyse 24h/24  ·  ⚡ Mode Improvisation\n\n📩 Rejoins AlphaBot maintenant\n➡️ @leaderodg_bot"},
    {"id":"promo_2","label":"💰 Preuve sociale",
     "text":"💰 <b>ILS GAGNENT. ET TOI ?</b>\n\nPendant que tu hésites, d\'autres exécutent 🚀\n\nOr · Forex · BTC · Indices US\nAnalyse ICT/SMC + ⚡ Mode Improvisation\n\n✅ Signal reçu  ✅ Entrée placée  ✅ TP atteint\n\n📩 Commence <b>GRATUIT</b>\n➡️ @leaderodg_bot"},
    {"id":"promo_3","label":"⏰ Urgence / Opportunité",
     "text":"⏰ <b>LE MARCHÉ N\'ATTEND PAS</b>\n\nChaque bougie est une opportunité...\n\nAlphaBot scanne <b>EURUSD · GBPJPY · XAUUSD · NAS100</b>\net t\'envoie le signal avec l\'entrée exacte 🎯\n\n🆓 2 signaux gratuits/jour\n💎 PRO = jusqu\'à 10 signaux/jour\n\n📩 Lance-toi\n➡️ @leaderodg_bot"},
    {"id":"promo_4","label":"📊 Résultats du jour","text":None},
    {"id":"promo_5","label":"🆓 FREE vs 💎 PRO",
     "text":"🆓 <b>GRATUIT</b> ou 💎 <b>PRO ?</b>\n\n🆓 FREE → 2 signaux/jour\n💎 PRO → jusqu\'à 10 signaux/jour\n  + Analyse ICT complète\n  + ⚡ Mode Improvisation\n  + Rapports quotidiens\n  + Agent IA Binance (Challenge 5$→500$)\n\nTout ça pour seulement <b>10$ USDT</b> 💵\nOu <b>30 filleuls = 3 mois PRO GRATUIT</b> 🤝\n\n📩 @leaderodg_bot"},
]

def _build_promo(pid):
    p=next((x for x in PROMO_MSGS if x["id"]==pid),None)
    if not p: return None
    if pid!="promo_4": return p["text"]
    st=daily_stats()
    if not st["n"]: return None
    lines=["📊 <b>RÉSULTATS D\'AUJOURD\'HUI</b>\n"]
    for row in st["rows"]:
        pair,side,rr,g001,g1,l001,l1,sess,mode=row
        ok=rr>=2.5; icon="🟢" if ok else "🔴"; d="ACHAT" if side=="BUY" else "VENTE"
        res="✅ TP → <b>+${:.0f}</b>".format(g1) if ok else "❌ SL → <b>-${:.0f}</b>".format(l1)
        lines.append("{} <b>{}</b> {}  {} (lot 0.01)".format(icon,pair,d,res))
    lines+=["","💰 <b>Total : +${}</b> lot 0.01  ·  +${} lot 1.00 🔥".format(st["g001"],st["g1"]),
            "","Et toi tu étais où ? 👀","","📩 Rejoins la communauté\n➡️ @leaderodg_bot"]
    return "\n".join(lines)

def send_promo_list(uid):
    if uid!=ADMIN_ID: return
    st=daily_stats()
    btns=[[{"text":p["label"],"callback_data":"adm_promo_{}".format(p["id"])}] for p in PROMO_MSGS]
    btns.append([{"text":"◀️ Panel Admin","callback_data":"adm_panel"}])
    tg_send(uid,"📢 <b>MESSAGES PROMO</b>\n"+"═"*22+"\n\nSélectionne un message à envoyer.\n\n📊 Aujourd\'hui: <b>{} signaux · {} TP · +${} lot1</b>".format(st["n"],st["wins"],st["g1"]),kb={"inline_keyboard":btns})

def send_promo_preview(uid, pid):
    if uid!=ADMIN_ID: return
    p=next((x for x in PROMO_MSGS if x["id"]==pid),None)
    if not p: return
    text=_build_promo(pid)
    if not text: tg_send(uid,"⚠️ Pas de signaux aujourd\'hui pour ce message.",kb={"inline_keyboard":[[{"text":"◀️ Retour","callback_data":"adm_promo_list"}]]}); return
    total=len(set(pro_users()+free_users()))
    tg_send(uid,"👁 <b>APERÇU</b> — {}\n".format(p["label"])+"─"*22+"\n\n"+text+"\n\n"+"─"*22+"\n📤 Envoyer à <b>{}</b> membres ?".format(total),
        kb={"inline_keyboard":[[{"text":"✅ Envoyer à TOUS maintenant","callback_data":"adm_promo_send_{}".format(pid)}],[{"text":"◀️ Choisir autre message","callback_data":"adm_promo_list"}]]})

def broadcast_promo(uid, pid):
    if uid!=ADMIN_ID: return
    text=_build_promo(pid)
    if not text: tg_send(uid,"⚠️ Impossible de générer ce message."); return
    users=list(set(pro_users()+free_users()))
    tg_send(uid,"📤 Envoi en cours à <b>{}</b> membres...".format(len(users)))
    sent=fail=0
    for u in users:
        if u==uid: continue
        r=tg_send(u,text)
        if r.get("ok"): sent+=1
        else: fail+=1
        time.sleep(0.05)
    tg_sticker(uid,STK_ROCKET)
    tg_send(uid,"✅ <b>Broadcast terminé !</b>\n\n✉️ Envoyés: <b>{}</b>  ·  ❌ Échoués: <b>{}</b>".format(sent,fail),kb=kb_admin_back())

def handle_bcast_start(uid, target):
    _bcast_pending[uid]={"target":target,"step":"waiting"}
    nb=len(pro_users())+len(free_users()) if target=="ALL" else len(pro_users())
    tg_send(uid,"✉️ <b>BROADCAST → {}</b>\n\nEnvoie le message à diffuser à <b>{} membres</b>.\n\n💡 HTML supporté : <b>gras</b>, <i>italique</i>\n\n/annuler pour annuler.".format(target,nb),kb={"inline_keyboard":[[{"text":"❌ Annuler","callback_data":"adm_panel"}]]})

def handle_bcast_msg(uid, text):
    if uid not in _bcast_pending: return False
    state=_bcast_pending.pop(uid); target=state["target"]
    users=list(set(pro_users()+free_users())) if target=="ALL" else pro_users()
    tg_send(uid,"📤 Envoi en cours à <b>{}</b> membres...".format(len(users)))
    sent=fail=0
    for u in users:
        if u==uid: continue
        r=tg_send(u,"📢 <b>Message de l\'équipe AlphaBot :</b>\n\n"+text+"\n\n— <i>@leaderOdg · AlphaBot PRO</i>")
        if r.get("ok"): sent+=1
        else: fail+=1
        time.sleep(0.05)
    tg_sticker(uid,STK_ROCKET)
    tg_send(uid,"✅ <b>Broadcast terminé !</b>\n✉️ Envoyés: <b>{}</b>  ·  ❌ Échoués: <b>{}</b>".format(sent,fail),kb=kb_admin_back())
    return True


_test_mode_full = ""  # admin test mode FREE/PRO


# ══════════════════════════════════════════════════════
#  📊 MOTEUR BACKTEST — Rejoue les scans sur historique
# ══════════════════════════════════════════════════════
# Principe :
#   1. Charger N bougies H (ex: 200 bougies 1h = ~8 jours)
#   2. Glisser une fenêtre de lecture : bougies[0..i] → signal ?
#   3. Pour chaque signal trouvé → simuler TP/SL sur les bougies suivantes
#   4. Compter vrais TP, vrais SL, expirations
#   5. Envoyer le rapport résumé à l'admin

def backtest_market(m, nb_candles=150, tf="1h", score_min=72):
    """
    Rejoue le scan ICT + liquidité sur les nb_candles dernières bougies.
    Retourne liste de trades simulés avec résultat réel.
    """
    # Charger l'historique complet
    raw = fetch_c(m["sym"], tf, "60d")
    if not raw or len(raw) < nb_candles + 20:
        return []

    candles = raw[-(nb_candles + 20):]   # un peu de marge pour l'analyse
    results  = []
    in_trade = False   # une seule position à la fois par paire

    # Fenêtre glissante : on analyse à chaque bougie passée
    for i in range(40, len(candles) - 5):
        if in_trade:
            continue   # déjà en position → on attend le résultat

        window = candles[:i]   # historique visible jusqu'à la bougie i
        future = candles[i:]   # bougies "futures" pour simuler TP/SL

        # ── Analyser la fenêtre ─────────────────────────────────────
        try:
            b, _, bt = detect_bias(window[-50:] if len(window) >= 50 else window)
            if b == "NEUTRAL":
                continue

            liq = agent_liquidity(window, b)
            if not liq:
                continue   # liquidité obligatoire

            bbs = breakers(window, b)
            if not bbs:
                continue

            sc  = conf_score(window, b)
            fvg_z = fvg(window, b)
            _, cc2 = choch_seq(window[-50:] if len(window) >= 50 else window)
            sh_h  = max(x["h"] for x in window[-50:])
            sl_h  = min(x["l"] for x in window[-50:])
            ote_lo, ote_hi = ote_zone(sh_h, sl_h, b)
            lp    = window[-1]["c"]
            in_ote = bool(ote_lo and ote_hi and ote_lo <= lp <= ote_hi)

            if in_ote:  sc = min(sc + 12, 115)
            if fvg_z:   sc = min(sc + 15, 115)
            if cc2 >= 2: sc = min(sc + 10, 115)
            sc = min(sc + liq["score"], 115)

            if sc < score_min:
                continue

            # ── Calculer entrée / TP / SL ──────────────────────────
            bb   = bbs[0]
            a    = atr(window)
            sp_p = m["pip"] * 1.5   # spread estimé
            eq_h, eq_l = eqh_eql(window)

            if b == "BULLISH":
                sl   = bb["bottom"] - a * 0.15 - sp_p
                risk = lp - sl
                if risk <= 0 or risk > a * 10:
                    continue
                tp = (eq_h * 0.9995) if (eq_h and lp < eq_h < lp + risk * 5) else lp + risk * 2.5
                if (tp - lp) / risk < 2.0:
                    continue
                side = "BUY"
            else:
                sl   = bb["top"] + a * 0.15 + sp_p
                risk = sl - lp
                if risk <= 0 or risk > a * 10:
                    continue
                tp = (eq_l * 1.0005) if (eq_l and lp - risk * 5 < eq_l < lp) else lp - risk * 2.5
                if (lp - tp) / risk < 2.0:
                    continue
                side = "SELL"

            rr = round(abs(tp - lp) / risk, 1)

        except Exception:
            continue

        # ── Simuler TP/SL sur les bougies futures ──────────────────
        result = "OPEN"; exit_price = None; candles_held = 0
        for fi, fc in enumerate(future[1:30]):   # max 30 bougies pour expirer
            candles_held = fi + 1
            if side == "BUY":
                if fc["h"] >= tp:
                    result = "TP"; exit_price = tp; break
                if fc["l"] <= sl:
                    result = "SL"; exit_price = sl; break
            else:
                if fc["l"] <= tp:
                    result = "TP"; exit_price = tp; break
                if fc["h"] >= sl:
                    result = "SL"; exit_price = sl; break

        if result == "OPEN":
            result = "EXPIRED"; exit_price = future[min(29, len(future)-1)]["c"]

        dp    = 2 if lp > 1000 else (3 if lp > 10 else 5)
        f_rnd = lambda v: round(v, dp)
        gain_pips = abs(tp - lp)  / m["pip"]
        loss_pips = abs(sl - lp)  / m["pip"]

        results.append({
            "pair"    : m["name"],
            "side"    : side,
            "entry"   : f_rnd(lp),
            "tp"      : f_rnd(tp),
            "sl"      : f_rnd(sl),
            "rr"      : rr,
            "score"   : sc,
            "result"  : result,
            "exit"    : f_rnd(exit_price) if exit_price else None,
            "held"    : candles_held,
            "g001"    : round(gain_pips * 0.01, 2),
            "l001"    : round(loss_pips * 0.01, 2),
            "g1"      : round(gain_pips, 2),
            "l1"      : round(loss_pips, 2),
            "liq_lbl" : liq.get("label","?"),
            "bias"    : b,
            "tf"      : tf,
            "candle_i": i,
        })
        in_trade = True   # une position à la fois
        # Avancer après la clôture du trade
        if result != "EXPIRED":
            i += candles_held   # sauter les bougies déjà utilisées

    return results


def run_backtest(uid, nb_candles=150, tf="1h", score_min=72):
    """
    Lance le backtest sur tous les marchés actifs et envoie le rapport.
    Appelé en thread depuis /backtest admin.
    """
    tg_send(uid,
        "⏳ <b>BACKTEST EN COURS...</b>\n\n"
        "📊 Paramètres :\n"
        f"  · Timeframe : <b>{tf}</b>\n"
        f"  · Bougies   : <b>{nb_candles}</b>\n"
        f"  · Score min : <b>{score_min}</b>\n\n"
        "Analyse de {} marchés...".format(len(MARKETS)))

    all_trades = []
    for m in MARKETS:
        try:
            trades = backtest_market(m, nb_candles=nb_candles,
                                     tf=tf, score_min=score_min)
            all_trades.extend(trades)
        except Exception as e:
            log("WARN", f"backtest {m['name']}: {e}")

    if not all_trades:
        tg_send(uid,
            "🔍 <b>BACKTEST — Aucun signal détecté</b>\n\n"
            "Essaie avec un score min plus bas : /backtest 72\n"
            "Ou un TF différent : /backtest 72 30m")
        return

    # ── Calculer les stats globales ─────────────────────────────────
    tp_list  = [t for t in all_trades if t["result"] == "TP"]
    sl_list  = [t for t in all_trades if t["result"] == "SL"]
    exp_list = [t for t in all_trades if t["result"] == "EXPIRED"]
    total    = len(all_trades)
    wins     = len(tp_list)
    losses   = len(sl_list)
    wr       = round(wins / total * 100) if total > 0 else 0
    net_r    = round(wins * 2.5 - losses * 1.0, 2)  # RR moyen 2.5
    g1_total = round(sum(t["g1"] for t in tp_list)
                   - sum(t["l1"] for t in sl_list), 2)
    avg_rr   = round(sum(t["rr"] for t in all_trades) / total, 1) if total else 0

    sep = "═" * 24
    perf = "🔥🔥" if wr >= 70 else ("🔥" if wr >= 55 else ("📊" if wr >= 45 else "⚠️"))

    lines = [
        f"📊 <b>RAPPORT BACKTEST</b> {perf}",
        sep,
        f"⏱ TF : <b>{tf}</b>  ·  Bougies : <b>{nb_candles}</b>  ·  Score min : <b>{score_min}</b>",
        "",
        f"📡 Signaux détectés : <b>{total}</b>",
        f"✅ TP : <b>{wins}</b>  ({wr}% Win Rate)",
        f"❌ SL : <b>{losses}</b>",
        f"⏳ Expirés (30 bougies) : <b>{len(exp_list)}</b>",
        "",
        f"📐 RR moyen : <b>1:{avg_rr}</b>",
        f"💰 Résultat net lot 1.00 : <b>{'+'if g1_total>=0 else ''}{g1_total}$</b>",
        f"📈 R total : <b>{'+'if net_r>=0 else ''}{net_r}R</b>",
        sep,
        "",
        "📋 <b>DÉTAIL PAR PAIRE</b>",
        "",
    ]

    # ── Grouper par paire ───────────────────────────────────────────
    pairs_seen = {}
    for t in all_trades:
        p = t["pair"]
        pairs_seen.setdefault(p, {"tp":0,"sl":0,"exp":0,"g1":0})
        if t["result"] == "TP":
            pairs_seen[p]["tp"] += 1
            pairs_seen[p]["g1"] += t["g1"]
        elif t["result"] == "SL":
            pairs_seen[p]["sl"] += 1
            pairs_seen[p]["g1"] -= t["l1"]
        else:
            pairs_seen[p]["exp"] += 1

    for pair, st in sorted(pairs_seen.items(),
                           key=lambda x: -(x[1]["tp"])):
        tot_p = st["tp"] + st["sl"] + st["exp"]
        wr_p  = round(st["tp"] / tot_p * 100) if tot_p else 0
        g     = round(st["g1"], 2)
        lines.append(
            f"  <b>{pair}</b> — {tot_p} sig  "
            f"{st['tp']}✅ {st['sl']}❌  "
            f"{wr_p}% WR  "
            f"{'+'if g>=0 else ''}{g}$")

    lines += [
        "",
        sep,
        "📝 <b>10 DERNIERS TRADES</b>",
        "",
    ]

    for t in all_trades[-10:]:
        icon = "✅" if t["result"] == "TP" else ("❌" if t["result"] == "SL" else "⏳")
        d    = "⬆️" if t["side"] == "BUY" else "⬇️"
        g    = f"+{t['g1']}$" if t["result"] == "TP" else (
               f"-{t['l1']}$" if t["result"] == "SL" else "exp.")
        lines.append(
            f"{icon} <b>{t['pair']}</b> {d}  "
            f"E:<code>{t['entry']}</code> "
            f"TP:<code>{t['tp']}</code> "
            f"SL:<code>{t['sl']}</code>  "
            f"RR 1:{t['rr']}  {g}  "
            f"💧{t['liq_lbl']}")

    lines += [
        "",
        sep,
        "⚠️ Backtest = données historiques. Résultats passés ≠ futurs.",
        "🤖 AlphaBot PRO  ·  @leaderodg_bot",
    ]

    msg = "\n".join(lines)
    # Telegram limite à 4096 chars
    if len(msg) > 4000:
        msg = msg[:3900] + "\n\n...(tronqué — trop de signaux)"

    tg_send(uid, msg, kb=kb_admin_back())
    log("AI", clr(f"Backtest terminé — {total} trades, WR {wr}%", "g"))

def dispatch(uid, uname, txt):
    """Dispatcher principal — gère boutons clavier ET commandes slash."""
    t = txt.strip()
    db_register(uid, uname)
    db_run("UPDATE users SET last_seen=? WHERE user_id=?",
           (datetime.now().isoformat(), uid))

    # ── 1. BOUTONS DU CLAVIER PHYSIQUE (texte exact) ─────────────
    if t == "📡 Mes Signaux":
        threading.Thread(target=send_signals_info, args=(uid,), daemon=True).start(); return
    if t == "📊 Mon Compte":
        forced = _test_mode if uid == ADMIN_ID and _test_mode else None
        threading.Thread(target=send_account, args=(uid, uname, forced), daemon=True).start(); return
    if t == "💰 Devenir PRO":
        threading.Thread(target=send_pro_page, args=(uid,), daemon=True).start(); return
    if t == "🤝 Parrainage":
        threading.Thread(target=send_affilie, args=(uid, uname), daemon=True).start(); return
    if t == "💸 Mes Gains":
        threading.Thread(target=send_mes_gains, args=(uid,), daemon=True).start(); return
    if t in ("📖 Guide ICT", "📖 Guide AlphaBot"):
        threading.Thread(target=send_guide, args=(uid,), daemon=True).start(); return
    if t == "📈 Rapports":
        threading.Thread(target=send_rapports, args=(uid,), daemon=True).start(); return
    if t == "🏦 Broker Exness":
        threading.Thread(target=send_broker, args=(uid,), daemon=True).start(); return
    # Anciens boutons (rétrocompatibilité)
    if t in ("📩 Mes Signaux", "🛰 Mes Signaux"):
        threading.Thread(target=send_signals_info, args=(uid,), daemon=True).start(); return
    if t in ("💎 Devenir PRO", "💠 Devenir PRO", "💰 Paiement USDT"):
        threading.Thread(target=send_pro_page, args=(uid,), daemon=True).start(); return
    if t in ("📊 Mon Tableau de Bord", "📊 Mon compte"):
        threading.Thread(target=send_account, args=(uid, uname), daemon=True).start(); return
    if t in ("💰 Mes Gains", "📈 Mes Gains"):
        threading.Thread(target=send_mes_gains, args=(uid,), daemon=True).start(); return
    if t in ("🤝 Parrainage", "🤝 Devenir Affilié"):
        threading.Thread(target=send_affilie, args=(uid, uname), daemon=True).start(); return

    # ── 2. BROADCAST ADMIN (texte libre en attente) ──────────────
    if uid == ADMIN_ID and t and not t.startswith("/"):
        if handle_bcast_msg(uid, t):
            return  # message traité comme broadcast

    # ── 3. COMMANDES SLASH ────────────────────────────────────────
    parts = t.split()
    cmd   = parts[0].lower().lstrip("/").split("@")[0] if parts else ""
    arg   = " ".join(parts[1:]) if len(parts) > 1 else ""

    if cmd in ("start", "menu", "aide", "help"):
        ref = int(arg) if arg.isdigit() else 0
        db_register(uid, uname, ref, tg_fn=tg_send)
        send_welcome(uid, uname); return

    if cmd == "admin":
        threading.Thread(target=send_admin_full, args=(uid,), daemon=True).start(); return
    if cmd in ("pay",):
        threading.Thread(target=send_pay_plan, args=(uid,), daemon=True).start(); return
    if cmd == "pro":
        threading.Thread(target=send_pro_page, args=(uid,), daemon=True).start(); return
    if cmd in ("ref", "parrainage"):
        threading.Thread(target=send_affilie, args=(uid, uname), daemon=True).start(); return
    if cmd == "broker":
        threading.Thread(target=send_broker, args=(uid,), daemon=True).start(); return
    if cmd in ("guide", "pdf"):
        threading.Thread(target=send_guide, args=(uid,), daemon=True).start(); return
    if cmd in ("monstatus", "status", "compte", "account"):
        threading.Thread(target=send_account, args=(uid, uname), daemon=True).start(); return
    if cmd in ("rapports", "report", "perf"):
        threading.Thread(target=send_rapports, args=(uid,), daemon=True).start(); return
    if cmd == "challenge":
        threading.Thread(target=send_challenge, args=(uid,), daemon=True).start(); return
    if cmd == "support":
        tg_send(uid, "📩 <b>Support</b>\nID : <code>{}</code>\n👉 @leaderOdg".format(uid)); return
    if cmd == "marches":
        threading.Thread(target=handle_marches_full, args=(uid,), daemon=True).start(); return

    # ── TX Hash ────────────────────────────────────────────────────
    if cmd == "txhash" and arg:
        threading.Thread(target=lambda: handle_proof(uid, uname, tx=arg), daemon=True).start(); return

    # ── Commandes admin ────────────────────────────────────────────
    if uid == ADMIN_ID:
        if cmd == "scan":
            tg_send(uid, "📡 Scan lancé...")
            threading.Thread(target=scan_and_send, daemon=True).start(); return
        if cmd in ("backtest", "bt"):
            # Usage : /backtest [score_min] [tf] [nb_candles]
            # Ex: /backtest 72 1h 150  ou  /backtest 80 30m 200
            bt_args  = arg.split() if arg else []
            bt_score = int(bt_args[0]) if len(bt_args) > 0 and bt_args[0].isdigit() else 72
            bt_tf    = bt_args[1] if len(bt_args) > 1 else "1h"
            bt_nb    = int(bt_args[2]) if len(bt_args) > 2 and bt_args[2].isdigit() else 150
            # Valider le TF
            if bt_tf not in ("5m","15m","30m","1h","4h"):
                bt_tf = "1h"
            threading.Thread(target=run_backtest,
                             args=(uid, bt_nb, bt_tf, bt_score),
                             daemon=True).start(); return
        if cmd == "annuler":
            _bcast_pending.pop(uid, None)
            tg_send(uid, "❌ Broadcast annulé.", kb=kb_reply()); return
        if cmd == "debug":
            if not _last_results: tg_send(uid, "Aucun scan encore."); return
            lines = ["🔍 <b>DEBUG DERNIER SCAN</b>", ""]
            for r in _last_results:
                tag  = " ⚡" if r.get("improv") else ""
                icon = "🟢" if r["found"] else "⚪"
                lines.append("{} <b>{}</b>{}  {}".format(
                    icon, r["name"], tag,
                    "Signal ✓" if r["found"] else r.get("reason", "?")))
            msg = "\n".join(lines)
            if len(msg) > 4000: msg = msg[:3900] + "\n...(tronqué)"
            tg_send(uid, msg); return
        if cmd == "activate":
            handle_activate(uid, arg); return
        if cmd == "degrade":
            handle_degrade(uid, arg); return
        if cmd == "testfree":
            handle_testfree(uid); return
        if cmd == "testpro":
            handle_testpro(uid); return
        if cmd in ("stats",):
            threading.Thread(target=send_admin_stats_full, args=(uid,), daemon=True).start(); return
        if cmd == "membres":
            pg = int(arg) if arg.isdigit() else 1
            threading.Thread(target=handle_membres, args=(uid, pg), daemon=True).start(); return
        if cmd == "resetcount":
            handle_resetcount(uid, arg); return
        if cmd == "stop":
            tg_send(uid, "🛑 Bot arrêté.")
            raise KeyboardInterrupt

    # ── Fallback : afficher le menu ───────────────────────────────
    send_welcome(uid, uname)


def dispatch_cb(cb):
    """Gère tous les boutons inline Telegram."""
    uid   = cb["from"]["id"]
    uname = cb.get("from", {}).get("username", "")
    data  = cb.get("data", "")
    # Répondre immédiatement à Telegram (évite le spinner bloqué)
    try: tg_req("answerCallbackQuery", {"callback_query_id": cb["id"]})
    except: pass
    db_register(uid, uname)

    # ── Navigation principale ─────────────────────────────────
    if   data == "start":   send_welcome(uid, uname)
    elif data == "signals": threading.Thread(target=send_signals_info, args=(uid,), daemon=True).start()
    elif data == "account": threading.Thread(target=send_account, args=(uid, uname), daemon=True).start()
    elif data == "rapports":threading.Thread(target=send_rapports, args=(uid,), daemon=True).start()
    elif data == "challenge":send_challenge(uid)
    elif data == "pro":     threading.Thread(target=send_pro_page, args=(uid,), daemon=True).start()
    elif data == "pay":     send_pay_plan(uid)
    elif data == "ref":     threading.Thread(target=send_affilie, args=(uid, uname), daemon=True).start()
    elif data == "broker":  send_broker(uid)
    elif data == "guide":   threading.Thread(target=send_guide, args=(uid,), daemon=True).start()

    # ── Paiement ─────────────────────────────────────────────
    elif data == "pay_submitted":
        handle_pay_submitted(uid, uname)
    elif data.startswith("pay_submitted_"):
        handle_pay_submitted(uid, uname, plan_key=data.replace("pay_submitted_",""))
    elif data.startswith("pay_plan_"):
        send_pay_plan(uid, plan_key=data.replace("pay_plan_",""))
    elif data == "pay_confirm":
        threading.Thread(target=handle_pay_confirm, args=(uid, uname), daemon=True).start()
    elif data == "pay_cancel":
        _pay_state.pop(uid, None)
        tg_send(uid, "❌ Paiement annulé.", kb=kb_back())

    # ── Parrainage ────────────────────────────────────────────
    elif data == "ref_stats":
        refs = get_refs(uid)
        link = "https://t.me/{}?start={}".format(BOT_USER, uid)
        done = min(refs, REF_TARGET)
        bar  = "█"*int(done/REF_TARGET*10) + "░"*(10-int(done/REF_TARGET*10))
        tg_send(uid,
            "🤝 <b>MES FILLEULS</b>\n" + "═"*22 + "\n\n"
            "🔗 <code>{}</code>\n\n"
            "<b>{}/{}</b>  ({}%)\n[{}]\n\n"
            "🏆 {} filleuls = {} MOIS PRO".format(
                link, done, REF_TARGET, int(done/REF_TARGET*100), bar,
                REF_TARGET, REF_MONTHS),
            kb=kb_back())

    # ── Admin ─────────────────────────────────────────────────
    elif data == "adm_panel" and uid == ADMIN_ID:
        threading.Thread(target=send_admin_full, args=(uid,), daemon=True).start()
    elif data == "adm_stats" and uid == ADMIN_ID:
        threading.Thread(target=send_admin_stats_full, args=(uid,), daemon=True).start()
    elif data == "adm_pays" and uid == ADMIN_ID:
        threading.Thread(target=send_admin_payments_full, args=(uid,), daemon=True).start()
    elif data == "adm_scan" and uid == ADMIN_ID:
        tg_send(uid, "📡 Scan forcé...", kb=kb_admin_back())
        threading.Thread(target=scan_and_send, daemon=True).start()
    elif data == "adm_rapports" and uid == ADMIN_ID:
        threading.Thread(target=send_rapports, args=(uid,), daemon=True).start()
    elif data == "adm_reco" and uid == ADMIN_ID:
        threading.Thread(target=send_admin_reco, args=(uid,), daemon=True).start()
    elif data == "adm_debug" and uid == ADMIN_ID:
        if not _last_results:
            tg_send(uid, "Aucun scan encore."); return
        lines = ["🔍 <b>DEBUG DERNIER SCAN</b>", ""]
        found = [r for r in _last_results if r.get("found")]
        nf    = [r for r in _last_results if not r.get("found")]
        if found:
            lines.append("✅ <b>SIGNAUX ({}):</b>".format(len(found)))
            for r in found:
                s = r["signal"]
                lines.append("  🟢 {} {}  RR 1:{}  Score {}{}".format(
                    r["name"], s["side"], s["rr"], s["score"],
                    " ⚡" if r.get("improv") else ""))
        reasons = {}
        for r in nf: reasons.setdefault(r.get("reason","?"), []).append(r["name"])
        lines.append("\n⚪ <b>REJETÉS ({}):</b>".format(len(nf)))
        for reason, names in sorted(reasons.items(), key=lambda x: -len(x[1])):
            lines.append("  <b>{}</b> ({}): {}".format(reason, len(names), ", ".join(names[:5])))
        tg_send(uid, "\n".join(lines))
    elif data == "adm_marches" and uid == ADMIN_ID:
        threading.Thread(target=handle_marches_full, args=(uid,), daemon=True).start()
    elif data == "adm_promo_list" and uid == ADMIN_ID:
        threading.Thread(target=send_promo_list, args=(uid,), daemon=True).start()
    elif data.startswith("adm_promo_send_") and uid == ADMIN_ID:
        pid = data.replace("adm_promo_send_", "")
        threading.Thread(target=broadcast_promo, args=(uid, pid), daemon=True).start()
    elif data.startswith("adm_promo_") and uid == ADMIN_ID:
        pid = data.replace("adm_promo_", "")
        threading.Thread(target=send_promo_preview, args=(uid, pid), daemon=True).start()
    elif data == "adm_bcast_all" and uid == ADMIN_ID:
        handle_bcast_start(uid, "ALL")
    elif data == "adm_bcast_pro" and uid == ADMIN_ID:
        handle_bcast_start(uid, "PRO")
    elif data.startswith("adm_membres_") and uid == ADMIN_ID:
        pg = int(data.split("_")[-1])
        threading.Thread(target=handle_membres, args=(uid, pg), daemon=True).start()

    # ── Toggle PRO/FREE admin ─────────────────────────────────
    elif data.startswith("adm_pro_") and uid == ADMIN_ID:
        try:
            t_uid = int(data.split("_")[2])
            plan, _, _ = get_pro_info(t_uid)
            if plan != "PRO":
                db_activate_pro(t_uid, "ADMIN", days=None)
                tg_send(t_uid,
                    "🎉 <b>PRO activé !</b>\n\n"
                    "✅ Max {} signaux/jour\n"
                    "⚡ Mode Improvisation inclus\n"
                    "🚀 Bienvenue dans AlphaBot PRO !".format(PRO_LIMIT))
                tg_send(uid, "✅ PRO activé : <code>{}</code>".format(t_uid),
                    kb={"inline_keyboard": [[
                        {"text": "🔒 Désactiver PRO",
                         "callback_data": "adm_ban_{}".format(t_uid)}]]})
            else:
                tg_send(uid, "ℹ️ Déjà PRO : <code>{}</code>".format(t_uid))
        except Exception as ex:
            tg_send(uid, "❌ {}".format(ex))

    elif data.startswith("adm_ban_") and uid == ADMIN_ID:
        try:
            t_uid = int(data.split("_")[2])
            plan, _, _ = get_pro_info(t_uid)
            if plan == "PRO":
                db_downgrade_pro(t_uid)
                tg_send(t_uid,
                    "🔒 <b>PRO désactivé</b>\n"
                    "Plan : FREE ({} signaux/jour)\n"
                    "/pay pour revenir PRO.".format(FREE_LIMIT))
                tg_send(uid, "✅ FREE : <code>{}</code>".format(t_uid),
                    kb={"inline_keyboard": [[
                        {"text": "🔄 Réactiver PRO",
                         "callback_data": "adm_pro_{}".format(t_uid)}]]})
            else:
                # Refuser paiement
                db_run("UPDATE payments SET status='REJECTED' WHERE user_id=? AND status='PENDING'", (t_uid,))
                tg_send(uid, "❌ Paiement refusé : <code>{}</code>".format(t_uid))
        except Exception as ex:
            tg_send(uid, "❌ {}".format(ex))

    # ── Fallback ──────────────────────────────────────────────
    else:
        send_welcome(uid, uname)


def track_user(uid, uname, first_name=""):
    """
    Appelé à chaque interaction — enregistre l'utilisateur s'il est nouveau
    et notifie l'admin à la première apparition.
    Utilisé pour NE JAMAIS perdre un utilisateur même si la DB a été resetée.
    """
    try:
        # Vérifier si déjà connu AVANT db_register
        existing = db_one("SELECT user_id FROM users WHERE user_id=?", (uid,))
        is_new = existing is None
        # Enregistrer (INSERT OR IGNORE + update last_seen)
        db_register(uid, uname)
        db_run("UPDATE users SET last_seen=? WHERE user_id=?",
               (datetime.now().isoformat(), uid))
        if uname:
            db_run("UPDATE users SET username=? WHERE user_id=?", (uname, uid))
        # Notification admin uniquement pour les nouveaux
        if is_new and uid != ADMIN_ID:
            total, pro, sigs, _, _ = global_stats()
            name_disp = "@" + uname if uname else (first_name or "Inconnu")
            msg_admin = (
                "🆕 <b>NOUVEL UTILISATEUR</b>\n"
                "━━━━━━━━━━━━━━━━━━━━\n"
                "🆔 ID       : <code>{}</code>\n"
                "👤 Username : {}\n"
                "📋 Prenom   : {}\n"
                "━━━━━━━━━━━━━━━━━━━━\n"
                "👥 Total DB : <b>{}</b>  (PRO: <b>{}</b>)\n"
                "📡 Signaux  : {}"
            ).format(uid, "@" + uname if uname else "s/u",
                     first_name or "s/p", total, pro, sigs)
            tg_send(ADMIN_ID, msg_admin,
                kb={"inline_keyboard": [[
                    {"text": "Activer PRO", "callback_data": "adm_pro_{}".format(uid)},
                    {"text": "Contacter",   "url": "tg://user?id={}".format(uid)},
                ]]})
            log("INFO", clr("Nouveau user: {} ID:{} — notif admin OK".format(
                name_disp, uid), "g"))
    except Exception as e:
        log("WARN", "track_user {}: {}".format(uid, e))


def handle_new_group_member(uid, uname, first_name):
    """
    Nouveau membre rejoint le groupe :
    1. Enregistrement en base (via track_user)
    2. Message de bienvenue + essai PRO
    3. Invitation groupe VIP
    4. Notification admin (via track_user)
    """
    try:
        track_user(uid, uname, first_name)  # enregistrement + notif admin
        name = "@" + uname if uname else first_name or "Trader"

        # ── Message de bienvenue ────────────────────────────────
        tg_send(uid,
            "👋 <b>Bienvenue {} !</b>\n\n"
            "🤖 <b>AlphaBot PRO</b> — Signaux trading automatiques\n\n"
            "✅ {} signaux/jour GRATUITS\n"
            "📊 Forex · Or · BTC · Indices · Pétrole\n"
            "🎯 Entrée + TP + SL automatiques\n"
            "⚡ Mode Improvisation actif\n\n"
            "🎁 <b>Essai PRO {} jours offert !</b>\n\n"
            "👉 Clique /start pour commencer".format(
                name, FREE_LIMIT, TRIAL_DAYS),
            kb={{"inline_keyboard": [[
                {{"text": "🚀 Démarrer", "callback_data": "start"}},
                {{"text": "💎 Voir PRO",  "callback_data": "pro"}},
            ]]}})

        # ── Recommandation groupe VIP ───────────────────────────
        time.sleep(2)
        try:
            vip_link = "https://t.me/+{}".format(
                VIP_CH.lstrip("-100") if VIP_CH.startswith("-100") else VIP_CH.lstrip("-"))
        except:
            vip_link = "https://t.me/leaderOdg"
        tg_send(uid,
            "🏆 <b>GROUPE VIP AlphaBot</b>\n\n"
            "Rejoins notre groupe VIP pour :\n"
            "✅ Signaux en temps réel\n"
            "✅ Analyses de marché en direct\n"
            "✅ Discussion avec @leaderOdg\n\n"
            "❓ Questions sur la méthode ICT/SMC ?\n"
            "👉 Contacte directement @leaderOdg\n\n"
            "📩 Demande d'accès au groupe VIP :",
            kb={{"inline_keyboard": [[
                {{"text": "👑 Rejoindre le groupe VIP",
                  "url": "https://t.me/leaderOdg"}},
            ]]}})

        # ── Notification admin ──────────────────────────────────
        total, pro, _, _, _ = global_stats()
        tg_send(ADMIN_ID,
            "👤 <b>NOUVEAU MEMBRE</b>\n\n"
            "🆔 ID     : <code>{}</code>\n"
            "👤 Username: {}\n"
            "📋 Prénom  : {}\n\n"
            "👥 Total membres : <b>{}</b>  (PRO: {})\n\n"
            "Actions rapides ↓".format(
                uid,
                "@" + uname if uname else "—",
                first_name or "—",
                total, pro),
            kb={{"inline_keyboard": [[
                {{"text": "💠 Activer PRO",
                  "callback_data": "adm_pro_{}".format(uid)}},
                {{"text": "💬 Contacter",
                  "url": "tg://user?id={}".format(uid)}},
            ]]}})

        log("INFO", clr("Nouveau membre: @{} ID:{} — notif admin envoyée".format(
            uname or "?", uid), "g"))
    except Exception as e:
        log("WARN", "handle_new_group_member: {}".format(e))

def process_update(upd):
    try:
        # ── Nouveau membre dans le groupe ────────────────────────
        if "chat_member" in upd:
            cm = upd["chat_member"]
            new_m = cm.get("new_chat_member", {})
            status = new_m.get("status", "")
            user = new_m.get("user", {})
            if status == "member" and not user.get("is_bot"):
                uid   = user["id"]
                uname = user.get("username", "")
                fname = user.get("first_name", "")
                threading.Thread(target=handle_new_group_member,
                    args=(uid, uname, fname), daemon=True).start()
            return

        # ── Nouveau membre via message system (ancienne API) ─────
        if "message" in upd:
            msg = upd["message"]
            new_members = msg.get("new_chat_members", [])
            if new_members:
                for user in new_members:
                    if not user.get("is_bot"):
                        uid   = user["id"]
                        uname = user.get("username", "")
                        fname = user.get("first_name", "")
                        threading.Thread(target=handle_new_group_member,
                            args=(uid, uname, fname), daemon=True).start()
                return

            uid   = msg["from"]["id"]
            uname = msg.get("from", {}).get("username", "")
            fname = msg.get("from", {}).get("first_name", "")
            txt   = msg.get("text", "")
            # ── Tracker TOUT utilisateur qui envoie un message ───
            threading.Thread(target=track_user, args=(uid, uname, fname), daemon=True).start()
            if txt:
                log("INFO", clr("MSG @{} ({}): {}".format(uname or uid, uid, txt[:40]), "d"))
                def _h(uid=uid, uname=uname, txt=txt):
                    if uid in _pay_state and _pay_state[uid].get("step") == "waiting":
                        cleaned = txt.strip()
                        if len(cleaned) >= 20 and not cleaned.startswith("/"):
                            handle_proof(uid, uname, tx=cleaned)
                        else:
                            dispatch(uid, uname, txt)
                    else:
                        dispatch(uid, uname, txt)
                threading.Thread(target=_h, daemon=True).start()
        elif "callback_query" in upd:
            cb = upd["callback_query"]
            cb_uid   = cb.get("from", {}).get("id")
            cb_uname = cb.get("from", {}).get("username", "")
            cb_fname = cb.get("from", {}).get("first_name", "")
            if cb_uid:
                # Tracker aussi les callbacks (clics sur boutons)
                threading.Thread(target=track_user,
                                 args=(cb_uid, cb_uname, cb_fname), daemon=True).start()
            threading.Thread(target=dispatch_cb, args=(cb,), daemon=True).start()
    except Exception as e: log("ERR","process_update: {}".format(e))

# ══════════════════════════════════════════════════════
#  DÉMARRAGE & MAIN
# ══════════════════════════════════════════════════════
def startup():
    print("\n"+clr("  ╔══════════════════════════════════════════════════╗","b","c"))
    print(clr("  ║  AlphaBot PRO v10 — IA Adaptative · Improvisation  ║","b","c"))
    print(clr("  ║  Forex·Métaux·Crypto·Indices · ICT/SMC · ⚡Mode   ║","b","c"))
    print(clr("  ╚══════════════════════════════════════════════════╝","b","c")+"\n")
    db_init()
    db_register(ADMIN_ID,"leaderOdg"); db_pro(ADMIN_ID,"ADMIN_AUTO",days=None)
    log("INFO",clr("Init données Binance...","c"))
    threading.Thread(target=refresh_exch,daemon=True).start()
    threading.Thread(target=refresh_ai,daemon=True).start()
    sn,sm,sl_l,wknd=get_session(); ch=chal_get()
    # Message de démarrage en arrière-plan — ne bloque pas le serveur HTTP
    def _notify():
        try:
            tg_send(ADMIN_ID,
                "🤖 <b>AlphaBot PRO v10 — DÉMARRÉ !</b>\n\n"
                "⚡ Mode Improvisation actif\n"
                "🕐 {}  🎯 Score min : <b>{}</b>\n"
                "{}\n"
                "🌍 Régime IA : <b>{}</b>\n"
                "🏆 Challenge : <b>{:.4f}$</b> → {:.0f}$\n"
                "📡 FREE {}/j  ·  PRO {}/j\n\n"
                "✅ Bot actif — répond aux commandes\n"
                "🛠 /admin pour le panel".format(
                    sl_l, sm,
                    "🌍 <b>Week-end : crypto uniquement !</b>" if wknd else "📈 Session : {}".format(sl_l),
                    AI_REG.get("regime","Init"),
                    ch["balance"], ch["start_bal"]*100,
                    FREE_LIMIT, PRO_LIMIT),
                kb=kb_reply())   # ← envoie le clavier au démarrage
        except Exception as e:
            log("WARN", "notify startup: {}".format(e))
    threading.Thread(target=_notify, daemon=True).start()
    log("INFO", clr("AlphaBot v10 actif", "b", "g")); return True

def make_wh():
    class WH(BaseHTTPRequestHandler):
        def do_POST(self):
            try:
                length = int(self.headers.get("Content-Length", 0))
                body   = self.rfile.read(length)
                # Répondre immédiatement 200 à Telegram
                self.send_response(200); self.end_headers(); self.wfile.write(b"OK")
                if length > 0:
                    upd = json.loads(body.decode("utf-8"))
                    threading.Thread(target=process_update, args=(upd,), daemon=True).start()
            except Exception as ex:
                log("ERR", "WebhookHandler: {}".format(ex))
                try: self.send_response(200); self.end_headers()
                except: pass
        def do_GET(self):
            path = self.path.split("?")[0]
            ch   = chal_get(); reg = AI_REG
            if path == "/health":
                # Endpoint dédié au keepalive — réponse JSON légère
                body = '{{"status":"ok","balance":{:.4f},"regime":"{}","cycles":{}}}'.format(
                    ch["balance"], reg.get("regime","?"), _cycles_no_signal).encode()
                self.send_response(200)
                self.send_header("Content-Type","application/json")
                self.end_headers(); self.wfile.write(body)
            else:
                self.send_response(200); self.end_headers()
                self.wfile.write(
                    "AlphaBot v10 OK | {:.4f}$ | {} | cycles: {}".format(
                        ch["balance"], reg.get("regime","?"), _cycles_no_signal).encode())
        def log_message(self, *a): pass
    return WH

def main():
    port = int(os.environ.get("PORT", 10000))
    render = os.environ.get("RENDER_EXTERNAL_URL", "")
    if render:
        # ── ÉTAPE 1 : DB init synchrone (OBLIGATOIRE avant tout) ─
        db_init()
        db_register(ADMIN_ID, "leaderOdg")
        db_pro(ADMIN_ID, "ADMIN_AUTO", days=None)
        log("INFO", clr("DB OK", "b", "g"))

        # ── ÉTAPE 2 : Ouvrir le port HTTP (Render détecte ici) ───
        server = HTTPServer(("0.0.0.0", port), make_wh())
        log("INFO", clr("Port {} ouvert — Render OK".format(port), "b", "g"))

        # ── ÉTAPE 3 : Telegram + IA en arrière-plan ──────────────
        def _init_bg():
            # Binance data
            threading.Thread(target=refresh_exch, daemon=True).start()
            threading.Thread(target=refresh_ai, daemon=True).start()
            # Configurer le webhook
            tg_req("deleteWebhook", {"drop_pending_updates": "true"})
            time.sleep(1)
            r = tg_req("setWebhook", {
                "url": "{}/webhook".format(render.rstrip("/")),
                "drop_pending_updates": "true",
                "max_connections": 10,
                "allowed_updates": '["message","callback_query","chat_member","my_chat_member"]'
            })
            if r.get("ok"): log("INFO", clr("Webhook OK — Bot prêt!", "b", "g"))
            else: log("ERR", clr("Webhook échoué: {}".format(r), "red"))
            # Message de démarrage admin
            sn, sm, sl_l, wknd = get_session()
            ch = chal_get()
            tg_send(ADMIN_ID,
                "🤖 <b>AlphaBot PRO v10 — EN LIGNE !</b>\n\n"
                "✅ DB initialisée\n"
                "✅ Port {} ouvert\n"
                "✅ Webhook configuré\n\n"
                "🕐 Session : <b>{}</b>  Score min : <b>{}</b>\n"
                "🌍 Régime IA : <b>{}</b>\n"
                "🏆 Challenge : <b>{:.4f}$</b>\n\n"
                "📡 FREE {}/j  ·  PRO {}/j\n"
                "🛠 /admin pour le panel".format(
                    port, sl_l, sm,
                    AI_REG.get("regime", "Init"),
                    ch["balance"], FREE_LIMIT, PRO_LIMIT),
                kb=kb_reply())
        threading.Thread(target=_init_bg, daemon=True).start()
        state = {"ls": 0, "la": 0, "lc": 0}
        def _loop():
            while True:
                try:
                    now=time.time()
                    if now-state["ls"]>=SCAN_SEC: state["ls"]=now; threading.Thread(target=scan_and_send,daemon=True).start()
                    if now-state["la"]>=300: state["la"]=now; threading.Thread(target=refresh_ai,daemon=True).start()
                    if now-state["lc"]>=15: state["lc"]=now; threading.Thread(target=ai_check,daemon=True).start()
                except Exception as e: log("ERR","loop: {}".format(e))
                time.sleep(10)
        threading.Thread(target=_loop,daemon=True).start()
        def _ping():
            """Ping toutes les 5 min sur /health pour empêcher Render de dormir."""
            time.sleep(30)  # laisser le serveur démarrer
            while True:
                try:
                    url = render.rstrip("/") + "/health"
                    http_get(url, timeout=10)
                    log("INFO", clr("Keepalive /health OK", "d"))
                except Exception as e:
                    log("WARN", "Keepalive échoué: {}".format(e))
                time.sleep(5 * 60)  # toutes les 5 minutes
        threading.Thread(target=_ping, daemon=True).start()
        try: server.serve_forever()
        except KeyboardInterrupt: tg_send(ADMIN_ID,"🛑 Bot arrêté."); tg_req("deleteWebhook",{})
    else:
        log("INFO",clr("Mode polling local","y"))
        # DB init synchrone
        db_init()
        db_register(ADMIN_ID, "leaderOdg")
        db_pro(ADMIN_ID, "ADMIN_AUTO", days=None)
        threading.Thread(target=refresh_exch, daemon=True).start()
        threading.Thread(target=refresh_ai, daemon=True).start()
        tg_req("deleteWebhook",{"drop_pending_updates":"true"}); time.sleep(1)
        # Purge old updates
        offset=0
        for _ in range(20):
            batch=tg_req("getUpdates",{"offset":offset,"timeout":0,"limit":100}).get("result",[])
            if not batch: break
            offset=batch[-1]["update_id"]+1
        log("INFO", clr("Polling démarré (offset={})".format(offset), "g"))
        ls=la=lc=0
        while True:
            try:
                updates = tg_req("getUpdates", {
                    "offset": offset, "timeout": 10, "limit": 100,
                    "allowed_updates": '["message","callback_query","chat_member"]'
                }).get("result", [])
                for upd in updates:
                    offset=upd["update_id"]+1
                    threading.Thread(target=process_update,args=(upd,),daemon=True).start()
                now=time.time()
                if now-ls>=SCAN_SEC: ls=now; threading.Thread(target=scan_and_send,daemon=True).start()
                if now-la>=300: la=now; threading.Thread(target=refresh_ai,daemon=True).start()
                if now-lc>=15: lc=now; threading.Thread(target=ai_check,daemon=True).start()
            except KeyboardInterrupt: tg_send(ADMIN_ID,"🛑 Bot arrêté."); break
            except Exception as e: log("ERR",str(e)); time.sleep(5)

if __name__=="__main__":
    main()
