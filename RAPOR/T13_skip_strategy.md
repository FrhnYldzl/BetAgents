# T13 — Skip Week (PAS) Stratejisi

**Versiyon:** v1.0
**Tarih:** 2026-05-27T21:37:35

---

## Bilimsel Sorular

**H7a:** Düşük sinyal yoğunluklu haftalar kaybettiriyor?
**H7b:** Belirli season_week aralıkları sürekli kötü?
**H7c:** Combo odd çok yüksek olduğunda hit rate düşer?

---

## Sonuçlar

| Skip Rule | n play | n skip | Hit% | Avg Odd | Hacim | Net PnL | ROI | vs Baseline |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| baseline | 103 | 0 | 24% | 7.69 | 103,000 | +62,143 | +60.3% | +0 |
| skip_dark_weeks | 80 | 23 | 31% | 7.45 | 80,000 | +85,143 | +106.4% | +23,000 |
| skip_low_score | 98 | 5 | 23% | 7.48 | 98,000 | +49,167 | +50.2% | -12,976 |
| skip_high_odd | 74 | 29 | 28% | 6.34 | 74,000 | +45,022 | +60.8% | -17,122 |
| skip_low_signals | 98 | 5 | 24% | 7.71 | 98,000 | +58,118 | +59.3% | -4,025 |
| multi_dark_high | 63 | 40 | 33% | 6.34 | 63,000 | +56,022 | +88.9% | -6,122 |
| season_start_only | 60 | 43 | 30% | 7.44 | 60,000 | +55,970 | +93.3% | -6,173 |
| season_end_only | 15 | 88 | 33% | 7.08 | 15,000 | +15,173 | +101.2% | -46,970 |
| skip_first5 | 83 | 20 | 22% | 7.82 | 83,000 | +38,959 | +46.9% | -23,184 |
| midseason_W6_15 | 40 | 63 | 28% | 7.59 | 40,000 | +32,786 | +82.0% | -29,357 |

---

## Yorum

**En iyi skip rule:** `skip_dark_weeks` → ROI +106.4%, net +85,143 TL (baseline'dan +23,000 TL üstün)

**En kötü skip rule:** `season_end_only` → ROI +101.2%

### Önemli sorular:
1. **Skip rule edge'i artırdı mı?** Evet/hayır → veriye göre
2. **Sample boyutu yeterli mi?** Skip sonrası n düşmemeli
3. **Out-of-sample doğrulanır mı?** 2425 sezonu için test edilmeli

CSV: `07_LOG_VE_RAPORLAR/T13_skip_results.csv`
