"""
2025-26 sezonu icin DC lam degerlerini doldur ve A/U + KG sinyalleri uygula.

Sorun: signal_snapshots'ta 2526 satirlarinda model_lam_h, model_lam_a = NULL.
Cozum: consistency_test_v2 ile DC lam hesapla, UPDATE et.
Sonra A/U ve KG modelleri 2526'da da calisir.
"""
from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

THIS_DIR = Path(__file__).resolve().parent
YAZILIM = THIS_DIR.parent
sys.path.insert(0, str(THIS_DIR))
sys.path.insert(0, str(YAZILIM / "04_BACKTEST"))
sys.path.insert(0, str(YAZILIM / "03_MODELLER"))
sys.path.insert(0, str(YAZILIM / "03_MODELLER" / "selective"))

import database as db
import consistency_test_v2


def build_match_uid(league, season_code, home, away, date_str):
    def slug(s):
        return s.lower().replace(" ", "_").replace("'", "")
    return f"{league}_{season_code}_{slug(home)}_vs_{slug(away)}_{date_str[:10]}"


def run():
    print("=" * 80)
    print("2025-26 DC lam fix + multi-market sinyal uygulamasi")
    print("=" * 80)

    # 1) 2526 icin sinyal hesapla
    print("\n[1] 2025-26 sezonu sinyal hesaplama...")
    consistency_test_v2.SEASONS = ["2526"]
    consistency_test_v2.LEAGUES = ["T1", "E0", "D1", "SP1", "I1", "F1"]

    df = consistency_test_v2.compute_signals_v13(verbose=True)
    print(f"  Hesaplandi: {len(df)} satir")

    # 2) signal_snapshots'a UPDATE
    print("\n[2] signal_snapshots UPDATE (DC lam dolduruluyor)...")
    conn = db.connect()
    n_updated = 0
    for _, r in df.iterrows():
        try:
            kickoff = str(r['date'])[:10]
            uid = build_match_uid(r['league'], r['season'], r['home'], r['away'], kickoff)
            conn.execute("""
                UPDATE signal_snapshots
                SET model_lam_h=?, model_lam_a=?,
                    s_model=?, s_anomaly=?, s_xg=?, s_form=?, s_sharp=?, s_invvar=?,
                    dir_model=?, dir_anomaly=?, dir_xg=?, dir_form=?,
                    model_max_edge=?,
                    xg_luck_diff=?, form_delta=?
                WHERE match_uid=? AND source='football_data'
            """, (
                r.get('model_lam_h'), r.get('model_lam_a'),
                r.get('s_model'), r.get('s_anomaly'), r.get('s_xg'),
                r.get('s_form'), r.get('s_sharp'), r.get('s_invvar'),
                r.get('model_direction'), r.get('signal_direction'),
                r.get('xg_direction'), r.get('form_direction'),
                r.get('model_max_edge'),
                r.get('xg_luck_diff'), r.get('form_delta'),
                uid,
            ))
            n_updated += 1
        except Exception as e:
            pass
    conn.commit()
    print(f"  {n_updated} satir UPDATE edildi")

    # 3) Verify
    n_lam = conn.execute(
        "SELECT COUNT(*) FROM signal_snapshots WHERE season='2526' "
        "AND model_lam_h IS NOT NULL"
    ).fetchone()[0]
    print(f"  Verify: 2526 sezonu DC lam dolu = {n_lam}")
    conn.close()

    # 4) A/U modeli yeniden uygula
    print("\n[3] A/Ü 2.5 modeli yeniden uygulaniyor (2526 dahil)...")
    import apply_ou_25_model
    apply_ou_25_model.run()

    # 5) KG modeli yeniden uygula
    print("\n[4] KG modeli yeniden uygulaniyor (2526 dahil)...")
    import apply_btts_model
    apply_btts_model.run()

    print("\n" + "=" * 80)
    print("[OK] 2025-26 DC lam + multi-market sinyaller tamam")
    print("=" * 80)


if __name__ == "__main__":
    run()
