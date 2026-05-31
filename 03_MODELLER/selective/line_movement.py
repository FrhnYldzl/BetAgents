"""
SELECTIVE EDGE v1.1 — Line Movement Signal

Hipotez: Sharp money piyasaya geldikçe oran düşer.
    odd(T-24h) = 2.10
    odd(T-1h)  = 1.85 → sharp money "Üst" tarafında → güçlü sinyal.

Bu modül:
    1. compute_movement(iddaa_match_id, market, selection)
       İki snapshot arasında delta hesaplar.
    2. movement_score(delta) → 0-1 (yön: düşen oran = +sinyal)
    3. all_movements(snapshot_a, snapshot_b) → tüm pazarlar için delta

Selective edge'e nasıl entegre olur:
    Her maç için en güçlü "sharp move"u bul. consensus_score gibi ek bir sinyal:
    sharp_move_signal = max(|delta|) over markets where delta direction
                        agrees with anomaly_direction.
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

THIS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(THIS_DIR.parent.parent / "02_VERI"))

import database as db


def get_snapshots(iddaa_match_id: str | None = None) -> list[str]:
    """Mevcut snapshot ID'leri (en yeniden eskiye)."""
    conn = db.connect()
    try:
        if iddaa_match_id:
            rows = conn.execute(
                "SELECT DISTINCT snapshot_id FROM iddaa_odds "
                "WHERE iddaa_match_id=? ORDER BY snapshot_id DESC",
                (iddaa_match_id,)
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT DISTINCT snapshot_id FROM iddaa_odds ORDER BY snapshot_id DESC"
            ).fetchall()
        return [r[0] for r in rows]
    finally:
        conn.close()


def get_match_odds_snapshot(conn, iddaa_match_id: str, snapshot_id: str) -> dict:
    rows = conn.execute(
        "SELECT market, selection, odd FROM iddaa_odds "
        "WHERE iddaa_match_id=? AND snapshot_id=?",
        (iddaa_match_id, snapshot_id)
    ).fetchall()
    out = {}
    for r in rows:
        out[(r["market"], r["selection"])] = r["odd"]
    return out


def compute_movement(iddaa_match_id: str,
                     snapshot_old: str | None = None,
                     snapshot_new: str | None = None) -> dict:
    """
    İki snapshot arası tüm market+selection için odds delta.

    Returns:
        {
          (market, selection): {
            'odd_old': 2.10, 'odd_new': 1.85, 'delta': -0.25, 'pct_change': -11.9
          }, ...
        }
        + summary:
        max_move_market, max_move_delta, sharp_money_direction
    """
    snaps = get_snapshots(iddaa_match_id)
    if len(snaps) < 2:
        return {"available": False, "reason": "tek_snapshot"}

    if snapshot_new is None:
        snapshot_new = snaps[0]
    if snapshot_old is None:
        snapshot_old = snaps[-1]
    if snapshot_old == snapshot_new:
        return {"available": False, "reason": "ayni_snapshot"}

    conn = db.connect()
    try:
        old_odds = get_match_odds_snapshot(conn, iddaa_match_id, snapshot_old)
        new_odds = get_match_odds_snapshot(conn, iddaa_match_id, snapshot_new)

        moves = {}
        for key, old_odd in old_odds.items():
            new_odd = new_odds.get(key)
            if new_odd is None or old_odd <= 1.001 or new_odd <= 1.001:
                continue
            delta = new_odd - old_odd
            pct = (new_odd / old_odd - 1) * 100
            moves[key] = {
                "odd_old": old_odd,
                "odd_new": new_odd,
                "delta": delta,
                "pct_change": pct,
            }

        if not moves:
            return {"available": False, "reason": "esleme_yok"}

        # En büyük hareket (negatif delta = sharp money geliyor)
        sharpest = min(moves.items(), key=lambda kv: kv[1]["delta"])
        max_move = sharpest[1]
        max_move_key = sharpest[0]  # (market, selection)

        # Sharp money signal: pct_change < -3% güçlü düşüş
        signal = 0.0
        direction = None
        if max_move["pct_change"] < -3:
            # |pct| 3 → 0.3, 15 → 1.0
            signal = min(1.0, abs(max_move["pct_change"]) / 15)
            direction = f"{max_move_key[0]}|{max_move_key[1]}"

        return {
            "available": True,
            "snapshot_old": snapshot_old,
            "snapshot_new": snapshot_new,
            "moves": moves,
            "sharp_move_market": max_move_key[0],
            "sharp_move_selection": max_move_key[1],
            "sharp_move_delta": max_move["delta"],
            "sharp_move_pct": max_move["pct_change"],
            "signal": signal,
            "direction": direction,
        }
    finally:
        conn.close()


def report_all(top_n: int = 20):
    """Tüm maçlar için sharp money sinyal raporu."""
    snaps = get_snapshots()
    if len(snaps) < 2:
        print("[!] Tek snapshot var, line movement hesaplanamaz.")
        print(f"    Mevcut: {snaps}")
        print(f"    Cozum: iddaa_odds_scraper.py fetch komutunu birka kez calistir.")
        return

    print(f"Snapshot'lar: {len(snaps)} ({snaps[-1]} → {snaps[0]})")
    conn = db.connect()
    try:
        match_ids = [r[0] for r in conn.execute(
            "SELECT DISTINCT iddaa_match_id FROM iddaa_odds"
        ).fetchall()]
    finally:
        conn.close()

    results = []
    for mid in match_ids:
        m = compute_movement(mid)
        if m.get("available") and m["signal"] > 0:
            results.append((mid, m))
    results.sort(key=lambda kv: kv[1]["signal"], reverse=True)

    print(f"\nSharp-money signals: {len(results)} mac")
    print(f"\n{'Match':45s} {'Market':12s} {'Sel':10s} {'OldOdd':>7s} {'NewOdd':>7s} {'Pct':>7s} {'Sig':>5s}")
    print("-" * 100)
    conn = db.connect()
    try:
        for mid, m in results[:top_n]:
            row = conn.execute(
                "SELECT MAX(home_team) as h, MAX(away_team) as a FROM iddaa_odds "
                "WHERE iddaa_match_id=?", (mid,)
            ).fetchone()
            label = f"{row['h']} vs {row['a']}"[:43]
            odl = list(m['moves'].keys())[0] if m['moves'] else None
            mkt_sel = m['moves'].get((m['sharp_move_market'], m['sharp_move_selection']), {})
            print(f"{label:45s} {m['sharp_move_market']:12s} {m['sharp_move_selection']:10s} "
                  f"{mkt_sel.get('odd_old',0):>7.2f} {mkt_sel.get('odd_new',0):>7.2f} "
                  f"{m['sharp_move_pct']:>+6.1f}% {m['signal']:>5.2f}")
    finally:
        conn.close()


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "report"
    if cmd == "report":
        report_all(int(sys.argv[2]) if len(sys.argv) > 2 else 20)
    elif cmd == "match":
        m = compute_movement(sys.argv[2])
        import json
        print(json.dumps(m, ensure_ascii=False, indent=2, default=str)[:2000])
    else:
        print("Komutlar: report [N] | match <id>")
