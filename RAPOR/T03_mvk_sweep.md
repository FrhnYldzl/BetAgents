# T03 — Minimum Viable Kombin (MVK) Sweep

**Versiyon:** v1.0
**Tarih:** 2026-05-27T20:59:36
**Toplam hafta:** 697

---

## Yöntem

Her config için: K-leg combo per matchday, eşikler farklı.

**Sırala:** Önce edge_pos (CI sıfır üstü), sonra coverage (en az %30), sonra avg_pnl.

---

## TOP 20 Konfig

| Strateji | n hafta | Coverage | PWR | Avg Odd | Avg PnL | CI95 | Total PnL | Verdikt |
|---|---:|---:|---:|---:|---:|---|---:|:---:|
| K2 FAV_CONFIRMED | 461 | 66% | 39.5% | 3.23 | +14.30% | [+0.6%, +29.3%] | +65.9 | POZITIF |
| K3 FAV_CONFIRMED | 338 | 48% | 23.4% | 5.87 | +16.74% | [-7.0%, +43.1%] | +56.6 | MARJINAL |
| K1 FAV_CONFIRMED | 642 | 92% | 62.8% | 1.77 | +6.59% | [-0.4%, +13.0%] | +42.3 | MARJINAL |
| K1 just_FAV | 697 | 100% | 61.8% | 1.78 | +6.18% | [-0.4%, +12.6%] | +43.1 | MARJINAL |
| K1 cons sig2/ag2 | 100 | 14% | 62.0% | 1.97 | +15.34% | [-4.8%, +36.5%] | +15.3 | MARJINAL |
| K1 cons sig3/ag2 | 100 | 14% | 62.0% | 1.97 | +15.34% | [-6.2%, +37.2%] | +15.3 | MARJINAL |
| K2 cons sig2/ag2 | 14 | 2% | 28.6% | 5.50 | +12.88% | [-71.2%, +116.1%] | +1.8 | MARJINAL |
| K2 cons sig3/ag2 | 14 | 2% | 28.6% | 5.50 | +12.88% | [-71.2%, +112.4%] | +1.8 | MARJINAL |
| K3 cons sig2/ag2 | 3 | 0% | 0.0% | 7.93 | -100.00% | [-100.0%, -100.0%] | -3.0 | negatif |
| K3 cons sig3/ag2 | 3 | 0% | 0.0% | 7.93 | -100.00% | [-100.0%, -100.0%] | -3.0 | negatif |

---

## Sonraki Adım

En iyi config (verdikt POZITIF + coverage > %30 + PWR > %50) production'a alınacak.

Picks CSV: `07_LOG_VE_RAPORLAR/T03_best_picks.csv`
