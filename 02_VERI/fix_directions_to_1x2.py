"""
v1.2 — Signal Direction Normalize Fix

Sorun:
    dir_anomaly: OVER/UNDER (OU pazarı yönü) — 1X2 değil
    dir_model:   "1"/"X"/"2" karışık "Over"/"Under" — pazar tutarsız

Bunlar FAV_CONFIRMED (1X2 favori) ile eşleşmiyor → konsensüs %1.

Çözüm:
    Tüm direction kolonlarını SADECE 1X2 yönlerine normalize et:
    - "1", "H", "HOME"        → "HOME"
    - "2", "A", "AWAY"        → "AWAY"
    - "0", "X", "D", "DRAW"   → "DRAW"
    - "Over", "Under", "BTTS*" → None (1X2 değil)
    - Combo "1 ve Üst", "2 ve Alt" → ilk part ("1"→"HOME", "2"→"AWAY")

Etki:
    FAV_CONFIRMED filtre artık 4 sinyalden gerçekten 1X2 olanları kullanır.
    Konsensüs (agree_count) gerçek konsensüs olur.
"""
from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

THIS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(THIS_DIR))

import database as db


def to_1x2_dir(d):
    """Direction'ı SADECE 1X2 (HOME/AWAY/DRAW) veya None'a normalize et."""
    if not d or str(d).lower() == "nan":
        return None
    s = str(d).strip()
    if s in ("HOME", "H", "1"): return "HOME"
    if s in ("AWAY", "A", "2"): return "AWAY"
    if s in ("DRAW", "D", "X", "0"): return "DRAW"
    # OU yönü → 1X2 değil, None
    if s in ("Over", "OVER", "Üst", "Ust", "Under", "UNDER", "Alt"):
        return None
    # BTTS yönü → 1X2 değil
    if s.startswith("BTTS"):
        return None
    # Combo: "1 ve Üst", "2 ve Alt"
    if "ve" in s:
        first = s.split()[0]
        if first == "1": return "HOME"
        if first == "2": return "AWAY"
        if first == "0": return "DRAW"
        return None
    # TOTAL_GOALS gibi (3 gol veya az) → 1X2 değil
    return None


def run():
    print("=" * 80)
    print("v1.2 — DIRECTION NORMALIZATION (1X2 only)")
    print("=" * 80)

    conn = db.connect()
    # Önce mevcut dağılım
    print("\nÖNCE — dir_anomaly dağılım örneği (T1):")
    for r in conn.execute(
        "SELECT dir_anomaly, COUNT(*) FROM signal_snapshots "
        "WHERE league_code='T1' GROUP BY dir_anomaly ORDER BY COUNT(*) DESC LIMIT 5"
    ):
        print(f"  {r[0]!r}: {r[1]}")

    # Tüm direction kolonlarını al, normalize et, update
    rows = conn.execute(
        "SELECT match_uid, dir_anomaly, dir_model, dir_xg, dir_form, dir_consensus, dir_favorite "
        "FROM signal_snapshots"
    ).fetchall()
    print(f"\nİşlenen satır: {len(rows)}")

    from collections import Counter
    n_updated = 0
    for r in rows:
        # uid + 6 direction
        uid = r["match_uid"]
        new_dirs = {
            "dir_anomaly": to_1x2_dir(r["dir_anomaly"]),
            "dir_model":   to_1x2_dir(r["dir_model"]),
            "dir_xg":      to_1x2_dir(r["dir_xg"]),
            "dir_form":    to_1x2_dir(r["dir_form"]),
            "dir_favorite":to_1x2_dir(r["dir_favorite"]),
        }
        # consensus & agree_count'ı yeniden hesapla
        sigs = [new_dirs["dir_anomaly"], new_dirs["dir_model"],
                new_dirs["dir_xg"], new_dirs["dir_form"]]
        sigs = [s for s in sigs if s]
        cnt = Counter(sigs).most_common(1)
        if cnt:
            new_dirs["dir_consensus"] = cnt[0][0]
            new_dirs["agree_count"] = cnt[0][1]
        else:
            new_dirs["dir_consensus"] = None
            new_dirs["agree_count"] = 0
        new_dirs["signal_count"] = len(sigs)

        set_clause = ", ".join(f"{k}=?" for k in new_dirs.keys())
        conn.execute(
            f"UPDATE signal_snapshots SET {set_clause} WHERE match_uid=?",
            list(new_dirs.values()) + [uid]
        )
        n_updated += 1

    conn.commit()
    print(f"\n[OK] {n_updated} satir 1X2-only normalize edildi")

    # SONRA dağılım
    print("\nSONRA — dir_anomaly dağılım (T1):")
    for r in conn.execute(
        "SELECT dir_anomaly, COUNT(*) FROM signal_snapshots "
        "WHERE league_code='T1' GROUP BY dir_anomaly ORDER BY COUNT(*) DESC LIMIT 5"
    ):
        print(f"  {r[0]!r}: {r[1]}")

    print("\nSONRA — agree_count dağılım (T1, settled):")
    for r in conn.execute(
        "SELECT agree_count, COUNT(*) FROM signal_snapshots "
        "WHERE league_code='T1' AND settled=1 GROUP BY agree_count ORDER BY agree_count"
    ):
        print(f"  {r[0]} agree: {r[1]}")

    conn.close()


if __name__ == "__main__":
    run()
