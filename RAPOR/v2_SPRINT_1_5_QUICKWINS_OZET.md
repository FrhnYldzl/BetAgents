# v2 SPRINT 1.5 — QUICK WINS ÖZET

**Tarih:** 2026-05-28
**Faz:** Sprint 1 GATE PASS sonrası "Hızlı + Sürekli İyileştirme" (Option 3) — Day 1
**Durum:** Quick Wins tamamlandı

---

## 1) Yapılan İşler

### A4 — Football-Data Match Stats Kolonları
- 14 yeni kolon eklendi: `home_shots_total/away_shots_total`, `home_shots_on/away_shots_on`, `home_fouls/away_fouls`, `home_corners/away_corners`, `home_yellows/away_yellows`, `home_reds/away_reds`, `referee`, `has_match_stats`
- **19,198 satıra** uygulandı
- **Coverage:** D1/E0/F1/I1/SP1 **%100**, T1 **%99**

### B1 — 2017-2021 Historical Sezonları
- 6 lig × 4 ek sezon = **24 CSV** indirildi (mirror: huhao930422/football-odds-mirror)
- 2-haneli yıl parse fix uygulandı (T1_1718, D1_1718)
- `matches_v2_ingest_fd.py` SEASONS_MAP genişletildi: 1718→2017-18 ... 2526→2025-26 (9 sezon)
- **matches_v2: 10,657 → 19,198 satır (+80%)**

### C2 — Anomaly Detection
- `matches_v2_anomaly_detection.py` yazıldı
- 6 kontrol kategorisi: duplicates, extreme odds, score outliers, date sanity, team-name sanity, settled consistency
- **Sonuçlar:**
  - Duplicate maçlar: **0**
  - Overround outlier: **0**
  - Tarih anomalisi: **0**
  - Takım ismi anomalisi: **0**
  - Settled mismatch: **0**
  - Extreme tek-bacak odds: 3 (gerçek outlier maçlar)
  - Skor outlier (8+ gol): 137 (gerçek yüksek skorlu maçlar)
- Rapor: `anomalies_report.json`

### C1 — team_aliases Canonical Mapping
- `matches_v2_populate_aliases.py` yazıldı
- FD takımları canonical olarak işaretlendi: **188 takım** (6 lig)
- Understat (xg_data) takımları fuzzy-match ile FD canonical'a bağlandı
- **129 XG takımı:** 109 auto (≥0.85), 13 review (0.70-0.85), 7 skip (<0.70)
- Manuel düzeltme: "Paris Saint Germain" → "Paris SG" (yanlış olarak "Paris FC" eşleşmişti)
- Rapor: `aliases_review.json`

---

## 2) Sprint 1 GATE — DOĞRULAMA

| Metrik              | Hedef | Önceki (10,657 satır) | Şimdi (19,198 satır) |
|---------------------|-------|------------------------|----------------------|
| Satır sayısı        | -     | 10,657                 | **19,198 (+80%)**    |
| quality_score ≥0.70 | ≥%85  | %90.1                  | **%94.4** ✅          |
| quality_score ≥0.85 | -     | %87.0                  | **%94.4**            |
| Avg quality         | -     | 0.89                   | **0.88**             |

### Per-Lig Özet (yeni)

| Lig | Toplam | q≥0.70 | xG % | Stats % |
|-----|--------|--------|------|---------|
| D1  | 2,754  | %94    | varyat. | %100 |
| E0  | 3,420  | %95    | %22-100 | %100 |
| F1  | 3,096  | %95    | %22-90  | %100 |
| I1  | 3,420  | %95    | %22-100 | %100 |
| SP1 | 3,420  | %94    | %22-81  | %100 |
| T1  | 3,088  | %93    | **%0** | %99 |

---

## 3) Önemli Bulgular

### Güçlü
- ✅ **Hiç duplicate maç yok** (hash-based INSERT OR REPLACE temiz çalışıyor)
- ✅ **Match stats coverage %99-100** (shots/corners/cards/referee)
- ✅ **Quality gate aşıldı:** %94.4 (hedef %85)
- ✅ **Sample 2x büyüdü:** 10K → 19K maç → TRIVOX/EUVOX backtest istatistiksel gücü çok daha yüksek

### Açık Kalan (Sürekli İyileştirme fazı)
- ⚠️ **T1 xG %0** — Understat T1'yi tutmuyor. Çözüm: **A1 (FotMob/Sofascore scraper)**
- ⚠️ **D1 xG eski sezonlar (2017-2020) %0** — Understat'ın D1 retrofit'i sınırlı. Mevcut canlı sezonlarda %43-69
- ⚠️ **Sakatlık/lineup verisi yok** — Çözüm: **A2 (Transfermarkt injury backfill)**
- ⚠️ **2025-26 closing odds %44-55** — Doğal: sezon henüz oynanıyor, maçların çoğunun closing odd'u henüz teşekkül etmedi

---

## 4) Kazanım: TRIVOX/EUVOX v2 Üzerinde Etkisi

| Sinyal              | v1 Sample | v2 Sample (yeni) | Δ      |
|---------------------|-----------|-------------------|--------|
| T1 FAV_CONFIRMED    | 109 maç   | tahmini ~200 maç  | +83%   |
| EUVOX 6-lig sample  | ~2,800    | tahmini ~5,000    | +80%   |
| Bonferroni eşiği    | α/n=0.0025| α/n=0.0025 (aynı) | -      |
| Power @ 5% edge     | ~%60      | tahmini **~%80**  | +20pp  |

→ Model v2 yeniden eğitilirken **sample 2x büyüdü**, p-değerleri çok daha güvenilir olacak.

---

## 5) Sırada Ne Var?

### Sürekli İyileştirme (parallel, 2-5 gün)
- **A1** — T1 xG scraper (FotMob veya Sofascore)
- **A2** — Transfermarkt injury backfill (5 sezon)
- **S1** — Pinnacle opening odds backfill (OddsPortal)

### Yeni Model v2 İnşaatı (Sprint 2 başlat)
- **CLV pipeline**: opening vs closing tablosu üzerinden CLV hesabı
- **TRIVOX v2 retrain**: 6 sinyal × min_conf=2/6 kurallarıyla yeni sample üzerinde
- **EUVOX v2 retrain**: 8 sinyal × per-lig adaptive cfg

### Gate Kararı
> **Sprint 1 PASS** — Sprint 2 (CLV + Model v2 retrain) için **hazır**.

---

## 6) Dosyalar

| Dosya | Açıklama |
|---|---|
| `02_VERI/matches_v2_schema.py` | Master schema (Sprint 1.1) |
| `02_VERI/matches_v2_ingest_fd.py` | FD ingest, 9 sezon SEASONS_MAP |
| `02_VERI/matches_v2_extend_stats.py` | Match stats kolonları (A4) |
| `02_VERI/matches_v2_ingest_xg.py` | Understat xG join (Sprint 1.3) |
| `02_VERI/matches_v2_anomaly_detection.py` | C2 anomaly check |
| `02_VERI/matches_v2_populate_aliases.py` | C1 team_aliases populate |
| `02_VERI/matches_v2_quality_audit.py` | Quality gate audit |
| `02_VERI/scrapers/fd_download_historical.py` | B1 mirror downloader |
| `02_VERI/anomalies_report.json` | C2 raporu |
| `02_VERI/aliases_review.json` | C1 manuel review listesi |
