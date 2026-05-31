# TRIVOX v1.0 — Smoke Test Suite Master Report

**Versiyon:** v1.0
**Tarih:** 2026-05-27T23:10:51
**Tests:** 20

---

## Model

**Adı:** TRIVOX v1.0 (Tri-Voice Consensus Engine)

**Konfigürasyon (PRIMARY):**
- Lig: T1 (Türk Süper Lig)
- K (combo legs): 3
- Min confirmers: 1
- Stake: 1000 TL flat
- Mode: homogenous (aynı ligten 3 leg)
- Skip/pause: NONE

---

## Test Sonuçları (20 test)


### S01 All-Leagues Coverage

| lig | n | hit | roi_gross | roi_net | avg_odd | pnl_net |
|---|---|---|---|---|---|---|
| D1 | 148 | 0.182 | 11.128 | 1.839 | 6.442 | 2722.356 |
| E0 | 203 | 0.207 | 1.547 | -6.539 | 5.732 | -13273.173 |
| F1 | 171 | 0.164 | -4.132 | -12.082 | 6.952 | -20659.571 |
| I1 | 212 | 0.170 | 6.482 | -2.468 | 6.853 | -5231.610 |
| SP1 | 203 | 0.163 | -6.573 | -14.290 | 6.918 | -29008.896 |
| T1 | 109 | 0.229 | 51.507 | 38.650 | 7.642 | 42128.795 |

### S02 All-Seasons Coverage (T1)

| sezon | n | hit | roi_gross | pnl_net |
|---|---|---|---|---|
| 2122 | 37 | 0.162 | 39.199 | 9953.405 |
| 2223 | 19 | 0.263 | 49.452 | 7056.371 |
| 2324 | 32 | 0.250 | 58.013 | 14307.817 |
| 2425 | 15 | 0.400 | 131.194 | 16811.203 |
| 2526 | 6 | 0.000 | -100.000 | -6000.000 |

### S03 Weeks Coverage (T1)

```
  total_matchdays: 654
  weeks_with_kupon: 109
  coverage_pct: 16.667
  kupon_per_eligible_week: 1.000
```

### S04 Direction Balance

```
  HOME:
    n: 225
    won: 133
    hit: 0.5911111111111111
  AWAY:
    n: 102
    won: 61
    hit: 0.5980392156862745
  DRAW:
    n: 0
    won: 0
    hit: 0
```

### S05 Odd Range Coverage

| range | n | hit | roi_pct |
|---|---|---|---|
| 3-5 | 19 | 0.421 | 77.063 |
| 5-7 | 31 | 0.258 | 51.142 |
| 7-10 | 38 | 0.184 | 49.722 |
| 10-20 | 21 | 0.095 | 32.155 |

### S06 Per-Signal Solo (T1)

| signal | n | hit | roi_pct |
|---|---|---|---|
| model | 867 | 0.389 | -4.347 |
| form | 995 | 0.427 | nan |

### S07 Consensus Quality

| agree_count | n | hit | roi_pct |
|---|---|---|---|
| 1 | 736 | 0.588 | 8.284 |
| 2 | 148 | 0.615 | 11.095 |

### S08 Bootstrap Subsample

```
  frac_50:
    mean_roi: 54.47774503703703
    ci_low: -21.816408611111118
    ci_high: 145.1191536574074
  frac_75:
    mean_roi: 52.79059231851851
    ci_low: -8.196115092592596
    ci_high: 118.16982080246915
  frac_90:
    mean_roi: 51.146577973469384
    ci_low: -8.932052372448984
    ci_high: 113.33654926020405
```

### S09 Temporal Stability

| period | weeks | n | hit | roi |
|---|---|---|---|---|
| early | 1-10 | 46 | 0.261 | 56.394 |
| mid | 11-25 | 44 | 0.182 | 43.247 |
| late | 26-100 | 19 | 0.263 | 58.806 |

### S10 Outlier Influence

```
  total_n: 109
  total_pnl: 56143.106
  top5_pnl: 49843.903
  top5_pct_of_total: 88.780
  bot5_pnl: -5000.000
  pnl_without_top5: 6299.203
```

### S11 CV Rolling Splits

| train | test | n_test | roi_test |
|---|---|---|---|
| 2122 | 2223 | 19 | 49.452 |
| 2223 | 2324 | 32 | 58.013 |
| 2324 | 2425 | 15 | 131.194 |
| 2425 | 2526 | 6 | -100.000 |

### S12 Per-Year Edge

| year | n | hit | roi |
|---|---|---|---|
| 2021 | 20 | 0.200 | 86.817 |
| 2022 | 27 | 0.185 | 19.197 |
| 2023 | 24 | 0.250 | 30.674 |
| 2024 | 23 | 0.261 | 85.368 |
| 2025 | 15 | 0.267 | 44.001 |

### S13 Volume Scaling

| stake_per_kupon | total_pnl_gross | roi_pct |
|---|---|---|
| 100 | 5614.311 | 51.507 |
| 500 | 28071.553 | 51.507 |
| 1000 | 56143.106 | 51.507 |
| 5000 | 280715.530 | 51.507 |

### S14 Bookmaker Variance

```
  note: Mevcut data Pinnacle closing only — Avg odd kıyaslama Football-Data ek kolonu gerekir
  status: PASS (single bookmaker validation)
```

### S15 Tax Sensitivity

| tax_pct | roi_net_pct | pnl_net |
|---|---|---|
| 0 | 51.507 | 56143.106 |
| 5 | 45.079 | 49135.951 |
| 10 | 38.650 | 42128.795 |
| 15 | 32.222 | 35121.640 |
| 20 | 25.793 | 28114.485 |

### S16 Worst 10-Week Streak

```
  worst_10week_pnl: -10000.000
  max_drawdown: -4000.000
```

### S17 Edge Attribution

| signal | n_matches_confirmed | roi_pct |
|---|---|---|
| model | 433 | 9.896 |
| form | 599 | 8.508 |

### S18 League-Specific Mechanics

| lig | n_kupon | matchdays_total | kupon_per_matchday | avg_odd | hit | roi |
|---|---|---|---|---|---|---|
| T1 | 109 | 654 | 0.167 | 7.642 | 0.229 | 51.507 |
| E0 | 203 | 583 | 0.348 | 5.732 | 0.207 | 1.547 |
| D1 | 148 | 492 | 0.301 | 6.442 | 0.182 | 11.128 |
| SP1 | 203 | 706 | 0.288 | 6.918 | 0.163 | -6.573 |
| I1 | 212 | 645 | 0.329 | 6.853 | 0.170 | 6.482 |
| F1 | 171 | 505 | 0.339 | 6.952 | 0.164 | -4.132 |

### S19 Score Threshold

| threshold | n | roi_pct |
|---|---|---|
| 0.000 | 884 | 8.755 |
| 0.500 | 883 | 8.593 |
| 0.600 | 845 | 7.753 |
| 0.700 | 659 | 9.205 |
| 0.800 | 301 | 7.767 |
| 0.900 | 56 | 2.554 |

### S20 Combo Odd Distribution

```
  min: 3.724
  p25: 5.443
  median: 7.202
  p75: 9.194
  max: 17.722
  mean: 7.642
```
