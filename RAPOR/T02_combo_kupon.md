# T02 — Combo Kupon Konsensüs

**Versiyon:** v1.0
**Tarih:** 2026-05-27T20:58:17

---

## Hipotez

Her hafta konsensüs maçlardan en yüksek score'lu K'sını seç → K-leg combo kuponu.
Tüm leg'ler tutarsa kazanırız.

**Başarı:** PWR > 1/avg_combo_odd^K (breakeven üzerinde olan tutarlı oran)

---

## Sonuçlar — K ∈ {2, 3, 4}

| K | n hafta | Won | **PWR** | Breakeven | Avg Odd | Avg PnL/hafta | CI95 | Tot PnL | Verdikt |
|---|---:|---:|---:|---:|---:|---:|---|---:|:---:|
| **2** | 14 | 4 | 28.6% | 18.2% | 5.50 | +12.88% | [-71.2%, +114.8%] | +1.80 | ⚠️ BELİRSİZ |
| **3** | 3 | 0 | 0.0% | 12.6% | 7.93 | -100.00% | [-100.0%, -100.0%] | -3.00 | ⚠️ BELİRSİZ |

---

## Yorum

- K=2 combo: kombinli oran düşük (~3-4) → kolayca breakeven üstü olabilir
- K=3 combo: oran ~7-10 → daha az hafta kazanır ama oran yüksek
- K=4 combo: oran ~20+ → çok riskli ama büyük getiri

**En tutarlı PWR**: hangi K?

Picks CSV: `07_LOG_VE_RAPORLAR/T02_picks.csv`
