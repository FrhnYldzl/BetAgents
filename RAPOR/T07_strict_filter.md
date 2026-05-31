# T07 — K=3 Strict Filter (>=N confirmers)

**Versiyon:** v1.0
**Tarih:** 2026-05-27T21:08:17

---

## Hipotez

K=3 FAV_CONFIRMED stratejisinde **kaç sinyal favoriyi teyit etmeli?**
Sıkı filtre PWR'yi artırır mı yoksa sample küçülüp gürültü mü artar?

---

## Sonuçlar — Lig × N_confirmers

| Strateji | n | Won | PWR | Breakeven | Avg Odd | Avg PnL | CI95 | Verdikt |
|---|---:|---:|---:|---:|---:|---:|---|:---:|
| T1 only (>=1 confirm) | 103 | 25 | 24.3% | 13.0% | 7.69 | +60.33% | [+3.6%, +125.1%] | ✅ EDGE |
| ALL (>=1 confirm) | 338 | 79 | 23.4% | 17.0% | 5.87 | +16.74% | [-8.0%, +42.2%] | ➕ |
| E0+T1 (>=2 confirm) | 25 | 5 | 20.0% | 14.8% | 6.74 | +13.96% | [-68.5%, +112.5%] | ➕ |
| E0+T1 (>=1 confirm) | 293 | 66 | 22.5% | 16.9% | 5.90 | +9.56% | [-14.8%, +35.7%] | ➕ |
| E0 only (>=1 confirm) | 169 | 36 | 21.3% | 18.1% | 5.52 | +6.93% | [-25.9%, +43.6%] | ➕ |
| ALL (>=2 confirm) | 58 | 10 | 17.2% | 14.8% | 6.74 | +6.46% | [-50.8%, +72.0%] | ➕ |
| E0 only (>=2 confirm) | 11 | 1 | 9.1% | 15.7% | 6.37 | -33.80% | [-100.0%, +98.6%] | ➖ |
| T1 only (>=2 confirm) | 1 | 0 | 0.0% | 8.7% | 11.51 | -100.00% | [-100.0%, -100.0%] | ➖ |

---

## Yorum

CI95 sıfır üstü olan en sıkı filtre = optimum production config.

Picks CSV: `07_LOG_VE_RAPORLAR/T07_picks.csv`
