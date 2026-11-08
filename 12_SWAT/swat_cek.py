"""
SWAT · ÇEKİM — ilk yarı skorlarını getir, eşleştir, yaz
========================================================
    python 12_SWAT/swat_cek.py            # yapılandırılmış ligleri çek
    python 12_SWAT/swat_cek.py --durum    # hesap + doluluk raporu

⚠️ MALİYET: lig-sezon başına TEK çağrı. Ücretsiz katman günde 100 istek,
yani buradaki liste rahatlıkla günde birkaç kez koşturulabilir. Pahalı
olan şey maç istatistiği (/fixtures/statistics, maç başına bir çağrı) ve
o BİLEREK burada yok — SWAT'ın 1. aşaması yalnız ilk/ikinci yarı.

⚠️ LİG SEÇİMİ bu dosyada ELLE duruyor, bilerek. Otomatik seçmek için
bültendeki ligi tanımak gerekirdi; `matches_v2.league_code` maçların
%94'ünde 'ALL' ya da boş, yani güvenilmez. Elle liste dürüst olanı:
hangi ligi kapsadığımız açıkça yazılı ve denetlenebilir.
"""
from __future__ import annotations

import sys
from pathlib import Path

KOK = Path(__file__).resolve().parent
for _p in (str(KOK), str(KOK.parent / "02_VERI")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import swat_db as SDB  # noqa: E402
import swat_kaynak as SK  # noqa: E402


def _uretim_korumasi() -> None:
    """Yerelden ÜRETİME yazmayı engelle — canli_worker'daki korumanın aynısı.

    ⚠️ Bu koruma ilk koşuda eksikti ve betik `.env`'deki DATABASE_URL
    yüzünden doğrudan üretime bağlandı; orada iki BOŞ tablo oluştu
    (veri yazılmadı). Zararsız kaldı ama kural açık: üretime yalnız
    worker yazar, yerelden değil. Push et, canlıdan doğrula.
    """
    import os
    import db as _db
    if _db.is_postgres() and not os.environ.get("RAILWAY_ENVIRONMENT") \
            and os.environ.get("SWAT_URETIM_ONAY") != "1":
        sys.exit("SWAT: üretim veritabanına yerelden yazma engellendi "
                 "(RAILWAY_ENVIRONMENT yok). Yerel için "
                 "BETAGENTS_SQLITE_PATH kullan.")

# (API-Football lig kimliği, sezon, insan okunur ad)
# Başlangıç kadrosu: bültende sık geçen ve kimliğini doğrulayabildiğimiz
# ligler. Genişletmeden önce doluluk raporuna bakılmalı — kapsam iddiası
# değil, ÖLÇÜLEN doluluk karar versin.
LIGLER = [
    (203, 2026, "Türkiye Süper Lig"),
    (204, 2026, "Türkiye 1. Lig"),
    (135, 2026, "İtalya Serie A"),
    (140, 2026, "İspanya La Liga"),
    (39, 2026, "İngiltere Premier Lig"),
]


def calistir(ligler=None, yaz=True) -> dict:
    ligler = ligler or LIGLER
    import db
    toplam, yazilan, hatalar = 0, 0, []
    conn = db.connect()
    try:
        SDB.kur(conn)
        for lig_id, sezon, ad in ligler:
            ham = SK.cek_fikstur(lig_id, sezon)
            if not ham:
                hatalar.append(f"{ad}: {SK.SON_HATA or 'veri yok'}")
                continue
            toplam += len(ham)
            eslesen = SK.esle(ham, conn)
            if yaz and eslesen:
                yazilan += SDB.yaz(eslesen, conn)
            print(f"  {ad:24} çekilen {len(ham):4} · eşleşen "
                  f"{len(eslesen):4} · yazılan {len(eslesen) if yaz else 0:4}")
        if hatalar:
            SDB.kayit("hata", " | ".join(hatalar)[:400], conn)
    finally:
        conn.close()
    return {"cekilen": toplam, "yazilan": yazilan, "hata": hatalar,
            "kota_kalan": SK.KALAN}


def durum() -> None:
    h = SK.hesap_durumu()
    print("HESAP:", h)
    if not h.get("acik"):
        print("\n⚠️ Kaynak kapalı — SWAT ajanları MEŞRU PAS geçer, "
              "sahte ölçüm üretmez.")
    print("\nDOLULUK (lig × alan, yalnız bitmiş maçlar)")
    d = SDB.doluluk()
    if not d:
        print("  henüz veri yok")
        return
    print(f"  {'lig':10} {'n':>5} {'ilk yarı':>9} {'şut':>7} {'korner':>7} "
          f"{'oynanabilir':>12}")
    for x in d:
        print(f"  {str(x['lig']):10} {x['n']:5} {x['iy_ev']*100:8.1f}% "
              f"{x.get('sut_ev', 0)*100:6.1f}% {x.get('korner_ev', 0)*100:6.1f}% "
              f"{'EVET' if x['oynanabilir'] else 'hayır':>12}")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    _uretim_korumasi()
    if "--durum" in sys.argv:
        durum()
    else:
        print(calistir())
