"""
2025-26 sezonu signal_snapshots tam refresh
=============================================

Sorun: 2526'da signal_snapshots opening odds (B365) ve closing PSC odds
       tam yazilmamis. Anomaly sinyali %50 boş bu yüzden.

Çözüm:
  1) signal_snapshots'tan 2526 satırlarını SIL
  2) extend_signals_2017_2021.py pattern'i ile yeniden INSERT
     (opening + closing odds tüm sinyaller + DC lam)
  3) A/U ve KG modeli yeniden uygula
  4) Audit tekrar — uyum sağlandı mı?
"""
from __future__ import annotations

import sys
from collections import Counter
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
    print("2025-26 SIGNAL_SNAPSHOTS TAM REFRESH")
    print("=" * 80)

    conn = db.connect()

    # 1) Mevcut 2526 satırlarını sayalım
    n_before = conn.execute(
        "SELECT COUNT(*) FROM signal_snapshots WHERE source='football_data' AND season='2526'"
    ).fetchone()[0]
    print(f"\n[1] Mevcut 2526 satir: {n_before}")

    # 2) SIL
    print("\n[2] 2526 satirlari SIL...")
    conn.execute(
        "DELETE FROM signal_snapshots WHERE source='football_data' AND season='2526'"
    )
    conn.commit()
    n_after = conn.execute(
        "SELECT COUNT(*) FROM signal_snapshots WHERE source='football_data' AND season='2526'"
    ).fetchone()[0]
    print(f"    Silindi: {n_before - n_after} satir, kalan 2526: {n_after}")

    # 3) Yeniden hesapla
    print("\n[3] 2526 sezonu sinyal yeniden hesaplama...")
    consistency_test_v2.SEASONS = ["2526"]
    consistency_test_v2.LEAGUES = ["T1", "E0", "D1", "SP1", "I1", "F1"]
    df = consistency_test_v2.compute_signals_v13(verbose=True)
    print(f"\n    {len(df)} satir hesaplandi")

    # 4) INSERT (tüm alanlar dahil — opening + closing odds + sinyaller)
    print(f"\n[4] INSERT yapiliyor...")
    now = datetime.utcnow().isoformat()
    n_ins = 0; n_err = 0

    for _, r in df.iterrows():
        try:
            kickoff = str(r['date'])[:10]
            uid = build_match_uid(r['league'], r['season'], r['home'], r['away'], kickoff)

            dirs = [r.get('model_direction'), r.get('signal_direction'),
                    r.get('xg_direction'), r.get('form_direction')]
            dirs = [d for d in dirs if d and str(d) != 'nan']
            cnt = Counter(dirs).most_common(1)
            agree_count = cnt[0][1] if cnt else 0
            settled = 1 if r.get('ftr') in ('H','D','A') else 0
            home_score = int(r['fthg']) if pd.notna(r.get('fthg')) else None
            away_score = int(r['ftag']) if pd.notna(r.get('ftag')) else None
            total_goals = ((home_score or 0) + (away_score or 0)) if settled else None
            btts = 1 if (home_score and away_score and home_score>0 and away_score>0) else 0

            psc_h = r.get('psc_h'); psc_d = r.get('psc_d'); psc_a = r.get('psc_a')
            fav = None
            if psc_h and psc_d and psc_a:
                m = min(psc_h, psc_d, psc_a)
                fav = 'H' if m == psc_h else ('A' if m == psc_a else 'D')

            row_data = {
                "snapshot_id": "fd_backtest_2526_refresh",
                "match_uid": uid, "source": "football_data",
                "league_code": r['league'], "season": r['season'],
                "kickoff_iso": kickoff,
                "home_team": r['home'], "away_team": r['away'],
                "odd_1": psc_h, "odd_X": psc_d, "odd_2": psc_a,
                "odd_over25": r.get('pc_over'), "odd_under25": r.get('pc_under'),
                "odd_open_1": r.get('b_h'), "odd_open_X": r.get('b_d'),
                "odd_open_2": r.get('b_a'),
                "odd_open_over25": r.get('b_over'),
                "odd_open_under25": r.get('b_under'),
                "s_model": r.get('s_model'), "s_anomaly": r.get('s_anomaly'),
                "s_xg": r.get('s_xg'), "s_form": r.get('s_form'),
                "s_sharp": r.get('s_sharp'), "s_invvar": r.get('s_invvar'),
                "dir_model": r.get('model_direction'),
                "dir_anomaly": r.get('signal_direction'),
                "dir_xg": r.get('xg_direction'),
                "dir_form": r.get('form_direction'),
                "dir_consensus": r.get('consensus_direction'),
                "dir_favorite": fav,
                "score_v12": r.get('score_v12'),
                "score_v13": r.get('score_v13'),
                "agree_count": agree_count,
                "signal_count": len(dirs),
                "model_lam_h": r.get('model_lam_h'),
                "model_lam_a": r.get('model_lam_a'),
                "model_max_edge": r.get('model_max_edge'),
                "model_league": r['league'],
                "xg_luck_diff": r.get('xg_luck_diff'),
                "form_delta": r.get('form_delta'),
                "result_1x2": r.get('ftr'),
                "home_score": home_score, "away_score": away_score,
                "total_goals": total_goals,
                "ft_btts": btts if settled else None,
                "settled": settled, "created_at": now,
            }
            cols = list(row_data.keys())
            ph = ", ".join("?" for _ in cols)
            col_list = ", ".join(cols)
            conn.execute(
                f"INSERT INTO signal_snapshots ({col_list}) VALUES ({ph})",
                list(row_data.values())
            )
            n_ins += 1
        except Exception as e:
            n_err += 1

    conn.commit()
    print(f"    Inserted: {n_ins}, Err: {n_err}")

    # 5) Verify
    print("\n[5] Verify:")
    n_total = conn.execute(
        "SELECT COUNT(*) FROM signal_snapshots WHERE source='football_data' AND season='2526'"
    ).fetchone()[0]
    n_clo = conn.execute(
        "SELECT COUNT(*) FROM signal_snapshots WHERE season='2526' AND odd_1 IS NOT NULL"
    ).fetchone()[0]
    n_opn = conn.execute(
        "SELECT COUNT(*) FROM signal_snapshots WHERE season='2526' AND odd_open_1 IS NOT NULL"
    ).fetchone()[0]
    n_anom = conn.execute(
        "SELECT COUNT(*) FROM signal_snapshots WHERE season='2526' AND s_anomaly IS NOT NULL"
    ).fetchone()[0]
    n_lam = conn.execute(
        "SELECT COUNT(*) FROM signal_snapshots WHERE season='2526' AND model_lam_h IS NOT NULL"
    ).fetchone()[0]

    print(f"  Total 2526: {n_total}")
    print(f"  Closing 1X2 dolu: {n_clo} ({n_clo/n_total*100:.0f}%)")
    print(f"  Opening 1X2 dolu: {n_opn} ({n_opn/n_total*100:.0f}%)")
    print(f"  s_anomaly dolu:   {n_anom} ({n_anom/n_total*100:.0f}%)")
    print(f"  DC lam dolu:      {n_lam} ({n_lam/n_total*100:.0f}%)")

    conn.close()

    # 6) Match stats + A/U + KG modellerini yeniden uygula
    print("\n[6] Match stats sinyalleri re-apply...")
    try:
        import apply_match_stats_signals
        apply_match_stats_signals.apply_signals()
    except Exception as e:
        print(f"   match_stats re-apply hata: {e}")

    print("\n[7] A/U 2.5 re-apply...")
    try:
        import apply_ou_25_model
        apply_ou_25_model.run()
    except Exception as e:
        print(f"   OU re-apply hata: {e}")

    print("\n[8] KG re-apply...")
    try:
        import apply_btts_model
        apply_btts_model.run()
    except Exception as e:
        print(f"   KG re-apply hata: {e}")

    print("\n" + "=" * 80)
    print("[OK] 2025-26 tam refresh tamam")
    print("=" * 80)


if __name__ == "__main__":
    run()
