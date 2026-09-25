"""
BETAGENTS · SÜREKLİ PUANLAMA — ajanı oynadığı bahiste değil, HER MAÇTA ölç
==========================================================================
Neden gerekti
-------------
Bugüne kadar bir ajanı yalnız deftere geçen bahislerinden ölçtük: 1.271
sonuçlanmış bahis, ajan başına 20-300. Bu örneklemle hiçbir ajan şanstan
ayırt edilemiyor — JOKER (rastgele kontrol) çoğunu geçiyor.

İki şey örneklemi kısıyordu:
  • günlük kota (max_daily) — ajan görüş bildirdiği maçların çoğunu oynamıyor;
  • kupon kurgusu — üçlü kombine üç ayrı iddia, ama tek sonuç olarak kapanıyor.

Oysa ajanın İDDİASI oynamadığı maçta da vardır ve ölçülebilir. Anlık görüntüde
5.772 maçın kapanış fiyatı ve sonucu birlikte var: 4,5 kat örneklem.

Neyi ölçüyoruz — ve neyi ÖLÇMÜYORUZ
------------------------------------
Ajanlar olasılık üretmiyor. Üreteçlerin `model_prob` alanı `_vig_strip(fiyat)`,
yani PİYASANIN kendi olasılığı. Bu yüzden "ajanın olasılığı ne kadar iyi"
diye soramayız — sorsak piyasayı ölçmüş oluruz. (Aynı sebeple `edge` sütunu
daima eksidir: edge = −raw·(S−1)/S, ödenen marjın eksi işaretlisi. 1.252
bahsin 1.252'sinde doğrulandı.)

Ajanın bilgisi TAMAMEN FİLTRESİNDE: hangi maçlarda konuştuğu ve hangi tarafı
seçtiği. Ölçülecek soru bu yüzden tek:

    Ajanın seçtiği maçlarda iddia, AYNI FİYATA sahip maçlardakinden
    daha sık mı tutuyor?

Taban "piyasanın teorik olasılığı" DEĞİL, aynı fiyat bandındaki maçların
gerçekleşen oranıdır (eşleştirilmiş kontrol). Sebebi Kalibrasyon sınıfının
başında ölçümüyle yazılı: marjsızlaştırma ağır favoride kalibre değil ve
teorik tabanla ağır favori oynayan her ajan haksız yere eksi z alıyor.

Sınama (Poisson-binom)
----------------------
H0: ajanın filtresi bilgi taşımıyor — her iddia, fiyatının tarihsel oranı
    p_i kadar tutar.
    E[isabet]   = Σ p_i
    Var[isabet] = Σ p_i(1 − p_i)          (iddialar bağımsız maçlarda)
    z = (gerçekleşen − E) / √Var
Maçlar farklı olasılıklara sahip olduğu için düz binom değil, Poisson-binom.

z > 0  filtre, fiyatın bildiğinden fazlasını biliyor
z ≈ 0  filtre fiyatın tekrarı — bilgi yok (ROI = −marj olur)
z < 0  filtre ters yönde bilgi taşıyor — karşı taraf sınanmalı

UYARI — z bir KEŞİF aracıdır, onay değil. Bantlar aynı veriden kuruluyor;
z>0 çıkan bir filtre, ileriye dönük yeni veride tekrar sınanmadan
"çalışıyor" sayılmaz.

ÖNEMLİ: z>0 tek başına para demek değil. Marjı aşması da gerekir; o yüzden
sanal ROI ayrıca yazılır. "İsabet yüksek ama ROI eksi" en sık görülen tuzak —
düşük oranlı favori seçerek isabet şişirilir, kasa erir.

Okuma notu — bu tablo BAHİS ÖNERMEZ
------------------------------------
Sanal ROI, günlük kota ve kupon kurgusu YOKSAYILARAK her iddiaya 1 birim
oynanmış varsayar. Gerçek defterle karşılaştırılamaz; ajanlar arası
karşılaştırma içindir.
"""
from __future__ import annotations

import math
import random
import sys
from pathlib import Path

THIS_DIR = Path(__file__).resolve().parent
if str(THIS_DIR) not in sys.path:
    sys.path.insert(0, str(THIS_DIR))

# İki yönlü pazarlar: (market, pick) → maçın sonucundan nasıl derecelendirilir
IKI_YONLU = {
    "UST_25": lambda h, a: (h + a) > 2.5,
    "ALT_25": lambda h, a: (h + a) < 2.5,
    "KG_VAR": lambda h, a: h > 0 and a > 0,
    "KG_YOK": lambda h, a: not (h > 0 and a > 0),
}
# Bu pazarların fiyat alanları — marjsızlaştırma ikisini birlikte ister
ESLI_ALAN = {
    "UST_25": ("closing_over25", "closing_under25"),
    "ALT_25": ("closing_under25", "closing_over25"),
    "KG_VAR": ("closing_btts_yes", "closing_btts_no"),
    "KG_YOK": ("closing_btts_no", "closing_btts_yes"),
}
GECERLI_MIN_ORAN = 1.05          # paper_engine ile aynı taban: 1,00 fiyat değil


# ----------------------------------------------------------------------
# MARJSIZLAŞTIRMA
# ----------------------------------------------------------------------
def marjsiz(oranlar: list[float]) -> list[float] | None:
    """Kuvvet yöntemiyle vig soy: Σ (1/o)^k = 1 olacak k'yı bul.

    Orantılı yöntem (raw/Σraw) favoriyi sistematik olarak fazla fiyatlar —
    favori-uzun atkuyruğu yanlılığı. Kuvvet yöntemi marjı olasılığa göre
    dağıtır ve kapanış fiyatlarında ölçülebilir biçimde daha kalibre.
    Karşılaştırma bu modülün tabanı olduğu için doğru olanı kullanıyoruz.
    """
    o = [x for x in oranlar if x and x >= GECERLI_MIN_ORAN]
    if len(o) != len(oranlar) or not o:
        return None                       # bir ayak yer tutucu → pazarı atla
    ham = [1.0 / x for x in o]
    if abs(sum(ham) - 1.0) < 1e-9:
        return ham
    lo, hi = 0.5, 3.0
    for _ in range(60):                   # k monoton: ikili arama yeter
        k = (lo + hi) / 2
        if sum(r ** k for r in ham) > 1.0:
            lo = k
        else:
            hi = k
    k = (lo + hi) / 2
    p = [r ** k for r in ham]
    t = sum(p)
    return [x / t for x in p] if t > 0 else None


def piyasa_1x2(m: dict) -> list[float] | None:
    return marjsiz([_f(m.get("closing_1")), _f(m.get("closing_X")), _f(m.get("closing_2"))])


def _f(v) -> float:
    try:
        return float(v or 0)
    except (TypeError, ValueError):
        return 0.0


# ----------------------------------------------------------------------
# İDDİANIN DERECELENDİRİLMESİ
# ----------------------------------------------------------------------
def sonuc_1x2(h: int, a: int) -> str:
    return "1" if h > a else ("2" if a > h else "X")


def tuttu_mu(market: str, pick: str, h: int, a: int) -> bool | None:
    if market == "1X2":
        return sonuc_1x2(h, a) == str(pick)
    f = IKI_YONLU.get(market)
    return f(h, a) if f else None


def iddia_olasiligi(market: str, pick: str, m: dict) -> float | None:
    """Piyasanın bu iddiaya biçtiği MARJSIZ olasılık — sınamanın tabanı."""
    if market == "1X2":
        p = piyasa_1x2(m)
        return None if not p else p[{"1": 0, "X": 1, "2": 2}[str(pick)]]
    alan = ESLI_ALAN.get(market)
    if not alan:
        return None
    p = marjsiz([_f(m.get(alan[0])), _f(m.get(alan[1]))])
    return p[0] if p else None


# ----------------------------------------------------------------------
# EŞLEŞTİRİLMİŞ KONTROL — tabanı teoriden değil, veriden al
# ----------------------------------------------------------------------
# NEDEN GEREKTİ (25.09.2026, bu modülün ilk koşusunda yakalandı)
# İlk tasarımda taban, marjsızlaştırılmış olasılıktı. O tabanla beş ajan
# z ≤ −2,4 verdi ve üçü −3'ü geçti; "filtreleri ters bilgi taşıyor" gibi
# göründü. Ölçünce sebep başka çıktı: KUVVET YÖNTEMİ AĞIR FAVORİYİ
# SİSTEMATİK OLARAK FAZLA FİYATLIYOR.
#
#   favori bandı   model der   gerçek    fark
#     %55'ten az     %44,7      %44,5     −0,2   ✓ kalibre
#     %55-65         %59,7      %60,2     +0,4   ✓ kalibre
#     %72-78         %75,0      %71,5     −3,5
#     %78-85         %81,1      %74,2     −6,9   ← en büyük sapma
#     %85 üstü       %88,5      %83,5     −4,9
#
# Söz konusu beş ajan 1,28-1,39 oran oynuyor, yani tam bu bantta. Eksi z
# onların filtresinin değil, TABANIN özelliğiydi. (Favori-uzunatkuyruk
# yanlılığının marjsızlaştırmadan sonra bile kaldığı hâli.)
#
# Çözüm: teorik olasılık yerine AYNI FİYAT BANDINDAKİ maçların gerçekleşen
# oranını taban al. Soru şuna dönüşür ve marjsızlaştırmanın kalibrasyonundan
# tamamen bağımsız olur:
#
#     Ajanın seçtiği maçlarda iddia, AYNI FİYATA sahip maçlardakinden
#     daha sık mı tutuyor?
#
# Band oranı ajanın kendi seçimini de içerdiği için "dışarıda bırak" (leave
# -one-out) uygulanır: kendi sonucunu kendi tabanına katıp testi kolaylaştırmasın.
class Kalibrasyon:
    """(pazar, fiyat bandı) → o bantta iddianın gerçekleşme oranı."""

    GENISLIK = 0.05          # 1/oran ekseninde bant genişliği
    ASGARI = 40              # bir bandın kendi oranını hak etmesi için

    def __init__(self, maclar: list[dict]) -> None:
        self.kova: dict[tuple, list[int]] = {}      # anahtar → [isabet, n]
        for m in maclar:
            h, a = m.get("home_score"), m.get("away_score")
            if h is None or a is None:
                continue
            for market, pick, alan in (
                    ("1X2", "1", "closing_1"), ("1X2", "X", "closing_X"),
                    ("1X2", "2", "closing_2"),
                    ("UST_25", "UST", "closing_over25"), ("ALT_25", "ALT", "closing_under25"),
                    ("KG_VAR", "VAR", "closing_btts_yes"), ("KG_YOK", "YOK", "closing_btts_no")):
                o = _f(m.get(alan))
                if o < GECERLI_MIN_ORAN:
                    continue
                t = tuttu_mu(market, pick, int(h), int(a))
                if t is None:
                    continue
                k = self._anahtar(market, o)
                v = self.kova.setdefault(k, [0, 0])
                v[0] += 1 if t else 0
                v[1] += 1

    def _anahtar(self, market: str, oran: float) -> tuple:
        return (market, int((1.0 / oran) / self.GENISLIK))

    def bekle(self, market: str, oran: float, dusur: bool | None = None) -> float | None:
        """Bu fiyatta iddianın tarihsel gerçekleşme oranı.

        `dusur` verilirse o gözlem bandan çıkarılır (leave-one-out) — ajanın
        kendi sonucu kendi tabanını yukarı çekmesin."""
        k = self._anahtar(market, oran)
        v = self.kova.get(k)
        if not v or v[1] < self.ASGARI:
            return None                      # ince bant → sessiz kal, uydurma
        isabet, n = v
        if dusur is not None:
            isabet -= 1 if dusur else 0
            n -= 1
        if n <= 0:
            return None
        return min(0.999, max(0.001, isabet / n))


# ----------------------------------------------------------------------
# PUANLAMA
# ----------------------------------------------------------------------
class Karne:
    """Bir ajanın sürekli karnesi. İddialar tek tek eklenir, sonda özetlenir."""

    def __init__(self, ad: str) -> None:
        self.ad = ad
        self.n = 0                  # kaç maçta konuştu
        self.isabet = 0
        self.beklenen = 0.0         # Σ p_i  — piyasanın beklediği isabet
        self.varyans = 0.0          # Σ p_i(1-p_i)
        self.getiri = 0.0           # sanal birim getiri toplamı
        self.getiri_kare = 0.0
        self.oran_top = 0.0
        self.clv_top = 0.0
        self.clv_n = 0

    def ekle(self, tuttu: bool, p_piyasa: float, oran: float,
             acilis: float | None = None) -> None:
        self.n += 1
        self.isabet += 1 if tuttu else 0
        self.beklenen += p_piyasa
        self.varyans += p_piyasa * (1.0 - p_piyasa)
        g = (oran - 1.0) if tuttu else -1.0
        self.getiri += g
        self.getiri_kare += g * g
        self.oran_top += oran
        if acilis and acilis >= GECERLI_MIN_ORAN:
            # CLV: açılışta aldığın fiyat kapanışa göre ne kazandırdı
            self.clv_top += oran / acilis - 1.0
            self.clv_n += 1

    def ozet(self) -> dict:
        if not self.n:
            return {"ajan": self.ad, "n": 0}
        n = self.n
        isabet = self.isabet / n
        bekl = self.beklenen / n
        sd = math.sqrt(self.varyans) if self.varyans > 0 else 0.0
        z = (self.isabet - self.beklenen) / sd if sd > 0 else 0.0
        roi = self.getiri / n
        # birim getirinin std'si → ROI'nin standart hatası
        var_g = max(0.0, self.getiri_kare / n - roi * roi)
        se_roi = math.sqrt(var_g / n) if n else 0.0
        return {
            "ajan": self.ad, "n": n,
            "isabet": isabet,
            "piyasa_bekler": bekl,
            "fark": isabet - bekl,
            "z": z,
            "ort_oran": self.oran_top / n,
            "roi": roi,
            "roi_ci": 1.96 * se_roi,
            "clv": (self.clv_top / self.clv_n) if self.clv_n else None,
            "clv_n": self.clv_n,
        }


def puanla(iddialar, ad: str, kal: "Kalibrasyon | None" = None) -> dict:
    """iddialar: (market, pick, oran, mac) üreteci → karne özeti.

    `kal` verilirse taban EŞLEŞTİRİLMİŞ KONTROL olur (aynı fiyat bandındaki
    maçların gerçekleşen oranı) — tercih edilen yol. Verilmezse teorik
    marjsız olasılığa düşer; o taban ağır favoride kalibre DEĞİL, bkz.
    Kalibrasyon sınıfının başındaki not.
    """
    k = Karne(ad)
    atlanan_bant = 0
    for market, pick, oran, m in iddialar:
        if not oran or oran < GECERLI_MIN_ORAN:
            continue
        h, a = m.get("home_score"), m.get("away_score")
        if h is None or a is None:
            continue
        t = tuttu_mu(market, str(pick), int(h), int(a))
        if t is None:
            continue
        if kal is not None:
            p = kal.bekle(market, float(oran), dusur=t)
            if p is None:
                atlanan_bant += 1
                continue
        else:
            p = iddia_olasiligi(market, str(pick), m)
        if p is None or not (0.0 < p < 1.0):
            continue
        acilis = None
        if market == "1X2":
            acilis = _f(m.get({"1": "opening_1", "X": "opening_X", "2": "opening_2"}[str(pick)]))
        k.ekle(t, p, float(oran), acilis or None)
    o = k.ozet()
    o["bant_yok"] = atlanan_bant      # kalibrasyon bandı ince → puanlanamayan iddia
    return o


# ----------------------------------------------------------------------
# TABAN ÇİZGİLERİ — ajanı neyle karşılaştırıyoruz
# ----------------------------------------------------------------------
def taban_piyasa(maclar):
    """PİYASA: her maçta favoriyi seç. Ajanın aşması gereken çizgi."""
    for m in maclar:
        p = piyasa_1x2(m)
        if not p:
            continue
        i = max(range(3), key=lambda j: p[j])
        pick = ("1", "X", "2")[i]
        oran = _f(m.get({"1": "closing_1", "X": "closing_X", "2": "closing_2"}[pick]))
        yield "1X2", pick, oran, m


def taban_joker(maclar, tohum: int = 20260925):
    """JOKER: rastgele taraf. Beceri yokluğunun referansı."""
    rnd = random.Random(tohum)
    for m in maclar:
        if not piyasa_1x2(m):
            continue
        pick = rnd.choice(("1", "X", "2"))
        oran = _f(m.get({"1": "closing_1", "X": "closing_X", "2": "closing_2"}[pick]))
        yield "1X2", pick, oran, m


def taban_hep_ev(maclar):
    """HEP EV: en basit kural. Bir ajan bunu geçemiyorsa filtresi boştur."""
    for m in maclar:
        if piyasa_1x2(m):
            yield "1X2", "1", _f(m.get("closing_1")), m


# ----------------------------------------------------------------------
# RAPOR
# ----------------------------------------------------------------------
BASLIK = (f"{'ajan':22} {'n':>5} {'isabet':>7} {'taban':>7} {'fark':>7} "
          f"{'z':>6} {'oran':>6} {'ROI':>8} {'±95%':>7} {'CLV':>7}")


def satir(o: dict) -> str:
    if not o.get("n"):
        return f"{o['ajan']:22} {'—':>5}  (hiç konuşmadı)"
    clv = f"%{o['clv']*100:+.1f}" if o.get("clv") is not None else "—"
    return (f"{o['ajan']:22} {o['n']:5d} %{o['isabet']*100:6.1f} %{o['piyasa_bekler']*100:6.1f} "
            f"{o['fark']*100:+6.1f} {o['z']:+6.2f} {o['ort_oran']:6.2f} "
            f"%{o['roi']*100:+7.1f} %{o['roi_ci']*100:6.1f} {clv:>7}")


def yorum(o: dict, esik: float = 3.0) -> str:
    """Çoklu karşılaştırma için eşik 3σ: ~20 ajan sınanıyor, 2σ'da yanlış
    alarm beklenen sayı 1'dir. Bonferroni'nin kaba ama dürüst hâli."""
    if not o.get("n"):
        return "veri yok"
    z, roi, ci = o["z"], o["roi"], o["roi_ci"]
    if z >= esik and roi - ci > 0:
        return "filtre bilgi taşıyor VE marjı aşıyor"
    if z >= esik:
        return "filtre bilgi taşıyor ama marjı aşmıyor"
    if z <= -esik:
        return "filtre TERS bilgi taşıyor — karşı taraf sınanmalı"
    return "piyasadan ayırt edilemiyor"
