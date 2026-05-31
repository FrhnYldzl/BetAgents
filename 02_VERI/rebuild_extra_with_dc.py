"""
SP1, I1, F1 için signal_snapshots'ı YENİDEN HESAPLA — bu sefer DC dahil.

Önceki signal_snapshots_extra.py DC olmadan yüklemiş.
Şimdi yeni DC modelleri eğitildi, recompute gerek.
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


# consistency_test_v2'yi 6 lig için çalıştır + reload
def run():
    import consistency_test_v2
    consistency_test_v2.SEASONS = ["2122", "2223", "2324", "2425", "2526"]
    consistency_test_v2.LEAGUES = ["SP1", "I1", "F1"]  # yeniden hesaplanacak ligler

    print("[rebuild] SP1, I1, F1 — DC dahil signal'leri hesapliyor (5 sezon)...")
    df = consistency_test_v2.compute_signals_v13(verbose=True)
    print(f"  {len(df)} maç işlendi")

    from collections import Counter
    conn = db.connect()
    now = datetime.utcnow().isoformat()
    # Sadece yeni ligleri update et
    n_updated = 0
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

            def fav_dir(rr):
                odds = [rr.get('psc_h'), rr.get('psc_d'), rr.get('psc_a')]
                if not all(o and o > 1.01 for o in odds): return None
                m = min(odds)
                if m == odds[0]: return 'H'
                if m == odds[2]: return 'A'
                return 'D'
            fav = fav_dir(r)

            updates = {
                's_model': r.get('s_model'),
                's_anomaly': r.get('s_anomaly'),
                's_xg': r.get('s_xg'),
                's_form': r.get('s_form'),
                's_sharp': r.get('s_sharp'),
                's_invvar': r.get('s_invvar'),
                'dir_model': r.get('model_direction'),
                'dir_anomaly': r.get('signal_direction'),
                'dir_xg': r.get('xg_direction'),
                'dir_form': r.get('form_direction'),
                'dir_consensus': r.get('consensus_direction'),
                'dir_favorite': fav,
                'score_v12': r.get('score_v12'),
                'score_v13': r.get('score_v13'),
                'agree_count': agree_count,
                'signal_count': len(dirs),
                'model_lam_h': r.get('model_lam_h'),
                'model_lam_a': r.get('model_lam_a'),
                'model_max_edge': r.get('model_max_edge'),
            }
            # UPDATE
            set_clause = ", ".join(f"{k}=?" for k in updates.keys())
            params = list(updates.values()) + [uid]
            conn.execute(
                f"UPDATE signal_snapshots SET {set_clause} WHERE match_uid=?",
                params
            )
            n_updated += 1
        except Exception as e:
            pass
    conn.commit()
    conn.close()
    print(f"[OK] {n_updated} satir yeniden hesaplandi (DC dahil)")


if __name__ == "__main__":
    run()
