"""
v2 — Sprint 2.1: CLV Pipeline
================================

Her settled maç için CLV (Closing Line Value) hesabı:

  CLV(leg) = (opening_odd / closing_odd) - 1

Pozitif CLV = opening odd kapanış altında düştü -> opening'de değer vardı.
Negatif CLV = opening odd kapanışta yükseldi -> opening'de underpriced'di.

Hesaplanan kolonlar (matches_v2'ye ALTER ile eklenir):
  clv_home, clv_draw, clv_away              (1X2)
  clv_over25, clv_under25                   (totals)
  clv_avg_1x2                               (1X2 ortalama, mutlak değer değil)

Notlar:
  - opening = B365 (Bet365 erken)
  - closing = Pinnacle PSCH/PSCD/PSCA
  - "Aynı oyuncu (book) olmasa da, B365 opening Pinnacle closing'i temsil eder"
    sıklıkla kabul edilen yaklaşım. Gerçek Pinnacle opening için S1 (OddsPortal)
    bekleyecek; v0.1'de bu yeterlidir.
"""
from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

THIS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(THIS_DIR))

import database as db


EXTEND_SCHEMA = """
ALTER TABLE matches_v2 ADD COLUMN clv_home REAL;
ALTER TABLE matches_v2 ADD COLUMN clv_draw REAL;
ALTER TABLE matches_v2 ADD COLUMN clv_away REAL;
ALTER TABLE matches_v2 ADD COLUMN clv_over25 REAL;
ALTER TABLE matches_v2 ADD COLUMN clv_under25 REAL;
ALTER TABLE matches_v2 ADD COLUMN clv_avg_1x2 REAL;
ALTER TABLE matches_v2 ADD COLUMN has_clv INTEGER DEFAULT 0;
"""


def add_columns():
    conn = db.connect()
    try:
        for stmt in EXTEND_SCHEMA.strip().split(";"):
            stmt = stmt.strip()
            if not stmt:
                continue
            try:
                conn.execute(stmt)
            except Exception as e:
                if "duplicate column" not in str(e).lower():
                    print(f"  ALTER err: {e}")
        conn.commit()
        print("[OK] CLV kolonlari eklendi")
    finally:
        conn.close()


def clv_leg(opening: float | None, closing: float | None) -> float | None:
    if opening is None or closing is None or opening <= 1 or closing <= 1:
        return None
    return opening / closing - 1


def compute_all():
    conn = db.connect()
    now = datetime.utcnow().isoformat()
    n_updated = 0
    n_with_clv = 0

    rows = conn.execute("""
        SELECT match_id, opening_1, opening_X, opening_2,
               opening_over25, opening_under25,
               closing_1, closing_X, closing_2,
               closing_over25, closing_under25
        FROM matches_v2
    """).fetchall()
    print(f"İşlenen: {len(rows)} satir")

    for r in rows:
        c_h = clv_leg(r["opening_1"], r["closing_1"])
        c_d = clv_leg(r["opening_X"], r["closing_X"])
        c_a = clv_leg(r["opening_2"], r["closing_2"])
        c_o = clv_leg(r["opening_over25"], r["closing_over25"])
        c_u = clv_leg(r["opening_under25"], r["closing_under25"])

        legs = [x for x in (c_h, c_d, c_a) if x is not None]
        avg_1x2 = sum(legs) / len(legs) if legs else None
        has_clv = 1 if avg_1x2 is not None else 0

        conn.execute("""
            UPDATE matches_v2
            SET clv_home=?, clv_draw=?, clv_away=?,
                clv_over25=?, clv_under25=?, clv_avg_1x2=?,
                has_clv=?, refreshed_at=?
            WHERE match_id=?
        """, (c_h, c_d, c_a, c_o, c_u, avg_1x2, has_clv, now, r["match_id"]))
        n_updated += 1
        if has_clv:
            n_with_clv += 1

    conn.commit()
    conn.close()
    return n_updated, n_with_clv


def clv_report():
    conn = db.connect()
    try:
        print(f"\n=== CLV Coverage per Lig × Sezon ===")
        print(f"{'lig':4s} {'sezon':>8s} {'n':>5s} {'with_clv':>10s} {'avg_home':>9s} {'avg_draw':>9s} {'avg_away':>9s}")
        print("-" * 70)
        rows = conn.execute("""
            SELECT league_code, season,
                   COUNT(*) as n,
                   SUM(has_clv) as has_clv,
                   AVG(clv_home) as avg_h,
                   AVG(clv_draw) as avg_d,
                   AVG(clv_away) as avg_a
            FROM matches_v2
            GROUP BY league_code, season
            ORDER BY league_code, season
        """).fetchall()
        for r in rows:
            ah = f"{r['avg_h']*100:>+6.2f}%" if r["avg_h"] is not None else "    n/a"
            ad = f"{r['avg_d']*100:>+6.2f}%" if r["avg_d"] is not None else "    n/a"
            aa = f"{r['avg_a']*100:>+6.2f}%" if r["avg_a"] is not None else "    n/a"
            print(f"  {r['league_code']:3s} {r['season']:>8s} {r['n']:>5d} "
                  f"{r['has_clv'] or 0:>9d} {ah:>9s} {ad:>9s} {aa:>9s}")

        # Per-lig özet
        print(f"\n=== Per-Lig CLV Özet ===")
        rows = conn.execute("""
            SELECT league_code,
                   COUNT(*) as n,
                   SUM(has_clv) as has_clv,
                   AVG(clv_home) as avg_h,
                   AVG(clv_draw) as avg_d,
                   AVG(clv_away) as avg_a,
                   AVG(clv_over25) as avg_o,
                   AVG(clv_under25) as avg_u
            FROM matches_v2
            GROUP BY league_code
            ORDER BY league_code
        """).fetchall()
        for r in rows:
            print(f"  [{r['league_code']:3s}] n={r['n']}, has_clv={r['has_clv']} "
                  f"H={r['avg_h']*100:+.2f}% D={r['avg_d']*100:+.2f}% A={r['avg_a']*100:+.2f}% "
                  f"O={(r['avg_o'] or 0)*100:+.2f}% U={(r['avg_u'] or 0)*100:+.2f}%")
    finally:
        conn.close()


def run():
    print("=" * 70)
    print("Sprint 2.1 — CLV Pipeline (B365 opening vs Pinnacle closing)")
    print("=" * 70)
    add_columns()
    n_upd, n_clv = compute_all()
    print(f"\n[OK] {n_upd} satir update edildi")
    print(f"  CLV hesaplanabildi: {n_clv} ({n_clv/n_upd*100:.0f}%)")
    clv_report()


if __name__ == "__main__":
    run()
