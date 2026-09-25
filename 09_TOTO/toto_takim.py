"""
TOTO TAKIM — adlandırılmış Toto ajanları, güçlü/orta kupon paketleri
=====================================================================
BetAgents'taki ajan standardının Toto'ya taşınmış hâli: her ajanın İLAN
EDİLMİŞ bir hipotezi, ön kayıtlı bir emeklilik kuralı ve zorunlu bir
rastgele kontrolü (TOTO JOKER) var. Hipotez önce yazılır, sonra ölçülür —
"iyi görünen kuponu sonradan açıklamak" yasak.

Ajan nedir
----------
Toto'da bir profil, aynı P üzerinde farklı bir AMAÇ FONKSİYONUDUR:
  FAVORİ      en yüksek P'yi al, bütçeyi sırayla genişlet
  15_AVCISI   P(15) × havuz payını maksimize et
  DENGELİ     kademeler arası beklenen değeri maksimize et
TOTO TAKIM ajanları buna bir AĞIRLIK ekler: bütçeyi hangi maçlarda
harcayacağını çeyrek konumuna göre fiyatlar (yasaklamaz, tercih eder).

Ama bir ajanı ajan yapan asıl şey KUPON KURMASI DEĞİL, SİCİL TUTMASIDIR.
Mavi/Kırmızı/Turuncu takımlarda her ajanın kasası ve karnesi var; burada da
öyle: ajanlar her hafta kuponlarını `toto_kupon` defterine yazar, haftalık
kapanış onları derecelendirir, `karne()` birikmiş sicili verir. İlk hâlinde
bu yoktu — her hafta sıfırdan hesaplanan dört tarifti, hafızası yoktu ve
"hangi ajan iyi" sorusu sorulamıyordu.

Sicil iki yerden okunur ve KARIŞTIRILMAZ:
  karne()         canlı defter — haftada bir satır büyür, gerçek sicil
  gecmis_karne()  166 haftalık geri test (geri_test.calis ile AYNI sızıntısız
                  protokol, cikti='geri_test_takim') — canlı defter dolana
                  dek referans verir, onun yerine GEÇMEZ

Çeyrek (toto_panel ile aynı eşikler)
-------------------------------------
    güç      = P[favorimiz]                       — ne kadar biliyoruz
    kaldıraç = P[favorimiz] / Q[favorimiz]        — kalabalık oraya ne kadar yığılmış

    BANKO             güç ≥ 0,55 · kaldıraç ≥ 1   biliyoruz + kalabalık az oynuyor
    KALABALIK FAVORİ  güç ≥ 0,55 · kaldıraç < 1   biliyoruz ama herkes orada
    FIRSAT            güç < 0,55 · kaldıraç ≥ 1   belirsiz ama kalabalık yanlış yerde
    KARANLIK          güç < 0,55 · kaldıraç < 1   ne bilgi ne fırsat

Kaldıraç 1'in ALTINDA olmak, o sonucu bilmenin para kazandırmadığı demektir:
ikramiye paylaşıldığı için kalabalıkla aynı yere oynamak payı böler.

Paketler
--------
GÜÇLÜ  32 kolon  — az kolon, yalnız en sağlam yapı
ORTA  256 kolon  — geniş; 12+ kademesini yakalamak için

Ölçülen taban çizgileri (166 hafta, 25.09.2026 · haftalar üzerinden önyükleme)
------------------------------------------------------------------------------
    profil        bütçe  dönüş/TL   %95 aralık    ödeyen hafta
    FAVORİ          256     0,83   [0,29-1,67]        73/166
    KALABALIK        32     0,54   [0,21-1,03]        37
    FAVORİ           32     0,43   [0,21-0,73]        39
    DENGELİ         256     0,08   [0,00-0,20]        10
    TOTO JOKER       32     0,00   [0,00-0,00]         0

Okuma: JOKER 166 haftanın hiçbirinde ödeme almadı — model BİLGİ TAŞIYOR
(iddaa tarafında JOKER çoğu ajanı geçiyordu, burada tersi). Ama kimse
başabaşı (1,00) geçmiyor; en iyisi lira başına 17 kuruş kayıp. Üstelik
FAVORİ@256'nın getirisinin %53'ü 166 haftanın 2'sinden geliyor.

⚠️ Bu yüzden hiçbir ajan "kârlı" diye ilan EDİLEMEZ. Ajanların işi şu an
kâr üretmek değil, hipotezlerini ölçülebilir kılmak.
"""
from __future__ import annotations

import math

import numpy as np

from deger import Degerlendirici, boyut, kur

# toto_panel.GX / GY ile AYNI olmalı — sapmayı kendi_testi() yakalar.
GX, GY = 0.55, 1.00
SEC = ("1", "0", "2")

GUCLU, ORTA = 32, 256


# ----------------------------------------------------------------------
# ÇEYREK
# ----------------------------------------------------------------------
def ceyrekler(P, Q) -> list[dict]:
    """Her maç için güç, kaldıraç ve çeyrek adı."""
    P, Q = np.asarray(P, float), np.asarray(Q, float)
    out = []
    for i in range(len(P)):
        f = int(np.argmax(P[i]))
        guc = float(P[i][f])
        kal = float(P[i][f] / max(Q[i][f], 1e-9))
        ad = ("BANKO" if kal >= GY else "KALABALIK FAVORİ") if guc >= GX \
            else ("FIRSAT" if kal >= GY else "KARANLIK")
        out.append({"i": i, "fav": f, "isaret": SEC[f], "guc": guc,
                    "kaldirac": kal, "ceyrek": ad})
    return out


# ----------------------------------------------------------------------
# AJANLAR — hipotez önce, ölçüm sonra
# ----------------------------------------------------------------------
# `agirlik(c)` → bu maçta bütçe harcamanın çekiciliği.
#   0    yasak (bu maça hiç dokunma)
#   1    nötr
#   >1   tercih et — kazanç oranı bu katsayıyla çarpılır
# SERT maske (0/1) yerine ağırlık kullanmanın sebebi POLLY'de ortaya çıktı:
# "kaldıraç < 1 olana hiç dokunma" kuralı, BANKO'nun boş olduğu haftalarda
# tam olarak FIRSAT maçlarına denk düşüyor ve POLLY ile FIRSATÇI BİREBİR AYNI
# kuponu üretiyordu (7. Hafta 2026/27'de yakalandı). Üstelik yalnız 2 maça
# izin kalınca en çok 9 kolon kurulabiliyor ve ORTA paketi GÜÇLÜ ile aynı
# oluyordu — bütçe kullanılamıyordu. Ağırlık, tercihi korur ama yolu kapatmaz.
TAKIM: dict[str, dict] = {
    "OMURGA": {
        "ad": "OMURGA",
        "hipotez":
            "Kuponun omurgası yalnız BANKO maçlarıdır. Bildiğimiz VE kalabalığın "
            "az oynadığı maçta tek işaret bırakmak, bütçeyi bilmediğimiz maçlara "
            "kaydırır. KALABALIK FAVORİ'de tek işaret bırakmak ise sahte güven: "
            "orada bilmek para kazandırmıyor, çünkü ikramiye bölünüyor.",
        "agirlik": lambda c: 0.0 if c["ceyrek"] == "BANKO" else 1.0,
        "emeklilik":
            "60 hafta sonra: BANKO maçlarındaki isabet, aynı GÜÇ bandındaki "
            "BANKO-olmayan maçlardan yüksek değilse çeyrek ayrımı bilgi taşımıyor "
            "demektir — ajan kapanır.",
    },
    "POLLY": {
        "ad": "POLLY",
        "hipotez":
            "Ortak yol: FAVORİ saf güce, FIRSATÇI saf kaldıraca bakıyor. POLLY "
            "beklenen değeri maksimize eder ama her maçı KALDIRACIYLA fiyatlar: "
            "kalabalığın bizden çok yığıldığı maçta genişlemek cazibesini yitirir, "
            "az yığıldığı maçta artar. Yasak koymaz — o yol FIRSATÇI'nın. "
            "Gerekçe: kalabalıkla aynı yere ikinci işaret koymak kolon maliyetini "
            "artırırken ikramiye payını böler; iki yönden birden kaybettirir. Ama "
            "bazı haftalarda yüksek kaldıraçlı maç yoktur ve o zaman da oynanmalı.",
        # Ortak yol: kaldıraç YASAKLAMAZ, fiyatlandırır. 1'in altındaki her maç
        # kaldıracı oranında cazibesini yitirir; 1'in üstü ödüllendirilir.
        "agirlik": lambda c: float(min(2.0, max(0.15, c["kaldirac"] ** 1.5))),
        "emeklilik":
            "60 hafta sonra: POLLY'nin dönüş/TL'si DENGELİ'yi geçmiyorsa kaldıraç "
            "tabanı bilgi taşımıyor demektir — ajan kapanır.",
    },
    "FIRSATÇI": {
        "ad": "FIRSATÇI",
        "hipotez":
            "Getiriyi FIRSAT çeyreği taşır: kalabalığın yanlış yerde olduğu "
            "belirsiz maçlar. Belirsizlik ucuza alınır, kalabalık hatası ise "
            "ikramiye payını büyütür. Bütçe oraya yığılmalı.",
        "agirlik": lambda c: 1.0 if c["ceyrek"] == "FIRSAT" else 0.0,
        "emeklilik":
            "60 hafta sonra: FIRSAT'a yığılan bütçenin dönüş/TL'si FAVORİ'yi "
            "geçmiyorsa çeyrek hedeflemesi işe yaramıyor — ajan kapanır.",
    },
    "TOTO JOKER": {
        "ad": "TOTO JOKER",
        "hipotez":
            "Hipotez YOK — rastgele kontrol. Diğer ajanlar bunu geçemiyorsa "
            "hiçbiri bilgi taşımıyor demektir. Ölçüldü (166 hafta): JOKER "
            "dönüş/TL = 0,00, hiçbir haftada ödeme almadı.",
        "agirlik": None,       # özel: rastgele
        "emeklilik": "Kapanmaz — kontrol çizgisidir.",
    },
}


# ----------------------------------------------------------------------
# KUPON KURMA
# ----------------------------------------------------------------------
def _joker(P, butce: int, tohum: int):
    """Rastgele sistem kuponu — bütçeyi rastgele maçlara rastgele dağıt."""
    rnd = np.random.default_rng(tohum)
    S = [(int(rnd.integers(0, 3)),) for _ in range(len(P))]
    while boyut(S) * 2 <= butce:
        i = int(rnd.integers(0, len(S)))
        if len(S[i]) == 3:
            continue
        kalan = [o for o in range(3) if o not in S[i]]
        S[i] = tuple(sorted(S[i] + (int(rnd.choice(kalan)),)))
    return S


def _agirlikli(P, Q, N, havuz, butce: int, agirlik, deg) -> list:
    """Beklenen değeri maksimize et; genişleme kazancını ajanın ağırlığıyla tart.

    deger.kur()'un açgözlü döngüsünün ağırlıklı hâli: her adımda kolon başına
    en çok değer katan genişlemeyi seç (log-boy başına kazanç), ama kazancı
    ajanın o maça verdiği ağırlıkla çarp. Ağırlık 0 ise o maç hiç genişlemez.

    ⚠️ Ağırlık YALNIZ SIRALAMAYI değiştirir; "gerçekten değer katıyor mu"
    kararı (en[2] > v) ham EV üzerinden verilir. Aksi hâlde ağırlık, değer
    katmayan bir genişlemeyi de kupona sokabilirdi.
    """
    P = np.asarray(P, float)
    C = ceyrekler(P, Q)
    W = [float(agirlik(c)) for c in C]
    S = [(int(np.argmax(P[i])),) for i in range(len(P))]
    deg.hazirla(S)
    v = deg.ev(S)
    while True:
        en = None
        for i in range(len(S)):
            if len(S[i]) == 3 or W[i] <= 0.0:
                continue
            if boyut(S) // len(S[i]) * (len(S[i]) + 1) > butce:
                continue
            for o in range(3):
                if o in S[i]:
                    continue
                T = list(S)
                T[i] = tuple(sorted(S[i] + (o,)))
                vt = deg.ev(T)
                oran = W[i] * (vt - v) / math.log((len(S[i]) + 1) / len(S[i]))
                if en is None or oran > en[0]:
                    en = (oran, T, vt)
        if en is None or en[2] <= v:
            break
        S, v = en[1], en[2]
        deg.hazirla(S)
        v = deg.ev(S)
    return S


def kupon(ajan: str, P, Q, N, havuz: dict, butce: int,
          deg: Degerlendirici | None = None, tohum: int = 0) -> list:
    """Bir ajanın bu bütçedeki sistem kuponu."""
    a = TAKIM[ajan]
    if a["agirlik"] is None:
        return _joker(P, butce, tohum)
    deg = deg or Degerlendirici(P, Q, N, havuz)
    return _agirlikli(P, Q, N, havuz, butce, a["agirlik"], deg)


def paketler(A: dict, tohum: int | None = None) -> list[dict]:
    """Haftanın GÜÇLÜ ve ORTA paketleri — her ajan için.

    A: canli.analiz() çıktısı (P, Q, N_tahmin, havuz, maclar, fiyat).
    """
    P = np.asarray(A["P"], float)
    Q = np.asarray(A["Q"], float)
    N = A["N_tahmin"]
    # JSON'dan okunan analizde kademe anahtarları metin ("13") olur; Degerlendirici
    # sayı bekliyor ve aradaki fark KeyError olarak patlıyordu.
    havuz = {int(k): float(v) for k, v in A["havuz"].items()}
    fiyat = A["fiyat"]
    tohum = tohum if tohum is not None else int(A["hafta"]["id"])
    C = ceyrekler(P, Q)
    deg = Degerlendirici(P, Q, N, havuz, M=16000, tohum=tohum)
    olcer = Degerlendirici(P, Q, N, havuz, M=60000, tohum=tohum + 1)

    out = []
    for ad, a in TAKIM.items():
        for paket, B in (("GÜÇLÜ", GUCLU), ("ORTA", ORTA)):
            S = kupon(ad, P, Q, N, havuz, B, deg, tohum + B)
            kol = boyut(S)
            r = olcer.degerle(S)
            maliyet = kol * fiyat
            out.append({
                "ajan": ad, "paket": paket, "butce": B, "kolon": kol,
                "maliyet": maliyet,
                "isaret": [" ".join(SEC[j] for j in x) for x in S],
                "S": [list(map(int, x)) for x in S],
                "ev_tl": r["ev"] / maliyet if maliyet else 0.0,
                # EV'nin ne kadarı 15 kademesinden (yani milyonda bir olasılıklı
                # bir olaydan) geliyor. Yüksekse EV sıralama için kullanılamaz:
                # TOTO JOKER'in EV'sinin yarısı oradan geliyor ama 166 haftalık
                # gerçek ölçümde hiç tutmadı.
                "ev15_pay": (r["ev_k"][15] / r["ev"]) if r.get("ev") else 0.0,
                "p15": r["p15"], "p12p": r["p12p"],
                # hangi çeyreklere harcandı — hipotezin uygulanıp uygulanmadığı
                "harcama": _harcama(S, C),
                "hipotez": a["hipotez"], "emeklilik": a["emeklilik"],
            })
    return out


def _harcama(S, C) -> dict:
    """Çoklu işaret konan maçların çeyrek dağılımı — ajan dediğini yapmış mı."""
    d: dict[str, int] = {}
    for i, x in enumerate(S):
        if len(x) > 1:
            d[C[i]["ceyrek"]] = d.get(C[i]["ceyrek"], 0) + 1
    return d


# ----------------------------------------------------------------------
# RAPOR
# ----------------------------------------------------------------------
def rapor(A: dict) -> None:
    import sys
    sys.stdout.reconfigure(encoding="utf-8")
    C = ceyrekler(A["P"], A["Q"])
    say: dict[str, int] = {}
    for c in C:
        say[c["ceyrek"]] = say.get(c["ceyrek"], 0) + 1
    print(f"TOTO TAKIM · {A['hafta']['ad']} ({A['hafta']['sezon']})")
    print("çeyrek dağılımı: " + " · ".join(f"{k} {v}" for k, v in sorted(say.items())))
    print()
    print(f"{'ajan':12} {'paket':6} {'kolon':>6} {'maliyet':>9} {'EV/TL':>7} "
          f"{'EV 15pay':>9} {'P(12+)':>7}  harcama")
    print("-" * 84)
    for p in paketler(A):
        h = " ".join(f"{k[:4]}×{v}" for k, v in sorted(p["harcama"].items())) or "—"
        print(f"{p['ajan']:12} {p['paket']:6} {p['kolon']:6d} {p['maliyet']:9.0f} "
              f"{p['ev_tl']:7.2f} %{p['ev15_pay']*100:8.0f} {p['p12p']:7.4f}  {h}")
    print("\n⚠️ EV/TL'yi sıralama ölçütü olarak KULLANMA. 'EV 15pay' sütunu, EV'nin"
          "\n   ne kadarının 15 kademesinden geldiğini gösterir; o kademe milyonda bir"
          "\n   olasılıkla gerçekleşiyor. TOTO JOKER'in EV'si de yüksek çıkar ama 166"
          "\n   haftada hiç ödeme almadı — rastgele kolon benzersiz olduğu için model"
          "\n   'tutarsa havuzu tek başına alır' diyor. Karşılaştırma için P(12+) ve"
          "\n   ÖLÇÜLEN dönüş/TL kullanılmalı.")
    print("\nTaban (166 hafta): FAVORİ@256 0,83 · KALABALIK@32 0,54 · "
          "DENGELİ@256 0,08 · TOTO JOKER 0,00")
    print("Hiçbir profil başabaşı (1,00) geçmiyor — ajanlar kâr için değil, "
          "hipotezleri ölçülebilsin diye var.")


# ----------------------------------------------------------------------
# KENDİ TESTİ — eşikler toto_panel'den kaymasın
# ----------------------------------------------------------------------
def kendi_testi() -> list[str]:
    """Sessiz bozulmaları yakala. Haftalık Bakım çağırabilir."""
    hata = []
    try:
        import toto_panel
        if (toto_panel.GX, toto_panel.GY) != (GX, GY):
            hata.append(f"çeyrek eşikleri kaydı: panel {(toto_panel.GX, toto_panel.GY)} "
                        f"≠ takım {(GX, GY)}")
    except Exception as e:
        hata.append(f"toto_panel okunamadı: {type(e).__name__}")

    # Her ajanın hipotezi ve emeklilik kuralı YAZILI olmalı.
    for ad, a in TAKIM.items():
        if not a.get("hipotez") or len(a["hipotez"]) < 40:
            hata.append(f"{ad}: hipotez yazılmamış")
        if not a.get("emeklilik"):
            hata.append(f"{ad}: emeklilik kuralı yok")

    # Ajanlar gerçekten ayrışıyor mu? İKİ tahtada birden sınanır: BANKO'lu ve
    # BANKO'suz. Sert maskeli ilk sürüm yalnız BANKO'lu tahtada sınanmıştı ve
    # POLLY ile FIRSATÇI'nın BANKO'suz haftalarda birebir aynı kuponu ürettiği
    # ancak gerçek veride (7. Hafta 2026/27) ortaya çıktı.
    TAHTALAR = {
        "BANKO'lu": (
            np.array([[0.70, 0.20, 0.10]] * 5 + [[0.40, 0.30, 0.30]] * 10),
            np.array([[0.55, 0.25, 0.20]] * 5 + [[0.30, 0.40, 0.30]] * 5
                     + [[0.55, 0.25, 0.20]] * 5)),
        "BANKO'suz": (
            np.array([[0.70, 0.20, 0.10]] * 6 + [[0.40, 0.30, 0.30]] * 9),
            np.array([[0.85, 0.09, 0.06]] * 6 + [[0.30, 0.40, 0.30]] * 2
                     + [[0.55, 0.25, 0.20]] * 7)),
    }
    for tahta, (P, Q) in TAHTALAR.items():
        C = ceyrekler(P, Q)
        if tahta == "BANKO'suz" and any(c["ceyrek"] == "BANKO" for c in C):
            hata.append("sınama tahtası bozuk: BANKO'suz tahtada BANKO var")
        imza = {}
        for ad, a in TAKIM.items():
            if a["agirlik"] is None:
                continue
            imza[ad] = tuple(round(float(a["agirlik"](c)), 4) for c in C)
        for x in imza:
            for y in imza:
                if x < y and imza[x] == imza[y]:
                    hata.append(f"{tahta}: {x} ve {y} aynı ağırlıkları veriyor "
                                f"— ayrı ajan değiller")
        # Bir ajan tahtanın TAMAMINI yasaklıyorsa o hafta kupon kuramaz.
        for ad, w in imza.items():
            if all(v <= 0 for v in w):
                hata.append(f"{tahta}: {ad} hiçbir maça bütçe ayıramıyor")
    return hata


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8")
    h = kendi_testi()
    print("kendi testi:", "TEMİZ" if not h else f"{len(h)} sorun")
    for x in h:
        print("  ", x)


# ----------------------------------------------------------------------
# DEFTER — ajanlar gerçekten OYNAR ve sicil tutar
# ----------------------------------------------------------------------
# Bu olmadan TOTO TAKIM bir takım değil, her hafta sıfırdan hesaplanan dört
# kupon kurma tarifiydi: hafızası yok, karnesi yok, kimin iyi olduğu
# sorulamıyordu. Diğer takımlarda (Mavi/Kırmızı/Turuncu) her ajanın kasası ve
# karnesi var; Toto ajanlarının da olmalı.
#
# Ayrı bir defter AÇMIYORUZ: toto_kupon zaten (hafta, profil, bütçe) anahtarlı
# ve haftalık kapanış `durum='kagit'` olan HER kuponu derecelendiriyor. Ajanlar
# oraya yazılınca mevcut akış onları da kapatır — ve aynı tabloda FAVORİ,
# 15_AVCISI, DENGELİ ile aynı ölçekte yarışırlar.
#
# GÜÇLÜ/ORTA ayrımı bütçeden okunur (32 / 256), ayrı sütuna gerek yok.
PAKET_BUTCE = {GUCLU: "GÜÇLÜ", ORTA: "ORTA"}


def defter_satirlari(paketler_: list[dict]) -> list[dict]:
    """paketler() çıktısını toto_db.kupon_yaz biçimine çevir."""
    out = []
    for p in paketler_:
        out.append({
            "profil": p["ajan"], "butce": p["butce"], "kolon": p["kolon"],
            "maliyet": p["maliyet"], "S": p["S"],
            # toto_kupon 'ev' sütunu MUTLAK beklenen değer tutuyor (TL);
            # paketler() lira başına veriyor. Maliyetle çarpıp hizala.
            "ev": p["ev_tl"] * p["maliyet"],
            "p15": p["p15"], "p12p": p["p12p"],
        })
    return out


def karne(kuponlar: list[dict] | None = None) -> list[dict]:
    """Ajanların birikmiş sicili — kapanmış kuponlardan.

    `kuponlar` verilmezse toto_db'den okunur. Yalnız TAKIM ajanlarının
    satırları sayılır; FAVORİ/DENGELİ vb. ayrı profillerdir.
    """
    if kuponlar is None:
        import toto_db
        kuponlar = toto_db.kuponlar()
    from collections import defaultdict
    g = defaultdict(list)
    for k in kuponlar:
        if k["profil"] in TAKIM and k.get("dogru") is not None:
            g[(k["profil"], k["butce"])].append(k)

    out = []
    for (ajan, butce), K in g.items():
        maliyet = sum(float(k["maliyet"] or 0) for k in K)
        odeme = sum(float(k["odeme"] or 0) for k in K)
        dagilim = {15: 0, 14: 0, 13: 0, 12: 0}
        for k in K:
            d = int(k["dogru"] or 0)
            if d >= 12:
                dagilim[min(d, 15)] += 1
        odeyen = sum(1 for k in K if float(k["odeme"] or 0) > 0)
        out.append({
            "ajan": ajan, "paket": PAKET_BUTCE.get(butce, str(butce)), "butce": butce,
            "hafta": len(K), "maliyet": maliyet, "odeme": odeme,
            "donus": (odeme / maliyet) if maliyet else 0.0,
            "odeyen": odeyen,
            "en_iyi": max((int(k["dogru"] or 0) for k in K), default=0),
            "dagilim": dagilim,
            # Tek haftaya bağımlılık: en büyük ödemenin toplam içindeki payı.
            # Yüksekse sayı bir haftanın şansıdır, sicil değil.
            "tek_hafta_pay": (max((float(k["odeme"] or 0) for k in K), default=0.0) / odeme)
                             if odeme > 0 else 0.0,
        })
    return sorted(out, key=lambda x: (-x["donus"], x["ajan"]))


def gecmis_karne() -> list[dict] | None:
    """166 haftalık geri testten ajan sicili — canlı defter dolana dek referans.

    Canlı sicil (karne()) haftada bir satır büyür; ilk anlamlı karşılaştırma
    aylar sonra olur. Geri test aynı SIZINTISIZ protokolde koşturulduğu için
    (geri_test.calis, cikti='geri_test_takim') o boşluğu dürüstçe doldurur.
    Dosya yoksa None döner — uydurma sayı üretilmez.
    """
    import numpy as np
    import pandas as pd
    from toto_ortak import CACHE
    yol = CACHE / "geri_test_takim.pkl"
    if not yol.exists():
        return None
    try:
        K = pd.read_pickle(yol)
    except Exception:
        return None
    if not len(K):
        return None
    rng = np.random.default_rng(20260925)
    out = []
    for (prof, B), g in K.groupby(["profil", "butce"]):
        od = g.groupby("hafta_id")["odeme"].sum().values
        ma = g.groupby("hafta_id")["maliyet"].sum().values
        n = len(od)
        if not n or ma.sum() <= 0:
            continue
        # Haftalar üzerinden önyükleme: ödeme birkaç haftada yoğunlaştığı için
        # klasik standart hata yanıltır.
        idx = rng.integers(0, n, size=(4000, n))
        bs = od[idx].sum(1) / ma[idx].sum(1)
        out.append({
            "ajan": prof, "paket": PAKET_BUTCE.get(B, str(B)), "butce": int(B),
            "hafta": int(n), "donus": float(od.sum() / ma.sum()),
            "alt": float(np.percentile(bs, 2.5)), "ust": float(np.percentile(bs, 97.5)),
            "odeyen": int((od > 0).sum()),
            "tek_hafta_pay": float(np.sort(od)[-2:].sum() / od.sum()) if od.sum() > 0 else 0.0,
        })
    return sorted(out, key=lambda x: -x["donus"])
