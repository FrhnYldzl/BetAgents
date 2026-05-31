# T09 — Multi-League Portfolio Simülasyonu

**Versiyon:** v1.0
**Tarih:** 2026-05-27T21:21:33

---

## Bilimsel Sorular

**H1:** Multi-league portföy T1-only'den daha iyi growth+volatilite oranı verir mi?
**H2:** Ligler arası outcome korelasyonu ne kadar?
**H3:** Diversifikasyon Sharpe'i arttırır mı?
**H4:** Portföy max drawdown < single-league mı?

---

## Sonuçlar

| Portföy | Initial | Final | Return | n picks | Hit% | MaxDD | Sharpe |
|---|---:|---:|---:|---:|---:|---:|---:|
| T1-only (ref) | 1000 | 7,745 | +674.5% | 103 | 24% | 51.2% | 1.39 |
| Equal 3-league | 1000 | 3,020 | +202.0% | 397 | 21% | 36.3% | 0.57 |
| E0+T1 (T04 winners) | 1000 | 4,216 | +321.6% | 272 | 22% | 42.6% | 0.76 |
| T1-weighted (70/20/10) | 1000 | 5,621 | +462.1% | 397 | 21% | 43.2% | 0.68 |

---

## Korelasyon Analizi

**28 ortak hafta** (3 lig de kupon üretmiş):

```
       E0     D1     T1
E0  1.000 -0.190 -0.054
D1 -0.190  1.000 -0.236
T1 -0.054 -0.236  1.000
```


**Düşük korelasyon (|r| < 0.3)** = bağımsız → diversifikasyon faydalı
**Yüksek korelasyon (|r| > 0.5)** = aynı yönde hareket → diversifikasyon işe yaramaz

---

## Cevaplar

**H1:** Portföy growth: +202% - +674%. T1-only ile equal-weight farkı: -472.5 pp.

**H2:** Lig outcome'ları arası korelasyon → CSV'de detay.

**H3:** En yüksek Sharpe: 1.39 (T1-only (ref)). T1-only Sharpe: 1.39.

**H4:** Min max-drawdown: %36 (Equal 3-league).

---

## Yorum

Diversifikasyon **growth'tan ödün vermeden** drawdown'u azaltıyorsa optimal. Portföyün üstün özelliği: aynı hafta farklı liglerin bağımsız sonuçları → variance düşer.

Equity CSV: `07_LOG_VE_RAPORLAR/T09_portfolio_equity.csv`
