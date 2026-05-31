# 🔌 API KAYIT DEFTERİ (Registry)
## Tüm Veri Kaynakları + Endpoint'ler + Şemalar

**Tarih:** 2026-05-31  
**Amaç:** Sağlam mimari için merkezî API referansı. Her kaynak versiyonlu adapter ile soyutlanır.

---

## 1. iddaa.com — CANLI VERİ (birincil kaynak)

### 1.1 sportsbookv2.iddaa.com (Odds + Program)
| Endpoint | Açıklama | Kullanım |
|---|---|---|
| `GET /sportsbook/event/{eventId}` | Tek maç: oranlar + canlı skor + BetRadar ID | `fetch_iddaa_live`, `fetch_results` |
| `GET /sportsbook/event/list?sportId=1&date=YYYY-MM-DD` | Günlük program | scraper |
| `GET /sportsbook/events?sportId=1` | Sayfalı event listesi | scraper |
| `GET /sportsbook/get_market_config` | 804 pazar tipi tanımı | market decode |
| `GET /sportsbook/competitions` | Tüm ligler | lig eşleme |

**Önemli alanlar:** `bri`=BetRadar ID, `m`=marketler (st=27→1X2, st=54→A/Ü), `sc`=canlı skor

### 1.2 statisticsv2.iddaa.com (İstatistik — 6 sekme)
| Endpoint | Sekme | Kritik Veri |
|---|---|---|
| `GET /statistics/soccer/match-card/{id}?isLive=true` | Canlı İstatistik | skor(`sc`), şut, korner, kart, durum(`st`) |
| `GET /statistics/soccer/recent-matches/{id}?matchHistoryType=2` | H2H | son N maç IY+FT skoru |
| `GET /statistics/soccer/lineup/{id}` | Kadrolar | 11'ler, pozisyon, forma no, antrenör |
| `GET /statistics/soccer/player-details/{id}` | Oyuncu Bilgileri | sezon gol(`g`) + asist(`a`) |
| `GET /statistics/soccer/card-corners/{id}` | Korner & Kart | son 6 maç korner/sarı/kırmızı + ortalama |
| `GET /statistics/soccer/standings/{id}?standingType=0` | Puan Durumu | tam tablo + kader(Şampiyonlar/Düşme) |

**Maç durum kodları (`st`):** 6/9/12/13 = bitti · diğer = devam/başlamadı

### 1.3 Header gereksinimleri
```
User-Agent: Mozilla/5.0 (...)
Accept: application/json
Referer: https://www.iddaa.com/
Origin: https://www.iddaa.com
```

### ⚠️ Bilinen kısıt
iddaa, biten maçı **birkaç saat sonra API'den siler** (özellikle yaz ligleri).
→ Çözüm: `fetch_results` void-fallback (14sa+ veri yoksa VOID/iade).

---

## 2. Football-Data.co.uk — TARİHSEL (ücretsiz)
| Veri | Kapsam |
|---|---|
| Sonuçlar + 1X2/A/Ü odds | 6 lig × 9 sezon (19.166 maç) |
| Korner, sarı/kırmızı kart, faul | 19.166 maç |
| CSV indirme | sezon başına |

**Kullanım:** `matches_v2_ingest_fd.py` · tarihsel backtest temeli

---

## 3. Understat — xG (ücretsiz scrape)
| Veri | Kapsam |
|---|---|
| Expected Goals (xG) | 5.752 maç (2021-22 sonrası, 5 Avrupa ligi) |

**Kullanım:** `xg_ingest.py` · model xG onayı

---

## 4. Sofascore — xG + maç istatistiği (ENTEGRE ✅)
**Adapter:** `02_VERI/data_sources/sofascore.py` · **Analiz:** `RAPOR/v3_SOFASCORE_API_ANALIZI.md`
**Erişim:** Cloudflare korumalı (düz HTTP 403) → **headless Playwright + sayfa-içi `fetch()`** (gerçek tarayıcı bağlamı 200). Yalnız yerel/araştırma; canlı app import etmez.

| Endpoint | Veri |
|---|---|
| `GET /api/v1/sport/football/scheduled-events/{YYYY-MM-DD}` | Günün tüm maçları (eşleme) |
| `GET /api/v1/event/{id}/statistics` | **xG** + şut/big-chance/possession/korner/pas (~40 metrik) |
| `GET /api/v1/event/{id}/lineups` | 11'ler + oyuncu rating (üst liglerde) |
| `GET /api/v1/event/{id}/votes` | Kitle 1X2 tahmini |
| `GET /api/v1/event/{id}/incidents` · `pregame-form` · `managers` | Olaylar / form / TD |

**Kapsam (ampirik):** xG üst+orta liglerin neredeyse hepsinde (Brezilya/Çin/Mısır/İrlanda/İskandinavya…). **T1 (Türkiye): 2023+ xG var (%100 eşleşme).** En dip egzotik (Belarus 2.düzey) sığ → "xG yoksa PAS".
**Tablo:** `sofascore_stats` (match_id FK) — matches_v2 şişmez.

## 4b. BetRadar Ekosistemi (köprü — gelecek)
iddaa'nın `bri` (BetRadar ID) alanı ile bağlanılabilecek diğer kaynaklar:
| Kaynak | Veri | Durum |
|---|---|---|
| **Mackolik arşivi** (arsiv.mackolik.com) | TR tarihsel derinlik (kadro/gol-dk/kart/H2H) | 🔜 değerlendirilecek (#149) |
| Sportradar API | Tam kadro, sakatlık, hakem | 🔜 ücretli (lisanslı) |

---

## 5. Hesaplanmış Veri (dış API yok — DB içi)
| Özellik | Kaynak | Script |
|---|---|---|
| H2H (son 10) | matches_v2 geçmiş | `historical_enricher.py` |
| Puan tablosu pozisyonu | sezon içi sonuçlar | `historical_enricher.py` |
| Form 5G (WWDLL) | son 5 maç | `historical_enricher.py` |
| Korner/kart ortalaması | Football-Data kolonları | `historical_enricher.py` |

---

## 6. ADAPTER MİMARİSİ (hedef)

Her kaynak versiyonlu adapter arkasında soyutlanır:
```
data_sources/
  ├── iddaa_sportsbook.py    (v1)  — odds + program
  ├── iddaa_statistics.py    (v1)  — 6 sekme
  ├── football_data.py       (v1)  — tarihsel
  ├── understat.py           (v1)  — xG
  └── betradar_bridge.py     (v0)  — gelecek
```
API değişirse: sadece ilgili adapter güncellenir, sistem etkilenmez.

---

## 7. ENV / SIRLAR
```
DATABASE_URL=postgresql://...        (Railway Postgres)
IDDAA_BASE_SPORTSBOOK=https://sportsbookv2.iddaa.com
IDDAA_BASE_STATISTICS=https://statisticsv2.iddaa.com
```
**Hassas anahtarlar `.env`'de, repo'ya GİRMEZ (.gitignore).**

---

*Registry: 2026-05-31 · 6 iddaa endpoint + 3 tarihsel kaynak + BetRadar köprüsü*
