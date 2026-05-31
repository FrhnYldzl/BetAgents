# DD DEEP TEST — 20 Acquirer Sorusu (Backtest derinliği)

**Tarih:** 2026-05-27T23:29:37
**Sample:** 4 sezon (2122-2425) backtest data


### Q1 Lookback Window


**TRIVOX:**

| n_train_seasons | test_season | n_kupon | roi |
|---|---|---|---|
| 1 | 2223 | 19 | 49.452 |
| 1 | 2324 | 32 | 58.013 |
| 1 | 2425 | 15 | 131.194 |
| 2 | 2324 | 32 | 58.013 |
| 2 | 2425 | 15 | 131.194 |
| 3 | 2425 | 15 | 131.194 |

**EUVOX:**

| n_train_seasons | test_season | n_kupon | roi |
|---|---|---|---|
| 1 | 2223 | 210 | 29.576 |
| 1 | 2324 | 217 | 17.115 |
| 1 | 2425 | 204 | 35.111 |
| 2 | 2324 | 217 | 17.115 |
| 2 | 2425 | 204 | 35.111 |
| 3 | 2425 | 204 | 35.111 |

### Q2 Edge Attribution

| signal | n | hit | roi |
|---|---|---|---|
| model | 2055 | 0.568 | 11.349 |
| xg | 1931 | 0.533 | 0.433 |
| form | 3690 | 0.578 | -0.037 |

### Q3 Random Control

  TRIVOX_model_roi: 60.33311262135922
  TRIVOX_random_roi: nan
  EUVOX_model_roi: 20.416113078703702
  EUVOX_random_roi: 24.3760630787037

### Q4 Outlier Removal


**TRIVOX:**

| top_excluded | n_remaining | pnl | roi |
|---|---|---|---|
| 0 | 103 | 62143.106 | 60.333 |
| 5 | 98 | 12299.203 | 12.550 |
| 10 | 93 | -19373.014 | -20.831 |
| 20 | 83 | -63906.087 | -76.995 |

**EUVOX:**

| top_excluded | n_remaining | pnl | roi |
|---|---|---|---|
| 0 | 864 | 176395.217 | 20.416 |
| 5 | 859 | 121291.447 | 14.120 |
| 10 | 854 | 81854.400 | 9.585 |
| 20 | 844 | 22062.508 | 2.614 |

### Q5 Calibration


**TRIVOX:**
```
  n: 103
  avg_implied_prob: 0.148
  actual_hit_rate: 0.243
  brier_score: 0.183
  calibration_gap: -0.095
```

**EUVOX:**
```
  n: 864
  avg_implied_prob: 0.294
  actual_hit_rate: 0.333
  brier_score: 0.213
  calibration_gap: -0.040
```

### Q7 Per-Direction


**TRIVOX:**
```
  HOME:
    n: 215
    hit: 0.5906976744186047
    avg_odd: 1.9592558139534884
  AWAY:
    n: 94
    hit: 0.6170212765957447
    avg_odd: 2.032340425531915
  DRAW:
    n: 0
    hit: 0
    avg_odd: 0
```

**EUVOX:**
```
  HOME:
    n: 1186
    hit: 0.6087689713322091
    avg_odd: 1.8067200674536237
  AWAY:
    n: 741
    hit: 0.5748987854251012
    avg_odd: 1.9535627530364414
  DRAW:
    n: 0
    hit: 0
    avg_odd: 0
```

### Q10 Sample Size Sensitivity


**TRIVOX:**

| n_sample | mean_roi | std_roi | ci_low | ci_high |
|---|---|---|---|---|
| 25 | 62.122 | 62.011 | -52.624 | 181.852 |
| 50 | 62.835 | 46.448 | -14.403 | 163.543 |
| 100 | 63.598 | 32.245 | 1.390 | 125.282 |
| 103 | 62.152 | 30.285 | 0.916 | 116.203 |

**EUVOX:**

| n_sample | mean_roi | std_roi | ci_low | ci_high |
|---|---|---|---|---|
| 25 | 16.235 | 38.670 | -51.051 | 103.401 |
| 50 | 21.262 | 27.038 | -26.021 | 71.414 |
| 100 | 19.704 | 20.979 | -18.020 | 62.068 |
| 200 | 18.699 | 14.672 | -12.976 | 47.494 |
| 864 | 20.191 | 6.847 | 7.275 | 33.009 |

### Q12 Monte Carlo 1000TL Bankroll


**TRIVOX:**
```
  median_final: 4107.155
  mean_final: 4070.191
  p5_final: 4107.155
  p95_final: 4107.155
  prob_bankrupt: 0.009
  prob_2x: 0.991
```

**EUVOX:**
```
  median_final: 9819.761
  mean_final: 9073.141
  p5_final: 0.000
  p95_final: 9819.761
  prob_bankrupt: 0.076
  prob_2x: 0.924
```

### Q15 Worst Quarter


**TRIVOX:**
```
  worst_quarter_pnl: -14000.000
  worst_quarter_start: 2021-12-18
```

**EUVOX:**
```
  worst_quarter_pnl: -19584.340
  worst_quarter_start: 2021-12-15
```

### Q20 Time Decay


**TRIVOX:**
```
  yearly: [{'year': 2021, 'n': 20, 'roi': 86.81708}, {'year': 2022, 'n': 27, 'roi': 19.197003703703704}, {'year': 2023, 'n': 24, 'roi': 30.673720833333327}, {'year': 2024, 'n': 23, 'roi': 85.36801739130435}, {'year': 2025, 'n': 9, 'roi': 140.00180000000003}]
  trend_slope_per_year: 13.296
```

**EUVOX:**
```
  yearly: [{'year': 2021, 'n': 107, 'roi': 12.23898691588785}, {'year': 2022, 'n': 212, 'roi': 11.392586320754715}, {'year': 2023, 'n': 224, 'roi': 11.207511607142855}, {'year': 2024, 'n': 210, 'roi': 42.66982571428571}, {'year': 2025, 'n': 111, 'roi': 22.014196396396393}]
  trend_slope_per_year: 2.444
```
