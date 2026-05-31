"""
DB KATMANI TESTLERİ — db.py (SQLite ↔ PostgreSQL soyutlaması)
==============================================================
Çalıştır:
  python test_db_layer.py

PostgreSQL çeviri mantığı sunucu OLMADAN test edilir (saf string dönüşümü).
SQLite işlevsel testler yerel bahis_agent.db üzerinde koşar.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

import db

PASS = 0
FAIL = 0


def check(name, cond):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  ✓ {name}")
    else:
        FAIL += 1
        print(f"  ✗ {name}  <-- HATA")


# ============================================================
# 1) PostgreSQL DIALECT ÇEVİRİSİ (sunucu gerekmez)
# ============================================================
print("\n[1] PostgreSQL çeviri mantığı")

s = db._xlate_dialect("INSERT OR IGNORE INTO paper_journal (a, b) VALUES (?, ?)")
check("INSERT OR IGNORE → ON CONFLICT DO NOTHING",
      "INSERT INTO paper_journal" in s and "ON CONFLICT DO NOTHING" in s and "OR IGNORE" not in s)

check("? → %s placeholder",
      db._xlate_params("SELECT * FROM t WHERE a=? AND b=?") == "SELECT * FROM t WHERE a=%s AND b=%s")

check("literal % kaçırma (%% )",
      db._xlate_params("x LIKE '%y%' AND a=?") == "x LIKE '%%y%%' AND a=%s")

check("substr/lower/replace dialect'e dokunmaz",
      db._xlate_dialect("SELECT substr(k,1,10) FROM m").startswith("SELECT substr"))

try:
    db._xlate_dialect("INSERT OR REPLACE INTO t VALUES (?)")
    check("INSERT OR REPLACE → NotImplementedError", False)
except NotImplementedError:
    check("INSERT OR REPLACE → NotImplementedError", True)

# Büyük harfli kolon otomatik tırnaklama (PG lowercase-folding sorunu)
check("closing_X tırnaklanır, closing_1 dokunulmaz",
      db._xlate_dialect("SELECT closing_1, closing_X, closing_2")
      == 'SELECT closing_1, "closing_X", closing_2')
check("signal kolonları (odd_X/odd_open_X/fp_X) tırnaklanır",
      db._xlate_dialect("SELECT m.closing_X, ss.odd_X, ss.odd_open_X, ss.fp_X")
      == 'SELECT m."closing_X", ss."odd_X", ss."odd_open_X", ss."fp_X"')
check("zaten tırnaklı çift-tırnaklanmaz",
      db._xlate_dialect('SELECT "closing_X"').count('"') == 2)
check("UPDATE SET closing_X tırnaklanır",
      '"closing_X"' in db._xlate_dialect("UPDATE matches_v2 SET closing_X=?"))

# 2-arg MAX/MIN → GREATEST/LEAST (PG'de skaler MAX/MIN yok)
check("MAX(a,b) → GREATEST(a,b)",
      "GREATEST(peak_bankroll, current_bankroll)" in
      db._xlate_dialect("SET peak_bankroll = MAX(peak_bankroll, current_bankroll)"))
check("MIN(a,b) → LEAST(a,b)",
      "LEAST(a, b)" in db._xlate_dialect("SELECT MIN(a, b)"))
check("aggregate MAX(col) korunur",
      db._xlate_dialect("SELECT MAX(quality_score) FROM m")
      == "SELECT MAX(quality_score) FROM m")


# ============================================================
# 2) SQLite İŞLEVSEL (yerel DB)
# ============================================================
print("\n[2] SQLite işlevsel (yerel bahis_agent.db)")

check("backend() = sqlite (DATABASE_URL boş)", db.backend() == "sqlite")

c = db.connect()
check("connect() → Conn (is_postgres False)", c.is_postgres is False)

row = c.execute("SELECT coupon_id, status, stake FROM paper_coupons LIMIT 1").fetchone()
if row is not None:
    check("row[0] pozisyonel erişim", row[0] is not None)
    check("row['status'] anahtar erişim", row["status"] is not None)
    check("dict(row) çalışır", isinstance(dict(row), dict))

n = c.execute("SELECT COUNT(*) FROM matches_v2").fetchone()[0]
check("matches_v2 sayısı > 0", n > 0)

t1 = c.execute("SELECT COUNT(*) FROM matches_v2 WHERE league_code=?", ("T1",)).fetchone()[0]
check("parametreli sorgu (? placeholder)", t1 > 0)

df = c.read_df("SELECT COUNT(*) AS n FROM signal_snapshots")
check("read_df → DataFrame", hasattr(df, "columns") and int(df["n"][0]) > 0)

# context manager
with db.connect() as c2:
    m = c2.execute("SELECT COUNT(*) FROM paper_portfolio").fetchone()[0]
check("context manager (with) çalışır", m >= 1)

c.close()


# ============================================================
# SONUÇ
# ============================================================
print(f"\n{'='*48}")
print(f"SONUÇ: {PASS} geçti, {FAIL} başarısız")
print("="*48)
sys.exit(1 if FAIL else 0)
