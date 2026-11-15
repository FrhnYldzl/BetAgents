"""
DENETÇİ — kupon oynanmadan ÖNCEKİ son kapı
============================================
Kullanıcı (15.11.2026): *"İki ajan birbiriyle çelişen maçlar tahminliyor
ama isabet oranı iyiyse ve üst üste kazanma trendi iyiyse ben kupona
koyuyorum — çelişkili bir iş yapmış oluyorum. O yüzden ayrı bir katman
bunları analiz etsin."*

Kupon Master KURAR, Denetçi ONAYLAR ya da REDDEDER, Finans Ajanı parayı
yönetir. Üç ayrı kafa, üç ayrı sorumluluk.

NE ÖLÇÜLDÜ, NE ÖLÇÜLMEDİ
-------------------------
"Ajanlar bir maçta çelişiyorsa o maç kötüdür" hipotezi ölçüldü
(15.11.2026, 4.157 bahis). Ham fark büyük görünüyordu — çelişkili
maçlarda −%21,6, tek ajanlı maçlarda −%13,3. Ama AYNI FİYAT BANDINDA
karşılaştırılınca eridi:

    oran 1,00-1,35   çelişkili −%14,3  ·  çelişkisiz −%12,0   (−2,3p)
    oran 1,35-1,80   çelişkili −%17,3  ·  çelişkisiz −%11,6   (−5,7p)
    oran 3,00+       çelişkili −%42,6  ·  çelişkisiz −%48,8   (+6,3p ters)

Yani ham sinyal büyük ölçüde FİYAT BANDI ARTEFAKTIYDI: çelişkili maçlarda
uzun oranlı ajanlar daha çok bulunuyordu ve kaybeden onlardı.

Bu yüzden çelişki burada RED sebebi DEĞİL, UYARI'dır. Kesin red yalnız
aritmetik olarak yanlış olan şeye verilir (aynı maçtan iki ayak).
Ölçülmemiş bir hipotezi kural hâline getirmek, bu projede üç kez yapılan
hatanın dördüncüsü olurdu.
"""
from __future__ import annotations

import sys
from collections import Counter, defaultdict
from pathlib import Path

THIS_DIR = Path(__file__).resolve().parent
if str(THIS_DIR) not in sys.path:
    sys.path.insert(0, str(THIS_DIR))

RED, UYARI, NOT = "RED", "UYARI", "NOT"

# Tek ajandan bir kuponda en çok kaç ayak (kupon_master ile aynı)
AJAN_AYAK_TAVAN = 2
# Aynı ligden bir kuponda en çok kaç ayak
LIG_AYAK_TAVAN = 2
# Kanıt eşiği — altındaki ajan "deneysel" sayılır
ASGARI_N = 30
# Bu uzunlukta seri "trend" sanılmaya başlanıyor
SERI_UYARI = 4

# Aynı pazarda zıt seçimler — ikisi birden KAZANAMAZ
_ZIT_PAZAR = ({"ALT_25", "UST_25"}, {"KG_VAR", "KG_YOK"})


def _zit(a: dict, b: dict) -> bool:
    """İki ayak aynı maçta birbirini çürütüyor mu?"""
    if str(a.get("mac_id")) != str(b.get("mac_id")):
        return False
    ma, mb = str(a.get("market") or ""), str(b.get("market") or "")
    pa, pb = str(a.get("pick") or "").upper(), str(b.get("pick") or "").upper()
    if ma == mb:
        return pa != pb
    return {ma, mb} in _ZIT_PAZAR


def denetle(kupon: dict, havuz: list[dict] | None = None,
            karneler: dict | None = None,
            seriler: dict | None = None) -> dict:
    """Bir kuponu denetle.

    kupon   : kupon_master.uret() çıktısındaki sözlük
    havuz   : o günün BÜTÜN adayları — çelişkiyi görmek için
    karneler: {ajan: kasa karnesi} — kanıt seviyesi için
    seriler : {ajan: ardışık kazanç sayısı} — seri uyarısı için
    """
    ayak = kupon.get("ayaklar") or []
    bulgu = []
    havuz = havuz or []
    karneler = karneler or {}
    seriler = seriler or {}

    # ── 1) ARİTMETİK RED: aynı maçtan iki ayak ───────────────────────
    # Bu bir hipotez değil: aynı maçın iki sonucu bağımsız değildir ve
    # çoğu birbirini dışlar. Çarpım kuralı orada yalan söyler.
    for i in range(len(ayak)):
        for j in range(i + 1, len(ayak)):
            if str(ayak[i].get("mac_id")) == str(ayak[j].get("mac_id")):
                tur = "çelişen" if _zit(ayak[i], ayak[j]) else "bağımlı"
                bulgu.append({
                    "tur": "ayni_mac", "seviye": RED,
                    "mesaj": f"Aynı maçtan iki ayak ({tur}): "
                             f"{ayak[i].get('pick')} + {ayak[j].get('pick')}. "
                             f"Çarpım kuralı burada geçersiz."})

    # ── 2) HAVUZDA ÇELİŞKİ: ajanlarımız bu maçta anlaşamıyor ─────────
    mac_gorus = defaultdict(list)
    for a in havuz:
        mac_gorus[str(a.get("mac_id"))].append(a)
    gorulen_mac = set()
    for a in ayak:
        if str(a.get("mac_id")) in gorulen_mac:
            continue
        gorulen_mac.add(str(a.get("mac_id")))
        digerleri = [x for x in mac_gorus.get(str(a.get("mac_id")), [])
                     if x.get("ajan") != a.get("ajan")]
        celisen = [x for x in digerleri if _zit(a, x)]
        if celisen:
            kim = ", ".join(sorted({str(x.get("ajan", "")).split("_")[0]
                                    for x in celisen})[:3])
            bulgu.append({
                "tur": "havuz_celiski", "seviye": UYARI,
                "mesaj": f"{str(a.get('ajan','')).split('_')[0]} "
                         f"'{a.get('pick')}' derken {kim} tersini diyor. "
                         f"Ölçüldü: bu fark aynı fiyat bandında küçülüyor "
                         f"(−2 … −6 puan), yani red sebebi değil — ama "
                         f"ajanlarımız bu maçta anlaşmıyor."})

    # ── 3) YOĞUNLAŞMA ────────────────────────────────────────────────
    say = Counter(str(a.get("ajan") or "") for a in ayak)
    for ajan, n in say.items():
        if n > AJAN_AYAK_TAVAN:
            bulgu.append({
                "tur": "ajan_yogunlasma", "seviye": RED,
                "mesaj": f"{ajan.split('_')[0]} kuponun {n} ayağını "
                         f"taşıyor (tavan {AJAN_AYAK_TAVAN}). Ajan "
                         f"yanılırsa kupon {n} kat yanılır."})
    lig = Counter(str((a.get("_match") or {}).get("league_code") or "?")
                  for a in ayak)
    for kod, n in lig.items():
        if kod not in ("?", "ALL", "") and n > LIG_AYAK_TAVAN:
            bulgu.append({
                "tur": "lig_yogunlasma", "seviye": UYARI,
                "mesaj": f"{n} ayak aynı ligden ({kod}) — lig çapında bir "
                         f"sürpriz kuponun tamamını götürür."})

    # ── 4) KANIT SEVİYESİ ────────────────────────────────────────────
    zayif = []
    for a in ayak:
        k = karneler.get(a.get("ajan")) or {}
        if not k.get("yeterli"):
            zayif.append(f"{str(a.get('ajan','')).split('_')[0]}"
                         f"(n={int(k.get('n') or 0)})")
    if zayif:
        bulgu.append({
            "tur": "kanit", "seviye": UYARI,
            "mesaj": f"Kanıt eşiğini (n≥{ASGARI_N}) geçmeyen ajan: "
                     f"{', '.join(zayif)}. Bu ayakların olasılığı piyasanın "
                     f"marjsız fiyatıdır — ajanın iddiası sayılmaz."})

    # ── 5) SERİ YANILGISI ────────────────────────────────────────────
    # Kullanıcı: "üst üste kazanma trendi iyiyse kupona koyuyorum."
    # 5 maç kazanan ajanın 6.'yı kazanma olasılığı DEĞİŞMEZ. Seri bir
    # gerekçe değil, gerekçe sanılan bir örüntüdür.
    # Ajan başına BİR kez uyar: aynı ajanın iki ayağı varsa uyarı iki kez
    # basılıyordu ve bulgu listesini gürültüye boğuyordu.
    for ajan in sorted({str(a.get("ajan") or "") for a in ayak}):
        a = {"ajan": ajan}
        s = int(seriler.get(ajan) or 0)
        if s >= SERI_UYARI:
            bulgu.append({
                "tur": "seri", "seviye": NOT,
                "mesaj": f"{str(a.get('ajan','')).split('_')[0]} "
                         f"{s} maçtır kazanıyor. Bu bir GEREKÇE DEĞİL: "
                         f"serinin sonraki maçın olasılığına etkisi yok. "
                         f"Kanıt n ve kenardır, seri değil."})

    red = [b for b in bulgu if b["seviye"] == RED]
    return {"onay": not red, "bulgular": bulgu,
            "red": len(red),
            "uyari": sum(1 for b in bulgu if b["seviye"] == UYARI),
            "not": sum(1 for b in bulgu if b["seviye"] == NOT)}


def seri_haritasi(conn=None) -> dict:
    """{ajan: ardışık kazanç sayısı} — son bahislerden."""
    import db
    kapat = conn is None
    conn = conn or db.connect()
    try:
        r = conn.execute(
            "SELECT portfolio_id, status FROM paper_bets "
            "WHERE status IN ('won','lost') "
            "ORDER BY COALESCE(settled_at, bet_id) DESC").fetchall()
    except Exception:
        return {}
    finally:
        if kapat:
            conn.close()
    out, bitti = {}, set()
    for pid, st in r:
        if pid in bitti:
            continue
        if st == "won":
            out[pid] = out.get(pid, 0) + 1
        else:
            bitti.add(pid)
    return out


def kendi_testi() -> list[str]:
    hata = []

    def ay(ajan, mac, market="1X2", pick="1", lig="T1"):
        return {"ajan": ajan, "mac_id": mac, "market": market, "pick": pick,
                "oran": 1.3, "_match": {"league_code": lig}}

    # 1) Aynı maçtan iki ayak RED olmalı — çelişsin ya da çelişmesin
    k = {"ayaklar": [ay("A_V1", 1, "1X2", "1"), ay("B_V1", 1, "1X2", "2")]}
    r = denetle(k)
    if r["onay"]:
        hata.append("aynı maçtan çelişen iki ayak onaylandı")
    k2 = {"ayaklar": [ay("A_V1", 1, "1X2", "1"), ay("B_V1", 1, "ALT_25", "ALT")]}
    r2 = denetle(k2)
    if r2["onay"]:
        hata.append("aynı maçtan BAĞIMLI iki ayak onaylandı "
                    "(çarpım kuralı geçersiz)")
    # 2) Farklı maçlar onaylanmalı
    k3 = {"ayaklar": [ay("A_V1", 1), ay("B_V1", 2)]}
    if not denetle(k3)["onay"]:
        hata.append("farklı maçlardan iki ayak reddedildi")
    # 3) Tek ajan tavanı RED
    k4 = {"ayaklar": [ay("A_V1", i) for i in range(1, 4)]}
    if denetle(k4)["onay"]:
        hata.append("tek ajandan 3 ayak onaylandı")
    # 4) Havuz çelişkisi UYARI olmalı, RED DEĞİL
    hav = [ay("C_V1", 1, "1X2", "2")]
    k5 = {"ayaklar": [ay("A_V1", 1, "1X2", "1"), ay("B_V1", 2)]}
    r5 = denetle(k5, havuz=hav)
    if not r5["onay"]:
        hata.append("havuz çelişkisi RED sebebi oldu — ölçüm bunu "
                    "desteklemiyor, UYARI olmalı")
    if not any(b["tur"] == "havuz_celiski" for b in r5["bulgular"]):
        hata.append("havuz çelişkisi yakalanmadı")
    # 5) Kanıtsız ajan UYARI
    r6 = denetle(k3, karneler={"A_V1": {"n": 5, "yeterli": False},
                               "B_V1": {"n": 99, "yeterli": True}})
    if not any(b["tur"] == "kanit" for b in r6["bulgular"]):
        hata.append("kanıtsız ajan uyarısı yok")
    # 6) Seri NOT olmalı, onayı düşürmemeli
    r7 = denetle(k3, seriler={"A_V1": 6})
    if not r7["onay"]:
        hata.append("seri uyarısı kuponu reddetti — seri gerekçe değil "
                    "ama red sebebi de değil")
    if not any(b["tur"] == "seri" for b in r7["bulgular"]):
        hata.append("seri uyarısı yok")
    # 7) Lig yoğunlaşması UYARI
    k8 = {"ayaklar": [ay(f"A{i}_V1", i, lig="E0") for i in range(1, 4)]}
    r8 = denetle(k8)
    if not any(b["tur"] == "lig_yogunlasma" for b in r8["bulgular"]):
        hata.append("lig yoğunlaşması yakalanmadı")
    return hata


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    h = kendi_testi()
    print("kendi testi:", "TEMİZ" if not h else f"{len(h)} sorun")
    for x in h:
        print("  ", x)
