# 02_VERI — Veri Kaynakları ve Toplama

Bu klasör, BAHIS AGENT'ın beslendiği tüm veri kaynaklarının scraper'larını, API entegrasyonlarını ve ham/işlenmiş veri depolamasını içerir.

## Veri Kaynakları

| Kaynak | İçerik | Erişim Yöntemi | Öncelik |
|---|---|---|---|
| **iddaa.com** | Anlık ve açılış oranları, MBS, oyun programı | Web scrape (Selenium/Playwright) | ⭐⭐⭐⭐⭐ |
| **Football-Data.co.uk** | 15+ sezon tarihsel sonuç + oranlar (CSV) | Direkt indirme | ⭐⭐⭐⭐⭐ |
| **Understat** | xG, xA, shot data (Top 5 Avrupa ligi) | Scrape (basit) | ⭐⭐⭐⭐⭐ |
| **FBRef** | Detaylı maç ve oyuncu istatistikleri | Scrape | ⭐⭐⭐⭐ |
| **SofaScore** | Lineup, sakatlık, hakem ataması, canlı veri | API + scrape | ⭐⭐⭐⭐ |
| **OddsPortal** | Çoklu site oran karşılaştırma + closing line | Scrape | ⭐⭐⭐⭐⭐ |
| **Pinnacle** | Sharp piyasa referansı | API (kısıtlı) | ⭐⭐⭐⭐⭐ |
| **OpenMeteo** | Hava durumu (rüzgar, yağış, sıcaklık) | Free API | ⭐⭐⭐ |
| **FotMob** | Oyuncu rating, predicted lineup | Scrape | ⭐⭐⭐ |
| **Transfermarkt** | Sakatlık, ceza, transfer | Scrape | ⭐⭐ |

## Klasör Yapısı (Planlanan)

```
02_VERI/
├── scrapers/
│   ├── iddaa_scraper.py
│   ├── understat_scraper.py
│   ├── fbref_scraper.py
│   ├── sofascore_scraper.py
│   ├── oddsportal_scraper.py
│   └── football_data_downloader.py
├── api_clients/
│   ├── pinnacle_client.py
│   └── openmeteo_client.py
├── raw/                          (ham veri — git ignore)
│   ├── iddaa/
│   ├── understat/
│   └── ...
├── processed/                    (temizlenmiş, normalize)
│   ├── matches.parquet
│   ├── odds_history.parquet
│   └── team_stats.parquet
└── schemas/
    ├── match_schema.py
    └── odds_schema.py
```

## Veri Şeması — Temel `match` tablosu

```python
{
    "match_id": str,           # unique ID (kaynak_yıl_homeID_awayID)
    "kickoff_utc": datetime,
    "league": str,             # "TR1", "ENG1", vb.
    "home_team": str,
    "away_team": str,
    "home_score": int | None,  # bahis öncesi None
    "away_score": int | None,
    "home_xg": float | None,
    "away_xg": float | None,
    "venue": str,
    "referee": str | None,
    "weather": dict | None,
    "odds": {
        "iddaa": {"1": float, "X": float, "2": float, ...},
        "pinnacle_open": {...},
        "pinnacle_close": {...}
    }
}
```

## Önemli Notlar

1. **iddaa scraping etik/yasal:** ToS dikkatli oku. Anormal sıklıkta sorgu → IP ban. Rate limit kullan (saniyede 1 istek max).
2. **Veri kalitesi >> veri miktarı.** Bozuk veri ile eğitilen model zararlıdır.
3. **Closing odds toplama otomatik olmalı** — CLV hesabı için kritik. Maç başından 10 dk önce snapshot al.
4. **Timezone:** Her şey UTC'de saklan, UI'da TR saatine çevir.
