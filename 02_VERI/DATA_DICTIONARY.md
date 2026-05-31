# DATA DICTIONARY — BAHIS AGENT DB

**Otomatik üretildi:** 2026-05-28 16:26

**Toplam tablo:** 16

---

## İçindekiler

- [cache_meta](#cache-meta)
- [fixture_statistics](#fixture-statistics)
- [fixtures](#fixtures)
- [iddaa_odds](#iddaa-odds)
- [injuries](#injuries)
- [matches_v2](#matches-v2)
- [odds](#odds)
- [odds_anomaly_signals](#odds-anomaly-signals)
- [picks_log_v2](#picks-log-v2)
- [seasons_meta](#seasons-meta)
- [signal_snapshots](#signal-snapshots)
- [team_aliases](#team-aliases)
- [tipster_picks](#tipster-picks)
- [tipster_stats](#tipster-stats)
- [top_players](#top-players)
- [xg_data](#xg-data)

---

## cache_meta

**Satır sayısı:** 0

| Kolon | Tip | NN | PK | Default | Açıklama |
|---|---|---|---|---|---|
| `key` | TEXT |  | 🔑 |  |  |
| `value` | TEXT |  |  |  |  |
| `updated_at` | TEXT | ✓ |  |  |  |

---

## fixture_statistics

**Satır sayısı:** 96

| Kolon | Tip | NN | PK | Default | Açıklama |
|---|---|---|---|---|---|
| `fixture_id` | INTEGER | ✓ | 🔑 |  |  |
| `team_id` | INTEGER | ✓ | 🔑 |  |  |
| `team_name` | TEXT |  |  |  |  |
| `is_home` | INTEGER | ✓ |  |  |  |
| `shots_on` | INTEGER |  |  |  |  |
| `shots_off` | INTEGER |  |  |  |  |
| `shots_total` | INTEGER |  |  |  |  |
| `shots_blocked` | INTEGER |  |  |  |  |
| `shots_inside` | INTEGER |  |  |  |  |
| `shots_outside` | INTEGER |  |  |  |  |
| `fouls` | INTEGER |  |  |  |  |
| `corners` | INTEGER |  |  |  |  |
| `offsides` | INTEGER |  |  |  |  |
| `possession_pct` | INTEGER |  |  |  |  |
| `yellow` | INTEGER |  |  |  |  |
| `red` | INTEGER |  |  |  |  |
| `saves` | INTEGER |  |  |  |  |
| `passes_total` | INTEGER |  |  |  |  |
| `passes_acc` | INTEGER |  |  |  |  |
| `passes_pct` | INTEGER |  |  |  |  |
| `xg` | REAL |  |  |  |  |
| `goals_prevented` | REAL |  |  |  |  |
| `inserted_at` | TEXT | ✓ |  |  |  |

---

## fixtures

api-football fixture verisi (canlı sezon için)

**Satır sayısı:** 2,098

| Kolon | Tip | NN | PK | Default | Açıklama |
|---|---|---|---|---|---|
| `fixture_id` | INTEGER |  | 🔑 |  |  |
| `league_code` | TEXT | ✓ |  |  | T1/E0/D1/SP1/I1/F1 |
| `league_name` | TEXT |  |  |  |  |
| `season` | INTEGER | ✓ |  |  | Canonical sezon kodu (YYYY-YY) |
| `kickoff_utc` | TEXT | ✓ |  |  | Maç başlama saati UTC |
| `status` | TEXT |  |  |  |  |
| `home_team` | TEXT | ✓ |  |  | Ev sahibi takım (canonical isim) |
| `away_team` | TEXT | ✓ |  |  | Deplasman takım (canonical isim) |
| `home_score` | INTEGER |  |  |  | Ev sahibi tam zaman skor |
| `away_score` | INTEGER |  |  |  | Deplasman tam zaman skor |
| `venue` | TEXT |  |  |  |  |
| `city` | TEXT |  |  |  |  |
| `referee` | TEXT |  |  |  | Hakem ismi |
| `raw_json` | TEXT |  |  |  |  |
| `inserted_at` | TEXT | ✓ |  |  |  |

---

## iddaa_odds

iddaa.com odds snapshot'ları (multi-snapshot)

**Satır sayısı:** 2,855

| Kolon | Tip | NN | PK | Default | Açıklama |
|---|---|---|---|---|---|
| `snapshot_id` | TEXT | ✓ | 🔑 |  |  |
| `fixture_id` | INTEGER |  |  |  |  |
| `iddaa_match_id` | TEXT | ✓ | 🔑 |  |  |
| `league_code` | TEXT |  |  |  | T1/E0/D1/SP1/I1/F1 |
| `kickoff_iso` | TEXT | ✓ |  |  |  |
| `home_team` | TEXT | ✓ |  |  | Ev sahibi takım (canonical isim) |
| `away_team` | TEXT | ✓ |  |  | Deplasman takım (canonical isim) |
| `market` | TEXT | ✓ | 🔑 |  |  |
| `selection` | TEXT | ✓ | 🔑 |  |  |
| `odd` | REAL | ✓ |  |  |  |
| `implied_prob` | REAL |  |  |  |  |
| `fetched_at` | TEXT | ✓ |  |  |  |
| `raw_json` | TEXT |  |  |  |  |

---

## injuries

Sakatlık verisi (api-football)

**Satır sayısı:** 15,475

| Kolon | Tip | NN | PK | Default | Açıklama |
|---|---|---|---|---|---|
| `fixture_id` | INTEGER | ✓ | 🔑 |  |  |
| `league_code` | TEXT | ✓ |  |  | T1/E0/D1/SP1/I1/F1 |
| `season` | INTEGER | ✓ |  |  | Canonical sezon kodu (YYYY-YY) |
| `fixture_date` | TEXT | ✓ |  |  |  |
| `team_id` | INTEGER | ✓ | 🔑 |  |  |
| `team_name` | TEXT | ✓ |  |  |  |
| `player_id` | INTEGER | ✓ | 🔑 |  |  |
| `player_name` | TEXT | ✓ |  |  |  |
| `injury_type` | TEXT |  |  |  |  |
| `injury_reason` | TEXT |  |  |  |  |
| `inserted_at` | TEXT | ✓ |  |  |  |

---

## matches_v2

**MASTER TABLE** — Canonical maç verileri. Tüm sezonlar+ligler+pazarlar burada. 19,198 satır.

**Satır sayısı:** 19,198

| Kolon | Tip | NN | PK | Default | Açıklama |
|---|---|---|---|---|---|
| `match_id` | INTEGER |  | 🔑 |  | Internal primary key |
| `external_id_fd` | TEXT |  |  |  | Football-Data hash ID (lig+sezon+date+home+away) |
| `external_id_us` | TEXT |  |  |  | Understat match id |
| `external_id_af` | INTEGER |  |  |  | api-football fixture id |
| `external_id_iddaa` | TEXT |  |  |  | iddaa.com event id |
| `league_code` | TEXT | ✓ |  |  | T1/E0/D1/SP1/I1/F1 |
| `season` | TEXT | ✓ |  |  | Canonical sezon kodu (YYYY-YY) |
| `matchday` | TEXT | ✓ |  |  | Maç tarihi YYYY-MM-DD |
| `kickoff_utc` | TEXT |  |  |  | Maç başlama saati UTC |
| `home_team` | TEXT | ✓ |  |  | Ev sahibi takım (canonical isim) |
| `away_team` | TEXT | ✓ |  |  | Deplasman takım (canonical isim) |
| `status` | TEXT |  |  |  |  |
| `home_score` | INTEGER |  |  |  | Ev sahibi tam zaman skor |
| `away_score` | INTEGER |  |  |  | Deplasman tam zaman skor |
| `home_score_ht` | INTEGER |  |  |  |  |
| `away_score_ht` | INTEGER |  |  |  |  |
| `opening_1` | REAL |  |  |  | 1X2 açılış oranı home (B365) |
| `opening_X` | REAL |  |  |  | 1X2 açılış oranı draw |
| `opening_2` | REAL |  |  |  | 1X2 açılış oranı away |
| `opening_over25` | REAL |  |  |  | A/Ü 2.5 açılış oranı Üst |
| `opening_under25` | REAL |  |  |  | A/Ü 2.5 açılış oranı Alt |
| `opening_source` | TEXT |  |  |  |  |
| `opening_fetched_at` | TEXT |  |  |  |  |
| `closing_1` | REAL |  |  |  | 1X2 kapanış oranı home (Pinnacle veya Avg fallback) |
| `closing_X` | REAL |  |  |  | 1X2 kapanış oranı draw |
| `closing_2` | REAL |  |  |  | 1X2 kapanış oranı away |
| `closing_over25` | REAL |  |  |  | A/Ü 2.5 kapanış oranı Üst |
| `closing_under25` | REAL |  |  |  | A/Ü 2.5 kapanış oranı Alt |
| `closing_btts_yes` | REAL |  |  |  | KG kapanış oranı Var |
| `closing_btts_no` | REAL |  |  |  | KG kapanış oranı Yok |
| `closing_source` | TEXT |  |  |  |  |
| `closing_fetched_at` | TEXT |  |  |  |  |
| `home_xg` | REAL |  |  |  | Understat home xG |
| `away_xg` | REAL |  |  |  | Understat away xG |
| `home_shots` | INTEGER |  |  |  |  |
| `away_shots` | INTEGER |  |  |  |  |
| `home_possession_pct` | REAL |  |  |  |  |
| `away_possession_pct` | REAL |  |  |  |  |
| `home_key_injuries` | INTEGER |  |  |  |  |
| `away_key_injuries` | INTEGER |  |  |  |  |
| `home_lineup_quality` | REAL |  |  |  |  |
| `away_lineup_quality` | REAL |  |  |  |  |
| `has_full_odds` | INTEGER |  |  | 0 | 1X2 closing odds tam mı (1/0) |
| `has_opening_odds` | INTEGER |  |  | 0 | Opening odds var mı |
| `has_xg` | INTEGER |  |  | 0 | xG verisi var mı |
| `has_result` | INTEGER |  |  | 0 |  |
| `is_settled` | INTEGER |  |  | 0 | Maç oynanıp sonuçlandı mı |
| `quality_score` | REAL |  |  |  | 0-1 arası kalite skoru (sinyal coverage) |
| `ingested_at` | TEXT | ✓ |  |  | İlk ingest zaman damgası |
| `refreshed_at` | TEXT |  |  |  | Son güncelleme zamanı |
| `home_shots_total` | INTEGER |  |  |  | Total shots home |
| `away_shots_total` | INTEGER |  |  |  | Total shots away |
| `home_shots_on` | INTEGER |  |  |  |  |
| `away_shots_on` | INTEGER |  |  |  |  |
| `home_fouls` | INTEGER |  |  |  |  |
| `away_fouls` | INTEGER |  |  |  |  |
| `home_corners` | INTEGER |  |  |  | Korner sayısı home |
| `away_corners` | INTEGER |  |  |  | Korner sayısı away |
| `home_yellows` | INTEGER |  |  |  | Sarı kart home |
| `away_yellows` | INTEGER |  |  |  | Sarı kart away |
| `home_reds` | INTEGER |  |  |  | Kırmızı kart home |
| `away_reds` | INTEGER |  |  |  | Kırmızı kart away |
| `referee` | TEXT |  |  |  | Hakem ismi |
| `has_match_stats` | INTEGER |  |  | 0 | Match stats (shots/corners/cards) var mı |
| `clv_home` | REAL |  |  |  | CLV home leg = (opening_1 / closing_1) - 1 |
| `clv_draw` | REAL |  |  |  | CLV draw leg |
| `clv_away` | REAL |  |  |  | CLV away leg |
| `clv_over25` | REAL |  |  |  |  |
| `clv_under25` | REAL |  |  |  |  |
| `clv_avg_1x2` | REAL |  |  |  | 1X2 ortalama CLV |
| `has_clv` | INTEGER |  |  | 0 | CLV hesaplanmış mı |

---

## odds

**Satır sayısı:** 0

| Kolon | Tip | NN | PK | Default | Açıklama |
|---|---|---|---|---|---|
| `fixture_id` | INTEGER | ✓ | 🔑 |  |  |
| `market` | TEXT | ✓ | 🔑 |  |  |
| `selection` | TEXT | ✓ | 🔑 |  |  |
| `bookmaker` | TEXT | ✓ | 🔑 |  |  |
| `odd` | REAL | ✓ |  |  |  |
| `fetched_at` | TEXT | ✓ |  |  |  |

---

## odds_anomaly_signals

Cross-market anomaly tespitleri

**Satır sayısı:** 89

| Kolon | Tip | NN | PK | Default | Açıklama |
|---|---|---|---|---|---|
| `fixture_id` | INTEGER |  |  |  |  |
| `iddaa_match_id` | TEXT | ✓ | 🔑 |  |  |
| `snapshot_id` | TEXT | ✓ | 🔑 |  |  |
| `overround_1x2` | REAL |  |  |  |  |
| `overround_ou` | REAL |  |  |  |  |
| `overround_btts` | REAL |  |  |  |  |
| `consistency_score` | REAL |  |  |  |  |
| `structural_signal` | TEXT |  |  |  |  |
| `anomaly_direction` | TEXT |  |  |  |  |
| `anomaly_strength` | REAL |  |  |  |  |
| `computed_at` | TEXT | ✓ |  |  |  |

---

## picks_log_v2

Canlı picks log (gerçek bahisler için)

**Satır sayısı:** 0

| Kolon | Tip | NN | PK | Default | Açıklama |
|---|---|---|---|---|---|
| `pick_id` | INTEGER |  | 🔑 |  | Pick unique id |
| `model` | TEXT | ✓ |  |  | Hangi model üretti (TRIVOX/DUOVOX vb.) |
| `pick_created_at` | TEXT | ✓ |  |  |  |
| `league_code` | TEXT | ✓ |  |  | T1/E0/D1/SP1/I1/F1 |
| `matchday` | TEXT | ✓ |  |  | Maç tarihi YYYY-MM-DD |
| `match_id` | INTEGER |  |  |  | Internal primary key |
| `K` | INTEGER |  |  |  | Kupon leg sayısı |
| `leg_no` | INTEGER |  |  |  | Kombin içindeki leg numarası |
| `home_team` | TEXT |  |  |  | Ev sahibi takım (canonical isim) |
| `away_team` | TEXT |  |  |  | Deplasman takım (canonical isim) |
| `direction` | TEXT |  |  |  | HOME/DRAW/AWAY |
| `opening_odd` | REAL |  |  |  | Pick yapıldığında oran |
| `closing_odd` | REAL |  |  |  | Maç başlangıcında oran |
| `clv_pct` | REAL |  |  |  | CLV yüzdesi |
| `score_v2` | REAL |  |  |  |  |
| `confirmers_count` | INTEGER |  |  |  |  |
| `signals_used` | TEXT |  |  |  |  |
| `stake_tl` | REAL |  |  |  | Stake TL |
| `kelly_fraction` | REAL |  |  |  | Kelly fraction kullanılan |
| `settled` | INTEGER |  |  | 0 | Maç oynanmış mı (1/0) |
| `won` | INTEGER |  |  |  |  |
| `pnl_gross` | REAL |  |  |  | Brüt kar/zarar TL |
| `pnl_net` | REAL |  |  |  | Net (vergi sonrası) TL |
| `settled_at` | TEXT |  |  |  |  |

---

## seasons_meta

Sezon-lig coverage özet metadata

**Satır sayısı:** 54

| Kolon | Tip | NN | PK | Default | Açıklama |
|---|---|---|---|---|---|
| `league_code` | TEXT | ✓ | 🔑 |  | T1/E0/D1/SP1/I1/F1 |
| `season` | TEXT | ✓ | 🔑 |  | Canonical sezon kodu (YYYY-YY) |
| `start_date` | TEXT |  |  |  |  |
| `end_date` | TEXT |  |  |  |  |
| `n_total_matches` | INTEGER |  |  |  |  |
| `n_settled` | INTEGER |  |  |  |  |
| `coverage_pct` | REAL |  |  |  |  |
| `last_refresh` | TEXT |  |  |  |  |

---

## signal_snapshots

**MODEL ÇIKTILARI** — Her maç için tüm sinyallerin durumu + outcome. Q5+a2 picks bu tablodan çıkar.

**Satır sayısı:** 19,198

| Kolon | Tip | NN | PK | Default | Açıklama |
|---|---|---|---|---|---|
| `snapshot_id` | TEXT | ✓ | 🔑 |  |  |
| `match_uid` | TEXT | ✓ | 🔑 |  | Tabloda unique identifier (lig_sezon_home_away_date) |
| `source` | TEXT | ✓ |  |  | football_data / iddaa / manual |
| `iddaa_match_id` | TEXT |  |  |  |  |
| `fixture_id` | INTEGER |  |  |  |  |
| `league_code` | TEXT |  |  |  | T1/E0/D1/SP1/I1/F1 |
| `season` | TEXT |  |  |  | Canonical sezon kodu (YYYY-YY) |
| `kickoff_iso` | TEXT |  |  |  |  |
| `home_team` | TEXT | ✓ |  |  | Ev sahibi takım (canonical isim) |
| `away_team` | TEXT | ✓ |  |  | Deplasman takım (canonical isim) |
| `odd_1` | REAL |  |  |  |  |
| `odd_X` | REAL |  |  |  |  |
| `odd_2` | REAL |  |  |  |  |
| `odd_over25` | REAL |  |  |  |  |
| `odd_under25` | REAL |  |  |  |  |
| `odd_btts_yes` | REAL |  |  |  |  |
| `odd_btts_no` | REAL |  |  |  |  |
| `odd_open_1` | REAL |  |  |  |  |
| `odd_open_X` | REAL |  |  |  |  |
| `odd_open_2` | REAL |  |  |  |  |
| `odd_open_over25` | REAL |  |  |  |  |
| `odd_open_under25` | REAL |  |  |  |  |
| `fp_1` | REAL |  |  |  | Vig-stripped fair probability home (closing) |
| `fp_X` | REAL |  |  |  | Vig-stripped fair probability draw |
| `fp_2` | REAL |  |  |  | Vig-stripped fair probability away |
| `fp_over25` | REAL |  |  |  | Fair prob Üst 2.5 (closing) |
| `fp_under25` | REAL |  |  |  | Fair prob Alt 2.5 |
| `fp_btts_yes` | REAL |  |  |  |  |
| `fp_btts_no` | REAL |  |  |  |  |
| `overround_1x2` | REAL |  |  |  |  |
| `overround_ou` | REAL |  |  |  |  |
| `overround_btts` | REAL |  |  |  |  |
| `s_anomaly` | REAL |  |  |  | Cross-market anomaly sinyal gücü 0-1 |
| `s_model` | REAL |  |  |  | Dixon-Coles model güven sinyali |
| `s_xg` | REAL |  |  |  | xG luck (mean reversion) sinyali |
| `s_form` | REAL |  |  |  | Rolling 5-maç form sinyali |
| `s_sharp` | REAL |  |  |  | Sharp money detection |
| `s_invvar` | REAL |  |  |  | Inverse variance (overround) |
| `s_tipster` | REAL |  |  |  |  |
| `dir_anomaly` | TEXT |  |  |  | Anomaly yönü HOME/DRAW/AWAY |
| `dir_model` | TEXT |  |  |  | DC modelin tahminediği yön |
| `dir_xg` | TEXT |  |  |  | xG sinyalinin yönü |
| `dir_form` | TEXT |  |  |  | Form sinyalinin yönü |
| `dir_sharp` | TEXT |  |  |  |  |
| `dir_tipster` | TEXT |  |  |  |  |
| `dir_consensus` | TEXT |  |  |  | Çoğunluk sinyalin gösterdiği yön |
| `dir_favorite` | TEXT |  |  |  | Pinnacle implied favori (en düşük odd) |
| `score_v12` | REAL |  |  |  | Eski v1.2 birleşik skor |
| `score_v13` | REAL |  |  |  | v1.3 score (anomaly+model+xG+form+sharp+invvar) |
| `agree_count` | INTEGER |  |  |  | Kaç sinyal favori yönü ile aynı |
| `signal_count` | INTEGER |  |  |  | Kaç sinyal aktif |
| `model_lam_h` | REAL |  |  |  | DC home expected goals lambda |
| `model_lam_a` | REAL |  |  |  | DC away expected goals mu |
| `model_league` | TEXT |  |  |  |  |
| `model_max_edge` | REAL |  |  |  | DC modelin en yüksek edge gördüğü leg |
| `xg_luck_diff` | REAL |  |  |  | Home_xg_luck - away_xg_luck |
| `form_delta` | REAL |  |  |  | Home_form_pts - away_form_pts |
| `result_1x2` | TEXT |  |  |  | FT result H/D/A |
| `home_score` | INTEGER |  |  |  | Ev sahibi tam zaman skor |
| `away_score` | INTEGER |  |  |  | Deplasman tam zaman skor |
| `total_goals` | INTEGER |  |  |  | Toplam gol |
| `ft_btts` | INTEGER |  |  |  | KG gerçekleşti mi (1/0) |
| `settled` | INTEGER |  |  | 0 | Maç oynanmış mı (1/0) |
| `pnl_top3_v13` | REAL |  |  |  |  |
| `pnl_agree23` | REAL |  |  |  |  |
| `pnl_fav` | REAL |  |  |  |  |
| `pnl_xg_fav` | REAL |  |  |  |  |
| `created_at` | TEXT | ✓ |  |  |  |
| `s_shots` | REAL |  |  |  | Shots-form differential sinyal (yeni v14) |
| `dir_shots` | TEXT |  |  |  | Shots-form sinyalinin yönü |
| `s_referee` | REAL |  |  |  | Referee bias sinyal (yeni v14) |
| `dir_referee` | TEXT |  |  |  | Referee bias yönü |
| `s_cards` | REAL |  |  |  | Cards pressure sinyal (yeni v14) |
| `dir_cards` | TEXT |  |  |  | Cards pressure yönü (DRAW) |
| `score_v14` | REAL |  |  |  | v1.4 score (v13 + shots+referee+cards) |
| `fp_ou_model_over` | REAL |  |  |  | Model Üst 2.5 olasılığı (DC Poisson) |
| `fp_ou_model_under` | REAL |  |  |  | Model Alt 2.5 olasılığı |
| `s_ou_model` | REAL |  |  |  | A/Ü 2.5 DC Poisson sinyal gücü |
| `dir_ou_model` | TEXT |  |  |  | A/Ü 2.5 model yönü Over/Under |
| `ou_model_edge` | REAL |  |  |  | Model_p_over - Market_p_over |
| `fp_btts_model_yes` | REAL |  |  |  | Model KG Var olasılığı |
| `fp_btts_model_no` | REAL |  |  |  | Model KG Yok olasılığı |
| `s_btts_model` | REAL |  |  |  | KG DC model sinyal gücü |
| `dir_btts_model` | TEXT |  |  |  | KG model yönü Var/Yok |

---

## team_aliases

Takım isimleri canonical mapping (Understat-FD vs.)

**Satır sayısı:** 310

| Kolon | Tip | NN | PK | Default | Açıklama |
|---|---|---|---|---|---|
| `alias` | TEXT | ✓ | 🔑 |  | Alternatif takım ismi (Understat, iddaa vb.) |
| `source` | TEXT | ✓ | 🔑 |  | football_data / iddaa / manual |
| `league_code` | TEXT | ✓ | 🔑 |  | T1/E0/D1/SP1/I1/F1 |
| `canonical_name` | TEXT | ✓ |  |  | Canonical (matches_v2'deki) isim |
| `notes` | TEXT |  |  |  |  |

---

## tipster_picks

Tipster verisi (alternatif sinyal kaynağı)

**Satır sayısı:** 142

| Kolon | Tip | NN | PK | Default | Açıklama |
|---|---|---|---|---|---|
| `pick_id` | INTEGER |  | 🔑 |  | Pick unique id |
| `tipster_id` | TEXT | ✓ |  |  |  |
| `tipster_name` | TEXT |  |  |  |  |
| `source` | TEXT | ✓ |  |  | football_data / iddaa / manual |
| `posted_at` | TEXT |  |  |  |  |
| `kickoff_iso` | TEXT |  |  |  |  |
| `home_team` | TEXT | ✓ |  |  | Ev sahibi takım (canonical isim) |
| `away_team` | TEXT | ✓ |  |  | Deplasman takım (canonical isim) |
| `market` | TEXT | ✓ |  |  |  |
| `selection` | TEXT | ✓ |  |  |  |
| `pick_odd` | REAL |  |  |  |  |
| `stake_units` | REAL |  |  |  |  |
| `confidence` | REAL |  |  |  |  |
| `settled` | INTEGER | ✓ |  | 0 | Maç oynanmış mı (1/0) |
| `won` | INTEGER |  |  |  |  |
| `inserted_at` | TEXT | ✓ |  |  |  |
| `raw_json` | TEXT |  |  |  |  |

---

## tipster_stats

**Satır sayısı:** 12

| Kolon | Tip | NN | PK | Default | Açıklama |
|---|---|---|---|---|---|
| `tipster_id` | TEXT |  | 🔑 |  |  |
| `tipster_name` | TEXT |  |  |  |  |
| `source` | TEXT | ✓ |  |  | football_data / iddaa / manual |
| `total_picks` | INTEGER | ✓ |  | 0 |  |
| `settled_picks` | INTEGER | ✓ |  | 0 |  |
| `wins` | INTEGER | ✓ |  | 0 |  |
| `win_rate` | REAL |  |  |  |  |
| `avg_odd` | REAL |  |  |  |  |
| `roi` | REAL |  |  |  |  |
| `recent_form_50` | REAL |  |  |  |  |
| `variance` | REAL |  |  |  |  |
| `score` | REAL |  |  |  |  |
| `last_pick_at` | TEXT |  |  |  |  |
| `updated_at` | TEXT | ✓ |  |  |  |
| `wilson_lower` | REAL |  |  |  |  |
| `wilson_upper` | REAL |  |  |  |  |

---

## top_players

**Satır sayısı:** 439

| Kolon | Tip | NN | PK | Default | Açıklama |
|---|---|---|---|---|---|
| `league_code` | TEXT | ✓ | 🔑 |  | T1/E0/D1/SP1/I1/F1 |
| `season` | INTEGER | ✓ | 🔑 |  | Canonical sezon kodu (YYYY-YY) |
| `rank_type` | TEXT | ✓ | 🔑 |  |  |
| `rank` | INTEGER | ✓ | 🔑 |  |  |
| `player_id` | INTEGER | ✓ |  |  |  |
| `player_name` | TEXT | ✓ |  |  |  |
| `team_id` | INTEGER |  |  |  |  |
| `team_name` | TEXT |  |  |  |  |
| `value` | INTEGER | ✓ |  |  |  |
| `appearances` | INTEGER |  |  |  |  |
| `minutes` | INTEGER |  |  |  |  |
| `inserted_at` | TEXT | ✓ |  |  |  |

---

## xg_data

Understat xG verisi (5 lig × 4-5 sezon)

**Satır sayısı:** 7,156

| Kolon | Tip | NN | PK | Default | Açıklama |
|---|---|---|---|---|---|
| `fixture_id` | INTEGER |  |  |  |  |
| `league_code` | TEXT | ✓ | 🔑 |  | T1/E0/D1/SP1/I1/F1 |
| `season` | INTEGER | ✓ | 🔑 |  | Canonical sezon kodu (YYYY-YY) |
| `match_date` | TEXT | ✓ | 🔑 |  |  |
| `home_team` | TEXT | ✓ | 🔑 |  | Ev sahibi takım (canonical isim) |
| `away_team` | TEXT | ✓ | 🔑 |  | Deplasman takım (canonical isim) |
| `home_xg` | REAL |  |  |  | Understat home xG |
| `away_xg` | REAL |  |  |  | Understat away xG |
| `home_goals` | INTEGER |  |  |  |  |
| `away_goals` | INTEGER |  |  |  |  |
| `understat_url` | TEXT |  |  |  |  |
| `inserted_at` | TEXT | ✓ |  |  |  |

---

