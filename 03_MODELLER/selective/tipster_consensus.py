"""
SELECTIVE EDGE v1.1 — Tipster Consensus Signal (FUZZY-AWARE)

v1.0 problemi:
    Tipster picks ile iddaa events için exact-match team adı arıyordu.
    Sadece 1 overlap → consensus signal hep 0 → ağırlığın %30'u ölü.

v1.1 çözümü:
    team_match.py fuzzy similarity ile maç eşleştir.
    Threshold ≥0.70 (her iki takım da).

Skor formülü değişmedi:
    consensus_score = Σ(tipster_score for group) / Σ(all_tipster_scores)
    Sadece "bu maça pick atan tipsterleri bulma" katmanı fuzzy.
"""
from __future__ import annotations

import sys
from pathlib import Path

THIS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(THIS_DIR.parent.parent / "02_VERI"))
sys.path.insert(0, str(THIS_DIR))

import database as db
from team_match import similarity, match_pair


def get_tipster_consensus(home: str, away: str,
                          min_score: float = 0.5,
                          fuzzy_threshold: float = 0.70,
                          conn=None) -> dict:
    """
    Bir maç için tipster konsensüsünü hesapla (fuzzy-aware).

    Args:
        min_score        : tipster_stats.score altındaki tipsterleri ignore et
        fuzzy_threshold  : team_name benzerlik eşiği (her iki takım için)
    """
    close = conn is None
    if conn is None:
        conn = db.connect()
    try:
        tipsters = {r["tipster_id"]: dict(r) for r in conn.execute(
            "SELECT * FROM tipster_stats WHERE score >= ? ORDER BY score DESC",
            (min_score,)
        ).fetchall()}
        if not tipsters:
            return {"consensus_score": 0.0, "picks": [], "total_weight": 0.0,
                    "match_count": 0, "tipster_count": 0}

        # tüm tipster picks'leri tara — fuzzy match
        all_picks = conn.execute("""
            SELECT pick_id, tipster_id, tipster_name, home_team, away_team,
                   market, selection, pick_odd, won, settled, kickoff_iso
            FROM tipster_picks
        """).fetchall()

        matched = []
        for p in all_picks:
            if match_pair(home, away, p["home_team"], p["away_team"],
                          min_score=fuzzy_threshold):
                tid = p["tipster_id"]
                t = tipsters.get(tid)
                if not t:
                    continue
                matched.append({
                    "tipster_id": tid,
                    "tipster_name": t.get("tipster_name"),
                    "tipster_score": t.get("score") or 0,
                    "win_rate": t.get("win_rate") or 0,
                    "wilson_lower": t.get("wilson_lower"),
                    "market": p["market"],
                    "selection": p["selection"],
                    "pick_odd": p["pick_odd"],
                    "settled": p["settled"],
                    "won": p["won"],
                    "kickoff_iso": p["kickoff_iso"],
                    "iddaa_home": p["home_team"],
                    "iddaa_away": p["away_team"],
                })

        if not matched:
            return {
                "consensus_score": 0.0,
                "picks": [],
                "total_weight": sum(t.get("score") or 0 for t in tipsters.values()),
                "match_count": 0,
                "tipster_count": 0,
            }

        # Group by (market, selection)
        groups: dict[tuple[str, str], dict] = {}
        for p in matched:
            k = (p["market"], p["selection"])
            g = groups.setdefault(k, {"weight": 0.0, "tipsters": []})
            g["weight"] += p["tipster_score"]
            g["tipsters"].append(p["tipster_name"])

        total_w = sum(t.get("score") or 0 for t in tipsters.values())
        top = max(groups.items(), key=lambda kv: kv[1]["weight"])
        top_market, top_selection = top[0]
        top_weight = top[1]["weight"]

        consensus_score = top_weight / total_w if total_w > 0 else 0.0
        return {
            "consensus_score": consensus_score,
            "consensus_market": top_market,
            "consensus_selection": top_selection,
            "consensus_tipsters": top[1]["tipsters"],
            "total_weight": total_w,
            "picks": matched,
            "match_count": len(matched),
            "tipster_count": len(set(p["tipster_id"] for p in matched)),
            "groups": {f"{k[0]}|{k[1]}": v for k, v in groups.items()},
        }
    finally:
        if close:
            conn.close()


def report_overlap():
    """iddaa odds × tipster picks fuzzy match overlap raporu."""
    conn = db.connect()
    try:
        iddaa_matches = conn.execute(
            "SELECT DISTINCT home_team, away_team FROM iddaa_odds"
        ).fetchall()
        tipster_matches = conn.execute(
            "SELECT DISTINCT home_team, away_team FROM tipster_picks"
        ).fetchall()
        print(f"iddaa events: {len(iddaa_matches)} maç")
        print(f"tipster picks: {len(tipster_matches)} unique maç")

        overlap = 0
        examples = []
        for i in iddaa_matches:
            for t in tipster_matches:
                if match_pair(i["home_team"], i["away_team"],
                              t["home_team"], t["away_team"], 0.70):
                    overlap += 1
                    if len(examples) < 5:
                        examples.append(
                            f"  iddaa: {i['home_team']} vs {i['away_team']}\n"
                            f"  tip  : {t['home_team']} vs {t['away_team']}"
                        )
                    break
        print(f"\nFUZZY OVERLAP: {overlap} maç eşleşti (threshold=0.70)")
        for ex in examples:
            print(ex)
    finally:
        conn.close()


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "overlap"
    if cmd == "overlap":
        report_overlap()
    elif cmd == "test":
        conn = db.connect()
        rows = conn.execute(
            "SELECT DISTINCT home_team, away_team FROM iddaa_odds LIMIT 30"
        ).fetchall()
        found = 0
        for r in rows:
            c = get_tipster_consensus(r["home_team"], r["away_team"], conn=conn)
            if c["match_count"] > 0:
                found += 1
                print(f"  {r['home_team']} vs {r['away_team']}")
                print(f"    consensus_score: {c['consensus_score']:.3f}  matches: {c['match_count']}")
                print(f"    direction: {c.get('consensus_market')}/{c.get('consensus_selection')}")
                print(f"    tipsters: {c.get('consensus_tipsters', [])}")
        print(f"\n[OK] {found} mac icin tipster overlap bulundu")
        conn.close()
