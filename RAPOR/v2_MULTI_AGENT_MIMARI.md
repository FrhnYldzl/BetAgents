# MULTI-AGENT + SKILL MİMARİSİ
## "AI Trader = Orchestrator + 10 Specialist Agent + 50+ Skill"

**Tarih:** 2026-05-28
**Felsefe:** Tek model yerine **uzman ağı**, sürekli besleyen + öğrenen sistem
**Çıktı:** Trader'ın **Digital Twin'i** — pratik, zeki, kazançlı

---

## 1) AGENT MİMARİSİ — Genel Görünüm

```
┌──────────────────────────────────────────────────────────────────┐
│                                                                  │
│           ███  ORCHESTRATOR (Ana AI Trader)  ███                 │
│                                                                  │
│   Trader ile konuşan, soru anlayan, agent'lara delegate eden     │
│   sonuçları toparlayan, anlaşılabilir cevap üreten ana ajan      │
│                                                                  │
└─────────────────────────────┬────────────────────────────────────┘
                              │
            ┌─────────────────┼─────────────────┐
            ↓                 ↓                 ↓
   ┌────────────────┬─────────────────┬────────────────┐
   │ VERİ AKIŞI     │  ANALİZ AKIŞI   │ KARAR AKIŞI    │
   └────┬───────────┴────────┬────────┴────────┬───────┘
        │                    │                 │
   ┌────▼─────┐    ┌────────▼────────┐  ┌─────▼──────┐
   │ DATA      │    │  TEAM ANALYST   │  │  MODEL      │
   │ HUNTER    │    │  PLAYER ANALYST │  │  ENSEMBLE   │
   │ AGENT     │    │  MARKET ANALYST │  │  AGENT      │
   │           │    │  MATCH CONTEXT  │  │             │
   └────┬─────┘    └────────┬────────┘  └─────┬──────┘
        │                   │                 │
        └───────────┬───────┴─────────────────┘
                    ↓
              ┌─────────────┐
              │  STRATEGY   │
              │  OPTIMIZER  │
              │  AGENT      │
              └─────┬───────┘
                    ↓
              ┌─────────────┐
              │  RISK       │
              │  GUARDIAN   │
              │  AGENT      │
              └─────┬───────┘
                    ↓
              ┌─────────────┐
              │  LEARNING   │
              │  AGENT      │
              │  (feedback) │
              └─────┬───────┘
                    ↓
              ┌─────────────┐
              │  EXPLAINER  │
              │  AGENT      │
              │  → Trader   │
              └─────────────┘
```

---

## 2) 10 SPECIALIST AGENT

### [0] ORCHESTRATOR — Ana AI Trader

**Rolü:** Trader ile doğrudan konuşur, niyeti anlar, doğru agent'a delegate eder, sonuçları toparlayıp natural language çıktı verir.

**Yetenekler:**
- Niyet sınıflandırma ("Bu hafta ne öneriyorsun?" → DECISION_REQUEST)
- Agent çağrı orkestrasyonu (parallel + sequential)
- Çıktı sentezleme (markdown rapor + öneri listesi)
- Trader feedback işleme

**Teknoloji:** Claude API (Sonnet) + ChatGPT-4 alternative

---

### [1] DATA HUNTER AGENT

**Rolü:** 12+ veri kaynağından sürekli ingest, schema mapping, quality control.

**Skill listesi:**
- `ingest_football_data(season, league)` — FD CSV
- `scrape_fotmob(match_id)` — T1 xG
- `scrape_transfermarkt(team)` — kadro değeri, sakatlık
- `query_api_football(endpoint, params)` — REST API
- `scrape_sofascore(match_id)` — oyuncu rating
- `scrape_fbref(team, season)` — gelişmiş stats
- `get_weather(location, kickoff_dt)` — OpenWeather
- `tweet_stream(account, keyword)` — Twitter sentiment
- `validate_schema(data, schema)` — canonical kontrol
- `detect_anomaly(data)` — duplicate, outlier
- `snapshot_save(data, timestamp)` — version control

**Tetikleyiciler:** Cron (her 6 saat), event-driven (lineup açıklandığında)

---

### [2] TEAM ANALYST AGENT

**Rolü:** Takım seviyesi derinleştirme. Form, kadro, motivasyon analizi.

**Skill listesi:**
- `predict_lineup(team, match_date)` — muhtemel kadro
- `team_form(team, lookback=5)` — son 5 maç form
- `injury_summary(team, match_date)` — sakatlık listesi
- `head_to_head(team_a, team_b, n=10)` — son n maç karşılaştırma
- `fatigue_score(team, match_date)` — fixture yoğunluğu
- `motivation_factor(team, season_position)` — küme/şampiyon yarışı
- `home_away_split(team, season)` — ev/dep performans farkı
- `coach_change_check(team, last_n_days=30)` — yeni teknik direktör
- `transfer_window_impact(team, season)` — kadro değişikliği

**Çıktı:** TeamProfile JSON (10-15 kategori metric)

---

### [3] PLAYER ANALYST AGENT

**Rolü:** Bireysel oyuncu derinleşmesi. Star player effect.

**Skill listesi:**
- `player_form(player_id, lookback=5)` — son maç performansları
- `player_vs_team_history(player_id, opponent)` — bu rakibe karşı
- `player_injury_history(player_id)` — sakatlık riski
- `player_fatigue(player_id, fixture_density)` — dakika yüklemesi
- `star_player_impact(team, missing_player)` — kim eksikse ne kadar zayıflıyor
- `goal_scorer_predict(team, match)` — kim gol atar pazarı için

**Çıktı:** PlayerImpact JSON

---

### [4] MARKET ANALYST AGENT

**Rolü:** Piyasa hareketini izle, sharp money tespit et.

**Skill listesi:**
- `get_opening_odds(match_id)` — opening fiyat
- `get_closing_odds(match_id)` — closing fiyat
- `compute_CLV(match_id, side)` — bu pick için CLV
- `detect_sharp_drop(match_id, side, threshold=0.05)` — sert düşüş
- `bookmaker_compare(match_id)` — iddaa vs B365 vs Pinnacle
- `market_efficiency(match_id, market)` — kalibrasyon ölçümü
- `vig_estimate(odds_1, odds_X, odds_2)` — overround hesabı
- `find_value_line(market_p, model_p, edge_threshold=0.03)` — value detection

**Çıktı:** MarketState JSON (her pazar için)

---

### [5] MATCH CONTEXT AGENT

**Rolü:** Maç-spesifik dış faktörler.

**Skill listesi:**
- `weather_at_kickoff(match_id)` — yağış, rüzgar, sıcaklık
- `travel_distance(away_team, stadium)` — deplasman yorgunluğu
- `derby_check(home, away)` — derbi/rakip tarihsel
- `crowd_attendance_predict(match_id)` — taraftar yoğunluğu
- `referee_history(referee_id, lookback=30)` — hakem profili
- `pitch_condition(stadium, recent_weather)` — saha durumu

**Çıktı:** MatchContext JSON

---

### [6] MODEL ENSEMBLE AGENT

**Rolü:** Çekirdek model çıktıları + ensemble.

**Skill listesi:**
- `run_trivox(match_id)` → score + direction (T1)
- `run_duovox(match_id)` → (E0+SP1)
- `run_triovox(match_id)` → (E0+SP1+D1)
- `run_monovox_e0(match_id)` → (E0)
- `run_monovox_sp1(match_id)` → (SP1)
- `compute_quintile(scores)` → Q1-Q5
- `agree_count(directions)` → kaç sinyal aynı yönü
- `ensemble_weighted(model_outputs, weights)` — Bayesian blend
- `multi_market_project(dc_lam_h, dc_lam_a)` — DC → 5 pazar projection
- `retrain_trigger_check()` — yeniden eğitim zamanı geldi mi?

**Çıktı:** ModelDecision JSON (her model × pazar için)

---

### [7] STRATEGY OPTIMIZER AGENT

**Rolü:** Kupon yapısı + sistem önerisi + Kelly.

**Skill listesi:**
- `kelly_stake(prob, odd, bankroll, cap=0.10)` — pozisyon büyüklüğü
- `correlation_check(picks)` — kombin korelasyon kontrolü
- `propose_combo(picks, max_legs=3)` — kombin önerisi
- `propose_system(picks, n, m)` — n/m sistem
- `compare_strategies(picks)` — A/B/C seçenek üretici (EV + varyans)
- `tax_optimize(stake, odd, K)` — vergi-optimum K seçimi
- `bankroll_alloc(picks, target_pct=0.05)` — toplam stake limiti

**Çıktı:** StrategyProposal JSON

---

### [8] RISK GUARDIAN AGENT

**Rolü:** Trader'ı kendinden koruma. Risk gerçek zamanlı izleme.

**Skill listesi:**
- `check_drawdown(bankroll_series)` — mevcut DD
- `loss_streak_check(recent_picks)` — kayıp serisi
- `psi_drift_detect(model_probs, market_probs)` — model drift
- `concentration_warning(picks)` — aynı yön/lig yığılması
- `red_flag_alert(trader_action, profile)` — disiplin uyarısı
- `position_size_cap(intended_stake, max_pct)` — overshoot koruma
- `pause_recommendation(streak, dd)` — bu hafta PAS uyarısı

**Çıktı:** RiskAlerts list

---

### [9] LEARNING AGENT

**Rolü:** Sürekli iyileşme. Hit/Miss kaydı, pattern recognition, retraining.

**Skill listesi:**
- `log_pick(pick, result)` — DB kaydı
- `calibration_update(picks_log)` — Platt yeniden fit
- `find_pattern(picks_history, dimensions)` — örnek: "TRIVOX devre arası kötü"
- `feature_importance_track(model)` — hangi sinyal önemli
- `suggest_new_feature(unexplained_residual)` — yeni sinyal önerisi
- `monthly_retrain(model_id)` — otomatik retrain trigger
- `trader_feedback_process(feedback)` — "Bu picki atladım çünkü..." işleme

**Çıktı:** LearningReport (haftalık)

---

### [10] EXPLAINER AGENT

**Rolü:** Trader iletişim. Anlaşılabilir doğal dil çıktı.

**Skill listesi:**
- `explain_pick(pick_id)` — "Neden bu pick?"
- `weekly_report(picks, results)` — haftalık özet
- `monthly_report(picks, results)` — aylık özet
- `season_summary(season)` — sezon raporu
- `compare_picks(pick_a, pick_b)` — iki seçenek karşılaştırma
- `risk_warning_message(alerts)` — uyarı dili
- `generate_telegram_msg(decision)` — Telegram mesajı
- `voice_response(query)` — voice komut cevabı

**Çıktı:** Natural language (TR/EN)

---

## 3) AGENT KOORDİNASYONU — Örnek Senaryo

**Trader:** "Bu hafta ne öneriyorsun?"

**ORCHESTRATOR (akış):**

```
1. Niyet: WEEKLY_DECISION_REQUEST
2. DATA HUNTER → "Son 6 saat içinde yeni ingest yapıldı mı?"
   ↳ "Evet, FotMob T1 lineup güncel"
3. PARALLEL CALL:
   a) TEAM ANALYST → her maç için TeamProfile
   b) PLAYER ANALYST → key player check
   c) MARKET ANALYST → opening odds, sharp money signals
   d) MATCH CONTEXT → hava, derbi, fixture yoğunluğu
4. MODEL ENSEMBLE → 5 model × 5 pazar = matrix
5. STRATEGY OPTIMIZER → Q5+a2 picks → kupon önerileri (A/B/C)
6. RISK GUARDIAN → drawdown check, concentration warning
7. EXPLAINER → natural language report

→ Trader'a final markdown rapor + 3 seçenek tablosu
```

**Süre:** ~30 saniye (paralel call'ler ile)

---

## 4) AGENT TEKNOLOJİ STACK

| Katman | Teknoloji |
|---|---|
| Orchestrator | Claude Sonnet API + LangGraph |
| Specialist agents | Claude Haiku (hızlı) veya Python modüller |
| Skill execution | Python (pandas, numpy, sklearn) |
| Data store | SQLite (mevcut) → PostgreSQL (scale) |
| Cache | Redis (live odds, prediction cache) |
| Scheduling | Cron / Apache Airflow |
| Notification | Telegram bot + Twilio (voice) |
| Monitoring | Prometheus + Grafana |
| Logging | Loki + Grafana |
| Versioning | DVC (data) + Git (code) |

---

## 5) SKILL CATALOG (50+ skill örneği)

Her agent'ın skill'leri yukarıda. Toplam:
- Data Hunter: 11 skill
- Team Analyst: 9
- Player Analyst: 6
- Market Analyst: 8
- Match Context: 6
- Model Ensemble: 10
- Strategy Optimizer: 7
- Risk Guardian: 7
- Learning Agent: 7
- Explainer: 8

**Toplam: 79 skill**

Skill'ler **modüler** — yeni veri kaynağı eklendiğinde yeni skill yazılır. Agent'lar dokunulmaz.

---

## 6) INKREMENTAL İNŞA PLANI

### Faz 1: MVP (4-6 hafta) — Şu an buradayız
**Inşa edilecek:**
- [0] Orchestrator (basit Python orchestrator)
- [6] Model Ensemble Agent (mevcut TRIVOX/DUOVOX wrap)
- [7] Strategy Optimizer Agent (kupon optimizer)
- [9] Learning Agent (basit log)
- [10] Explainer Agent (basit markdown report)

**Yapılmayan:** Diğer agent'lar mock veya placeholder

**Çıktı:** "Tek kullanıcı, ana akış çalışır" MVP

### Faz 2: Veri Genişletme (Hafta 7-12)
**Inşa edilecek:**
- [1] Data Hunter Agent (FotMob + Transfermarkt entegrasyonu)
- [2] Team Analyst Agent (team profile temel)
- [4] Market Analyst Agent (CLV tracker)

**Çıktı:** Yeni veri kaynaklarıyla edge potansiyeli açılır

### Faz 3: Derinleşme (Hafta 13-20)
**Inşa edilecek:**
- [3] Player Analyst Agent
- [5] Match Context Agent
- [8] Risk Guardian Agent (full)

**Çıktı:** Trader için tam bağlamsal anlayış

### Faz 4: Production (Hafta 21+)
- Telegram bot + voice
- Multi-user support
- Beta launch (5-10 trader)

---

## 7) YENİ AGENTLAR EKLEME — Skill Felsefesi

**Yeni veri kaynağı = Yeni skill** (mevcut agent'a)
**Yeni karar mantığı = Yeni agent** (mevcut sistem'e)

Örnek: Trader "Twitter'ı da takip et" der → DATA HUNTER'a `tweet_stream` skill'i eklenir, MARKET ANALYST'e `process_breaking_news` skill'i eklenir. Yeni agent **gerekmez**.

Örnek: Trader "Tek pazara değil portföye bahis koymak istiyorum" der → Yeni agent **PORTFOLIO MANAGER AGENT** eklenir. Eski agent'lar dokunulmaz.

---

## 8) DIGITAL TWIN ÖZELLİĞİ — Trader Profili

Her trader için ayrı **TraderProfile** veritabanı:

```yaml
trader_id: trader_001
name: Ferhan
bankroll: 10000
risk_profile: "moderate"  # conservative / moderate / aggressive
preferred_leagues: [T1, E0, SP1]
preferred_markets: [MS, A/Ü]
frequency_preference: "selective"  # sniper / selective / active
max_stake_pct: 0.05
drawdown_tolerance: 0.15
favorite_models: [TRIVOX, DUOVOX]
historical_picks: 156
historical_hit_rate: 0.66
emotional_pattern: "tilts after 2 losses"  # learned
last_session: 2026-05-28
notes:
  - "Hep Liverpool 1 yatırmayı sever"
  - "Devre arası dönemini iyi yönetir"
```

AI Trader bu profile göre kişiselleştirir. **Aynı pick farklı trader'lara farklı pozisyon** önerir.

---

## 9) ÖZ KORUNUM — Kendi Edge'ini Geliştirme

Bu sistemin en gizli özelliği: **Trader davranışını öğrenir, model'i ona göre adapt eder**.

```
Trader: "Bu Q5+a2 picki atladım çünkü Galatasaray bu sezon kötü"
↓
LEARNING AGENT log: "trader_001 manually_skipped Galatasaray Q5"
↓
Sonraki Galatasaray pick'lerinde:
  - Eğer trader sürekli atlıyorsa → o pick için confidence_penalty 0.95
  - Eğer sonradan oynar ve haklı çıkarsa → +0.05 boost
↓
LEARNING AGENT: "Trader_001'in Galatasaray sezon başı sezgisi doğru çıktı, 
                 fav_confirmed Galatasaray için tied seezon yönü düşür"
```

Yani **Trader öğrenir + model öğrenir** = **birlikte iyileşir**.

---

## 10) TEK SAYFA ÖZET

```
┌──────────────────────────────────────────────────────────────────┐
│       AI TRADER DESTEK = ORCHESTRATOR + 10 AGENT + 79 SKILL      │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│  [0]  ORCHESTRATOR        Trader ile konuşan ana AI              │
│  [1]  DATA HUNTER         12+ kaynak ingest                      │
│  [2]  TEAM ANALYST        Takım derinleşmesi                     │
│  [3]  PLAYER ANALYST      Oyuncu seviyesi                        │
│  [4]  MARKET ANALYST      Sharp money + CLV                      │
│  [5]  MATCH CONTEXT       Hava, derbi, fixture                   │
│  [6]  MODEL ENSEMBLE      5 model × 5 pazar                      │
│  [7]  STRATEGY OPTIMIZER  Kupon + sistem önerisi                 │
│  [8]  RISK GUARDIAN       Drawdown + drift koruma                │
│  [9]  LEARNING AGENT      Sürekli iyileşme                       │
│  [10] EXPLAINER           Natural language çıktı                 │
│                                                                  │
│  Felsefe:                                                        │
│  • Yeni veri kaynağı = yeni skill                                │
│  • Yeni karar mantığı = yeni agent                               │
│  • Trader davranışı = model adaptasyonu                          │
│  • Mikro-edge birikimi = sürdürülebilir kazanç                   │
│                                                                  │
│  HEDEF: Dünyanın en zeki + pratik + kazançlı TRADER AI'ı         │
└──────────────────────────────────────────────────────────────────┘
```
