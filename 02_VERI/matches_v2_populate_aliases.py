"""
v2 — C1: team_aliases canonical mapping populate
==================================================

Strateji:
  1) Canonical_name = Football-Data takım ismi (matches_v2'deki) kabul edilir
  2) Her FD takım kendi adıyla alias olarak da kaydedilir (source=FD)
  3) Understat (xg_data) takımları fuzzy-match ile FD'ye eşlenir
       - similarity >= 0.85   -> otomatik alias (source=Understat)
       - 0.70 <= sim < 0.85   -> review_needed (notes alanına yazılır)
       - sim < 0.70           -> hiç ekleme yok
  4) iddaa/api-football geleneksel kaynaklar ileride eklenecek (placeholder)

Output:
  - team_aliases tablosuna INSERT
  - aliases_review.json (manuel inceleme gereken çiftler)
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

THIS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(THIS_DIR))
sys.path.insert(0, str(THIS_DIR.parent / "03_MODELLER" / "selective"))

import database as db
from team_match import similarity


LEAGUES_WITH_XG = ["E0", "D1", "SP1", "I1", "F1"]
LEAGUES_ALL = ["T1", "E0", "D1", "SP1", "I1", "F1"]


def fetch_fd_teams(conn, league: str):
    rows = conn.execute(
        "SELECT DISTINCT home_team FROM matches_v2 WHERE league_code=?", (league,)
    ).fetchall()
    return sorted({r["home_team"] for r in rows})


def fetch_xg_teams(conn, league: str):
    rows = conn.execute(
        "SELECT DISTINCT home_team FROM xg_data WHERE league_code=?", (league,)
    ).fetchall()
    return sorted({r["home_team"] for r in rows})


def insert_alias(conn, alias: str, source: str, league_code: str,
                 canonical: str, notes: str = None):
    try:
        conn.execute("""
            INSERT OR REPLACE INTO team_aliases(alias, source, league_code, canonical_name, notes)
            VALUES (?, ?, ?, ?, ?)
        """, (alias, source, league_code, canonical, notes))
    except Exception as e:
        print(f"  INSERT err {alias}/{source}/{league_code}: {e}")


def run():
    print("=" * 70)
    print("C1 — team_aliases populate (FD canonical, XG fuzzy)")
    print("=" * 70)

    conn = db.connect()
    review = []  # 0.70-0.85 arası, manuel onay
    n_fd = 0
    n_xg_auto = 0
    n_xg_review = 0
    n_xg_skip = 0

    # 1) FD takımları: canonical = kendi adı
    print("\n[1] FD takımları canonical olarak işaretleniyor")
    for lg in LEAGUES_ALL:
        fd_teams = fetch_fd_teams(conn, lg)
        for t in fd_teams:
            insert_alias(conn, alias=t, source="FD", league_code=lg, canonical=t,
                         notes="canonical_source")
            n_fd += 1
        print(f"  [{lg}] {len(fd_teams)} FD takım -> canonical")

    # 2) Understat takımları: fuzzy match FD'ye
    print("\n[2] Understat takımları fuzzy match")
    for lg in LEAGUES_WITH_XG:
        fd_teams = fetch_fd_teams(conn, lg)
        xg_teams = fetch_xg_teams(conn, lg)
        auto = []
        rev = []
        skip = []
        for xt in xg_teams:
            # Tam match (rare, ama olur)
            if xt in fd_teams:
                insert_alias(conn, alias=xt, source="Understat", league_code=lg,
                             canonical=xt, notes="exact_match")
                auto.append((xt, xt, 1.0))
                continue
            best = None; best_sim = 0
            for ft in fd_teams:
                s = similarity(xt, ft)
                if s > best_sim:
                    best_sim = s; best = ft
            if best_sim >= 0.85:
                insert_alias(conn, alias=xt, source="Understat", league_code=lg,
                             canonical=best, notes=f"fuzzy_sim={best_sim:.2f}")
                auto.append((xt, best, best_sim))
            elif best_sim >= 0.70:
                insert_alias(conn, alias=xt, source="Understat", league_code=lg,
                             canonical=best, notes=f"REVIEW_NEEDED sim={best_sim:.2f}")
                rev.append({"xg_team": xt, "best_fd_match": best,
                            "similarity": round(best_sim, 3), "league": lg})
            else:
                skip.append({"xg_team": xt, "best_fd_match": best,
                             "similarity": round(best_sim, 3), "league": lg})
        n_xg_auto += len(auto)
        n_xg_review += len(rev)
        n_xg_skip += len(skip)
        review.extend(rev)
        print(f"  [{lg}] auto={len(auto)} review={len(rev)} skip={len(skip)}")

    conn.commit()
    conn.close()

    # Review report
    out = THIS_DIR / "aliases_review.json"
    out.write_text(json.dumps(review, indent=2, ensure_ascii=False))

    print(f"\n[OZET]")
    print(f"  FD canonical alias       : {n_fd}")
    print(f"  XG auto-matched          : {n_xg_auto}")
    print(f"  XG review needed (0.70-0.85): {n_xg_review}")
    print(f"  XG skipped (<0.70)       : {n_xg_skip}")
    print(f"\n[OK] Review listesi: {out}")


if __name__ == "__main__":
    run()
