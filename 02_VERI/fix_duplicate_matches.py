"""
🔧 MÜKERRER MAÇ SATIRI TEMİZLİĞİ (tek seferlik veri düzeltmesi)
================================================================
Hata: fetch_iddaa_live.py mevcut satırı ararken anahtara `league_code`
koyuyordu. Lig kodu her fetch'te öğrenmeyle yeniden hesaplanıyordu, kod
değişince aynı maç BULUNAMIYOR ve YENİDEN EKLENİYORDU.

Üretimde 107 grup / 224 satır oluştu (2026-09-01). Örnek:
  Nottingham Forest - Brest, tek iddaa event'i (3059378), DÖRT satır:
  ALL + E0 + I1 + SP1 — aynı skor (2-0), neredeyse aynı fiyatlar.

Kök neden fetch_iddaa_live.py'de düzeltildi (kimlik artık
external_id_iddaa; yedek anahtarda da league_code yok).

NEDEN SİLMEK — İŞARETLEMEK DEĞİL:
matches_v2 60 dosyada 324 yerde okunuyor. `duplicate_of IS NULL` filtresi
eklemek her sorguyu değiştirmeyi gerektirirdi; biri atlanırsa o ölçüm
sessizce yanlış kalır — üstelik veri "temizlenmiş" göründüğü için kimse
bakmaz. Mükerrer satırlar özgün bilgi taşımıyor (aynı maç, aynı skor,
aynı event id), yani silmek bilgi kaybetmiyor.
GERİ ALINABİLİR: silinen satırların TAMAMI önce JSON'a yazılır.

KURAL (sonuç-kör — sonuçlara bakılmadan önce yazıldı):
  Grup = aynı (matchday, home_team, away_team).
  Kalıcı satır, şu sırayla seçilir:
    1. football-data kaynaklı olan (lig kodu GÜVENİLİR — kaynak söylüyor)
    2. En çok DOLU alan (bilgi kaybını en aza indirir)
    3. Eşitse: en çok paper_bets referansı (yetim bahis riskini azaltır)
    4. Eşitse: en erken ingested_at (özgün satır)
  Kalıcı satırın BOŞ olan alanları kardeşlerinden doldurulur —
  DOLU alan ASLA ezilmez. match_id referansı olan TÜM tablolar
  (şemadan keşfedilir) kalıcı satıra yönlendirilir. Kardeşler silinir.

LİG KODU kardeşten MİRAS ALINMAZ — kanıttan türetilir:
  Kardeşin kodu bu bozulmayı üreten hatalı öğrenmeden geliyor; miras
  almak yanlış kodu geri getirir (Nottingham Forest - Brest için E0
  vardı ve yanlıştı). Kural: İKİ TAKIM da aynı ligin işaretiyse kod
  yazılır, aksi halde 'ALL' kalır. Tek takım yetmez — Nottingham
  Forest (E0) + Brest (F1) bir Premier Lig maçı değildir.
  football-data satırında lig koduna hiç dokunulmaz.
  `--lig-koru` kardeşten miras almayı açar (varsayılan: KAPALI).

    python fix_duplicate_matches.py --dry     # sadece raporla
    python fix_duplicate_matches.py           # uygula
"""
from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

THIS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(THIS_DIR))
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

import db

YEDEK = THIS_DIR / "yedek_mukerrer_maclar.json"


def _gruplar(conn) -> list[dict]:
    return [dict(x) for x in conn.execute(
        "SELECT matchday d, home_team h, away_team a, COUNT(*) n "
        "FROM matches_v2 GROUP BY matchday, home_team, away_team "
        "HAVING COUNT(*) > 1 ORDER BY 4 DESC, 1").fetchall()]


def _satirlar(conn, g: dict) -> list[dict]:
    return [dict(x) for x in conn.execute(
        "SELECT * FROM matches_v2 WHERE matchday=? AND home_team=? "
        "AND away_team=? ORDER BY ingested_at", (g["d"], g["h"], g["a"])
    ).fetchall()]


def _bahis_sayisi(conn, mid) -> int:
    r = conn.execute("SELECT COUNT(*) FROM paper_bets WHERE match_id=?",
                     (mid,)).fetchone()
    return int(r[0]) if r else 0


def _iki_takim_ligi(h: str, a: str) -> str | None:
    """Lig kodu — YALNIZCA iki takım da AYNI ligin işaretiyse.

    Mükerrer gruplarda hangi lig kodunun kalacağı bir seçimdir; kardeş
    satırdan miras almak yanlış kodu geri getirir (Nottingham Forest -
    Brest için E0 vardı ve yanlıştı). Kod kardeşten DEĞİL, KANITTAN
    türetilir.

    Kural: iki takım da aynı ligin işaret listesinde olmalı. Tek takım
    yetmez — Nottingham Forest (E0) + Brest (F1) bir Premier Lig maçı
    değil, Avrupa kupası maçıdır. Kadın/genç/rezerv takım varsa kod YOK.

    Gözlenen vakalarda:
      Aston Villa + Arsenal      -> E0   (ikisi de E0) ✓
      Nottingham Forest + Brest  -> None (E0 + F1 çelişki) ✓
      Real Madrid (K) + Atl. (K) -> None (kadın, reddedildi) ✓
      AC Milan + Man United      -> None (I1 + E0 çelişki) ✓
      Millonarios + Int. Bogota  -> None (hiçbiri işaret değil) ✓
    Eşleşmezse 'ALL' kalır — dürüst olan budur.
    """
    try:
        from fetch_iddaa_live import (TEAM_MARKERS, _isaret_var,
                                      _takim_reddedildi)
    except Exception:
        return None
    if _takim_reddedildi(h or "") or _takim_reddedildi(a or ""):
        return None
    hn, an = (h or "").lower(), (a or "").lower()
    bulunan = set()
    for lg, markers in TEAM_MARKERS.items():
        h_var = any(_isaret_var(hn, m) for m in markers)
        a_var = any(_isaret_var(an, m) for m in markers)
        if h_var and a_var:
            bulunan.add(lg)
        elif h_var or a_var:
            bulunan.add("?" + lg)          # tek taraflı — çelişki işareti
    kesin = {x for x in bulunan if not x.startswith("?")}
    tekil = {x[1:] for x in bulunan if x.startswith("?")}
    if len(kesin) == 1 and not (tekil - kesin):
        return next(iter(kesin))
    return None


def _referans_tablolari(conn) -> list[str]:
    """match_id sütunu olan TÜM tablolar — şemadan keşfet, elle sayma.

    ⚠️ Sadece paper_bets'i yönlendirmek YETMEZ: silinen satıra referans
    veren başka bir tablo varsa o kayıtlar YETİM kalır ve sessizce ölçüm
    dışına düşer. Elle liste tutmak, yarın eklenen bir tabloyu kaçırmak
    demektir; şemadan sormak kaçırmaz.
    """
    r = conn.execute(
        "SELECT table_name FROM information_schema.columns "
        "WHERE column_name='match_id' AND table_schema='public' "
        "AND table_name <> 'matches_v2' ORDER BY table_name").fetchall()
    return [x[0] for x in r]


def _dolu(r: dict) -> int:
    return sum(1 for v in r.values() if v is not None)


def temizle(dry: bool = False, lig_koru: bool = False) -> dict:
    conn = db.connect()
    silinecek: list[dict] = []
    ozet = {"grup": 0, "silinen": 0, "tasinan_alan": 0, "yonlendirilen_bahis": 0}
    try:
        ref = _referans_tablolari(conn)
        print(f"   match_id referansı olan tablo: {', '.join(ref) or '—'}\n")
        gr = _gruplar(conn)
        ozet["grup"] = len(gr)
        if not gr:
            print("✅ Mükerrer maç satırı yok.")
            return ozet
        print(f"🔍 Mükerrer grup: {len(gr)}\n")

        plan = []
        for g in gr:
            rows = _satirlar(conn, g)
            if len(rows) < 2:
                continue
            # KURAL: football-data kaynağı > dolu alan > bahis > en erken
            #
            # football-data satırı ÖNCE gelir çünkü lig kodu GÜVENİLİR:
            # kaynağın kendisi ligi söyler. iddaa satırlarının kodu ise
            # bu temizliğe sebep olan hatalı öğrenmeden geliyor. Kalıcı
            # satırı seçmek, aynı zamanda hangi lig kodunun kalacağını
            # seçmektir — bu yüzden ölçüt açıkça yazıldı, _dolu'nun yan
            # etkisine bırakılmadı.
            skor = []
            for r in rows:
                fd = 1 if r.get("external_id_fd") else 0
                skor.append((fd, _dolu(r), _bahis_sayisi(conn, r["match_id"]),
                             str(r.get("ingested_at") or ""), r))
            skor.sort(key=lambda x: (-x[0], -x[1], -x[2], x[3]))
            kalici = skor[0][4]          # demet: (fd, dolu, bahis, tarih, satır)
            kardes = [x[4] for x in skor[1:]]

            # kalıcının BOŞ alanlarını kardeşlerden doldur (ezme YOK)
            tasima = {}
            for alan, v in kalici.items():
                if v is not None or alan in ("match_id",):
                    continue
                if alan == "league_code" and not lig_koru:
                    continue          # yanlış kodlar mükerrerliği üretti
                for k in kardes:
                    if k.get(alan) is not None:
                        tasima[alan] = k[alan]
                        break
            # LİG KODU — kardeşten miras DEĞİL, kanıttan türetilir.
            # Kardeşin kodu bu bozulmayı üreten hatalı öğrenmeden geliyor.
            # İki takım da aynı ligin işaretiyse kod yazılır, değilse
            # 'ALL' kalır. football-data satırında dokunulmaz: o kaynak
            # ligi kendisi söyler, tahmine gerek yok.
            lig_duzelt = None
            if not kalici.get("external_id_fd"):
                yeni = _iki_takim_ligi(g["h"], g["a"])
                if yeni and yeni != kalici.get("league_code"):
                    lig_duzelt = yeni

            n_bahis = sum(_bahis_sayisi(conn, k["match_id"]) for k in kardes)
            plan.append({"kalici": kalici, "kardes": kardes,
                         "tasima": tasima, "bahis": n_bahis, "g": g,
                         "lig_duzelt": lig_duzelt})
            silinecek.extend(kardes)
            ozet["tasinan_alan"] += len(tasima)
            ozet["yonlendirilen_bahis"] += n_bahis
            ozet["lig_duzeltilen"] = ozet.get("lig_duzeltilen", 0) + \
                (1 if lig_duzelt else 0)

        ozet["silinen"] = len(silinecek)
        print(f"   kalacak satır      : {len(plan)}")
        print(f"   silinecek satır    : {ozet['silinen']}")
        print(f"   taşınacak boş alan : {ozet['tasinan_alan']}")
        print(f"   yönlendirilecek bahis: {ozet['yonlendirilen_bahis']}\n")
        print(f"   kanıtla düzelen lig  : {ozet.get('lig_duzeltilen', 0)}\n")
        for p in plan[:10]:
            g = p["g"]
            lg = p["kalici"].get("league_code")
            ok = f" → {p['lig_duzelt']}" if p["lig_duzelt"] else ""
            print(f"   {g['d']} {str(g['h'])[:22]:22s}-{str(g['a'])[:20]:20s} "
                  f"{g['n']} satır → kalıcı id={p['kalici']['match_id']} "
                  f"lig={lg}{ok} bahis_taşı={p['bahis']}")
        if len(plan) > 10:
            print(f"   ... ve {len(plan)-10} grup daha")

        if dry:
            print("\n(dry-run — değişiklik yok)")
            return ozet

        # 1) YEDEK — silmeden ÖNCE, geri alınabilirlik için
        YEDEK.write_text(json.dumps(
            [{k: (v.isoformat() if hasattr(v, "isoformat") else v)
              for k, v in r.items()} for r in silinecek],
            ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"\n💾 {len(silinecek)} satır yedeklendi → {YEDEK.name}")

        # 2) alan taşı → 3) bahis yönlendir → 4) sil  (bu SIRAYLA)
        for p in plan:
            kid = p["kalici"]["match_id"]
            if p["lig_duzelt"]:
                conn.execute("UPDATE matches_v2 SET league_code=? "
                             "WHERE match_id=?", (p["lig_duzelt"], kid))
            if p["tasima"]:
                sut = ", ".join(f"{a}=?" for a in p["tasima"])
                conn.execute(f"UPDATE matches_v2 SET {sut} WHERE match_id=?",
                             tuple(p["tasima"].values()) + (kid,))
            for k in p["kardes"]:
                for tb in ref:          # ŞEMADAN bulunan TÜM referanslar
                    conn.execute(f"UPDATE {tb} SET match_id=? WHERE match_id=?",
                                 (kid, k["match_id"]))
                conn.execute("DELETE FROM matches_v2 WHERE match_id=?",
                             (k["match_id"],))
        conn.commit()
        print(f"✅ {ozet['silinen']} mükerrer satır silindi, "
              f"{ozet['yonlendirilen_bahis']} bahis yönlendirildi.")

        kalan = len(_gruplar(conn))
        print(f"   doğrulama: kalan mükerrer grup = {kalan}"
              f"  {'✅' if kalan == 0 else '⚠️ HÂLÂ VAR'}")
        # YETİM kontrolü — silme sonrası zorunlu. Bir referans maç
        # satırını kaybettiyse o kayıt sessizce ölçüm dışına düşer.
        for tb in ref:
            y = conn.execute(
                f"SELECT COUNT(*) FROM {tb} t WHERE t.match_id IS NOT NULL "
                f"AND NOT EXISTS (SELECT 1 FROM matches_v2 m "
                f"WHERE m.match_id = t.match_id)").fetchone()[0]
            if y:
                print(f"   ⚠️ {tb}: {y} YETİM referans — maç satırı yok")
    finally:
        conn.close()
    return ozet


if __name__ == "__main__":
    temizle(dry="--dry" in sys.argv, lig_koru="--lig-koru" in sys.argv)
