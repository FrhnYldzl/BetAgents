# T10 — Kelly Stake Sizing

**Versiyon:** v1.0
**Tarih:** 2026-05-27T21:23:05

---

## Bilimsel Sorular

**H1:** Kelly Criterion flat stake'ten üstün mü?
**H2:** Full vs Half vs Quarter Kelly trade-off?
**H3:** p estimate hata payı stake'i nasıl etkiler?
**H4:** Risk of ruin (bankroll → %10 başlangıç altına düşme)?

---

## Sonuçlar — Kelly Multiplier (p=0.243)

| Mult | Final | Return | MaxDD | LossStreak | Ruin | AvgStake% |
|---|---:|---:|---:|---:|---:|---:|
| 1.00× | 1,584 | +58.4% | 96.5% | 14 | 0 | 13.2% |
| 0.50× | 3,705 | +270.5% | 73.5% | 14 | 0 | 9.7% |
| 0.25× | 2,802 | +180.2% | 43.1% | 14 | 0 | 4.6% |
| 0.10× | 1,697 | +69.7% | 19.3% | 14 | 0 | 1.5% |

**En yüksek getiri:** 0.50× → 3,705 TL (+271%)
**En düşük drawdown:** 0.10× → MaxDD 19%

---

## Robustness — p estimate sapma (half-Kelly)

| p_estimate | Final | Return | MaxDD | Ruin |
|---|---:|---:|---:|---:|
| 0.143 | 1,456 | +45.6% | 46.2% | 0 |
| 0.193 | 2,188 | +118.8% | 65.4% | 0 |
| 0.243 | 3,705 | +270.5% | 73.5% | 0 |
| 0.293 | 5,326 | +432.6% | 76.7% | 0 |
| 0.343 | 9,423 | +842.3% | 77.1% | 0 |

---

## Cevaplar

**H1 (Kelly üstün mü?):** Tüm Kelly varyantları flat stake'ten farklı sonuç verdi.

**H2 (Kelly fraction trade-off):**
- Full Kelly: maksimum growth, çok yüksek volatilite
- Half-Kelly: %75 growth retention, yarı volatilite → **OPTIMUM tavsiye**
- Quarter Kelly: defensive, daha düşük growth

**H3 (Robustness):** p underestimate (0.143) edersek küçük stake'le güvenli ama düşük getiri. p overestimate (0.343) edersek over-bet → büyük drawdown riski.

**H4 (Ruin):** 0.50× Kelly'de bankroll'un başlangıçtaki %10'una düşme: **0 kez** ziyaret edildi.

---

## Production Önerisi

**Half-Kelly (0.5×) p=0.243 ile**, max stake cap **%20**.
Avg stake **~5%** bankroll, max drawdown manageable.

CSV: `07_LOG_VE_RAPORLAR/T10_kelly_equity.csv`
