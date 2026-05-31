# T20 — 6-Lig Backtest (T1+E0+D1+SP1+I1+F1)

**Versiyon:** v1.0
**Tarih:** 2026-05-27T22:12:00

---

## Bilimsel Soru

SP1 (La Liga), I1 (Serie A), F1 (Ligue 1) eklenince 6-lig multi-league
strateji 3-lig'den daha karlı mı?

NOT: SP1/I1/F1 için DC modeli YOK → sadece anomaly+xG+form sinyalleri.
FAV_CONFIRMED ≥1 confirmer.

---

## Per-Lig Sonuçlar (K=3 FAV_CONFIRMED Flat 1000 TL)

| Lig | n | Won | Hit% | Avg Odd | Hacim | Net PnL | ROI | Yıllık |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| T1 | 109 | 25 | 23% | 7.64 | 109,000 | +56,143 | +51.5% | +13,316 |
| E0 | 193 | 38 | 20% | 5.68 | 193,000 | -7,214 | -3.7% | -1,640 |
| D1 | 137 | 26 | 19% | 6.22 | 137,000 | +13,967 | +10.2% | +3,281 |
| SP1 | 97 | 15 | 15% | 6.59 | 97,000 | -16,827 | -17.3% | -4,553 |
| I1 | 170 | 29 | 17% | 6.49 | 170,000 | -1,213 | -0.7% | -330 |
| F1 | 132 | 24 | 18% | 6.54 | 132,000 | -20,762 | -15.7% | -5,588 |

---

## 6-Lig Toplam

- **Toplam kupon:** 838
- **Toplam hacim:** 838,000 TL
- **Toplam NET PnL:** +24,095 TL
- **ROI:** +2.9% (eğer hacim > 0)
- **Yıllık ortalama:** +4,486 TL

---

## Yorum

6-lig vs 3-lig: ek 3 lig (SP1+I1+F1) toplam PnL'ye nasıl etki etti?

Eğer her lig pozitif → diversifikasyon iyi, daha çok lig daha çok kar.
Eğer bazı lig negatif → o lig stratejinin dışına alınmalı (D1 örneği gibi).
