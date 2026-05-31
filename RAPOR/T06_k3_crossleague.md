# T06 — K=3 Cross-League Validasyon

**Versiyon:** v1.0
**Tarih:** 2026-05-27T21:06:44

---

## Hipotez

K=3 FAV_CONFIRMED stratejisi, ligler karışık halde çalışıyor mu?
Lig kombinasyonları ve cross-only modu test edildi.

---

## Sonuçlar — K=3 farklı lig kombinasyonları

| Strateji | n | Won | PWR | Breakeven | Avg Odd | Avg PnL | CI95 | Verdikt |
|---|---:|---:|---:|---:|---:|---:|---|:---:|
| A) ALL leagues (E0+D1+T1) | 338 | 79 | 23.4% | 17.0% | 5.87 | +16.74% | [-8.0%, +42.2%] | ➕ marjinal |
| B) E0 + T1 only | 293 | 66 | 22.5% | 16.9% | 5.90 | +9.56% | [-14.8%, +35.7%] | ➕ marjinal |
| C) E0 + D1 | 258 | 61 | 23.6% | 17.8% | 5.63 | +13.94% | [-12.1%, +44.0%] | ➕ marjinal |
| D) D1 + T1 | 254 | 48 | 18.9% | 15.3% | 6.55 | +1.27% | [-25.7%, +27.7%] | ➕ marjinal |
| E) CROSS-ONLY (3 ayrı lig) | 193 | 38 | 19.7% | 17.2% | 5.82 | -2.24% | [-31.4%, +30.0%] | ➖ negatif |
| F) HOMOGENOUS (aynı lig 3 leg) | 258 | 55 | 21.3% | 15.6% | 6.41 | +13.35% | [-15.2%, +44.8%] | ➕ marjinal |
| Z) Sadece E0 | 169 | 36 | 21.3% | 18.1% | 5.52 | +6.93% | [-25.9%, +43.6%] | ➕ marjinal |
| Z) Sadece D1 | 125 | 23 | 18.4% | 16.0% | 6.24 | +5.46% | [-33.2%, +51.2%] | ➕ marjinal |
| Z) Sadece T1 | 103 | 25 | 24.3% | 13.0% | 7.69 | +60.33% | [+3.6%, +125.1%] | ✅ EDGE |

---

## Yorum

PWR > Breakeven & CI95 sıfır üstü olan strateji = production-ready.

CSV: `07_LOG_VE_RAPORLAR/T06_picks.csv`
