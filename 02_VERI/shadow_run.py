"""
SELECTIVE EDGE v1.4 — Live Shadow Run Framework

Amaç:
    Mevcut iddaa events + signal pipeline'ı CANLI takip et.
    Her snapshot'ı signal_snapshots'a yaz.
    Maç sonuçlandığında settled=1, result_1x2 doldur.
    4 hafta sonra her stratejinin GERÇEK live performance'ını ölç.

Çalışma akışı:
    1. shadow_snapshot()  → mevcut iddaa odds çek, signal hesabı yap,
                            signal_snapshots tablosuna yaz (source='iddaa_live')
    2. settle_results()    → finished matches için outcome doldur
                            (api-football fixtures'tan)
    3. shadow_report()     → her strateji için live ROI

Cron / scheduling:
    # Her 2 saatte snapshot
    0 */2 * * * cd YAZILIM && python 02_VERI/shadow_run.py snapshot

    # Her gece settle
    0 3 * * * cd YAZILIM && python 02_VERI/shadow_run.py settle
"""
from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

THIS_DIR = Path(__file__).resolve().parent
YAZILIM = THIS_DIR.parent
sys.path.insert(0, str(THIS_DIR))
sys.path.insert(0, str(YAZILIM / "03_MODELLER"))
sys.path.insert(0, str(YAZILIM / "03_MODELLER" / "selective"))

import database as db


def snapshot():
    """Mevcut iddaa events'i çek + sinyalleri hesapla + signal_snapshots'a yaz."""
    print("[shadow] snapshot baslatildi...")

    # 1. iddaa odds çek (önceden tanımlı scraper)
    from scrapers.iddaa_odds_scraper import ingest_all, snapshot_id_now
    snap_id = snapshot_id_now()
    print(f"[shadow] snapshot_id: {snap_id}")
    ingest_all(detail=False)

    # 2. Anomaly hesabı
    from odds_anomaly import compute_all as compute_anomaly
    compute_anomaly(snap_id)

    # 3. signal_snapshots'a yaz
    from selector import get_all_match_signals
    from extra_signals import all_signals as extra_all
    from model_confidence import compute_model_confidence
    from signal_snapshots import init_schema, make_match_uid
    init_schema()

    signals = get_all_match_signals(snap_id)
    print(f"[shadow] {len(signals)} maç için sinyal hesaplandı")

    conn = db.connect()
    now = datetime.utcnow().isoformat()
    n_wrote = 0
    for sig in signals:
        try:
            # match_uid
            home = sig["home"]; away = sig["away"]
            kickoff = (sig.get("kickoff_iso") or now)[:10]
            uid = make_match_uid("iddaa", "live", home, away, kickoff)

            # Extra signals (xG + form)
            try:
                xtra = extra_all(home, away, kickoff)
            except Exception:
                xtra = {"s_xg": None, "xg_direction": None,
                        "s_form": None, "form_direction": None}

            # AGREE count
            dirs = [sig.get("signal_direction"), sig.get("model_direction"),
                    xtra.get("xg_direction"), xtra.get("form_direction")]
            dirs = [d for d in dirs if d]
            from collections import Counter
            agree_count = Counter(dirs).most_common(1)[0][1] if dirs else 0

            row = {
                "snapshot_id": snap_id,
                "source": "iddaa_live",
                "match_uid": uid,
                "iddaa_match_id": sig.get("iddaa_match_id"),
                "league_code": None,
                "season": None,
                "kickoff_iso": sig.get("kickoff_iso"),
                "home_team": home, "away_team": away,
                "s_anomaly": sig.get("s_odds_anomaly"),
                "s_model": sig.get("s_model_confidence"),
                "s_xg": xtra.get("s_xg"),
                "s_form": xtra.get("s_form"),
                "s_sharp": sig.get("s_sharp_money"),
                "s_invvar": sig.get("s_inverse_variance"),
                "dir_anomaly": sig.get("signal_direction"),
                "dir_model": sig.get("model_direction"),
                "dir_xg": xtra.get("xg_direction"),
                "dir_form": xtra.get("form_direction"),
                "dir_consensus": None,
                "score_v13": sig.get("selection_score"),
                "agree_count": agree_count,
                "signal_count": len(dirs),
                "settled": 0,
                "created_at": now,
            }
            cols = ",".join(row.keys())
            ph = ",".join(["?"] * len(row))
            conn.execute(
                f"INSERT OR REPLACE INTO signal_snapshots({cols}) VALUES({ph})",
                tuple(row.values())
            )
            n_wrote += 1
        except Exception:
            pass
    conn.commit()
    conn.close()
    print(f"[shadow] {n_wrote} satir signal_snapshots'a yazildi")


def settle_results():
    """Settled olmamış maçlar için sonuç ara."""
    print("[shadow] settle baslatildi...")
    conn = db.connect()
    unsettled = conn.execute("""
        SELECT match_uid, home_team, away_team, kickoff_iso, iddaa_match_id
        FROM signal_snapshots
        WHERE settled = 0 AND source = 'iddaa_live'
    """).fetchall()
    print(f"[shadow] {len(unsettled)} unsettled mac")

    n_settled = 0
    for u in unsettled:
        u = dict(u)
        # api-football fixtures'ta ara: home+away+date
        kickoff = (u["kickoff_iso"] or "")[:10]
        if not kickoff:
            continue
        # Önce DB'de bak
        row = conn.execute("""
            SELECT home_score, away_score, status
            FROM fixtures
            WHERE LOWER(TRIM(home_team)) = LOWER(TRIM(?))
              AND LOWER(TRIM(away_team)) = LOWER(TRIM(?))
              AND substr(kickoff_utc,1,10) = ?
        """, (u["home_team"], u["away_team"], kickoff)).fetchone()
        if not row or not row["home_score"]:
            continue
        hs, as_ = row["home_score"], row["away_score"]
        ftr = "H" if hs > as_ else ("A" if as_ > hs else "D")
        tg = hs + as_
        bts = 1 if hs >= 1 and as_ >= 1 else 0
        conn.execute("""
            UPDATE signal_snapshots
            SET settled = 1, result_1x2 = ?, home_score = ?, away_score = ?,
                total_goals = ?, ft_btts = ?
            WHERE match_uid = ?
        """, (ftr, hs, as_, tg, bts, u["match_uid"]))
        n_settled += 1
    conn.commit()
    print(f"[shadow] {n_settled} mac settle edildi")
    conn.close()


def report():
    """Shadow run performans raporu."""
    import numpy as np
    conn = db.connect()
    rows = conn.execute("""
        SELECT * FROM signal_snapshots
        WHERE source = 'iddaa_live' AND settled = 1
    """).fetchall()
    print(f"=== SHADOW RUN PERFORMANS ===")
    print(f"Settled live maç: {len(rows)}")
    if not rows:
        print("Henüz settled live mac yok. shadow_snapshot + settle calistirin.")
        return
    # Strateji-bazında ROI
    import pandas as pd
    df = pd.DataFrame([dict(r) for r in rows])
    print(df.head().to_string())
    conn.close()


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "report"
    if cmd == "snapshot":
        snapshot()
    elif cmd == "settle":
        settle_results()
    elif cmd == "report":
        report()
    else:
        print("Komutlar: snapshot | settle | report")
