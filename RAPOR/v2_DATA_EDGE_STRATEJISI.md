# DATA → EDGE STRATEJİSİ
## "Veri sürekli genişler, ortogonal kaynaklar birikir, mikro-edge'ler katlanır"

**Tarih:** 2026-05-28
**Vizyon:** Sürekli besleyen veri ekosistemi
**Hedef:** Mikro-edge birikimi → toplam edge %3-7 net (sürdürülebilir)

---

## 1) EDGE MATEMATİĞİ

**Mikro-edge birikim prensibi:**

```
Tek sinyal edge: %0.5-2 (zayıf ama gerçek)
10 ortogonal sinyal: √10 × ortalama_edge ≈ 3.2x birleşik
Sonuç: %1.5-6.4 toplam edge (kelime üstü ortalama)
```

**Anahtar kelime:** **ortogonal** — sinyaller aynı şeyi söylememeli. Aksi takdirde edge katlanmaz.

---

## 2) MEVCUT VERİ KAYNAKLARI

| Kaynak | Erişim | Coverage | Edge Potansiyeli | Durum |
|---|---|---|---|---|
| Football-Data.co.uk | Ücretsiz CSV | 6 lig × 9 sezon = 19K maç | Temel (1X2 odds, goal stats) | ✅ Aktif |
| Understat | Python scraper | 5 lig (T1 yok), 4-5 sezon | xG, xGA, shots | ✅ Aktif |
| iddaa.com | Manuel/scraper | Canlı 7 pazar | Türkiye odds canlı | 🟡 Kısmen |
| API-Football | REST (free tier) | Tüm dünya | Fixture, odds, stats | 🟡 Aktif |
| matches_v2 | Internal DB | Tüm yukarıdaki birleşik | Standardize sample | ✅ Aktif |

**Mevcut edge:** Sınırlı, çoğunlukla market-implied 1X2.

---

## 3) HEDEFLENEN VERİ KAYNAKLARI (12 KAYNAK)

### Tier 1 — Yüksek ROI Veri (öncelikli, edge potansiyeli net)

#### 1. **FotMob** (T1 xG + lineup)
- **Skill:** Web scraping (HTML + JSON endpoints)
- **Veri:** T1 dahil tüm lig xG, shot maps, kadrolar
- **Edge alanı:** T1 xG açığını kapat (TRIVOX'un en zayıf yanı)
- **Maliyet:** Free
- **Tahmini edge katkı:** +%1-2 (T1 picks doğruluğunda)

#### 2. **Sofascore** (oyuncu rating + olay listesi)
- **Skill:** Selenium + API endpoints
- **Veri:** Oyuncu rating, dakika-by-dakika olaylar, heat-map
- **Edge alanı:** Oyuncu-bazlı micro-prediction (gol atan, kart vs)
- **Maliyet:** Free (rate-limited)
- **Tahmini edge:** +%0.5-1.5

#### 3. **FBRef (StatsBomb partner)** (gelişmiş metrics)
- **Skill:** Pandas read_html + BS4
- **Veri:** Possession, pressure, progressive passes, xT (expected threat)
- **Edge alanı:** xG'den derin metrics, model girdileri
- **Maliyet:** Free (yavaş, polite scraping)
- **Tahmini edge:** +%1-2

#### 4. **Transfermarkt** (kadro değeri + transfer)
- **Skill:** Web scraping
- **Veri:** Kadro değeri, son transferler, sakatlıklar
- **Edge alanı:** Sezon-içi kadro değişimi → form prediction
- **Maliyet:** Free
- **Tahmini edge:** +%0.5-1

### Tier 2 — Orta Edge (sürdürülebilirlik)

#### 5. **Pinnacle (Premium API)** (sharp closing odds + opening)
- **Skill:** REST API
- **Veri:** Gerçek sharp odds (CLV altın standardı)
- **Edge alanı:** CLV ölçümü, sharp money detection, line movement
- **Maliyet:** ~$50/ay
- **Tahmini edge:** Indirect (model validation) → %1-3 long-term

#### 6. **Twitter/X API** (sentiment + breaking news)
- **Skill:** Twitter API v2 + NLP
- **Veri:** Takım hesapları, gazeteci tweetleri, lineup leaks
- **Edge alanı:** Lineup announcement 1 saat önce, sakatlık haberi
- **Maliyet:** API erişimi $100/ay
- **Tahmini edge:** +%0.5-1.5 (latency edge)

#### 7. **OpenWeatherMap** (hava durumu)
- **Skill:** REST API
- **Veri:** Maç günü/saati hava tahmini (yağış, rüzgar)
- **Edge alanı:** Yağışlı maç → A/Ü, gol etkisi
- **Maliyet:** Free tier yeterli
- **Tahmini edge:** +%0.3-0.8

#### 8. **iddaa.com canlı odds (multi-snapshot)**
- **Skill:** Selenium + interval polling
- **Veri:** Closing yaklaşımı, line movement Türk pazarda
- **Edge alanı:** Türk piyasa sapma + sharp money detection
- **Maliyet:** Free
- **Tahmini edge:** +%1 (CLV proxy)

### Tier 3 — Niche Edge (uzun vadeli)

#### 9. **Wyscout/InStat** (profesyonel scout data)
- **Skill:** Ücretli abonelik + manuel
- **Veri:** Oyuncu pre-match profile, kombinasyon paternleri
- **Edge alanı:** Korner, faul, kart pazarları
- **Maliyet:** $500+/ay (genelde kurumsal)
- **Tahmini edge:** +%2-3 (niş pazarlar)

#### 10. **Reddit / forumlar** (community wisdom)
- **Skill:** Reddit API + filter
- **Veri:** Takım taraftarı içgörüleri, lokal haberler
- **Edge alanı:** Local-knowledge edge
- **Maliyet:** Free
- **Tahmini edge:** +%0.2-0.5

#### 11. **Hava durumu + saha geçmişi** (advanced)
- **Skill:** Tarihsel veri + corrleation
- **Veri:** Yağışlı zemin × pas öncesi takım = düşük performans
- **Edge alanı:** Niş ama mevcut
- **Maliyet:** Geliştirme zamanı
- **Tahmini edge:** +%0.3-0.7

#### 12. **Avrupa kupası fixture yoğunluğu**
- **Skill:** UEFA fixture parse
- **Veri:** Bir takım çift maç haftası (CL + lig) = yorgunluk
- **Edge alanı:** Multi-fixture week → home advantage azalır
- **Maliyet:** Free
- **Tahmini edge:** +%0.5-1

---

## 4) ORTOGONAL EDGE BİRİKİMİ

Önemli kavram: Aynı şeyi söyleyen 2 sinyal **tek sinyal**dir. Edge katlanmaz.

```
ÖRNEK ÇAPRAZLAMA:
  - xG vs Goals (Understat)         : aynı şey (gol odaklı)
  - xG vs Shots (FBRef)              : ilişkili (gol-attempt)
  - Form vs Last 5 result            : aynı (sonuç-odaklı)
  - Lineup quality vs Transfer value : aynı (kadro-odaklı)

ORTOGONAL OLABILIR:
  - xG (geçmiş performans)
  - Sharp money (piyasa görüşü)
  - Hava (dış faktör)
  - Sakatlık (kadro değişim)
  - Twitter sentiment (kamuoyu)

Bunlar birbirini söylemez → edge birikir
```

**Korelasyon matrisi (hedef):**

```
              xG    Sharp  Hava   Sakat  Sentiment
xG            1.0   0.20   0.05   0.30   0.10
Sharp         0.20  1.0    0.05   0.40   0.30
Hava          0.05  0.05   1.0    0.00   0.05
Sakatlık      0.30  0.40   0.00   1.0    0.20
Sentiment     0.10  0.30   0.05   0.20   1.0
```

5 sinyal **ortogonal yakını** → birikim hakkı.

---

## 5) DATA → EDGE PIPELINE

```
┌──────────────────────────────────────────────────────────────┐
│  RAW DATA SOURCES  (12 kaynak)                                │
│  FotMob, Sofascore, FBRef, Transfermarkt, Pinnacle, X, etc.   │
└──────────────────────────────────────────────────────────────┘
                            ↓
┌──────────────────────────────────────────────────────────────┐
│  DATA HUNTER AGENT  (sürekli ingest)                          │
│  - Schema mapping (canonical_name, season format)             │
│  - Quality check (anomaly_detection)                          │
│  - Versioning (snapshot kaydet)                               │
└──────────────────────────────────────────────────────────────┘
                            ↓
┌──────────────────────────────────────────────────────────────┐
│  FEATURE ENGINEERING  (raw → signal)                          │
│  - xG → xG_luck, xG_var                                       │
│  - Sharp odds → CLV, sharp_drift                              │
│  - Twitter → sentiment_score                                  │
│  - Hava → weather_impact_score                                │
│  - Sakatlık → key_player_missing                              │
└──────────────────────────────────────────────────────────────┘
                            ↓
┌──────────────────────────────────────────────────────────────┐
│  ORTHOGONALITY CHECK  (her yeni sinyal için)                  │
│  - Mevcut sinyallerle korelasyon ölç                          │
│  - |r| > 0.6 ise yedekli (ekleme)                             │
│  - |r| < 0.4 ise yeni edge alanı (ekle)                       │
└──────────────────────────────────────────────────────────────┘
                            ↓
┌──────────────────────────────────────────────────────────────┐
│  MODEL ENSEMBLE  (sinyal → tahmin)                            │
│  - TRIVOX, DUOVOX, TRIOVOX × 5 pazar                          │
│  - Ortogonal sinyal ağırlıkları (LightGBM/Bayesian)           │
│  - Per-lig × pazar adaptive weights                           │
└──────────────────────────────────────────────────────────────┘
                            ↓
┌──────────────────────────────────────────────────────────────┐
│  EDGE OUTPUT  (her pazar için olasılık + güven)               │
│  - Model_p, market_p, edge_pp, quintile, agree_count          │
└──────────────────────────────────────────────────────────────┘
```

---

## 6) ROADMAP — Veri Genişletme

### Sprint A — Foundation (Şu an + 4 hafta)
**A1.** FotMob T1 xG scraper (Tier 1, #1)
**A2.** Transfermarkt sakatlık scraper (Tier 1, #4)
**A3.** iddaa.com canlı odds multi-snapshot (Tier 2, #8)
**A4.** Pinnacle premium API trial (Tier 2, #5) — opsiyonel ücretli karar

### Sprint B — Derinleşme (Hafta 5-12)
**B1.** Sofascore oyuncu rating ingest (Tier 1, #2)
**B2.** FBRef gelişmiş metrics (Tier 1, #3)
**B3.** OpenWeather hava (Tier 2, #7)
**B4.** Twitter sentiment (Tier 2, #6) — opsiyonel

### Sprint C — Niche (Hafta 13-24)
**C1.** Avrupa kupası fixture etkisi
**C2.** Reddit community signals (deneme)
**C3.** Wyscout (sadece kurumsal opsiyonu varsa)

---

## 7) EDGE BİRİKİM SİMÜLASYONU

**Eski paradigma (1 model, 1 pazar, 4 sinyal):**
- Net edge: %2 (TRIVOX K=1 baseline)

**Yeni paradigma (5 model × 5 pazar × 12+ veri kaynağı):**
- Çıkarım: 60 (model × pazar) × 12 sinyal kombinasyonu
- Her birinde mikro-edge %0.3-1.5
- Birikim formülü (ortogonal): √60 × 0.5pp = **%3.9 ek edge tahmin**

**Hedef:**
- Mevcut TRIVOX +%2 ROI
- Yeni paradigma: **+%5-8 net ROI** (sürdürülebilir, küçük varyans)

---

## 8) DATA VERSIONING + REPRODUCIBILITY

Veri sürekli değişirken karar denetlenebilir kalmalı:

```
matches_v2.snapshots/
  2026-05-28_18:00.parquet   ← Bu pick verildi
  2026-05-29_19:00.parquet   ← Maç oynandı, sonuç eklendi
  ...

Her pick: "Hangi snapshot ile karar verildi?" log'lanır.
6 ay sonra: "Eğer bu snapshot ile karar versek, bugün sonuç ne olurdu?"
```

Bu, **veri sürüklemesi (drift)** durumunda eski kararı re-evaluate etmeyi sağlar.

---

## 9) BU HAFTA YAPILACAK

1. **DATA HUNTER AGENT iskeleti** — Python modül + skill katalog
2. **FotMob T1 xG scraper** (A1) — ilk gerçek yeni veri
3. **Transfermarkt scraper hazırlığı** (A2)
4. **Data ingestion calendar** — hangi gün hangi kaynak çekilecek

Bunlar AI Trader'ın **veri sürekli zenginleşen** zeminini hazırlar.
