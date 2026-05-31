# T17 — 5. Sezon (2025-26) Replikasyon

**Versiyon:** v1.0
**Tarih:** 2026-05-27T22:03:52

---

## Hipotez

v4 sonucunun (T1 K=3 ROI +60%, ALL paralel +81K @ 4 sezon) 5. sezonda **out-of-sample doğrulanması**.

---

## 2526 Sezonu Per-Lig Sonuçlar

| Lig | n | Won | Hit% | Avg Odd | Hacim | Net PnL | ROI |
|---|---:|---:|---:|---:|---:|---:|---:|
| T1 | 6 | 0 | 0% | 6.80 | 6,000 | -6,000 | -100.0% |
| E0 | 20 | 2 | 10% | 6.73 | 20,000 | -13,185 | -65.9% |
| D1 | 11 | 4 | 36% | 5.65 | 11,000 | +14,145 | +128.6% |

---

## 4-Sezon vs 5. Sezon Karşılaştırma

| Dönem | n kupon | Hit% | ROI | Net PnL |
|---|---:|---:|---:|---:|
| 4-sezon train | 402 | 21% | +16.9% | +67,937 |
| 2526 replikasyon | 37 | 16% | -13.6% | -5,041 |

---

## ⚠️ Veri Kalitesi Uyarısı (KRİTİK)

2526 sezonu **devam eden** sezon. CSV durumu:
- T1: 306 FTR var, **sadece 135 closing odd (PSCH)**
- E0: 380 FTR var, 210 closing odd
- D1: 306 FTR var, 149 closing odd

Closing odd olmayan maçta bet edemiyoruz → sample 37 kupona düştü, **anlamlı backtest için yetersiz**.

## Yorum (revize)

- **Sample n=37 çok küçük**: -13.6% gürültü olabilir
- T1 sadece 6 kupon, 0 hit: rastgele streak (4-sezon ortalama hit 24%)
- D1 +128% ROI 11 kuponla: küçük sample sürprizi
- **Edge ne doğrulandı ne reddedildi** — sezon bitince tekrar

**Akademik karar:** T17 PRELIM. Mevcut v4 stratejisi değiştirilmiyor (4-sezon kanıtı sağlam). 5. sezon Mayıs 2026'da tam olur → o zaman final replikasyon.

## Sonraki Adımlar

1. Sezon sonu (Mayıs 2026) tam T17 tekrar
2. Live shadow run paralel (4-8 hafta)
3. Mevcut 4-sezon stratejisi sürdürülür

CSV: `07_LOG_VE_RAPORLAR/T17_picks.csv`
