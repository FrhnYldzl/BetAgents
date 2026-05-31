# 🔬 v2 — DATA İYİLEŞTİRME ANALİZİ ve ÖNERİLER

**Tarih:** 2026-05-27
**Durum:** Sprint 1 sonrası — matches_v2 yüklendi ama eksikler var
**Odak:** "Data tutarsız → her şey tutarsız"

---

## 1. MEVCUT DURUMUN ELEŞTİREL ANALİZİ

### Sayısal Durum (Sprint 1 Sonrası)

```
matches_v2 total:     10,657 maç
quality≥0.7 oranı:    %90.1
avg_quality:          0.89

Per-lig dağılım:
  T1:  1,750 maç  avg_q 0.81  ⚠️ EN DÜŞÜK
  D1:  1,530 maç  avg_q 0.89
  SP1: 1,900 maç  avg_q 0.91
  F1:  1,677 maç  avg_q 0.92
  E0:  1,900 maç  avg_q 0.93
  I1:  1,900 maç  avg_q 0.93
```

### Ne İyi (Mevcut Güçler)

✅ 6 lig × 5 sezon coverage (sample yeterli backtest için)
✅ Closing odds (Pinnacle) tam — settled maçlar için %100
✅ Opening odds (B365) tam — geçmiş sezonlar
✅ Result data %100 — settled tüm maçlar
✅ Canonical season codes uygulandı (`'2021-22'` formatı)

### Ne Kötü (Düzeltilmesi Gerekenler)

#### ❌ A) Sinyal Eksiklikleri

| Sinyal | Sorun | Etki |
|---|---|---|
| **T1 xG** | %0 — Understat T1 desteklemiyor | TRIVOX zayıf, 3 sinyal max |
| **D1 xG** | %46 — fuzzy match sınırlı | EUVOX D1 zayıf |
| **Injuries** | Sadece 2024 sezonu (15K kayıt) | 4 sezon backtest sinyal alamıyor |
| **Lineup quality** | Yok | api-football lineups çekilmedi |
| **Fixture stats** | 94 satır (rate limit) | Shots/possession/corners eksik |

#### ❌ B) Sample Sınırlamaları

| Konu | Mevcut | Olması Gereken |
|---|---|---|
| TRIVOX sample | 109 kupon (4 sezon) | 300+ (9 sezon) |
| Sezon kapsamı | 2021-22 → 2025-26 | 2017-18 → 2025-26 (9 sezon) |
| Lig sayısı | 6 (top 5 + T1) | 10+ (Eredivisie, Portugal, Belgium) |
| Alt-lig | Yok | TFF 1.Lig, EFL Championship |

#### ❌ C) Live Data Capability

| Konu | Sorun |
|---|---|
| Live odds | Tek snapshot (iddaa, 89 maç) |
| Line movement | Multi-snapshot yok → sharp money sinyal zayıf |
| CLV | Pinnacle opening kaynağı yok |
| Real-time settle | Manuel |
| Auto refresh | Daily cron kurulmadı |

#### ❌ D) Veri Kalitesi Quality Sorunları

| Konu | Sorun |
|---|---|
| team_aliases tablosu | **BOŞ** — manuel doldurulmadı |
| 2025-26 sezon | Yarısı oynanmamış → closing odds %44-55 |
| Duplikat check | Yok |
| Anomaly detection | Yok (örn. extreme odds) |
| Data lineage | İz sürme zayıf |

---

## 2. İYİLEŞTİRME ÖNERİLERİ — 5 KATEGORİ

### KATEGORİ A — Kritik Eksiklikler (model edge'i etkiler)

#### A1. T1 xG kaynak — Sofascore scrape
**Sorun:** TRIVOX'un 4 sinyalinden xG eksik = sadece 3 sinyal aktif
**Çözüm seçenekleri:**

| Seçenek | Süre | Risk | Kalite |
|---|---|:---:|:---:|
| Sofascore scrape (Selenium) | 2-3 gün | ORTA (ToS) | Yüksek |
| FotMob API/scrape | 2 gün | ORTA | Yüksek |
| FBRef (StatsPerform) | 1 hafta | DÜŞÜK | Çok yüksek |
| Mackolik scrape | 2 gün | YÜKSEK (yasal) | Orta |
| Manual transcription | 1 hafta | YOK | Yüksek ama yavaş |

**Önerim:** **FotMob** (free API yok ama AJAX endpoints açık)

#### A2. Injury data backfill (2021-2024)
**Sorun:** api-football sadece 2024 sezonu sakatlığını verdi
**Çözüm:**
- **api-football paid plan** ($25/ay) tarihsel injury data verir
- VEYA **transfermarkt scrape** (sakatlık tarihçeleri public)
- VEYA **sakatlık tahmin proxy**: maç başında kaç değişiklik / form değişimi

**Önerim:** Transfermarkt scrape (free, comprehensive)

#### A3. Pinnacle Opening Odds (CLV için kritik)
**Sorun:** Opening sadece B365 — Pinnacle "açılış" yok → gerçek CLV ölçülmez
**Çözüm:**

| Seçenek | Maliyet | Veri |
|---|---|---|
| Pinnacle API official | $150/ay | Real-time |
| OddsPortal scrape | Free (riskli) | Geçmiş 5 yıl |
| Best Odds Comparison sites | Free | Sınırlı |
| Free public archive | Free | 2-3 sezon |

**Önerim:** **OddsPortal historical scrape** (Pinnacle opening + 20 bookmaker)

#### A4. fixture_statistics (shots, possession, corners)
**Sorun:** Rate limit nedeniyle sadece 94 maç
**Çözüm:**
- api-football paid plan: 75K req/gün (vs free 100)
- VEYA Football-Data CSV bazı stat'ları içeriyor (HS, AS, HST, AST, HC, AC)
- **AKTIF kullanım:** Football-Data CSV'sindeki shots/corners zaten matches_v2'de YOK

**Önerim:** Football-Data CSV'sindeki **HS/AS/HST/AST/HF/AF/HC/AC/HY/AY/HR/AR** kolonlarını matches_v2'ye **ekle** — bu zaten elimizde!

---

### KATEGORİ B — Sample Genişletme

#### B1. Tarihsel sezonlar (2017-2021)
**Sorun:** Sadece 5 sezon → TRIVOX sample 109 kupon
**Çözüm:**
- Football-Data CSV'leri 1993'ten beri var
- 2017-2021 = 4 ek sezon × 6 lig × 380 maç = ~9000 ek maç
- Toplam matches_v2: 10K → 20K (2x)

**Önerim:** ✅ **YAP** — Sprint 1.5 olarak 4 ek sezon ingest

#### B2. Yeni ligler
**Adaylar:**
- N1 (Eredivisie — Hollanda)
- P1 (Primeira Liga — Portekiz)
- B1 (Belgium Pro)
- SC0 (Scotland Premier)
- Bundesliga 2 (D2)
- Serie B (I2)
- EFL Championship (E1)

**Faydaları:**
- xG coverage iyi (Understat 5 lig + Eredivisie)
- Daha az analiz görülen ligler → bookmaker daha az sharp → edge potansiyeli
- TRIVOX gibi "milli ligler" stratejisi genişler

**Önerim:** ✅ **Eredivisie + 2 Türk alt-lig (TFF1+TFF2)** eklenebilir

---

### KATEGORİ C — Veri Kalitesi

#### C1. team_aliases canonical mapping
**Sorun:** Tablo boş — manuel mapping yok, fuzzy match zayıf
**Çözüm:**
- Her ligin canonical takım isimlerini Football-Data'dan al
- Understat + api-football + iddaa alias'larını ekle
- Manuel review queue

**Önerim:** ✅ **YAP** — 2 saat manuel, sonra otomatik

#### C2. Duplikat + Anomaly Detection
**Sorun:** Aynı maçın farklı kaynaklardan farklı satır olabilir
**Çözüm:**
```python
def detect_anomalies():
    # Odd outliers (1X2 sum > 1.50 = vig çok yüksek, illiquid)
    # Score outliers (10-0 sonuçlar)
    # Date mismatches
    # Duplicate detection (same teams, ±2 day)
```

**Önerim:** ✅ Sprint 1.6 — quality check module

#### C3. Daily Cron Job
**Sorun:** Refresh manuel
**Çözüm:**
- Windows Task Scheduler veya cron
- Python `schedule` lib
- Cloud function (AWS Lambda, $0)

**Önerim:** Sprint 2 ile birlikte yapılır

---

### KATEGORİ D — Yeni Sinyal Kaynakları

#### D1. Hakem istatistikleri
**Sorun:** Hakemler kart/penaltı oranlarını etkiler
**Kaynak:** Football-Data CSV'de "Referee" var
**Hesap:**
- Hakem başına avg cards, avg pens
- High-card referee → daha çok kart/pen → OU value
**Önerim:** Marjinal etki, Sprint 3'te ele al

#### D2. Hava durumu
**Sorun:** Yağmur = düşük skor sinyali
**Kaynak:** OpenWeather API (free, $0)
**Hesap:** Maç saati + venue location → weather
**Önerim:** Sprint 3 (opsiyonel)

#### D3. Lineup quality
**Sorun:** Starting 11 vs B-team karşılaştırma
**Kaynak:** api-football lineups endpoint
**Önerim:** Sprint 3 (önemli)

---

### KATEGORİ E — Live Capability

#### E1. Multi-snapshot per matchday
**Sorun:** Tek snapshot = line movement yok
**Çözüm:**
- iddaa scraper saatlik koşsun (matchday ± 24h)
- Snapshot delta hesabı

**Önerim:** Sprint 2 ile birlikte

---

## 3. PRİORİTE MATRİSİ

```
                    YÜKSEK ETKİ
                          ▲
                          │
   B1 Tarihsel sezon  ───┤├─── A3 Pinnacle CLV
                          │
   C1 Team aliases    ───┤├─── A2 Injuries backfill
                          │
                ┌─────────┼─────────┐
       D3 Lineup│         │         │A1 T1 xG
                │   ETKİ  │   ETKİ  │
                │   ORTA  │  YÜKSEK │
                ├─────────┼─────────┤
       D1 Hakem │   ETKİ  │   ETKİ  │A4 FD stats
       D2 Hava  │  DÜŞÜK  │   ORTA  │
                └─────────┼─────────┘
                          │
                          ▼
                    DÜŞÜK ETKİ

       KOLAY ──────────────────────► ZOR
       (≤ 1 gün)               (> 1 hafta)
```

### YAP HEMEN (Quick Win — kolay + yüksek etki)

1. **A4: Football-Data shots/corners/cards → matches_v2** (15 dakika)
   - CSV'de zaten var, sadece SQL UPDATE
2. **B1: 2017-2021 sezonları ingest** (1 saat)
   - CSV download + ingest tekrarı
3. **C1: Team aliases doldur** (2 saat)
   - Manuel mapping + INSERT

### YAP YAKINDA (Quick Win — kolay + orta etki)

4. **C2: Anomaly detection** (1 saat)
5. **C3: Daily cron** (1 saat)
6. **A2: Transfermarkt sakatlık scrape** (1 gün)

### YAP SONRA (Yüksek etki + zor)

7. **A1: T1 xG (FotMob/Sofascore)** (2-3 gün)
8. **A3: Pinnacle opening (OddsPortal)** (2-3 gün)
9. **D3: Lineup quality (api-football)** (1 gün)
10. **E1: Multi-snapshot live odds** (1 gün)

### ATLA / SONRA

- D1 Hakem (marjinal)
- D2 Hava (opsiyonel)
- B2 Yeni lig (sample yeterli zaten)

---

## 4. ÖNERİLEN SPRINT 1.5 — DATA IYILESTIRME

```yaml
Sprint 1.5 — Quick Wins (2-3 gün):

Day 1:
  - [ ] A4: Football-Data shots/corners/cards → matches_v2 (15 dk)
  - [ ] B1: 2017-2021 sezonları CSV indir + ingest (1 saat)
  - [ ] C1: Team aliases manuel mapping doldur (2 saat)
  - [ ] C2: Anomaly detection (extreme odds, duplicate) (1 saat)

Day 2:
  - [ ] xG re-join (yeni sezonlar dahil) (1 saat)
  - [ ] Quality audit (Gate yeniden test) (30 dk)
  - [ ] A2: Transfermarkt injury scraper başlangıç (3 saat)

Day 3:
  - [ ] A2: Injury data 4 sezon backfill (3-4 saat)
  - [ ] Quality audit final + Sprint 1.5 raporu (1 saat)

Beklenen sonuç:
  matches_v2: 10,657 → ~20,000 satır (2x)
  avg_quality: 0.89 → 0.92+
  TRIVOX sample tahmini: 109 → 200+
  Injury coverage: 1 sezon → 5 sezon
  Shots/cards verisi: %0 → %100 (FD CSV'den)
```

---

## 5. SADE TARTIŞMA SORULARI

Hangilerini öncelik istersin?

**S1. Sample artırma:** 2017-2021 sezon ekleyelim mi (B1)?
- Pro: TRIVOX sample 2x, statistical confidence artar
- Con: 1 saat süre

**S2. T1 xG:** Sofascore/FotMob scrape yapalım mı (A1)?
- Pro: TRIVOX 3→4 sinyal, edge artar
- Con: 2-3 gün, ToS riski

**S3. Injury backfill:** Transfermarkt scrape (A2)?
- Pro: 5 sinyal → 6 sinyal, calibration iyileşir
- Con: 1 gün, scraping risk

**S4. CLV doğrulama:** OddsPortal Pinnacle opening (A3)?
- Pro: Acquirer'ın #1 sorusuna cevap
- Con: 2-3 gün, scraping

**S5. Quick wins paketi (Sprint 1.5):** Hepsini 3 günde yapalım mı?
- A4 + B1 + C1 + C2 + A2

---

## 6. ÖNERİM (Net)

```
ÖNCELİK A (kesin yapılmalı):
  1. A4: FD shots/corners/cards → matches_v2  (15 dk, sıfır risk)
  2. B1: 2017-2021 sezon ingest                (1 saat, sample 2x)
  3. C1: Team aliases mapping                  (2 saat, fuzzy match dahil iyileşir)
  4. C2: Anomaly detection                     (1 saat, data sanity)

ÖNCELİK B (yüksek değer ama zorlu):
  5. A2: Transfermarkt injury scrape           (1 gün, 5 sezon coverage)
  6. A1: T1 xG (FotMob deneyelim önce)         (2 gün, TRIVOX güçlenir)

SONRA (Sprint 2+):
  7. A3: OddsPortal CLV
  8. D3: Lineup quality
  9. E1: Multi-snapshot
```

**Önerim:** Önce **ÖNCELİK A**'yı 1 günde tamamla, audit yap, sonra B'ye gir.

Bu yolla 1 gün sonra **sample 2x büyük + canonical team aliases + clean data** elde ederiz. Sonra B sprint'leri ile sinyal sayısı artar.

Onayını bekliyorum — hangisini başlatayım?
