# 🗺️ v2 ROADMAP — Data Standardizasyon + Model v2 Tasarım/İnşa/Test

**Tarih:** 2026-05-27
**Hedef:** 2026-27 sezonu (Ağustos 2026 başlar) için **otomatik** ve **güvenilir** sistem
**Çerçeve:** DD eksikliklerini gideren v2 mimari

---

## 🎯 NEDEN v2?

DD Deep Test sonuçları gösterdi:

| Eksiklik | DD Bulgusu | v2 Çözüm |
|---|---|---|
| TRIVOX outlier-dependent | Top 10 hariç -%21 ROI | Sample büyütme + sıkı consensus filtre |
| Calibration gap %9.5 | Bahis "şanslı" görünüyor | Platt scaling per model |
| CLV ölçülmedi | En kritik metrik eksik | Pinnacle opening odds entegrasyonu |
| Edge attribution: xG/form zayıf | Solo +%0 ROI | Yeni sinyaller (sakatlık, lineup) |
| 2526 sample küçük | TRIVOX n=6 anlamsız | Otomatik weekly data refresh |
| Bankrupt riski %7.6 | EUVOX 1000 TL bankroll | Dinamik stake sizing |
| Live shadow run yok | En kritik validation eksik | 4-8 hafta otomatik takip pipeline |

---

# 📦 BÖLÜM 1 — DATA STANDARDIZASYON PLANI

## 1.1 Mevcut Durum (Audit)

```
Veri kaynakları (mevcut):
✅ Football-Data CSV mirror    : T1+E0+D1+SP1+I1+F1 × 5 sezon (10,657 maç)
✅ Understat (soccerdata)      : 5 lig × 4 sezon xG (7,156 maç)
✅ api-football                : Fixtures (2024 sezonu) + injuries
✅ iddaa.com sportsbookv2       : Live odds snapshot
✅ DC modelleri JSON           : 6 lig için eğitilmiş

Tablolar:
- signal_snapshots (10,657 kayıt — yeni master)
- fixtures (2024 sezonu)
- xg_data (7,156 kayıt)
- iddaa_odds (snapshot bazlı)
- injuries (15,475 kayıt — 2024)
- odds_anomaly_signals
- tipster_picks + tipster_stats

Standartlaşma sorunları:
❌ Sezon kodları karışık ("2122" vs season=2021 vs "2021-22")
❌ Takım isimleri farklı kaynaklarda ("FC Cologne" vs "Köln" vs "FC Koln")
❌ Tarih formatları: ISO vs "DD/MM/YYYY"
❌ T1 xG kaynak yok (Understat desteklemiyor)
❌ 2526 sezonu yarı yüklü (closing odds %44-65)
❌ Refresh manuel (otomatik değil)
```

## 1.2 v2 DATA CONTRACT (Standart)

### Master Schema

```sql
CREATE TABLE matches_v2 (
    -- Identity
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
    home_team           TEXT NOT NULL,   -- canonical (team_aliases tablosu)
    away_team           TEXT NOT NULL,

    -- Result
    status              TEXT,            -- 'NS','LIVE','FT','PST','CANC'
    home_score          INTEGER,
    away_score          INTEGER,
    home_score_ht       INTEGER,
    away_score_ht       INTEGER,

    -- Odds — opening (Bet365, Pinnacle istek)
    opening_1           REAL, opening_X  REAL, opening_2  REAL,
    opening_over25      REAL, opening_under25 REAL,
    opening_btts_yes    REAL, opening_btts_no REAL,
    opening_source      TEXT,            -- 'B365' or 'Pinnacle'

    -- Odds — closing (Pinnacle = referans)
    closing_1           REAL, closing_X  REAL, closing_2  REAL,
    closing_over25      REAL, closing_under25 REAL,
    closing_btts_yes    REAL, closing_btts_no REAL,
    closing_source      TEXT,

    -- Statistics
    home_xg             REAL,            -- Understat
    away_xg             REAL,
    home_shots          INTEGER,
    away_shots          INTEGER,
    home_possession     REAL,
    away_possession     REAL,

    -- Injuries (yeni)
    home_key_injuries   INTEGER,         -- önemli oyuncu sakatlık sayısı
    away_key_injuries   INTEGER,

    -- Quality flags
    has_full_odds       INTEGER DEFAULT 0,  -- closing tam mı?
    has_xg              INTEGER DEFAULT 0,
    has_result          INTEGER DEFAULT 0,
    is_settled          INTEGER DEFAULT 0,

    -- Audit
    ingested_at         TIMESTAMP,
    refreshed_at        TIMESTAMP,
    quality_score       REAL,             -- 0-1, eksik veri bayrak
    UNIQUE(league_code, season, matchday, home_team, away_team)
);

CREATE TABLE team_aliases (
    canonical_name      TEXT PRIMARY KEY,
    alias               TEXT,
    source              TEXT,             -- 'fd', 'us', 'af', 'iddaa'
    league_code         TEXT
);
-- Örnek: ('Leverkusen', 'Bayer Leverkusen', 'us', 'D1')
--        ('Leverkusen', 'B04', 'iddaa', 'D1')

CREATE TABLE seasons_meta (
    season              TEXT PRIMARY KEY,  -- '2026-27'
    league_code         TEXT,
    start_date          DATE,
    end_date            DATE,
    n_total_matches     INTEGER,
    n_settled           INTEGER,
    coverage_pct        REAL,
    last_refresh        TIMESTAMP
);
```

### Sezon Kodu Standardı

```
ESKİ              YENİ
'2122'         →  '2021-22'
season=2022    →  '2022-23'
'2024-25'      →  '2024-25' (zaten doğru)
```

### Takım İsmi Canonical Mapping

```python
# Her lig için canonical takım isimleri
T1_CANONICAL = {
    'fenerbahce': 'Fenerbahce',
    'galatasaray': 'Galatasaray',
    ...
}
D1_CANONICAL = {
    'bayer leverkusen': 'Leverkusen',  # us yazımı → fd yazımı
    'borussia dortmund': 'Dortmund',
    'rasenballsport leipzig': 'RB Leipzig',
    'fc cologne': 'FC Koln',
    ...
}
```

## 1.3 ETL PIPELINE (otomatik)

```
┌────────────────────────────────────────────────────────────┐
│                  v2 DATA PIPELINE                           │
│                                                             │
│  Cron her gün 03:00 UTC:                                    │
│                                                             │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │ Football-Data│  │ Understat    │  │ api-football │      │
│  │  CSV diff    │  │ scrape       │  │ fixtures+inj │      │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘      │
│         │                 │                 │                │
│         └──────┬──────────┴─────────────────┘                │
│                ▼                                            │
│       ┌─────────────────┐                                   │
│       │ Canonicalization│  (team_aliases lookup)            │
│       └────────┬────────┘                                   │
│                ▼                                            │
│       ┌─────────────────┐                                   │
│       │ Quality Check   │  (eksik bayrak, anomaly)         │
│       └────────┬────────┘                                   │
│                ▼                                            │
│       ┌─────────────────┐                                   │
│       │ matches_v2      │                                   │
│       │ INSERT/UPDATE   │                                   │
│       └────────┬────────┘                                   │
│                ▼                                            │
│       ┌─────────────────┐                                   │
│       │ Signal Compute  │  (anomaly, model, xg, form,...)  │
│       └────────┬────────┘                                   │
│                ▼                                            │
│       ┌─────────────────┐                                   │
│       │ signal_snapshots│                                   │
│       └─────────────────┘                                   │
│                                                             │
│  Saatlik (live mode):                                       │
│       iddaa.com odds snapshot → odds_snapshots tablosu      │
└────────────────────────────────────────────────────────────┘
```

### Quality Gates

```python
def quality_check(match_row) -> float:
    score = 1.0
    if not match_row.closing_1: score -= 0.3
    if not match_row.opening_1: score -= 0.2  # CLV için lazım
    if not match_row.home_xg: score -= 0.15
    if not match_row.has_result and match_row.kickoff_past_24h:
        score -= 0.2  # geç sonuç
    if match_row.kickoff_in_future_30d: score = 1.0  # future = OK
    return max(0, score)
```

## 1.4 CLV ENTEGRASYONU (v2 ÖNCELIK)

DD'de en büyük eksiklik. v2 çözümü:

**Plan A:** Pinnacle API satın al ($100-200/ay)
- Opening odds: maç açılışı
- Closing odds: maç başlamadan önce
- CLV = opening / closing - 1

**Plan B:** Free alternatif
- Football-Data B365 opening + PSC closing (B365 ≠ Pinnacle ama yakın proxy)
- OddsPortal scraping (riskli, ToS)

**v2 öneri:** Plan A — pinnacle.com API entegrasyonu.

## 1.5 LIVE REFRESH MEKANİZMASI

```yaml
schedules:
  - name: daily_data_sync
    when: 03:00 UTC
    actions:
      - football_data_pull
      - understat_pull
      - api_football_fixtures_pull
      - injury_data_pull
      - canonicalize
      - quality_check
      - signal_compute
      - signal_snapshots_update

  - name: hourly_live_odds
    when: every 1 hour (matchday +/- 24h)
    actions:
      - iddaa_odds_snapshot
      - pinnacle_odds_snapshot (v2)
      - line_movement_compute

  - name: realtime_settle
    when: after each match end
    actions:
      - fetch_final_score
      - update_match_result
      - settle_picks
      - update_performance_log
```

---

# 🤖 BÖLÜM 2 — MODEL v2 TASARIM

## 2.1 TRIVOX v2.0 (Türk Süper Lig odaklı)

### Mevcut Sorunlar (DD'den)
1. Outlier-dependent (top 10 hariç -%21)
2. Sample küçük (n=109)
3. xG yok
4. Sample-specific overfit

### v2.0 Çözümleri

#### A) Sample Büyütme
- Geriye dönük sezon ekleme: 2017-2021 (4 ek sezon)
- Pre-COVID lig dinamiklerini öğren
- Toplam: 9 sezon × ~340 maç = ~3,000 T1 maçı

#### B) T1 xG Alternatif Kaynak
- **Sofascore xG** (web scrape)
- **FotMob xG** (alternatif)
- En azından son 3 sezon T1 maçları için xG

#### C) Yeni Sinyaller (4 → 6 sinyal)
- **Sakatlık**: api-football injuries
- **Lineup quality**: starting 11 vs B-team
- **Travel fatigue**: deplasman seyahat mesafesi
- **Rest days**: son maçtan beri kaç gün

#### D) Konsensüs Eşik Yükseltme
- min_confirmers: 1 → 2 (eğer 6 sinyal varsa)
- Daha sıkı konsensüs = daha az outlier-dependent

#### E) Bonferroni-Compatible Picks
- Sadece p < 0.0026 olan picks
- Sample küçülür ama outlier-resistant olur

### TRIVOX v2 Spesifikasyon

```yaml
TRIVOX v2.0:
  ligler: [T1]
  sinyaller:
    - anomaly (cross-market, 1X2 only)
    - model (Dixon-Coles, calibrated Platt)
    - xg (Sofascore alternatif)
    - form (recency-weighted 5)
    - injury (lineup quality)
    - rest (days since last match)

  K (combo legs): 3 (sabit) veya 2-4 adaptive
  min_confirmers: 2 (6 sinyalden ≥2)
  score_threshold: 0.75
  stake_strategy: Half-Kelly with cap
  calibration: Platt scaling per model

  beklenen v2 metrikleri:
    Outlier risk: %88 → %40 (hedef)
    Sample: 109 → 300+ (3x)
    ROI: 51% → 40% (biraz düşer ama tutarlı)
    Sharpe: 1.38 → 1.5
```

## 2.2 EUVOX v2.0 (6-lig hibrit)

### Mevcut Sorunlar (DD'den)
1. Calibration gap %4
2. CLV ölçülmedi
3. Tax %20'de marj çok ince (+%1.3)
4. Bankrupt riski %7.6

### v2.0 Çözümleri

#### A) Platt Scaling Calibration
- Her lig için model probability → Platt scaled prob
- Calibration gap → 0'a yakın

#### B) CLV Entegrasyon
- Pinnacle opening vs closing tracking
- Edge ölçümü canlı

#### C) Adaptive Per-League Config
- Her hafta config refit (rolling 200 maç)
- Mevsim/dönem değişimine uyum

#### D) Smart Stake Sizing
- Half-Kelly + max_bet_cap (bankroll %5)
- Adaptive: edge yüksekse fazla, düşükse az
- Bankrupt riskini %7.6 → %3 düşür

#### E) New Signals
- **Sharp money tracker** (Pinnacle line movement)
- **News sentiment** (transfer rumor, manager change)
- **Weather** (yağmur → low scoring)

### EUVOX v2 Spesifikasyon

```yaml
EUVOX v2.0:
  ligler: [T1, E0, D1, SP1, I1, F1]
  sinyaller (8 toplam):
    1. anomaly (1X2 normalize)
    2. model (DC + Platt calibrated)
    3. xg (Understat + Sofascore T1)
    4. form (recency)
    5. injury
    6. rest_days
    7. sharp_money (Pinnacle line move)
    8. weather (yağmur → under)

  per_lig_adaptive_config:
    refit: weekly rolling
    metric: Sharpe + drawdown

  stake_strategy:
    type: Half-Kelly
    max_per_kupon: 5% bankroll
    min_per_kupon: 1% bankroll
    pause_after_drawdown: 20% (cool-off period)

  beklenen v2 metrikleri:
    Calibration gap: %4 → %1
    CLV: ölçülecek (hedef +%2)
    Bankrupt riski: %7.6 → %3
    ROI: %18 → %22 (sinyaller artar)
    Outlier resistance: korur
```

## 2.3 SHARED IMPROVEMENTS (her iki model)

### Real-time Data Pipeline
- Saatlik iddaa snapshot
- Sınırlı geç-loading
- Maç başlamadan önce: full odds picture

### Confidence Calibration
- Brier score < 0.20 hedef
- Reliability diagram per model
- Auto-recalibrate her ay

### Smart Skip (overfit-control)
- Skip rules T15'te overfit kanıtlandı
- v2'de **dynamic skip**: sample window içinde data-driven
- Her hafta yeniden hesapla, sabit kural değil

### Live Shadow Run Framework
- Kupon önerisi → DB'ye otomatik kayıt
- Maç sonucu → otomatik settle
- Haftalık + aylık + sezon ROI raporu
- Email/Slack notification

---

# 🛠️ BÖLÜM 3 — İNŞA + TEST PLANI

## 3.1 Sprint Yapısı

### Sprint 1 (1-2 hafta): Data Foundation
**Hedef:** matches_v2 tablosu + ETL pipeline canlı

- [ ] matches_v2 schema oluştur
- [ ] team_aliases canonical mapping
- [ ] Football-Data ingest → matches_v2
- [ ] Understat ingest → matches_v2 (xG)
- [ ] Quality check fonksiyonları
- [ ] Migration script (eski signal_snapshots → matches_v2)
- [ ] Daily cron job kurulum

**Gate:** matches_v2 tüm 6 lig × 5 sezon × ~10,000 maç yüklü, quality_score ≥0.7 olan %85+

### Sprint 2 (1 hafta): CLV Entegrasyonu
**Hedef:** Opening + closing odds tracking

- [ ] Pinnacle API hesap aç + auth
- [ ] Opening odds endpoint entegrasyonu
- [ ] CLV hesaplama modülü
- [ ] Mevcut backtest'lerde CLV doğrulama (geçmişe dönük)

**Gate:** CLV mean per model hesaplanmış, EUVOX CLV > 0 olduğu doğrulanmış

### Sprint 3 (1 hafta): Yeni Sinyaller
**Hedef:** 4 → 8 sinyal genişlemesi

- [ ] Injury scraper (api-football injuries)
- [ ] Lineup quality skor
- [ ] Rest days (kronolojik fixtures'tan)
- [ ] Travel fatigue (stadyum koordinat)
- [ ] Weather API (opsiyonel)
- [ ] Sharp money tracker (Pinnacle line move)
- [ ] T1 xG alternatif (Sofascore scrape)

**Gate:** Her sinyal solo backtest'te en az 50 kupon × 4 sezon, ROI hesaplanmış

### Sprint 4 (2 hafta): Model v2 Build
**Hedef:** TRIVOX v2 + EUVOX v2 inşa

- [ ] Platt scaling kalibrasyon modülü
- [ ] TRIVOX v2 config (min_conf=2, 6 sinyal)
- [ ] EUVOX v2 per-lig adaptive config refit
- [ ] Half-Kelly stake sizing (max cap)
- [ ] Smart skip framework (data-driven, not rule)
- [ ] Calibration validation (Brier score)

**Gate:** Brier < 0.20 her model, backtest +5pp ROI improvement minimum

### Sprint 5 (2 hafta): Validation Suite
**Hedef:** DD-Deep test + smoke test v2

- [ ] DD Q1-Q20 yeniden çalıştır v2 ile
- [ ] Smoke test 20/20 PASS
- [ ] Walk-forward DC (per-lig, full)
- [ ] Monte Carlo bankroll simulation
- [ ] Outlier removal test (top 20 hariç hala +EV olsun)

**Gate Kriterleri (v2 PASS):**
```
EUVOX v2:
  - ROI ≥ +%15 brüt (mevcut +%18 baseline)
  - Outlier resistance: top 20 hariç ROI ≥ +%5
  - Calibration gap ≤ %2
  - Bankrupt riski ≤ %3
  - CLV ≥ +%1

TRIVOX v2:
  - Sample ≥ 250 kupon (5 sezon + ek geçmiş)
  - Outlier risk: top 10 hariç ROI ≥ +%10
  - Calibration gap ≤ %3
  - Bonferroni p < 0.0026 kupon subset
```

### Sprint 6 (4-8 hafta): Live Shadow Run
**Hedef:** Gerçek sezon başlangıcı kanıt

- [ ] 2026-27 sezonu başlangıcı (Ağustos 2026)
- [ ] Otomatik weekly snapshot
- [ ] Otomatik settle
- [ ] Haftalık rapor email/Slack
- [ ] 4 hafta minimum, 8 hafta ideal

**Gate (Live PASS):**
```
- 4-8 hafta sonunda EUVOX ROI ≥ +%5 net
- TRIVOX sample ≥ 20 kupon, ROI ≥ +%15 net
- CLV ortalama ≥ +%1
- Bankrupt durumu olmamış
- Calibration sapma azalan trend
```

### Sprint 7 (1 hafta): Beta Launch
**Hedef:** UI production-ready

- [ ] Streamlit v2 UI (TRIVOX + EUVOX seçici)
- [ ] Otomatik kupon önerisi
- [ ] Bankroll tracker
- [ ] Performance dashboard
- [ ] Hata + drawdown bildirimleri

**Gate:** UI live, demo yatırımcılara açık

## 3.2 Risk Matrisi

| Risk | Olasılık | Etki | Mitigation |
|---|:---:|:---:|---|
| Pinnacle API erişimi sağlanamaz | ORTA | YÜKSEK | B365 opening fallback |
| Sofascore scrape yasak | ORTA | ORTA | xG alternatif: Opta, StatsBomb |
| 2026-27 sezonu lig değişimleri | DÜŞÜK | ORTA | DC retrain weekly |
| Bookmaker continued adaptation | YÜKSEK | YÜKSEK | Smart skip + edge re-tune |
| Live shadow run -EV | YÜKSEK | ÇOK YÜKSEK | Beta launch ertelenir |

## 3.3 Bütçe Tahmini

| Kalem | Tahmini Tutar |
|---|---:|
| Pinnacle API ($150/ay × 6 ay) | $900 |
| Sofascore scrape proxy (gerekirse) | $300 |
| Hosting (AWS/Heroku) | $200 |
| Development zamanı (8 hafta) | dahili |
| **Toplam** | **~$1,400** |

---

# 📊 BÖLÜM 4 — KARAR KRİTERLERİ

## 4.1 v2'ye GIT (GO) Kararı

v2 dev'e başla EĞER:
- ✅ Mevcut DD bulguları kabul (outlier, calibration, CLV)
- ✅ 2026-27 sezonu yaklaşıyor (Ağustos 2026)
- ✅ 6-8 hafta dev kapasitesi var
- ✅ ~$1,500 bütçe

## 4.2 İPTAL (NO-GO) Kriterleri

v2'yi iptal et EĞER:
- ❌ Sprint 2 sonunda CLV negatif (edge gerçek değil)
- ❌ Sprint 5 validation v1'den kötü
- ❌ Sprint 6 live shadow run 4 hafta -EV

## 4.3 BAŞARI KRİTERLERİ

v2 SUCCESS:
- ✅ EUVOX v2 net ROI ≥ +%10 (vergi sonrası)
- ✅ TRIVOX v2 outlier-resistant
- ✅ CLV > 0
- ✅ Live shadow run +EV
- ✅ Bankrupt riski < %3

---

# 🎯 ZAMANLAMA

```
Şu an (Mayıs 2026):    Plan onayı
Haziran 2026:          Sprint 1-2 (data + CLV)
Temmuz 2026:           Sprint 3-4 (sinyaller + v2 build)
Erken Ağustos:         Sprint 5 (validation)
Ağustos sonu:          2026-27 sezonu başlar
Eylül-Ekim 2026:       Sprint 6 (live shadow)
Kasım 2026:            Beta launch (Sprint 7)
```

---

# 🎓 YÖNETİCİ ÖZETİ

v2 = **gerçek mühendislik projesi**. v1 araştırma/PoC idi, v2 production.

**Anahtar farklılıklar:**

| Boyut | v1 | v2 |
|---|---|---|
| Veri | Manual snapshot | Otomatik daily sync |
| Sinyal sayısı | 4 | 8 |
| Calibration | Yok | Platt scaling |
| CLV | Ölçülmedi | Gerçek-zamanlı |
| Live test | Yok | 4-8 hafta shadow |
| Stake | Flat 1000 | Half-Kelly + cap |
| Outlier resistance | TRIVOX zayıf | Sıkı consensus |

**6 hafta dev + 4-8 hafta shadow run = ~3 ay**.
**Bütçe: ~$1,500**.

**Sonuç:** Eğer v2 başarırsa, **gerçek edge** doğrulanmış olur. Acquirer için satın alma değeri 10-50x artar.
