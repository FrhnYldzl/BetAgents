# EUVOX Faz I — Diagnostik

**Tarih:** 2026-05-27T22:30:16

T20'de 6-lig genişleme -38K zarar verdi. **Neden?**

---

## E01 — Per-Lig Coverage

| lig | n_settled | n_fav_dir | n_fc_match | n_kupon_K3 | coverage_pct |
|---|---|---|---|---|---|
| D1 | 1530 | 1373 | 845 | 137 | 27.85 |
| E0 | 1900 | 1730 | 1236 | 193 | 33.10 |
| F1 | 1372 | 1372 | 858 | 132 | 32.43 |
| I1 | 1520 | 1520 | 1023 | 170 | 33.14 |
| SP1 | 1520 | 1520 | 764 | 97 | 17.26 |
| T1 | 1750 | 1549 | 884 | 109 | 16.67 |


**Yorum:** FAV_CONFIRMED filtresinden geçen maç sayısı liglere göre değişir.
Az FC match → az kupon → az fırsat.

---

## E02 — DC Availability

| lig | n_total | has_dc | dc_pct | has_xg | xg_pct |
|---|---|---|---|---|---|
| D1 | 1530 | 1373 | 89.74 | 211 | 13.79 |
| E0 | 1900 | 1730 | 91.05 | 935 | 49.21 |
| F1 | 1372 | 0 | 0.00 | 723 | 52.70 |
| I1 | 1520 | 0 | 0.00 | 1017 | 66.91 |
| SP1 | 1520 | 0 | 0.00 | 417 | 27.43 |
| T1 | 1750 | 1549 | 88.51 | 0 | 0.00 |


**KRİTİK:** SP1, I1, F1'de DC modeli **YOK** (sadece T1, E0, D1).
FAV_CONFIRMED filtresinde DC sinyali en güçlü olduğundan, bu eksiklik zayıflığı açıklıyor.

---

## E03 — Signal Coverage Per League

| lig | anomaly_pct | model_pct | xg_pct | form_pct | all4_pct |
|---|---|---|---|---|---|
| D1 | 86.73 | 89.74 | 13.79 | 58.30 | 6.47 |
| E0 | 90.47 | 91.05 | 49.21 | 60.21 | 26.53 |
| F1 | 99.64 | 0.00 | 52.70 | 57.73 | 0.00 |
| I1 | 100.00 | 0.00 | 66.91 | 59.87 | 0.00 |
| SP1 | 99.87 | 0.00 | 27.43 | 56.91 | 0.00 |
| T1 | 88.51 | 88.51 | 0.00 | 56.86 | 0.00 |


**Yorum:** Sinyaller per-lig nasıl dağılıyor? all4 yüksekse iyi.

---

## E04 — Hit Rate Comparison

| lig | n_settled | fav_hit | fc_hit | k3_hit |
|---|---|---|---|---|
| D1 | 1530 | 0.54 | 0.56 | 0.19 |
| E0 | 1900 | 0.56 | 0.59 | 0.20 |
| F1 | 1372 | 0.53 | 0.55 | 0.18 |
| I1 | 1520 | 0.54 | 0.54 | 0.17 |
| SP1 | 1520 | 0.54 | 0.56 | 0.15 |
| T1 | 1750 | 0.56 | 0.59 | 0.23 |


**Yorum:**
- `fav_hit`: Hep favori baseline (referans)
- `fc_hit`: FAV_CONFIRMED filtre uygulanmış (en az 1 sinyal teyit)
- `k3_hit`: K=3 combo kupon hit rate

FAV_CONFIRMED filtresi fav_hit'ten ne kadar yüksek hit veriyor? Lig-spesifik.

---

## E05 — Per-Lig K=3 Combo Odd Distribution

| lig | n | min | p25 | median | p75 | max |
|---|---|---|---|---|---|---|
| D1 | 137 | 2.68 | 4.38 | 5.88 | 7.25 | 13.72 |
| E0 | 193 | 2.16 | 3.93 | 5.13 | 7.34 | 13.76 |
| F1 | 132 | 2.03 | 4.26 | 5.84 | 8.30 | 17.23 |
| I1 | 170 | 2.64 | 4.71 | 5.82 | 7.76 | 16.60 |
| SP1 | 97 | 2.32 | 4.57 | 5.96 | 7.76 | 16.76 |
| T1 | 109 | 3.72 | 5.44 | 7.20 | 9.19 | 17.72 |


**Yorum:** Combo odd dağılımı. Yüksek odd → daha az hit ama daha çok kazanç.

---

## Tespit (Diagnostik Sonucu)

1. **SP1, I1, F1'de DC modeli yok** — FAV_CONFIRMED filtresi zayıf
2. Her lig farklı **coverage, hit rate, odd dağılımı**
3. Lig-spesifik tuning gerek (T03 + T04 metodolojisi her lige uygulanmalı)

**Sonraki Adım:** Faz II — SP1, I1, F1 için DC modeli eğit.
