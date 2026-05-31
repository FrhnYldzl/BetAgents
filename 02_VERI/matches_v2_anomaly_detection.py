"""
v2 — C2: Anomaly Detection
============================

matches_v2 üzerinde bütünlük ve tutarlılık kontrolleri:

  1) Duplicate match: aynı (league, season, home, away) kombinasyonu birden fazla
  2) Duplicate matchday: aynı takım çiftinin aynı sezonda 2+ maç tarihi
  3) Extreme odds:
       - 1/X/2 implied prob >1.05 toplam (overround sanity)
       - tek bacak <1.01 veya >50 (uç oran)
  4) Score outliers:
       - tek maçta >=8 gol total
       - bilinen rekorlardan büyük skorlar (>10)
  5) Date sanity:
       - matchday < 2017-08-01 veya > today
  6) Team name sanity:
       - boş takım ismi
       - sayısal/anlamsız karakter

Output: anomalies_report.json + console summary
Hiçbir satırı silmez; sadece rapor üretir.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, date
from pathlib import Path

THIS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(THIS_DIR))

import database as db


def fetch_all():
    conn = db.connect()
    rows = conn.execute("""
        SELECT match_id, league_code, season, matchday,
               home_team, away_team, home_score, away_score,
               closing_1, closing_X, closing_2,
               opening_1, opening_X, opening_2,
               is_settled
        FROM matches_v2
    """).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def check_duplicates(rows):
    """Aynı (lig, sezon, home, away) çoklu kayıt."""
    seen = {}
    dupes = []
    for r in rows:
        key = (r["league_code"], r["season"], r["home_team"], r["away_team"])
        if key in seen:
            dupes.append({
                "key": list(key),
                "match_ids": [seen[key], r["match_id"]],
                "matchdays": [None, r["matchday"]],
            })
        else:
            seen[key] = r["match_id"]
    return dupes


def check_extreme_odds(rows):
    """1X2 oran sanity check."""
    odd_outliers = []
    overround_outliers = []
    for r in rows:
        c1, cx, c2 = r["closing_1"], r["closing_X"], r["closing_2"]
        if not (c1 and cx and c2):
            continue
        # Tek bacak ekstrem
        for name, v in (("closing_1", c1), ("closing_X", cx), ("closing_2", c2)):
            if v < 1.01 or v > 50:
                odd_outliers.append({
                    "match_id": r["match_id"], "leg": name, "value": v,
                    "league": r["league_code"], "season": r["season"],
                    "match": f"{r['home_team']} vs {r['away_team']}",
                })
        # Overround sanity
        try:
            imp = (1/c1) + (1/cx) + (1/c2)
            if imp < 0.95 or imp > 1.20:
                overround_outliers.append({
                    "match_id": r["match_id"], "implied_sum": round(imp, 3),
                    "league": r["league_code"], "season": r["season"],
                    "match": f"{r['home_team']} vs {r['away_team']}",
                })
        except Exception:
            pass
    return odd_outliers, overround_outliers


def check_score_outliers(rows):
    """Uç skor durumları."""
    outliers = []
    for r in rows:
        hs, as_ = r["home_score"], r["away_score"]
        if hs is None or as_ is None:
            continue
        total = hs + as_
        if total >= 8 or hs > 10 or as_ > 10:
            outliers.append({
                "match_id": r["match_id"],
                "score": f"{hs}-{as_}",
                "total": total,
                "league": r["league_code"], "season": r["season"],
                "match": f"{r['home_team']} vs {r['away_team']}",
                "date": r["matchday"],
            })
    return outliers


def check_date_sanity(rows):
    """Tarih aralığı sanity."""
    today = date.today().isoformat()
    bad_dates = []
    for r in rows:
        md = r["matchday"]
        if not md:
            bad_dates.append({"match_id": r["match_id"], "matchday": md, "issue": "null"})
            continue
        if md < "2017-08-01":
            bad_dates.append({"match_id": r["match_id"], "matchday": md, "issue": "too_early"})
        elif md > today and r["is_settled"]:
            bad_dates.append({"match_id": r["match_id"], "matchday": md,
                              "issue": "future_but_settled"})
    return bad_dates


def check_team_names(rows):
    """Takım isimlerinde anomaliler."""
    bad_names = []
    for r in rows:
        for fld in ("home_team", "away_team"):
            name = r[fld]
            if not name or len(name.strip()) < 2:
                bad_names.append({
                    "match_id": r["match_id"], "field": fld, "value": name,
                })
            elif any(ch.isdigit() for ch in name) and len(name) <= 4:
                bad_names.append({
                    "match_id": r["match_id"], "field": fld, "value": name,
                    "reason": "mostly_digits",
                })
    return bad_names


def check_settled_consistency(rows):
    """is_settled=1 ama skor yok / vice versa."""
    mismatches = []
    for r in rows:
        if r["is_settled"] and (r["home_score"] is None or r["away_score"] is None):
            mismatches.append({
                "match_id": r["match_id"], "issue": "settled_no_score",
                "league": r["league_code"], "season": r["season"],
            })
        elif not r["is_settled"] and r["home_score"] is not None:
            mismatches.append({
                "match_id": r["match_id"], "issue": "score_but_not_settled",
                "league": r["league_code"], "season": r["season"],
            })
    return mismatches


def run():
    print("=" * 70)
    print("C2 — Anomaly Detection on matches_v2")
    print("=" * 70)

    rows = fetch_all()
    print(f"Analiz: {len(rows)} satir\n")

    report = {
        "generated_at": datetime.utcnow().isoformat(),
        "n_total": len(rows),
        "duplicates": check_duplicates(rows),
    }
    odds, overround = check_extreme_odds(rows)
    report["extreme_odds"] = odds
    report["overround_outliers"] = overround
    report["score_outliers"] = check_score_outliers(rows)
    report["bad_dates"] = check_date_sanity(rows)
    report["bad_team_names"] = check_team_names(rows)
    report["settled_mismatches"] = check_settled_consistency(rows)

    # Console summary
    print("[ANOMALI OZETI]")
    print(f"  Duplicate maclar          : {len(report['duplicates'])}")
    print(f"  Ekstrem oranlar (tek bacak): {len(report['extreme_odds'])}")
    print(f"  Overround outlier         : {len(report['overround_outliers'])}")
    print(f"  Skor outlier (8+ gol)     : {len(report['score_outliers'])}")
    print(f"  Tarih anomalisi           : {len(report['bad_dates'])}")
    print(f"  Takim ismi anomalisi      : {len(report['bad_team_names'])}")
    print(f"  Settled mismatch          : {len(report['settled_mismatches'])}")

    # Save report
    out = THIS_DIR / "anomalies_report.json"
    out.write_text(json.dumps(report, indent=2, ensure_ascii=False))
    print(f"\n[OK] Rapor: {out}")

    # Top examples (kontrole yardim icin)
    if report["score_outliers"]:
        print("\nIlk 5 skor outlier:")
        for x in report["score_outliers"][:5]:
            print(f"  [{x['league']}/{x['season']}] {x['match']}: {x['score']} ({x['date']})")

    if report["overround_outliers"]:
        print("\nIlk 5 overround outlier:")
        for x in report["overround_outliers"][:5]:
            print(f"  [{x['league']}/{x['season']}] {x['match']}: sum={x['implied_sum']}")

    if report["duplicates"]:
        print("\nIlk 5 duplicate:")
        for x in report["duplicates"][:5]:
            print(f"  {x['key']} -> match_ids {x['match_ids']}")


if __name__ == "__main__":
    run()
