# T16 — Loss-Streak Triggered Pause

**Versiyon:** v1.0
**Tarih:** 2026-05-27T21:44:08

---

## Bilimsel Soru

**H10a:** Ardışık 3+ kayıptan sonra pause ROI'yi artırır mı?
**H10b:** Bu **gambler's fallacy** mi yoksa gerçek mean reversion mi?

---

## Sonuçlar

| Streak ≥ | Pause N | n played | n paused | Hit% | PnL | ROI | vs Baseline |
|---|---|---:|---:|---:|---:|---:|---:|
| 0 | 0 | 103 | 0 | 24% | +62,143 | +60.3% | +0 |
| 2 | 1 | 77 | 26 | 23% | +53,017 | +68.9% | -9,126 |
| 2 | 2 | 63 | 40 | 24% | +30,461 | +48.4% | -31,682 |
| 2 | 3 | 55 | 48 | 25% | +46,862 | +85.2% | -15,281 |
| 2 | 5 | 38 | 65 | 21% | +19,934 | +52.5% | -42,209 |
| 3 | 1 | 89 | 14 | 25% | +50,326 | +56.5% | -11,817 |
| 3 | 2 | 79 | 24 | 27% | +57,973 | +73.4% | -4,170 |
| 3 | 3 | 70 | 33 | 30% | +70,219 | +100.3% | +8,076 |
| 3 | 5 | 48 | 55 | 21% | +6,874 | +14.3% | -55,269 |
| 4 | 1 | 92 | 11 | 25% | +58,052 | +63.1% | -4,091 |
| 4 | 2 | 83 | 20 | 28% | +70,298 | +84.7% | +8,155 |
| 4 | 3 | 73 | 30 | 25% | +40,300 | +55.2% | -21,843 |
| 4 | 5 | 58 | 45 | 21% | +14,931 | +25.7% | -47,213 |
| 5 | 1 | 94 | 9 | 26% | +65,666 | +69.9% | +3,523 |
| 5 | 2 | 85 | 18 | 24% | +42,409 | +49.9% | -19,734 |
| 5 | 3 | 79 | 24 | 22% | +17,709 | +22.4% | -44,434 |
| 5 | 5 | 73 | 30 | 25% | +35,686 | +48.9% | -26,457 |

---

## En İyi Varyant

`streak>=4, pause=2` →
PnL **+70,298** (baseline'dan +8,155)

---

## Gambler's Fallacy Testi

Overall hit rate: **24.3%**

Eğer outcome'lar bağımsızsa, loss-streak sonrası hit rate ≈ overall olmalı.
Eğer streak sonrası hit rate ANLAMLI farklıysa, mean reversion gerçek.

---

## Yorum

- Pause stratejisi marjinal etki yaratıyorsa: rastgelelik. Pas geçmek gereksiz.
- Belirgin ROI artışı varsa: serial correlation ipucu.
- Akademik tavsiye: bir trader pas geçme kararını **emosyonel kontrol** için kullanabilir,
  ancak **matematiksel edge** beklenmemeli.

CSV: `07_LOG_VE_RAPORLAR/T16_streak_results.csv`
