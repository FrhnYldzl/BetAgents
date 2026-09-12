"""
🔐 KANIT KATMANI — Šidák eşiği, etkin ajan sayısı, CLV kapısı
===============================================================
Kaynak: kullanıcının "TAHMİN SİSTEMİ v3" belgesi (§1.4, §1.5, §3.4).
Belge bu üç hesabı tanımlıyor ama sistem hiçbirini yapmıyordu:

  §1.4 SEÇİM YANLILIĞI — m ajan test edip en iyisini seçmek, seçilenin
       performansını yukarı saptırır. Hiçbir ajanın gerçek edge'i
       olmasa bile 20 ajandan birkaçı TESADÜFEN mükemmel görünür.
       Düzeltme: α_ajan = 1 − (1 − α_aile)^(1/m). Sonuç, doğrulama
       eşiğinin YÜKSELMESİDİR.
  §3.4 ETKİN AJAN SAYISI — ajan sayısı çeşitlendirme sağlamaz,
       BAĞIMSIZLIK sağlar. Korelasyonlu ajanlar tek ajan gibi davranır:
       m_etkin = m / (1 + (m−1)·ρ). ρ=0,3'te 20 ajan 3 ajana denktir.
  §1.5 CLV KAPISI — isabet oranı orana bağlı ve karşılaştırılamaz;
       CLV öncü göstergedir. Üç bölge: >+%2 ölçeklendir, 0..+%2
       belirsiz (stake yarıya), ≤0 canlı parayı durdur.

⚠️ BAĞIMLILIK YOK: scipy canlı yolda KURULU DEĞİL (requirements-railway
slim). Binom kuyruğu log-gamma ile, standart kütüphaneyle hesaplanır.

⚠️ EŞİK, AJANIN KENDİ FİYATINA GÖRE: belge sabit p₀=0,625 (oran 1,60
başabaş) kullanıyor. Bizim ajanların ortalama oranı farklı, o yüzden
her ajan için p₀ = ortalama(1/oran) — yani FİYATIN beklediği isabet.
Bu, belgenin kuralının doğru genellemesidir: sorun "isabet yüksek mi"
değil, "fiyatın beklediğinden anlamlı yüksek mi".
"""
from __future__ import annotations

import math


# ── Šidák ────────────────────────────────────────────────────
def sidak_alpha(m: int, aile: float = 0.05) -> float:
    """Aile-düzeyi α'dan ajan-düzeyi α. m=1 iken aile α'sına eşit."""
    m = max(int(m or 1), 1)
    return 1.0 - (1.0 - aile) ** (1.0 / m)


def _log_binom(n: int, k: int) -> float:
    """log C(n,k) — büyük n'de taşma olmasın diye log-gamma ile."""
    return (math.lgamma(n + 1) - math.lgamma(k + 1) - math.lgamma(n - k + 1))


def binom_ust_kuyruk(n: int, k: int, p: float) -> float:
    """P(X >= k | n, p). Tam hesap, scipy'siz."""
    if k <= 0:
        return 1.0
    if k > n:
        return 0.0
    p = min(max(p, 1e-12), 1 - 1e-12)
    toplam = 0.0
    for i in range(k, n + 1):
        toplam += math.exp(_log_binom(n, i) + i * math.log(p)
                           + (n - i) * math.log(1 - p))
    return min(toplam, 1.0)


def gereken_isabet(n: int, p0: float, alpha: float) -> tuple[int, float] | None:
    """'Edge yok' hipotezini α'da reddetmek için gereken en küçük k.

    Döner: (k, k/n) · n=0 ise None.
    p0 = fiyatın ima ettiği isabet (başabaş). Tek yönlü test.
    """
    n = int(n or 0)
    if n <= 0:
        return None
    for k in range(math.ceil(n * p0), n + 1):
        if binom_ust_kuyruk(n, k, p0) <= alpha:
            return k, k / n
    return n + 1, 1.0 + 1e-9        # n kadar veriyle imkansiz


# ── Etkin ajan sayısı ────────────────────────────────────────
def etkin_ajan(m: int, ro: float) -> float:
    """m / (1 + (m−1)ρ) — belge §3.4.

    ρ=0 ise m, ρ=1 ise 1. Korelasyonlu ajanlar tek ajan gibi davranır.
    """
    m = max(int(m or 0), 0)
    if m <= 1:
        return float(m)
    ro = min(max(float(ro or 0.0), 0.0), 1.0)
    return m / (1.0 + (m - 1) * ro)


# ── CLV kapısı ───────────────────────────────────────────────
# Belge §1.5 — 200+ bahiste ortalama CLV'ye göre AKSİYON.
CLV_BOLGE = (
    (0.02, "ÖLÇEKLENDİR", "ps",
     "Edge kanıtı güçlü. Belge: stake artırılabilir."),
    (0.00, "BELİRSİZ", "",
     "Edge kanıtı belirsiz. Belge: stake'i YARIYA indir, canlı paraya "
     "geçme."),
    (-9.99, "DURDUR", "ng",
     "Edge kanıtı YOK. Belge: canlı parayı durdur."),
)


def clv_kapisi(ort: float | None, n: int) -> dict:
    """Ortalama CLV → bölge + aksiyon. n<200 ise henüz hüküm yok."""
    if ort is None:
        return {"bolge": "ÖLÇÜLEMEDİ", "cls": "", "not": "CLV kaydı yok.",
                "yeterli": False}
    yeterli = int(n or 0) >= 200
    for esik, ad, cls, nt in CLV_BOLGE:
        if ort > esik:
            return {"bolge": ad, "cls": cls, "not": nt, "yeterli": yeterli,
                    "ort": ort, "n": int(n or 0)}
    return {"bolge": "DURDUR", "cls": "ng", "not": CLV_BOLGE[-1][3],
            "yeterli": yeterli, "ort": ort, "n": int(n or 0)}
