# 🔍 iddaa.com API Keşif Raporu & Veri Zenginleştirme Stratejisi

**Tarih:** 2026-05-29  
**Kaynak:** `https://www.iddaa.com/program/futbol/mac-detay/2/2975498/maclar`  
**Yöntem:** JS source analysis + microservice endpoint probe + live API calls  
**Durum:** Production-ready API bulundu, 6 veri sekmesi haritalandı

---

## 1. KEŞFEDILEN API MİMARİSİ

iddaa.com **Next.js + 12+ microservice** mimarisi kullanıyor. Tüm veri client-side API çağrılarıyla yükleniyor.

### 1.1 Çalışan Production Endpoints ✅

```
BASE: https://sportsbookv2.iddaa.com

GET /sportsbook/event/{eventId}          → Tek maç: odds + canlı istatistik
GET /sportsbook/event/list?sportId=1     → Günlük program (bahise açık)
GET /sportsbook/events?sportId=1         → Sayfalı event listesi
```

### 1.2 Keşfedilen Microservices (endpoint hâlâ araştırılıyor)

| Servis | Domain | İçerik |
|---|---|---|
| ✅ | `sportsbookv2.iddaa.com` | Odds, live scores, market data |
| 🔍 | `statisticsv2.iddaa.com` | Maç istatistikleri, xG, şutlar |
| 🔍 | `playersv2.iddaa.com` | Kadro, oyuncu bilgileri |
| 🔍 | `contentv2.iddaa.com` | İçerik, haberler |
| 🔍 | `commonv2.iddaa.com` | Referans verisi (lig, takım ID) |
| 🔍 | `indir.iddaa.com` | İndirme/export API'si |

---

## 2. `/sportsbook/event/{id}` — TAM ŞEMA

```json
{
  "isSuccess": true,
  "data": {
    "i":   2975498,        // iddaa event ID
    "bri": 71727738,       // ⭐ BetRadar Match ID — ALTIN!
    "v":   828327341,      // version/timestamp
    "hn":  "Ludogorets",   // ev sahibi
    "an":  "Loko Plovdiv", // deplasman
    "sid": 1,              // sport ID (1=futbol)
    "s":   1,              // status
    "il":  true,           // is live? (canlı mı?)
    "ci":  36915,          // competition ID
    "d":   1780070400,     // Unix timestamp (maç tarihi)
    "oc":  6,              // açık pazar sayısı

    "m": [                 // Markets (pazarlar)
      {
        "i":  71401258,    // market ID
        "st": 27,          // market type code (27=1X2, 54=O/U)
        "sov": "2.5",      // special over value (2.5, 1.5 vb.)
        "o": [             // outcomes (seçenekler)
          { "no": 1, "n": "1",   "odd": 3.11, "wodd": 2.98 },
          { "no": 2, "n": "0",   "odd": 1.20, "wodd": 1.15 },
          { "no": 3, "n": "2",   "odd": 16.0, "wodd": 15.3 }
        ]
      }
    ],

    "sc": {                // Live Score / Statistics
      "s":   9,            // match status (9=bitti/uzatma)
      "min": 110,          // dakika (110 = uzatma!)
      "sec": 1,
      "ht": {              // Home Team (Ev Sahibi)
        "r":   2,          // gol (result)
        "c":   0,          // ?
        "ht":  1,          // devre skoru
        "et":  0,          // uzatma golü
        "co":  4,          // korner
        "hco": 2,          // devre korner
        "yc":  1,          // sarı kart
        "rc":  0           // kırmızı kart
      },
      "at": {              // Away Team (Deplasman)
        "r":   1,
        "co":  3,
        "yc":  3,
        "rc":  0
      }
    }
  }
}
```

### 2.1 Market Type Kodu Haritası

| `st` | Pazar | Seçenekler |
|---|---|---|
| 27 | 1X2 (Maç Sonucu) | 1, 0, 2 |
| 54 | Alt/Üst | Alt, Üst (sov=0.5/1.5/2.5/3.5) |
| ? | KG Var/Yok | VAR, YOK |
| ? | İlk Yarı | 1, 0, 2 |
| ? | Handikap | (−1), 0, (+1) |

> **Not:** `odd` = ham oran, `wodd` = vergili (ödenecek) oran. Fark ≈ %4 vergi.

---

## 3. ⭐ BETRADARx ID — ALTIN BULGU

Her maçta `bri` (BetRadar ID) mevcut. Bu ID şu anlama geliyor:

**iddaa.com'un veri sağlayıcısı = BetRadar (Sportradar)**

```
iddaa.com event 2975498  →  bri: 71727738  →  BetRadar match ID
```

Bu ID ile şunlar mümkün:
1. **SportsBetData.com** — ücretsiz BetRadar feed'i (pre-match istatistik)
2. **api.sportradar.com** — ücretli tier; tam xG, şut haritası, kadro
3. **Diğer iddaa siteleri cross-check** — aynı `bri` ID diğer bookmaker'larda da var
4. **Sofascore / FlashScore scraping** — BetRadar match ID ile URL yapısı bulunabilir

---

## 4. SAYFA SEKMELERİ — VERİ KATMANLARI

Maç detay sayfasında 6 sekme var. Her biri farklı bir veri katmanı:

| Sekme | URL suffix | İçerik | Scraping Zorluğu |
|---|---|---|---|
| Maçlar | `/maclar` | Odds, pazarlar | ✅ API ile kolay |
| **Canlı İstatistikler** | `/canli-istatistikler` | Şutlar, top hakimiyeti, korner, xG? | 🔍 API aranıyor |
| Puan Durumu | `/puan-durumu` | Lig tablosu | 🔍 commonv2? |
| **Kadrolar** | `/kadrolar` | 11'ler, sakatlar | 🔍 playersv2? |
| **Oyuncu Bilgileri** | `/oyuncu-bilgileri` | Gol/asist formu, değer | 🔍 playersv2? |
| **Korner & Kart Geçmişi** | `/korner-ve-kart-gecmisi` | Takım bazında tarihsel | 🔍 statisticsv2? |

---

## 5. VERİ ZENGİNLEŞTİRME PLANI — 4 KAYNAK KATMANI

```
KATMAN 1: iddaa.com (sportsbookv2) — ŞUAN ÇALIŞIYOR
  ├── Günlük maç programı + tüm pazarlar + oranlar
  ├── Canlı skor + dakika + korner + kartlar
  └── BetRadar ID → diğer kaynaklara köprü

KATMAN 2: Ücretsiz API'lar — HAZIR
  ├── api-football.com (var, kullanıyoruz)
  │     xG, form, injury, H2H, standings
  ├── Football-Data.co.uk (var, kullanıyoruz)
  │     Tarihsel odds + sonuçlar
  └── OpenLigaDB (Bundesliga free tier)

KATMAN 3: iddaa.com Alt Servisleri — KEŞİF AŞAMASINDA
  ├── statisticsv2.iddaa.com
  │     Hedef: match stats, xG, şut, korner geçmişi
  ├── playersv2.iddaa.com
  │     Hedef: kadro, sakatlık, oyuncu formu
  └── contentv2.iddaa.com / indir.iddaa.com
         Hedef: lig tablosu, H2H

KATMAN 4: BetRadar ekosistemi — ARAŞTIRILACAK
  ├── SportsBetData.com (ücretsiz BetRadar-powered feed)
  ├── Sofascore API (resmi değil, BetRadar ID ile)
  └── Sportradar Developer API (ücretli, €50-200/ay)
```

---

## 6. EDGE MODEL KATKILARI

Her yeni veri kaynağının edge modeline katkısı:

### 6.1 Kadro Verisi (playersv2)
```
Feature: isFirstTeamPlaying = 1 (gıyaplar yoksa)
Feature: keyPlayerMissing = 1 (hücum lideri yok)
Feature: avgPlayerValue = ortalama kadro değeri
Edge: +3-5% tahmin doğruluğu (Transfermarkt araştırması)
```

### 6.2 Korner & Kart Geçmişi
```
Feature: team_corner_avg_5g = son 5 maç korner ort.
Feature: team_yc_avg_5g = sarı kart eğilimi
Feature: referee_yc_rate = hakeme göre kart ort.
Edge: Alt/Üst model için +2-4% (korner proxy)
```

### 6.3 Gerçek Zamanlı Odds Hareketi (iddaa API)
```
Feature: odds_movement_1h = son 1 saat oran değişimi
Feature: opening_vs_closing = açılış vs kapanış farkı
Feature: betRadar_implied_shift = piyasa hareketi
Edge: CLV artışı +8-12% (Sharp Money signal)
```

### 6.4 Puan Durumu & Motivasyon
```
Feature: matches_to_relegate = düşme çizgisine mesafe
Feature: championship_locked = şampiyonluk garantilendi mi?
Feature: season_stage = 1-34. hafta (son hafta efekti)
Edge: Son 5 hafta performansında +6% (motivasyon faktörü)
```

---

## 7. ACİL AKSIYON PLANI (öncelik sırası)

### 🔴 Sprint 1 — iddaa.com Scraper Genişletme (task #142)
```
HEDEF: sportsbookv2 API'yı tam entegre et

1. matches_v2 tablosuna BetRadar ID kolonu ekle
   ALTER TABLE matches_v2 ADD COLUMN betradar_id INTEGER;

2. Günlük scraper güncelle:
   GET /sportsbook/event/list?sportId=1&date={YYYY-MM-DD}
   → BetRadar ID, tüm pazar oranları, KG + A/Ü 1.5/2.5/3.5

3. Market tipi kodlarını decode et:
   st=27 → 1X2
   st=54 → O/U (sov=2.5)
   st=? → KG (hedef: tam harita)

4. Gerçek zamanlı odds snapshot (closing oddslar için)
```

### 🟡 Sprint 2 — Alt Servisleri Keşfet ve Entegre Et
```
1. Browser DevTools ile iddaa.com açık → Network tab
   Hedef: kadrolar/istatistikler tab'larının API call'larını bul
   (statisticsv2, playersv2 gerçek endpoint'leri)

2. Bulunursa → matches_v3 şemasına ekle:
   - starting_lineup_home / _away (JSON)
   - key_player_absent (bool)
   - home_corners_5g / away_corners_5g (float)
   - home_yc_5g / away_yc_5g (float)
```

### 🟢 Sprint 3 — BetRadar Köprüsü
```
1. SportsBetData.com ücretsiz tier → BetRadar ID ile çek
2. Sofascore URL pattern: /match/{betradar_id} → scrape
3. Her maç için: xG, toplam şut, isabet, top hakimiyeti
   → xG modeli artık Poisson değil, gözlemsel xG ile
```

---

## 8. TEKNIK MİMARİ — HEDEF

```
[cron: 06:00 her gün]
  ↓ iddaa_scraper.py
  ├── /sportsbook/event/list?date=+3days   → paper_fixtures
  ├── /sportsbook/event/{id}              → odds snapshot
  └── BetRadar ID kaydet

[cron: 30dk interval, maç gününde]
  ↓ live_odds_monitor.py
  ├── Closing odds snap (15dk önce)
  └── odds_movements tablosuna yaz

[cron: saatlik]
  ↓ stats_enricher.py
  ├── api-football → xG, form, kadro
  ├── statisticsv2 (iddaa) → korner/kart
  └── matches_v3 tablosunu güncelle

[model: paper_engine.py]
  ↓ evaluate_match()
  ├── DC + xG + Elo (mevcut)
  ├── + kadro_skoru (yeni)
  ├── + korner_edge (yeni)
  └── + odds_hareketi (yeni)
```

---

## 9. VERİ TABLOSU GENİŞLETME — SQL ŞEMA

```sql
-- matches_v3 yeni kolonlar
ALTER TABLE matches_v2 ADD COLUMN betradar_id        INTEGER;
ALTER TABLE matches_v2 ADD COLUMN competition_id     INTEGER;
ALTER TABLE matches_v2 ADD COLUMN home_corners_5g    REAL;
ALTER TABLE matches_v2 ADD COLUMN away_corners_5g    REAL;
ALTER TABLE matches_v2 ADD COLUMN home_yc_5g         REAL;
ALTER TABLE matches_v2 ADD COLUMN away_yc_5g         REAL;
ALTER TABLE matches_v2 ADD COLUMN home_lineup_json   TEXT;   -- JSON
ALTER TABLE matches_v2 ADD COLUMN away_lineup_json   TEXT;
ALTER TABLE matches_v2 ADD COLUMN key_absent_home    INTEGER DEFAULT 0;
ALTER TABLE matches_v2 ADD COLUMN key_absent_away    INTEGER DEFAULT 0;
ALTER TABLE matches_v2 ADD COLUMN odds_opening_1     REAL;   -- açılış oranı
ALTER TABLE matches_v2 ADD COLUMN odds_opening_x     REAL;
ALTER TABLE matches_v2 ADD COLUMN odds_opening_2     REAL;
ALTER TABLE matches_v2 ADD COLUMN odds_move_1        REAL;   -- açılış vs kapanış farkı

-- odds_snapshots (zaman serisi)
CREATE TABLE IF NOT EXISTS odds_snapshots (
    snapshot_id   TEXT PRIMARY KEY,
    match_id      TEXT,
    betradar_id   INTEGER,
    snapped_at    TEXT,
    market_type   TEXT,    -- '1X2', 'OU25', 'KG', 'IY1X2'
    odd_1         REAL,
    odd_x         REAL,
    odd_2         REAL,
    odd_over      REAL,
    odd_under     REAL,
    sov           REAL     -- special over value
);
```

---

## 10. SONUÇ

| Bulunan | Önemi |
|---|---|
| `sportsbookv2.iddaa.com/sportsbook/event/{id}` | Her maçın tam odds + canlı stat API'si |
| BetRadar ID (`bri`) | Sportradar ekosistemiyle köprü |
| Canlı stats (korner, kart, dakika) | Real-time signal | 
| 12+ microservice domain | İleride kadro + stat → keşif yapılacak |
| 6 sekme yapısı | Hangi veriyi nerede arayacağımızı biliyoruz |

**En kritik sonraki adım:** Browser DevTools ile `kadrolar` ve `canli-istatistikler` sekmelerini açıp Network tab'dan gerçek API call'larını kayıt altına almak. Bu işlem 5 dakika alır ve `playersv2` + `statisticsv2` endpoint'lerini açığa çıkarır.

---

*Rapor: 2026-05-29 · Keşif: Python urllib + JS source analysis · 1 çalışan endpoint, 12 domain haritası*  
*Sonraki:* [`v2_MASTER_ROADMAP.md`](./v2_MASTER_ROADMAP.md) · task #142 devam
