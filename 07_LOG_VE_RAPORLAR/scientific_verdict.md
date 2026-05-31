# Bilimsel Validasyon Raporu

**Tarih:** 2026-05-27 14:22
**Ligler:** E0, T1, D1
**Test Sezonları:** 2324, 2425
**Bahis tipi:** Over 2.5 (Toplam Gol Üst 2.5)
**Model:** Dixon-Coles + Platt scaling
**Stake:** 0.20× Kelly, max %3 bankroll

## 1. Birleşik Sample

| Metrik | Değer |
|---|---|
| Toplam bahis (n) | **577** |
| Kazanan | 320 (55.5%) |
| Toplam stake | 124,378 ₺ |
| Toplam P&L | **-1,018 ₺** |
| Genel ROI | **-0.82%** |

## 2. Lig Bazlı Performans

| Lig | n | Win % | ROI % | CLV % | Durum |
|---|---|---|---|---|---|
| E0 | 213 | 55.9 | -2.99 | -1.71 | ⚠️ Şüpheli (CLV<0) |
| T1 | 195 | 58.5 | +9.09 | -1.77 | ⚠️ Şüpheli (CLV<0) |
| D1 | 169 | 51.5 | -13.56 | -2.13 | ⚠️ Şüpheli (CLV<0) |

## 3. İstatistiksel Test (One-sample t-test, H₀: ROI=0)

| Metrik | Değer |
|---|---|
| Mean ROI | **-2.660%** per bet |
| Std | 91.12% |
| Standard Error | 3.7932% |
| t-statistic | -0.701 |
| **p-value** | **0.4834** |
| 95% CI | [-10.11%, +4.79%] |
| **Sonuç** | ❌ ANLAMSIZ — şans olabilir |

## 4. Bootstrap Analizi (2000 resampling)

- Bootstrap median ROI: **-2.55%**
- Bootstrap 95% CI: [-10.16%, +4.72%]
- P(ROI > 0) ampirik: **23.7%**
- ❌ Sıfırı içeriyor — emin değiliz

## 5. CLV (Closing Line Value) — KRİTİK

| Metrik | Değer |
|---|---|
| Mean CLV | **-1.852%** |
| CLV > 0 oran | 33.3% (192/577) |
| t-statistic | -7.236 |
| p-value | **0.0000** |
| 95% CI | [-2.35%, -1.35%] |

❌ **CLV anlamlı şekilde NEGATİF — Pinnacle bizden daha doğru. ROI varsa şans.**

## 6. Risk Metrikleri

- Sharpe-equivalent (252-day annualized): **-0.46**
- Maksimum drawdown: **%14.32**

## 7. Sample Power Analizi

Mevcut sample (n=577). Gerçek edge tespit etmek için gereken:
- %2 edge için: **16,272** bahis (❌ yetersiz (15695 daha gerek))
- %3 edge için: **7,232** bahis (❌ yetersiz (6655 daha gerek))
- %5 edge için: **2,603** bahis (❌ yetersiz (2026 daha gerek))
- %8 edge için: **1,017** bahis (❌ yetersiz (440 daha gerek))

## 8. NİHAİ BİLİMSEL HÜKÜM

# ❌ EDGE KANITLANMADI

Gerçek bahis için bilimsel kanıt yok. Sorunlar:
- ❌ t-test p=0.483 (>0.05) — ROI anlamsız
- ❌ CLV ortalaması -1.85% — negatif, gerçek edge yok
- ❌ Bootstrap güvenilir değil

**Karar: PARA YATIRMA. Model iyileştirme gerekli (Sprint 2.3 LLM augmentation).**