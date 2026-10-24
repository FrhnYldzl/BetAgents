"""
VIBE BET · STÜDYO — bağlamı BESTELE, sonra sor
===============================================
Boş bir sohbet kutusu iyi bir geliştirme aracı değil: her seferinde "şu
tabloya bak, şu ajana bak" diye anlatmak gerekiyor, cevaplar tekrarlanabilir
olmuyor ve asistan turlarının çoğu veri aramaya gidiyor.

Stüdyo bunu tersine çevirir: ÖNCE ne göreceğini seçersin (kapsam · alan ·
bağlam kutuları), sonra sorarsın. Asistan soruyla birlikte GERÇEK VERİYİ
alır. Üç kazanç:
  • tekrarlanabilir — aynı seçim aynı bağlamı üretir
  • hızlı — veri aramak için tur harcanmaz
  • dürüst — asistanın neye baktığı ekranda yazılı, tahmin edilmiyor

KAPSAM takımı/ürünü, ALAN ise soruyu daraltır. ALAN aynı zamanda bağlam
kutularını ÖN SEÇER — "Veri sağlığı" seçince bakım raporu kendiliğinden
gelir. Seçimler elle değiştirilebilir; ön seçim öneridir, kilit değil.

⚠️ Bu modül yalnız OKUR. Hiçbir tabloya yazmaz; yazma işleri vibe_arac'taki
geri bildirim/istek araçlarında kalır.
"""
from __future__ import annotations

KAPSAM = {
    "tum": "Tüm sistem",
    "mavi": "Mavi (sinyal motoru)",
    "kirmizi": "Kırmızı (kombine korelasyon)",
    "turuncu": "Turuncu (bağımsız skor modeli)",
    "toto": "Toto (Süper Toto modeli × iddaa)",
    "sistem": "Sistem (N/M kuponları)",
    "canli": "Canlı",
    "supertoto": "Süper Toto (kolon oyunu)",
}

# ALAN → (açıklama, ön seçili bağlam kutuları)
ALAN = {
    "genel": ("Genel", ("lig", "acik")),
    "performans": ("Performans", ("lig", "son_bahis", "karne")),
    "kenar": ("Kenar ve CLV", ("lig", "son_bahis", "defter")),
    "veri": ("Veri sağlığı", ("bakim", "sayim")),
    "model": ("Model ve kalibrasyon", ("defter", "toto_pazar")),
    "kupon": ("Kupon ve sepet", ("acik", "son_bahis")),
    "bakim": ("Bakım ve onarım", ("bakim", "sayim")),
}

# Bağlam kutuları: anahtar → (etiket, üretici adı)
BAGLAM = {
    "lig":        "Ajan performans tablosu",
    "acik":       "Açık pozisyonlar",
    "son_bahis":  "Son kapanan bahisler",
    "karne":      "Ajan karneleri (ciro bazlı)",
    "bakim":      "Haftalık Bakım raporu",
    "sayim":      "Veri sayımı (maç · bahis · kapsam)",
    "defter":     "Ölçüm defteri bulguları",
    "toto":       "Toto · bu haftanın analizi",
    "toto_pazar": "Toto · ajan pazarı cüzdanları",
    "canli":      "Canlı · toplayıcı durumu",
}

# KAPSAM → hangi ajanlar (panel tarafındaki setlerle AYNI olmalı)
KAPSAM_AJAN = {
    "mavi": None,          # None = "diğerlerinin dışında kalanlar"
    "kirmizi": {"CARPAN_V1", "SIMETRI_V1", "KAVSAK_V1", "BANT_V1", "DEVRE_V1"},
    "turuncu": {"TEMEL_V1", "DAR_V1", "GENIS_V1", "GOLBANT_V1", "HARMAN_V1"},
    "toto": {"TOTOCU_V1", "AYKIRI_V1", "TOTO_KONTROL_V1"},
    "sistem": {"KALDIRAC_V1", "SIGORTA_V1", "SISTEM_JOKER_V1"},
}


def on_secim(alan: str) -> tuple:
    return ALAN.get(alan, ALAN["genel"])[1]


def _kirp(s: str, n: int = 2600) -> str:
    s = str(s)
    return s if len(s) <= n else s[:n] + f"\n… (kırpıldı, {len(s)} karakter)"


def _blok(baslik: str, govde) -> str:
    return f"\n### {baslik}\n{_kirp(govde)}\n"


def _diger_takimlar() -> set:
    k = set()
    for _ad, v in KAPSAM_AJAN.items():
        if v:
            k |= v
    return k


def _sz_ajan(satirlar: list, kapsam: str, alan: str = "ajan") -> list:
    """Ajan satırlarını kapsama göre süz — PID eşleşmesi, bulanık ad DEĞİL.

    İlk hâlinde ad içinde alt dizi arıyordum ("TOTO" geçiyor mu gibi). O
    yöntem hem TOTOCU'yu hem TOTO_KONTROL'ü hem de alakasız bir adı
    yakalayabiliyordu. Kimlik eşleşmesi tek doğru yol.
    'mavi' = diğer takımların DIŞINDA kalanlar; elle liste tutulmaz ki yeni
    Mavi ajanı eklenince burayı güncellemek unutulmasın.
    """
    if kapsam in ("tum", "canli", "supertoto"):
        return satirlar
    if kapsam == "mavi":
        dis = _diger_takimlar() | {"PAPER_V1", "OPUS5_V1", "KURUCU_V2"}
        return [r for r in satirlar if str(r.get(alan)) not in dis]
    kume = KAPSAM_AJAN.get(kapsam) or set()
    return [r for r in satirlar if str(r.get(alan)) in kume]


def _tablo(satirlar: list, sutunlar: list) -> str:
    """Sözlük listesini okunur tabloya çevir.

    Ham dict dökmek yerine tablo: hem asistana daha az jeton gider, hem de
    bağlamda ne gittiği ekranda GÖZLE kontrol edilebilir — stüdyonun bütün
    amacı bu.
    """
    if not satirlar:
        return "(kayıt yok)"
    bas = " | ".join(sutunlar)
    out = [bas, "-" * len(bas)]
    for r in satirlar:
        h = []
        for c in sutunlar:
            v = r.get(c)
            h.append(f"{v:.3f}" if isinstance(v, float)
                     else ("—" if v is None else str(v)))
        out.append(" | ".join(h))
    return "\n".join(out)


def baglam_metni(kapsam: str, alan: str, kutular) -> str:
    """Seçilen kutuları GERÇEK veriyle doldur ve tek metin olarak döndür.

    Her blok kendi try'ı içinde: biri patlarsa diğerleri yine gelir ve
    hatanın kendisi bağlama YAZILIR. Sessizce eksik bağlam, asistanı
    bilmediği şey hakkında konuşturur — en tehlikeli hâli budur.
    """
    import vibe_arac as VA
    parcalar = [f"## SEÇİM\nKapsam: {KAPSAM.get(kapsam, kapsam)} · "
                f"Alan: {ALAN.get(alan, ('?',))[0]}"]

    def _lig():
        d = VA.iddaa_ajan_performansi(40)
        sat = _sz_ajan(d.get("ajanlar") or [], kapsam)
        return (_tablo(sat, ["ajan", "kupon", "kazanan", "isabet",
                             "yatan", "donen", "donus_tl"])
                + "\n" + str(d.get("not", "")))

    uretici = {
        "lig": _lig,
        "acik": lambda: VA.iddaa_bahisler("acik", 30),
        "son_bahis": lambda: VA.iddaa_bahisler("kapanmis", 30),
        "karne": lambda: _karne(kapsam),
        "sayim": lambda: VA.iddaa_ozet(),
        "toto": lambda: VA.toto_bu_hafta(),
        "toto_pazar": lambda: VA.toto_ajan_pazari(),
        "bakim": _bakim,
        "defter": _defter,
        "canli": _canli,
    }
    for k in kutular:
        if k not in BAGLAM or k not in uretici:
            continue
        try:
            parcalar.append(_blok(BAGLAM[k], uretici[k]()))
        except Exception as e:
            parcalar.append(_blok(BAGLAM[k],
                                  f"(bu blok alınamadı: {type(e).__name__}: {e})"))
    return "\n".join(parcalar)


# ----------------------------------------------------------------------
# Özel bloklar — vibe_arac'ta karşılığı olmayanlar
# ----------------------------------------------------------------------
def _karne(kapsam: str = "tum") -> str:
    """Ciro bazlı karne. ⚠️ Kasa alanlarından DEĞİL — o alanlar kadro dışı
    devirleriyle bozuluyor (ölçüldü 24.10.2026: EUVOX +232 TL kârdayken
    defterde -%100 görünüyordu)."""
    import vibe_arac as VA
    r = VA._sorgu(
        "SELECT portfolio_id, COUNT(*), COALESCE(SUM(stake),0), "
        "COALESCE(SUM(actual_return),0) FROM paper_coupons "
        "WHERE status NOT IN ('open') GROUP BY portfolio_id "
        "ORDER BY 2 DESC")
    satirlar = []
    for pid, n, ya, do in r:
        ya = float(ya or 0); do = float(do or 0)
        satirlar.append({"ajan": pid, "kupon": n, "yatan": round(ya),
                         "donen": round(do),
                         "donus_tl": round(do / ya, 3) if ya else None})
    return _tablo(_sz_ajan(satirlar, kapsam),
                  ["ajan", "kupon", "yatan", "donen", "donus_tl"])


def _bakim() -> str:
    import sys
    from pathlib import Path
    p = str(Path(__file__).resolve().parent.parent / "11_BAKIM")
    if p not in sys.path:
        sys.path.append(p)
    import bakim_kontrol as BK
    r = BK.kos()
    sat = [f"kırmızı {r['kirmizi']} · sarı {r['sari']} · yeşil {r['yesil']} "
           f"· {r['bahis']} bahis"]
    for k in r["kontroller"]:
        sat.append(f"[{k['durum']}] {k['id']}: {k['ad']} = {k['deger']}")
        for o in (k.get("ornek") or [])[:3]:
            sat.append(f"    · {o}")
    return "\n".join(sat)


def _defter() -> str:
    import vibe_arac as VA
    r = VA._sorgu("SELECT * FROM measurement_runs ORDER BY rowid DESC LIMIT 12")
    if not r:
        return "(ölçüm defteri boş)"
    return "\n".join(" | ".join(str(x)[:90] for x in satir) for satir in r)


def _canli() -> str:
    import sys
    from pathlib import Path
    p = str(Path(__file__).resolve().parent.parent / "10_CANLI")
    if p not in sys.path:
        sys.path.append(p)
    import canli_db
    return str(canli_db.sayim())


def kendi_testi() -> list[str]:
    """Seçenek sözlükleri tutarlı mı."""
    hata = []
    for a, (ad, kutu) in ALAN.items():
        for k in kutu:
            if k not in BAGLAM:
                hata.append(f"ALAN '{a}' tanımsız bağlam kutusu istiyor: {k}")
    for k in KAPSAM_AJAN:
        if k not in KAPSAM:
            hata.append(f"KAPSAM_AJAN'da olup KAPSAM'da olmayan: {k}")
    return hata


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8")
    h = kendi_testi()
    print("kendi testi:", "TEMİZ" if not h else h)
    print(f"\nkapsam {len(KAPSAM)} · alan {len(ALAN)} · bağlam kutusu {len(BAGLAM)}")
    for a, (ad, kutu) in ALAN.items():
        print(f"  {ad:22} ön seçim: {', '.join(BAGLAM[k] for k in kutu)}")
