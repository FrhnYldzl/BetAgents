# T08 — Bankroll Simülasyonu (T1 K=3, Single League)

**Versiyon:** v1.0
**Tarih:** 2026-05-27T21:19:00

---

## Bilimsel Sorular

**H1:** 1000 TL başlangıç bankroll'u ile T1 K=3 stratejisi 4 sezon sonunda ne yapar?
**H2:** Flat vs Compound stake — hangisi daha üstün?
**H3:** Maximum drawdown ne kadar (volatilite)?
**H4:** Risk-adjusted growth (Sharpe ratio)?
**H5:** En uzun kayıp serisi (psychological tolerance)?

---

## Sample

- **103 kupon** kronolojik (4 sezon × T1)
- Hit rate: **24.3%**
- Avg combo odd: **7.69**
- Tarih: 2021-09-11 → 2025-05-18

---

## Sonuçlar

| Strateji | Initial | Final | Return | n | Hit% | Avg Stake | MaxDD | LossStreak | Sharpe |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| flat | 1000 | 4,107 | +310.7% | 103 | 24% | 50 | 33.0% | 14 | 1.38 |
| pct5 | 1000 | 7,745 | +674.5% | 103 | 24% | 112 | 51.2% | 14 | 1.39 |
| pct2 | 1000 | 2,864 | +186.4% | 103 | 24% | 31 | 24.6% | 14 | 1.39 |
| kelly_full | 1000 | 4,765 | +376.5% | 94 | 21% | 154 | 77.5% | 14 | 1.11 |
| kelly_half | 1000 | 4,118 | +311.8% | 94 | 21% | 80 | 50.7% | 14 | 1.11 |

---

## Cevaplar

**H1 (Final):** 4,107 TL (flat 50 TL stake ile). Compound stratejilerde range: 2,864 - 7,745 TL.

**H2 (Flat vs Compound):** Compound stratejiler üstün; Kelly daha optimum (variance-aware).

**H3 (Drawdown):** Max DD %78 (en kötü strateji). Bankrollunuzun 78%'ini bir anda kaybedebilirsiniz.

**H4 (Sharpe):** Yıllık Sharpe range: 1.11 - 1.39. Sharpe > 1 = iyi.

**H5 (Streak):** En uzun kayıp serisi: 14 kupon. Psikolojik dayanıklılık gerekir.

---

## Yorum

Sistem **matematiksel olarak +EV** olsa da, equity curve **volatil**. Drawdown'a hazır olmak şart. Kelly fractional stake variance'i azaltır ama growth da azalır.

Equity curves CSV: `07_LOG_VE_RAPORLAR/T08_equity_curve.csv`
