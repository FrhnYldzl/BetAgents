# EUVOX E11 — Per-Lig Tuning (DC dahil)

**Tarih:** 2026-05-27T23:08:01

DC modelleri SP1/I1/F1'e eklendi. Yeniden test.

---

## Default Config (K=3, min_conf=1, score_thr=0)

| Lig | n | Hit% | Avg Odd | Net PnL | ROI |
|---|---:|---:|---:|---:|---:|
| T1 | 109 | 23% | 7.64 | +56,143 | +51.5% |
| E0 | 203 | 21% | 5.73 | +3,141 | +1.5% |
| D1 | 148 | 18% | 6.44 | +16,469 | +11.1% |
| SP1 | 203 | 16% | 6.92 | -13,343 | -6.6% |
| I1 | 212 | 17% | 6.85 | +13,743 | +6.5% |
| F1 | 171 | 16% | 6.95 | -7,066 | -4.1% |

---

## Per-Lig En İyi Config (Grid Search)

| Lig | Config | n | Hit% | Avg Odd | Net PnL | ROI |
|---|---|---:|---:|---:|---:|---:|
| T1 | K3/mc1/thr0 | 109 | 23% | 7.64 | +56,143 | +51.5% |
| E0 | K2/mc1/thr0 | 306 | 38% | 3.16 | +35,816 | +11.7% |
| D1 | K3/mc1/thr0.7 | 108 | 19% | 6.29 | +23,239 | +21.5% |
| SP1 | K2/mc1/thr0 | 312 | 34% | 3.45 | +26,214 | +8.4% |
| I1 | K2/mc2/thr0.7 | 49 | 41% | 3.67 | +15,643 | +31.9% |
| F1 | K2/mc2/thr0 | 72 | 35% | 3.95 | +18,590 | +25.8% |

---

## EUVOX Birleşim (Pozitif edge ve n>=30)

**6/6 lig** eligible.

Toplam:
- n: 956
- pnl: +175,645 TL
- ROI: +18.4%

---

## Sonuç

EUVOX'un her ligi için **optimal config** tablonun üstünde.
