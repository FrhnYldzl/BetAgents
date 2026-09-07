"""
🔍 LİG KODU DENETİMİ — tarihsel satırlarda kaç kod yanlış
===========================================================
fetch_iddaa_live.py'nin hatalı öğrenmesi (takım adında sınırsız alt dizi
araması, kadın/genç takımlara uygulanmayan red listesi) iddaa kaynaklı
satırlara YANLIŞ kanonik kod yazdı. Kök neden düzeltildi; bu modül
GEÇMİŞTE ne kadar hasar kaldığını ölçer.

İKİ AYRI SORU, KARIŞTIRILMAMALI:
  A) KESİN YANLIŞ — kadın/genç/rezerv takımlı maç, erkek A-lig kodu
     taşıyor. Ölçüt takım adının kendisi; yorum gerektirmez.
  B) DESTEKSİZ — kod var ama iki takımdan hiçbiri o ligin işareti
     değil. Yanlış OLABİLİR; işaret listemiz eksik de olabilir
     (küçük kulüpler listede yok). Bu yüzden AYRI raporlanır ve
     varsayılan olarak DÜZELTİLMEZ.

football-data kaynaklı satırlara (external_id_fd dolu) HİÇ dokunulmaz:
o kaynak ligi kendisi söyler, tahmine gerek yok.

    python audit_league_codes.py            # yalnız ölç
    python audit_league_codes.py --duzelt   # A grubunu 'ALL' yap
"""
from __future__ import annotations

import sys
from pathlib import Path

THIS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(THIS_DIR))
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

import db
from fetch_iddaa_live import TEAM_MARKERS, _isaret_var, _takim_reddedildi

ANA = tuple(TEAM_MARKERS)          # T1 E0 SP1 D1 I1 F1


def _isaret_mi(ad: str, lig: str) -> bool:
    n = (ad or "").lower()
    return any(_isaret_var(n, m) for m in TEAM_MARKERS.get(lig, ()))


def denetle(duzelt: bool = False) -> dict:
    conn = db.connect()
    try:
        q = ("SELECT match_id, league_code lc, home_team h, away_team a, "
             "matchday d, external_id_iddaa idd "
             "FROM matches_v2 WHERE league_code IN (" +
             ",".join("'" + x + "'" for x in ANA) + ") "
             "AND external_id_fd IS NULL")
        rows = [dict(x) for x in conn.execute(q).fetchall()]
        print(f"🔍 iddaa kaynaklı, kanonik kodlu satır: {len(rows):,}\n")

        kesin, desteksiz = [], []
        for r in rows:
            h, a, lc = r["h"] or "", r["a"] or "", r["lc"]
            if _takim_reddedildi(h) or _takim_reddedildi(a):
                kesin.append(r)                       # A
            elif not (_isaret_mi(h, lc) or _isaret_mi(a, lc)):
                desteksiz.append(r)                   # B

        print(f"  A · KESİN YANLIŞ (kadın/genç/rezerv takım, erkek A-lig kodu)"
              f"  : {len(kesin):,}")
        for r in kesin[:12]:
            print(f"       {r['d']} [{r['lc']}] {str(r['h'])[:26]:26s} - "
                  f"{str(r['a'])[:26]}")
        if len(kesin) > 12:
            print(f"       ... ve {len(kesin)-12} satır daha")

        print(f"\n  B · DESTEKSİZ (iki takım da o ligin işareti değil)"
              f"       : {len(desteksiz):,}")
        for r in desteksiz[:10]:
            print(f"       {r['d']} [{r['lc']}] {str(r['h'])[:26]:26s} - "
                  f"{str(r['a'])[:26]}")
        if len(desteksiz) > 10:
            print(f"       ... ve {len(desteksiz)-10} satır daha")
        print("\n  B DÜZELTİLMEZ: işaret listemiz eksik olabilir (küçük "
              "kulüpler listede yok). Yanlış kod kadar, doğru kodu silmek "
              "de zarardır.")

        if kesin and duzelt:
            for r in kesin:
                conn.execute("UPDATE matches_v2 SET league_code='ALL' "
                             "WHERE match_id=?", (r["match_id"],))
            conn.commit()
            print(f"\n✅ A grubundaki {len(kesin)} satır 'ALL' yapıldı — "
                  f"'bilmiyorum', yanlış bilmekten iyidir.")
        elif kesin:
            print("\n  (ölçüm — değişiklik yok · --duzelt ile A grubu 'ALL')")
        return {"toplam": len(rows), "kesin": len(kesin),
                "desteksiz": len(desteksiz)}
    finally:
        conn.close()


if __name__ == "__main__":
    denetle(duzelt="--duzelt" in sys.argv)
