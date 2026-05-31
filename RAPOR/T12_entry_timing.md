# T12 — Entry Timing Analizi (T1 K=3)

**Versiyon:** v1.0
**Tarih:** 2026-05-27T21:36:12

---

## Hipotez

**H6a:** Sezon başında ROI düşük (warm-up gerek).
**H6b:** Sezon ortası (W10-25) ROI en yüksek.
**H6c:** Sezon sonu motivasyon dağılır, gürültü.

---

## Entry Week Sweep (T1 K=3, 1000 TL flat)

| Entry W | n | Hit% | Avg Odd | Hacim | Net PnL | ROI |
|---|---:|---:|---:|---:|---:|---:|
| 1 | 103 | 24% | 7.69 | 103,000 | +62,143 | +60.3% |
| 5 | 87 | 23% | 7.78 | 87,000 | +47,734 | +54.9% |
| 10 | 67 | 21% | 8.06 | 67,000 | +33,071 | +49.4% |
| 15 | 47 | 17% | 8.29 | 47,000 | +16,403 | +34.9% |
| 20 | 31 | 19% | 8.00 | 31,000 | +12,696 | +41.0% |
| 25 | 21 | 24% | 7.48 | 21,000 | +9,173 | +43.7% |
| 30 | 11 | 36% | 6.55 | 11,000 | +12,319 | +112.0% |

**En iyi entry:** W30 ROI +112.0%

---

## En Karlı Haftalar (sezon içi)

| Week | n | Wins | Hit% | Avg Odd | EV per kupon (TL) |
|---|---:|---:|---:|---:|---:|
| W8 | 4 | 3 | 75% | 6.01 | +3,504 |
| W4 | 4 | 2 | 50% | 8.36 | +3,178 |
| W1 | 4 | 2 | 50% | 7.99 | +2,996 |
| W5 | 4 | 2 | 50% | 6.83 | +2,417 |
| W13 | 4 | 2 | 50% | 6.31 | +2,156 |

## En Az Karlı (KAÇINILACAK) Haftalar

| Week | n | Wins | Hit% | Avg Odd | EV per kupon (TL) |
|---|---:|---:|---:|---:|---:|
| W2 | 4 | 0 | 0% | 7.21 | -1,000 |
| W7 | 4 | 0 | 0% | 7.55 | -1,000 |
| W16 | 3 | 0 | 0% | 9.36 | -1,000 |
| W9 | 4 | 0 | 0% | 6.97 | -1,000 |
| W18 | 3 | 0 | 0% | 8.11 | -1,000 |

---

## Yorum

- **Sezon-içi ROI dalgalanması** açık görünüyor mu?
- **Warm-up week** kaç haftası kayıp ediyor?
- **Sezon sonu** noise artıyor mu?

Bu sorulara T13 (skip-week) test cevap verecek.

CSV: `07_LOG_VE_RAPORLAR/T12_entry_curve.csv`, `T12_week_stats.csv`
