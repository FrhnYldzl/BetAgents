"""
WEEKLY KOMBIN (T05) — Haftalık 1 Kombin Üretici (Production)

T04 sonuçlarına dayanarak final strateji:

    1. Sadece E0 + T1 (D1 hariç — backtest'te negatif)
    2. FAV_CONFIRMED filter:
        favori yön (Pinnacle implied prob max) + ≥1 sinyal teyit (DC/anom/xG/form)
    3. K=2 combo: en yüksek score'lu 2 maç (combo)
    4. PWR ~%40, ROI ~+14% per kombin (4 sezon backtest CI tamamen pozitif)
    5. Alternatif: K=1 (PWR ~%62, ROI ~+8%, daha güvenli)

INPUT: signal_snapshots tablosu (live iddaa veya backtest)
OUTPUT: 2 maç + combo odd + breakdown
"""
from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

import pandas as pd

THIS_DIR = Path(__file__).resolve().parent
YAZILIM = THIS_DIR.parent.parent
DB_PATH = YAZILIM / "02_VERI" / "bahis_agent.db"


# v4 / T14+T15 sonrası: 3-lig paralel flat 1000 TL strateji
# T1-only:        103 kupon, +62K (yüksek ROI, az hacim)
# 3-lig paralel:  397 kupon, +81K (orta ROI, yüksek hacim) ← v4 ÖNERİ
# Karar: kullanıcı her lig için ayrı kupon kurar, flat 1000 TL stake'er
PRODUCTION_LEAGUES = ["T1", "E0", "D1"]           # 3-lig paralel (T14 winner +81K)
PRODUCTION_LEAGUES_T1_ONLY = ["T1"]               # Alternative: T1 saf (+62K, daha az volatil)
PRODUCTION_K_DEFAULT = 3                          # T06: K=3 optimum
# NOT KULLAN:
# - Skip dark weeks (T15 overfit kanıtladı)
# - Loss-streak pause (T16 gambler's fallacy)


def normalize_dir(d: str | None) -> str | None:
    if not d:
        return None
    if d in ("HOME", "H", "1"): return "HOME"
    if d in ("AWAY", "A", "2"): return "AWAY"
    if d in ("DRAW", "D", "X"): return "DRAW"
    return d


def is_fav_confirmed(row) -> str | None:
    """Favori yön + ≥1 sinyal teyit varsa favori yönünü dön."""
    fav = row.get("dir_favorite")
    if not fav:
        return None
    fav_n = normalize_dir(fav)
    sigs = [row.get("dir_model"), row.get("dir_anomaly"),
            row.get("dir_xg"), row.get("dir_form")]
    agreeing = [s for s in sigs if s and normalize_dir(s) == fav_n]
    return fav if len(agreeing) >= 1 else None


def get_odd(row, direction):
    if direction in ("HOME", "H", "1"): return row.get("odd_1")
    if direction in ("AWAY", "A", "2"): return row.get("odd_2")
    if direction in ("DRAW", "D", "X"): return row.get("odd_X")
    if direction == "Over": return row.get("odd_over25")
    if direction == "Under": return row.get("odd_under25")
    return None


def get_weekly_kombin(snapshot_id: str | None = None,
                     matchday: str | None = None,
                     K: int = 2,
                     leagues: list | None = None,
                     source: str = "any") -> dict:
    """
    Belli bir matchday için K-leg combo öner.

    snapshot_id: belirli snapshot (örn. live)
    matchday: belirli gün (örn. backtest)
    leagues: None = PRODUCTION_LEAGUES (E0 + T1)
    source: 'iddaa_live', 'football_data', 'any'
    """
    if leagues is None:
        leagues = PRODUCTION_LEAGUES

    conn = sqlite3.connect(DB_PATH)
    where = ["1=1"]
    params = []
    if snapshot_id:
        where.append("snapshot_id = ?"); params.append(snapshot_id)
    if matchday:
        where.append("substr(kickoff_iso, 1, 10) = ?"); params.append(matchday)
    if source != "any":
        where.append("source = ?"); params.append(source)
    if leagues:
        ph = ",".join(["?"] * len(leagues))
        where.append(f"league_code IN ({ph})"); params.extend(leagues)

    q = f"""
        SELECT * FROM signal_snapshots
        WHERE {' AND '.join(where)}
    """
    df = pd.read_sql_query(q, conn, params=params)
    conn.close()

    if df.empty:
        return {"K": K, "found": 0, "error": "no_matches"}

    # FAV_CONFIRMED filter
    df["dir_fav_confirmed"] = df.apply(is_fav_confirmed, axis=1)
    df = df[df["dir_fav_confirmed"].notna()]
    if df.empty:
        return {"K": K, "found": 0, "error": "no_confirmed"}

    # Top K by score
    df = df.sort_values("score_v13", ascending=False).head(K)
    if len(df) < K:
        return {"K": K, "found": len(df), "error": f"only_{len(df)}_picks"}

    legs = []
    combo_odd = 1.0
    for _, r in df.iterrows():
        d = r["dir_fav_confirmed"]
        odd = get_odd(r, d)
        if not odd:
            continue
        combo_odd *= odd

        # Confirmin sinyaller listesi
        confirmers = []
        d_n = normalize_dir(d)
        for sig_name, sig_col, dir_col in [
            ("DC model", "s_model", "dir_model"),
            ("Anomaly", "s_anomaly", "dir_anomaly"),
            ("xG", "s_xg", "dir_xg"),
            ("Form", "s_form", "dir_form"),
        ]:
            sdir = r.get(dir_col)
            sval = r.get(sig_col)
            if sdir and normalize_dir(sdir) == d_n:
                confirmers.append(f"{sig_name}({sval:.2f})" if sval else sig_name)

        legs.append({
            "home": r["home_team"], "away": r["away_team"],
            "league": r["league_code"], "season": r["season"],
            "kickoff": r["kickoff_iso"],
            "direction": d,
            "direction_label": {"H": "MS-1", "1": "MS-1",
                               "A": "MS-2", "2": "MS-2",
                               "D": "MS-X", "X": "MS-X"}.get(d, d),
            "odd": odd,
            "score": r["score_v13"],
            "agree_count": r.get("agree_count"),
            "confirmers": confirmers,
            "result_1x2": r.get("result_1x2"),
            "settled": bool(r.get("settled")),
        })

    return {
        "K": K,
        "found": len(legs),
        "combo_odd": combo_odd,
        "legs": legs,
        "implied_fair_prob": 1.0 / combo_odd if combo_odd > 0 else 0,
    }


def get_weekly_kombin_for_date_range(date_from: str, date_to: str,
                                     K: int = 2,
                                     leagues: list | None = None,
                                     source: str = "football_data") -> list:
    """Belirli bir tarih aralığında her gün için kombin önerisi."""
    conn = sqlite3.connect(DB_PATH)
    days = conn.execute(
        f"SELECT DISTINCT substr(kickoff_iso,1,10) as d FROM signal_snapshots "
        f"WHERE substr(kickoff_iso,1,10) BETWEEN ? AND ? AND source = ? "
        f"ORDER BY d", (date_from, date_to, source)
    ).fetchall()
    conn.close()

    results = []
    for d in days:
        kombin = get_weekly_kombin(matchday=d[0], K=K, leagues=leagues, source=source)
        kombin["matchday"] = d[0]
        results.append(kombin)
    return results


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "demo":
        # Backtest'ten son matchday için demo
        conn = sqlite3.connect(DB_PATH)
        last_day = conn.execute(
            "SELECT MAX(substr(kickoff_iso,1,10)) FROM signal_snapshots "
            "WHERE source='football_data'"
        ).fetchone()[0]
        conn.close()
        print(f"Son matchday: {last_day}")
        for K in [1, 2]:
            r = get_weekly_kombin(matchday=last_day, K=K, source="football_data")
            print(f"\n=== K={K} ===")
            if r.get("error"):
                print(f"  Hata: {r['error']}")
                continue
            print(f"  Combo odd: {r['combo_odd']:.2f}")
            print(f"  Implied fair prob: {r['implied_fair_prob']*100:.1f}%")
            for i, leg in enumerate(r["legs"], 1):
                print(f"  Leg {i}: {leg['league']} {leg['home']} vs {leg['away']}")
                print(f"          Pick: {leg['direction_label']} @ {leg['odd']:.2f}  "
                      f"(score {leg['score']:.2f}, agree {leg['agree_count']})")
                print(f"          Confirmers: {leg['confirmers']}")
                if leg["settled"]:
                    print(f"          Result: {leg['result_1x2']}  "
                          f"{'TUTTU' if leg['direction'] == leg['result_1x2'] else 'TUTMADI'}")
    else:
        print("Komutlar: demo")
