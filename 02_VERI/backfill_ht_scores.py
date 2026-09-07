"""
🕐 İLK YARI SKORU DOLDURMA — mevcut veriden, yeni API çağrısı YOK
==================================================================
matches_v2.home_score_ht / away_score_ht sütunları 26.746 satırın
HEPSİNDE boştu. Neden önemli: iddaa'nın HT/FT pazarında marjı %25,8 —
kitabın en az güvendiği yer orası. İlk yarı skoru olmadan o pazar
hakkında hiçbir şey ölçemiyoruz.

BULUŞ: veriyi ZATEN ÇEKMİŞİZ. fixtures tablosundaki 2.098 satırın
raw_json'unda score.halftime.{home,away} duruyor — kaydedilmiş ama
matches_v2'ye hiç aktarılmamış. Yeni API çağrısı, yeni kota, yeni
bekleme yok; sadece elimizdekini taşımak.

EŞLEME: (matchday, home_team, away_team). Takım adları kaynaklar arası
farklı olabilir (API-Football / football-data / iddaa); eşleşmeyenler
RAPORLANIR, tahmin edilmez. Yanlış maça skor yazmak, skor yazmamaktan
kötüdür.

⚠️ SADECE BOŞ ALAN DOLDURULUR. Dolu bir değer ASLA ezilmez —
doğrulanabilirlik için: bu betiği iki kez koşmak veriyi değiştirmez.

    python backfill_ht_scores.py           # ölç
    python backfill_ht_scores.py --uygula  # yaz
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

THIS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(THIS_DIR))
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

import db


def doldur(uygula: bool = False) -> dict:
    conn = db.connect()
    try:
        fx = [dict(x) for x in conn.execute(
            "SELECT home_team h, away_team a, kickoff_utc ko, raw_json rj "
            "FROM fixtures WHERE raw_json IS NOT NULL").fetchall()]
        print(f"📦 ham JSON taşıyan fixture: {len(fx):,}")

        ht = {}
        bozuk = 0
        for f in fx:
            try:
                d = f["rj"] if isinstance(f["rj"], dict) else json.loads(f["rj"])
                s = (d.get("score") or {}).get("halftime") or {}
                hh, aa = s.get("home"), s.get("away")
                if hh is None or aa is None:
                    bozuk += 1
                    continue
                gun = str(f["ko"])[:10]
                ht[(gun, f["h"], f["a"])] = (int(hh), int(aa))
            except Exception:
                bozuk += 1
        print(f"   ilk yarı skoru çıkarılan: {len(ht):,}"
              f"  ·  çıkarılamayan: {bozuk:,}")

        bos = [dict(x) for x in conn.execute(
            "SELECT match_id, matchday d, home_team h, away_team a "
            "FROM matches_v2 WHERE home_score_ht IS NULL").fetchall()]
        print(f"\n🎯 ilk yarı skoru BOŞ olan maç: {len(bos):,}")

        eslesen = []
        for m in bos:
            k = (str(m["d"])[:10], m["h"], m["a"])
            if k in ht:
                eslesen.append((m["match_id"], ) + ht[k])
        print(f"   eşleşen: {len(eslesen):,}"
              f"  ·  eşleşmeyen: {len(bos) - len(eslesen):,}")
        print("   (eşleşmeyenler TAHMİN EDİLMEZ — takım adları kaynaklar "
              "arası farklı olabilir; yanlış maça skor yazmak, skor "
              "yazmamaktan kötüdür.)")

        if not eslesen:
            return {"eslesen": 0}
        if not uygula:
            print(f"\n   örnek: {eslesen[:3]}")
            print("\n   (ölçüm — değişiklik yok · --uygula ile yazılır)")
            return {"eslesen": len(eslesen), "yazilan": 0}

        for mid, hh, aa in eslesen:
            # SADECE BOŞSA yaz — dolu değer asla ezilmez
            conn.execute(
                "UPDATE matches_v2 SET home_score_ht=?, away_score_ht=? "
                "WHERE match_id=? AND home_score_ht IS NULL", (hh, aa, mid))
        conn.commit()
        n = conn.execute("SELECT COUNT(*) FROM matches_v2 "
                         "WHERE home_score_ht IS NOT NULL").fetchone()[0]
        top = conn.execute("SELECT COUNT(*) FROM matches_v2").fetchone()[0]
        print(f"\n✅ {len(eslesen):,} maça ilk yarı skoru yazıldı.")
        print(f"   doluluk: {n:,} / {top:,}  (%{n/top*100:.1f})")
        return {"eslesen": len(eslesen), "yazilan": len(eslesen), "dolu": n}
    finally:
        conn.close()


if __name__ == "__main__":
    doldur(uygula="--uygula" in sys.argv)
