"""SQLite layer (same idea as attendance_manager.py in the reference repo)."""
import sqlite3, datetime as dt
import pandas as pd

DB = "skillguard.db"

def conn():
    return sqlite3.connect(DB, check_same_thread=False)

def init():
    c = conn()
    c.executescript("""
    CREATE TABLE IF NOT EXISTS trainees(trainee_id TEXT PRIMARY KEY, name TEXT, batch TEXT, centre TEXT);
    CREATE TABLE IF NOT EXISTS attendance(id INTEGER PRIMARY KEY AUTOINCREMENT, trainee_id TEXT,
        date TEXT, time_in TEXT, centre TEXT, UNIQUE(trainee_id, date));
    CREATE TABLE IF NOT EXISTS ai_checks(id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT, centre TEXT,
        scanned INTEGER, detected INTEGER, flag TEXT);
    CREATE TABLE IF NOT EXISTS safety_events(id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT, centre TEXT,
        persons INTEGER, violations INTEGER, compliance REAL, details TEXT);
    CREATE TABLE IF NOT EXISTS infra_checks(id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT, centre TEXT,
        missing TEXT, overdue TEXT);
    """)
    c.commit(); c.close()

def q(sql, args=()):
    c = conn(); df = pd.read_sql_query(sql, c, params=args); c.close(); return df

def run(sql, args=()):
    c = conn(); cur = c.execute(sql, args); c.commit(); c.close(); return cur

def add_trainee(tid, name, batch, centre):
    run("INSERT OR REPLACE INTO trainees VALUES(?,?,?,?)", (tid, name, batch, centre))

def mark(tid, centre):
    """Barcode scan -> attendance. Returns (status, name)."""
    t = q("SELECT name FROM trainees WHERE trainee_id=?", (tid,))
    if t.empty:
        return "UNKNOWN", None
    now = dt.datetime.now()
    try:
        run("INSERT INTO attendance(trainee_id,date,time_in,centre) VALUES(?,?,?,?)",
            (tid, now.strftime("%Y-%m-%d"), now.strftime("%H:%M:%S"), centre))
        return "MARKED", t.name[0]
    except sqlite3.IntegrityError:
        return "DUPLICATE", t.name[0]

def today_marked(centre):
    d = dt.date.today().isoformat()
    return q("""SELECT a.trainee_id, t.name, t.batch, a.time_in FROM attendance a
                JOIN trainees t USING(trainee_id) WHERE a.date=? AND a.centre=?""", (d, centre))

def log(table, **kw):
    kw["ts"] = dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cols = ",".join(kw); ph = ",".join("?" * len(kw))
    run(f"INSERT INTO {table}({cols}) VALUES({ph})", tuple(kw.values()))
