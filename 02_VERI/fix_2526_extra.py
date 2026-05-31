"""
SP1, I1, F1 için 2526 sezonu signal_snapshots'a INSERT
=======================================================

DATA_AUDIT'te çıkan eksiklik fix.
"""
from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

THIS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(THIS_DIR))
sys.path.insert(0, str(THIS_DIR.parent / "04_BACKTEST"))
sys.path.insert(0, str(THIS_DIR.parent / "03_MODELLER"))
sys.path.insert(0, str(THIS_DIR.parent / "03_MODELLER" / "selective"))

import database as db


def run():
    import consistency_test_v2
    consistency_test_v2.SEASONS = ["2526"]
    consistency_test_v2.LEAGUES = ["SP1", "I1", "F1"]

    print("[fix-2526] SP1/I1/F1 / 2526 yukleniyor...")
    df = consistency_test_v2.compute_signals_v13(verbose=True)
    print(f"  {len(df)} mac")

    from collections import Counter
    conn = db.connect()
    now = datetime.utcnow().isoformat()

    def fav_dir(r):
        odds = [r.get('psc_h'), r.get('psc_d'), r.get('psc_a')]
        if not all(o and o > 1.01 for o in odds): return None
        m = min(odds)
        if m == odds[0]: return 'H'
        if m == odds[2]: return 'A'
        return 'D'

    n_loaded = 0
    for _, r in df.iterrows():
        try:
            kickoff = str(r['date'])[:10]
            uid = f"{r['league']}_{r['season']}_{r['home'].lower().replace(' ','_').replace(chr(39),'')}_vs_{r['away'].lower().replace(' ','_').replace(chr(39),'')}_{kickoff[:10]}"
            dirs = [r.get('model_direction'), r.get('signal_direction'),
                    r.get('xg_direction'), r.get('form_direction')]
            dirs = [d for d in dirs if d and str(d) != 'nan']
            cnt = Counter(dirs).most_common(1)
            agree_count = cnt[0][1] if cnt else 0
            settled = 1 if r.get('ftr') in ('H', 'D', 'A') else 0
            tg = (r.get('fthg') or 0) + (r.get('ftag') or 0) if settled else None
            fav = fav_dir(r)
            bts = 1 if settled and r.get('fthg', 0) >= 1 and r.get('ftag', 0) >= 1 else 0 if settled else None

            row = {
                'match_uid': uid, 'league_code': r['league'], 'season': r['season'],
                'kickoff_iso': kickoff, 'home_team': r['home'], 'away_team': r['away'],
                'odd_1': r.get('psc_h'), 'odd_X': r.get('psc_d'), 'odd_2': r.get('psc_a'),
                'odd_over25': r.get('pc_over'), 'odd_under25': r.get('pc_under'),
                's_anomaly': r.get('s_anomaly'), 's_model': r.get('s_model'),
                's_xg': r.get('s_xg'), 's_form': r.get('s_form'),
                's_sharp': r.get('s_sharp'), 's_invvar': r.get('s_invvar'),
                'dir_anomaly': r.get('signal_direction'), 'dir_model': r.get('model_direction'),
                'dir_xg': r.get('xg_direction'), 'dir_form': r.get('form_direction'),
                'dir_consensus': r.get('consensus_direction'), 'dir_favorite': fav,
                'score_v12': r.get('score_v12'), 'score_v13': r.get('score_v13'),
                'agree_count': agree_count, 'signal_count': len(dirs),
                'model_lam_h': r.get('model_lam_h'), 'model_lam_a': r.get('model_lam_a'),
                'model_max_edge': r.get('model_max_edge'),
                'xg_luck_diff': r.get('xg_luck_diff'), 'form_delta': r.get('form_delta'),
                'result_1x2': r.get('ftr') if settled else None,
                'home_score': r.get('fthg') if settled else None,
                'away_score': r.get('ftag') if settled else None,
                'total_goals': tg, 'ft_btts': bts, 'settled': settled,
                'created_at': now,
            }
            cols = ','.join(['snapshot_id', 'source'] + list(row.keys()))
            ph = ','.join(['?'] * (len(row) + 2))
            conn.execute(f"INSERT OR REPLACE INTO signal_snapshots({cols}) VALUES({ph})",
                         ('fd_backtest', 'football_data', *row.values()))
            n_loaded += 1
        except Exception:
            pass
    conn.commit()
    conn.close()
    print(f"[OK] {n_loaded} satir eklendi")


if __name__ == "__main__":
    run()
