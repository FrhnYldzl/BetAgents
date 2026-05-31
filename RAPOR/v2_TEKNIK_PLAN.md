# 🔧 v2 TEKNİK PLAN — DATA + MODEL

**Tarih:** 2026-05-27
**Odak:** Sadece teknik. Data standardizasyon + Model v2.
**Hedef:** 2026-27 sezonu (Ağustos) için sağlam altyapı

---

## NEDEN v2

DD Deep Test eksiklikleri (TEKNİK):

| # | Eksiklik | DD Bulgusu | v2 Çözüm |
|---|---|---|---|
| 1 | TRIVOX outlier-dependent | Top 10 hariç ROI -%21 | Sample 3x + sıkı consensus |
| 2 | Calibration gap | %9.5 (TRIVOX), %4 (EUVOX) | Platt scaling |
| 3 | CLV ölçülmedi | Edge kanıt eksik | Opening odds entegrasyonu |
| 4 | Edge attribution zayıf | xG/form solo +%0 | Yeni sinyaller |
| 5 | 2526 sample küçük | TRIVOX n=6 anlamsız | Otomatik weekly sync |
| 6 | Bankrupt riski %7.6 | EUVOX 1000 TL'de | Half-Kelly + cap |
| 7 | Live shadow yok | Validation eksik | Auto pipeline |
| 8 | Sezon kodları karışık | 2122 vs 2024 vs 2024-25 | Canonical mapping |
| 9 | Takım isimleri farklı | "FC Cologne" vs "FC Koln" | team_aliases tablosu |
| 10 | Refresh manuel | Saatler/günler gecikme | Otomatik ETL |

---

# 📦 BÖLÜM 1 — DATA STANDARDİZASYON

## 1.1 Mevcut Veri Audit

### Kaynaklar
```
✅ Football-Data CSV mirror (huhao930422 GitHub)
   - T1, E0, D1, SP1, I1, F1 × 5 sezon (10,657 maç)
   - Format: 1X2 + OU + AH + CSV + BTTS yok

✅ Understat (soccerdata kütüphanesi)
   - E0, D1, SP1, I1, F1 × 4 sezon (7,156 maç)
   - T1 YOK (Understat desteklemiyor)

✅ api-football REST API
   - Free plan: 10 RPM, 100 req/gün
   - Fixtures: 2024 sezonu
   - Injuries: 2024 sezonu (15,475 kayıt)
   - fixture_statistics: 94 satır (rate limit nedeniyle az)

✅ iddaa.com sportsbookv2 API (reverse-engineered)
   - 60+ pazar her event için
   - Live snapshot kabul ediyor
```

### Tablolar (Mevcut)
```
signal_snapshots  10,657 kayıt   ← master (yeni)
fixtures          2,098          ← api-football 2024
xg_data           7,156          ← Understat
iddaa_odds        2,855          ← single snapshot
injuries          15,475         ← api-football 2024
odds              0              ← boş (legacy)
odds_anomaly_signals
tipster_picks
tipster_stats
```

### Standartlaşma Sorunları
```
❌ Sezon kodları: '2122' (FD) vs 2022 (Understat) vs '2024-25' (api-football)
❌ Takım isimleri:
   - "Bayer Leverkusen" (Understat) vs "Leverkusen" (FD) vs "B04" (iddaa)
   - "FC Cologne" vs "FC Koln" vs "Köln"
❌ Tarih formatları: ISO vs "DD/MM/YYYY"
❌ T1 xG kaynak yok
❌ 2526 sezonu yarı yüklü (closing odds %44-65)
❌ Refresh manuel
```

## 1.2 Yeni Master Şema: `matches_v2`

```sql
CREATE TABLE matches_v2 (
    -- Identity (multi-source mapping)
    match_id            INTEGER PRIMARY KEY AUTOINCREMENT,
    external_id_fd      TEXT,            -- Football-Data row hash
    external_id_us      TEXT,            -- Understat URL
    external_id_af      INTEGER,         -- api-football fixture_id
    external_id_iddaa   TEXT,            -- iddaa event ID

    -- Meta (canonical)
    league_code         TEXT NOT NULL,   -- 'T1','E0','D1','SP1','I1','F1'
    season              TEXT NOT NULL,   -- '2024-25', '2025-26', '2026-27'
    matchday            DATE NOT NULL,
    kickoff_utc         TIMESTAMP,
    home_team           TEXT NOT NULL,   -- canonical
    away_team           TEXT NOT NULL,

    -- Result
    status              TEXT,            -- 'NS','LIVE','FT','PST'
    home_score          INTEGER,
    away_score          INTEGER,
    home_score_ht       INTEGER,
    away_score_ht       INTEGER,

    -- Odds: Opening (CLV için kritik)
    opening_1           REAL, opening_X  REAL, opening_2  REAL,
    opening_over25      REAL, opening_under25 REAL,
    opening_source      TEXT,            -- 'B365', 'Pinnacle'
    opening_fetched_at  TIMESTAMP,

    -- Odds: Closing (Pinnacle = referans)
    closing_1           REAL, closing_X  REAL, closing_2  REAL,
    closing_over25      REAL, closing_under25 REAL,
    closing_btts_yes    REAL, closing_btts_no REAL,
    closing_source      TEXT,
    closing_fetched_at  TIMESTAMP,

    -- Statistics (Understat ve fixture_statistics)
    home_xg             REAL,
    away_xg             REAL,
    home_shots          INTEGER,
    away_shots          INTEGER,
    home_possession_pct REAL,
    away_possession_pct REAL,

    -- Injuries (api-football)
    home_key_injuries   INTEGER,         -- önemli oyuncu sakatlık sayısı
    away_key_injuries   INTEGER,
    home_lineup_quality REAL,             -- 0-1 (starting 11 vs B-team)
    away_lineup_quality REAL,

    -- Quality flags
    has_full_odds       INTEGER DEFAULT 0,  -- closing tam mı?
    has_opening_odds    INTEGER DEFAULT 0,  -- CLV için lazım
    has_xg              INTEGER DEFAULT 0,
    has_result          INTEGER DEFAULT 0,
    is_settled          INTEGER DEFAULT 0,
    quality_score       REAL,             -- 0-1, eksik veri bayrak

    -- Audit
    ingested_at         TIMESTAMP,
    refreshed_at        TIMESTAMP,

    UNIQUE(league_code, season, matchday, home_team, away_team)
);

CREATE INDEX idx_m2_league_season ON matches_v2(league_code, season);
CREATE INDEX idx_m2_matchday ON matches_v2(matchday);
CREATE INDEX idx_m2_settled ON matches_v2(is_settled, has_result);
CREATE INDEX idx_m2_quality ON matches_v2(quality_score);
```

## 1.3 team_aliases Tablosu (Canonical Mapping)

```sql
CREATE TABLE team_aliases (
    canonical_name      TEXT NOT NULL,    -- target name (Football-Data style)
    alias               TEXT NOT NULL,    -- as appears in source
    source              TEXT NOT NULL,    -- 'fd','us','af','iddaa'
    league_code         TEXT,
    PRIMARY KEY(alias, source, league_code)
);

-- Örnek girdiler:
-- ('Leverkusen', 'Bayer Leverkusen', 'us', 'D1')
-- ('Leverkusen', 'Bayer 04 Leverkusen', 'af', 'D1')
-- ('FC Koln', 'FC Cologne', 'us', 'D1')
-- ('M\'gladbach', 'Borussia M.Gladbach', 'us', 'D1')
-- ('RB Leipzig', 'RasenBallsport Leipzig', 'us', 'D1')
```

## 1.4 seasons_meta Tablosu

```sql
CREATE TABLE seasons_meta (
    league_code         TEXT,
    season              TEXT,            -- '2026-27'
    start_date          DATE,
    end_date            DATE,
    n_total_matches     INTEGER,
    n_settled           INTEGER,
    coverage_pct        REAL,
    last_refresh        TIMESTAMP,
    PRIMARY KEY(league_code, season)
);
```

## 1.5 Sezon Kodu Canonical

```
ESKİ              YENİ        START          END
'2122'         →  '2021-22'   2021-08-01     2022-06-30
'2223'         →  '2022-23'   2022-08-01     2023-06-30
'2324'         →  '2023-24'   2023-08-01     2024-06-30
'2425'         →  '2024-25'   2024-08-01     2025-06-30
'2526'         →  '2025-26'   2025-08-01     2026-06-30
'2627' (NEW)   →  '2026-27'   2026-08-01     2027-06-30
```

## 1.6 ETL Pipeline (Otomatik)

```
DAILY CRON (03:00 UTC):
  1. football_data_sync()
     - Mirror'dan CSV diff çek
     - Sezonlar: '2021-22' → şu anki
     - matches_v2'ye INSERT/UPDATE

  2. understat_sync()
     - soccerdata.Understat()
     - 5 lig × current_season
     - matches_v2.home_xg / away_xg güncelle

  3. api_football_sync()
     - Fixtures + injuries
     - Rate-limited (10 RPM)
     - matches_v2 + lineup_quality

  4. team_alias_resolve()
     - Yeni takım çıkarsa fuzzy match + manual review queue

  5. quality_check_all()
     - quality_score per match
     - Eksik veri log + bayrak

  6. signal_compute_v2()
     - 8 sinyal hesabı
     - signal_snapshots_v2 tablosuna yaz

HOURLY (matchday ± 24h):
  7. iddaa_snapshot()
     - Live odds → odds_snapshots tablosu
     - Line movement compute

  8. opening_odds_pinnacle()
     - Pinnacle API (eğer entegre edilirse)
     - matches_v2.opening_* güncelle

REALTIME (maç bitince):
  9. settle_results()
     - api-football final score
     - matches_v2.home_score, .is_settled update
     - Active picks settle
```

## 1.7 Quality Score Hesabı

```python
def quality_score(m: matches_v2) -> float:
    score = 1.0
    if not m.has_full_odds:        score -= 0.30
    if not m.has_opening_odds:     score -= 0.20  # CLV için
    if not m.has_xg:               score -= 0.15
    if not m.home_lineup_quality:  score -= 0.10
    if m.is_past_24h and not m.has_result:
        score -= 0.25  # geç settle
    return max(0, score)

# quality_score >= 0.7 olan kuponlar production-ready
# quality_score < 0.7 olan picks WARNING bayraklı
```

---

# 🤖 BÖLÜM 2 — MODEL v2 TEKNİK

## 2.1 TRIVOX v2.0 (T1 odaklı)

### DD Endişelerini Gideren Tasarım

#### A) Sample Büyütme
```
Mevcut: 2021-22 → 2024-25 (4 sezon, ~1500 T1 maç)
v2: 2017-18 → 2025-26 (9 sezon, ~3200 T1 maç)

Pre-COVID lig dinamikleri öğrenilir
Sample 3x artar → outlier-dependence azalır
```

#### B) Yeni Sinyaller (4 → 6)

```python
SIGNALS_TRIVOX_V2 = [
    "anomaly_1x2",      # cross-market 1X2-normalize (v1.2)
    "model_dc",         # Platt-calibrated Dixon-Coles
    "form_5",           # rolling 5 weighted
    "injury_lineup",    # YENI: api-football injuries → lineup quality
    "rest_days",        # YENI: günler since last match
    "xg_sofascore",     # YENI: T1 için Sofascore xG (web scrape)
]
```

#### C) Platt Scaling Calibration

```python
# DC model raw probability → kalibre edilmiş probability
# Logistic regression: p_calibrated = 1 / (1 + exp(a*log(p_raw/(1-p_raw)) + b))

def fit_platt(raw_probs, actual_wins):
    """Sample'dan a, b öğren."""
    ...

# Her lig için ayrı Platt params
```

#### D) Konsensüs Eşik Yükseltme

```yaml
TRIVOX v2 FAV_CONFIRMED:
  min_confirmers: 2 of 6 (eskiden 1 of 4)
  sebebi: 6 sinyalden ≥2 teyit = daha güvenilir
```

#### E) Spec

```yaml
TRIVOX v2.0:
  ligler: [T1]
  sezonlar: 2017-18 → 2025-26 (9 sezon)
  K (combo legs): 3
  min_confirmers: 2 / 6
  score_threshold: 0.75
  calibration: Platt scaling per signal
  stake: Half-Kelly + max %5 bankroll

  hedefler:
    sample: 109 → 300+ kupon
    outlier risk: %88 → %40
    Brier: 0.18 → 0.12
    ROI: stabil +%40
```

## 2.2 EUVOX v2.0 (6-lig hibrit)

### DD Endişelerini Gideren Tasarım

#### A) CLV Entegrasyonu (KRİTİK)

```python
def compute_clv(opening_odd, closing_odd):
    """Closing Line Value: profesyonel bahisçinin altın metriği."""
    if not opening_odd or not closing_odd:
        return None
    return (opening_odd / closing_odd) - 1.0
    # Positive CLV = sharp money sizinle aynı yönde → uzun vadeli edge
```

Pinnacle API ya da B365 opening fallback ile her pick için CLV hesabı.

#### B) Platt Scaling per Lig

Her ligin Dixon-Coles output'u kendi sample'ında kalibre edilir:

```python
calibration_models = {
    "T1":  PlattScaler.fit(T1_DC_probs, T1_actual),
    "E0":  PlattScaler.fit(E0_DC_probs, E0_actual),
    "D1":  PlattScaler.fit(D1_DC_probs, D1_actual),
    "SP1": PlattScaler.fit(SP1_DC_probs, SP1_actual),
    "I1":  PlattScaler.fit(I1_DC_probs, I1_actual),
    "F1":  PlattScaler.fit(F1_DC_probs, F1_actual),
}
```

#### C) Adaptive Per-Lig Config (Weekly Refit)

```python
def refit_per_league_config(league, lookback_n=200):
    """Son 200 kupon'la lig konfigi yeniden tune."""
    cand_K = [2, 3, 4]
    cand_mc = [1, 2, 3]
    cand_thr = [0.0, 0.5, 0.7, 0.85]
    # Grid search → en yüksek Sharpe
    return best_config
```

Mevsim/dönem değişimine uyum (mid-season form değişimi, transfer dönemi etkisi).

#### D) Yeni Sinyaller (4 → 8)

```python
SIGNALS_EUVOX_V2 = [
    "anomaly_1x2",
    "model_dc_platt",
    "xg_understat",
    "form_5_weighted",
    "injury_lineup",       # YENI
    "rest_days",           # YENI
    "sharp_money",         # YENI: Pinnacle line movement
    "weather_yagmur",      # YENI (opsiyonel): yağmur → under sinyali
]
```

#### E) Smart Stake Sizing

```python
def stake_v2(bankroll, p_estimate, odd, edge_strength):
    """Half-Kelly + bankroll cap + edge-strength multiplier."""
    b = odd - 1
    kelly_full = (b * p_estimate - (1 - p_estimate)) / b
    kelly_half = max(0, kelly_full * 0.5)
    cap = bankroll * 0.05  # max %5
    stake = min(kelly_half * bankroll, cap)
    # Edge-strength multiplier (0.5 - 1.5)
    stake *= (0.5 + edge_strength)
    return max(stake, 0)
```

#### F) Spec

```yaml
EUVOX v2.0:
  ligler: [T1, E0, D1, SP1, I1, F1]
  sezonlar: 2021-22 → 2025-26 (5 sezon)
  per_lig_config: weekly adaptive refit
  signals: 8
  calibration: Platt per lig
  stake: Half-Kelly + max %5 cap + edge multiplier

  hedefler:
    calibration gap: %4 → %1
    CLV: ölçülür (hedef +%1)
    Bankrupt riski: %7.6 → %3
    ROI: %18 → %22
    Outlier resistance: korur
```

## 2.3 Ortak v2 İyileştirmeler

### Real-Time Data Pipeline
- Saatlik iddaa snapshot
- Maç başlamadan 4 saat önce: final odds picture
- Pre-match closing capture

### Live Shadow Run Framework
```python
class ShadowRun:
    def weekly_run(self):
        picks = model.weekly_picks()
        for p in picks:
            self.db.insert(p)  # paper money
            self.notify(p)     # Slack/email

    def settle_pending(self):
        unsettled = self.db.unsettled_picks()
        for p in unsettled:
            result = api_football.fixture_result(p.match_id)
            if result:
                self.db.settle(p, result)
                self.log_performance(p)
```

### Confidence Calibration Test
```python
def calibration_test(picks, expected_brier=0.20):
    """Brier score hedefimizden uzak mı?"""
    brier = compute_brier(picks)
    if brier > expected_brier:
        return "RECALIBRATE_NEEDED"
    return "OK"
```

### Smart Skip (Data-Driven)
```yaml
v1 skip rules: SABIT (W16-18 kötü) — OVERFIT (T15 reddetti)

v2 smart skip:
  - rolling 50-kupon window içinde skor < 0.65 → skip
  - bookmaker overround > %8 → skip (illiquid lig)
  - matchday'de < 2 confirmed match → skip
```

---

# 🛠️ BÖLÜM 3 — SPRİNT PLANI

## Sprint 1 (1-2 hafta): Data Foundation

**Hedef:** matches_v2 + ETL canlı

- [ ] matches_v2 + team_aliases + seasons_meta schema
- [ ] Football-Data → matches_v2 migration script
- [ ] Understat → matches_v2 (xG)
- [ ] api-football → matches_v2 (fixtures + injuries)
- [ ] team_alias_resolver (Levenshtein + manual fallback)
- [ ] quality_check_all() fonksiyonu
- [ ] Eski signal_snapshots → matches_v2 migration
- [ ] Daily cron job (cron / scheduled task)

**Gate:** matches_v2 tüm 6 lig × 6 sezon yüklü, quality_score ≥0.7 olan oran %85+

## Sprint 2 (1 hafta): CLV Entegrasyonu

**Hedef:** Opening + closing odds tracking

- [ ] Opening odds source seçimi (Pinnacle API vs B365 fallback)
- [ ] opening_odds_sync() fonksiyonu
- [ ] CLV hesaplama modülü
- [ ] Geçmiş kuponlar için CLV doğrulama
- [ ] picks_log tablosuna CLV alanı

**Gate:** Geçmiş 1000 picks için CLV hesaplanmış, EUVOX CLV ortalaması > 0

## Sprint 3 (1 hafta): Yeni Sinyaller

**Hedef:** 4 → 8 sinyal

- [ ] Injury → lineup_quality skor (api-football)
- [ ] Rest days (kronolojik fixtures)
- [ ] Sharp money tracker (iddaa multi-snapshot delta)
- [ ] T1 xG: Sofascore scrape (selenium veya requests)
- [ ] Travel fatigue (opsiyonel)
- [ ] Weather (opsiyonel, OpenWeather API)

**Gate:** Her sinyal solo backtest +/- ROI raporu hazır

## Sprint 4 (2 hafta): Model v2 Build

**Hedef:** TRIVOX v2 + EUVOX v2 inşa

- [ ] platt_scaling.py modülü
- [ ] trivox_v2.py (6 sinyal, min_conf=2)
- [ ] euvox_v2.py (8 sinyal, per-lig adaptive)
- [ ] smart_stake.py (Half-Kelly + cap)
- [ ] smart_skip_v2.py (data-driven)
- [ ] Calibration test

**Gate:** Brier score < 0.20 her model, smoke test PASS

## Sprint 5 (2 hafta): Validation Suite

**Hedef:** v2 robust mu?

- [ ] DD-Deep test 20 soru yeniden çalıştır v2 ile
- [ ] Smoke test 20/20 PASS
- [ ] Walk-forward DC (her lig, full)
- [ ] Monte Carlo bankroll (1000 simulation)
- [ ] Outlier removal test (top 20 hariç ROI ≥ +%5 hedef)
- [ ] CLV validation
- [ ] Calibration validation (Brier < 0.15)

**Gate:**
```
EUVOX v2:
  ROI ≥ +%15 brüt
  Outlier: top 20 hariç ROI ≥ +%5
  Calibration gap ≤ %2
  CLV ≥ +%1
  Bankrupt riski ≤ %3

TRIVOX v2:
  Sample ≥ 250 kupon
  Outlier: top 10 hariç ROI ≥ +%10
  Brier ≤ 0.15
```

## Sprint 6 (4-8 hafta): Live Shadow Run

**Hedef:** Gerçek 2026-27 sezonunda doğrulama

- [ ] 2026-27 sezonu data ingest (Ağustos başı)
- [ ] Otomatik weekly picks
- [ ] Otomatik settle
- [ ] Haftalık ROI raporu
- [ ] Drawdown bildirimi

**Gate:**
```
4-8 hafta sonu:
  EUVOX live ROI ≥ +%5 net
  TRIVOX sample ≥ 20 kupon (varsa)
  CLV ortalama ≥ +%1
  Bankrupt durumu olmamış
  Calibration sapma azalan trend
```

## Sprint 7 (1 hafta): Streamlit v2 UI

**Hedef:** Production UI

- [ ] TRIVOX + EUVOX seçici (model toggle)
- [ ] Otomatik kupon önerisi tab
- [ ] Bankroll tracker (canlı)
- [ ] Performance dashboard (haftalık/aylık)
- [ ] CLV display per pick
- [ ] Alert (drawdown, bankrupt risk)

**Gate:** UI live, kullanıma hazır

---

# 📊 GATE KRİTERLERİ ÖZET

| Sprint | Kriter | Eğer FAİL → |
|---|---|---|
| 1 | matches_v2 quality_score ≥0.7 oranı ≥%85 | Veri kaynaklarını gözden geçir |
| 2 | EUVOX historical CLV > 0 | Edge tahmininden vazgeç |
| 3 | Yeni sinyallerin solo ROI > 0 | Sinyali kullanma |
| 4 | Brier < 0.20 | Calibration retune |
| 5 | DD-Deep + smoke test PASS | v2'yi iptal et |
| 6 | Live ROI ≥ +%5 net | Beta launch ertelenir |
| 7 | UI live + functional | Dev devam |

---

# 🎯 ZAMANLAMA

```
Mayıs 2026 (şu an):    Plan onayı
Haziran 2026:          Sprint 1-2 (data + CLV)
Temmuz 2026:           Sprint 3-4 (sinyaller + build)
Ağustos başı:          Sprint 5 (validation)
Ağustos sonu:          2026-27 sezonu başlar → Sprint 6
Eylül-Ekim:            Sprint 6 (live shadow)
Kasım 2026:            Sprint 7 (UI)
```

**Toplam dev:** ~6 hafta + 4-8 hafta shadow run = 3 ay.

---

# 🎓 ÖZET

v2 = v1 PoC → Production mühendislik.

**Anahtar teknik değişimler:**

| Boyut | v1 | v2 |
|---|---|---|
| Master tablo | signal_snapshots (eski) | matches_v2 (yeni) |
| Sezon kodu | Karışık | Canonical "YYYY-YY" |
| Takım ismi | Source'a göre | Canonical mapping |
| Sinyal sayısı | 4 | 8 |
| Calibration | Yok | Platt scaling per lig |
| CLV | Ölçülmedi | Real-time |
| Stake | Flat 1000 | Half-Kelly + cap |
| Smart skip | Sabit rules (OVERFIT) | Data-driven adaptive |
| Refresh | Manuel | Daily cron + hourly live |
| Live test | Yok | Auto shadow run |
| Outlier resistance | TRIVOX zayıf | Sıkı consensus + Brier check |

**Ana hedefler:**
- ✅ DD Deep'in 10 eksiklığını çöz
- ✅ Calibration gap %9.5 → %2
- ✅ Outlier-resistant (top 20 hariç +EV)
- ✅ CLV measurable + positive
- ✅ Bankrupt riski %7.6 → %3
- ✅ Live shadow run yapısı kuruldu

**Bütçe: $0 (Pinnacle yerine B365 opening fallback) - $1,000 (Pinnacle ile)**
**Süre: 6-8 hafta dev + 4-8 hafta shadow run**

---

**v2 tamamen teknik. Data + Model. Ticari yok.**
