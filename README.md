# 🎯 BetAgents — Kantitatif Spor Bahsi Karar-Destek Sistemi

iddaa.com (Spor Toto, lisanslı Türkiye platformu) üzerinde **kantitatif (Renaissance/Jim Simons tarzı) yaklaşımla** uzun vadede pozitif beklenen değer (**EV+**) arayan bir **karar-destek + kâğıt-ticaret (paper-trading)** sistemi.

> "Her bahis matematiksel bir karardır. Model olasılık tahmin eder, iddaa fiyat verir, fark **edge**'dir. Edge varsa Kelly kadar gir, yoksa geç. Disiplin > Tahmin."

⚠️ Bu bir **karar-destek aracıdır**, otomatik kumar botu değildir. Gerçek para ile bahis koymaz — paper-trading ile strateji doğrular.

---

## 🚀 Hızlı Başlangıç

```bash
# 1) Bağımlılıklar
pip install -r requirements.txt

# 2) TEK birleşik uygulamayı çalıştır (8503 + 8504 → tek app)
python -m streamlit run 08_AI_TRADER/app_unified.py --server.port 8500
```

Tarayıcı: `http://localhost:8500`

> Not: Veritabanı (`*.db`), API cache'leri, backup/export/snapshot ve `.env` repo'ya **dahil değildir** (bkz. `.gitignore`). Veri katmanını yeniden üretmek için `02_VERI/` altındaki ingest/enricher script'leri kullanılır.

---

## 🏗️ Mimari — DATA · MODEL · TRADE

Sistem üç eksende versiyonlanır:

| Eksen | Ne yapar | Ana modüller |
|---|---|---|
| **DATA** | Veri toplama + zenginleştirme | `02_VERI/` — football-data ingest, Understat xG, iddaa API'leri, H2H/standings/form enricher |
| **MODEL** | Olasılık tahmini + edge | `03_MODELLER/` — Dixon-Coles, xG, Elo, LightGBM ensemble; Model Registry/Catalog |
| **TRADE** | Sinyal → kupon → settle → journal | `02_VERI/paper_engine.py`, `08_AI_TRADER/` — paper trading, risk, hedefli para yönetimi |

### Birleşik Uygulama (`08_AI_TRADER/app_unified.py`)
Tek giriş, tek sol-menü, mod-toggle YOK. İki grup:
- **💸 CANLI TRADER** — Genel Bakış · Maçlar & Sinyaller · Pozisyonlar · Emirler · Journal · Grafikler · Risk · Ayarlar
- **📊 ANALİZ** — Canlı Takvim · Trading Desk · Kupon Mühendisi · Model Kataloğu · Analitik · Veri Kalitesi · Playbook

---

## 📊 Veri Seti

- **19.275 maç** · 6 lig (T1, E0, SP1, D1, I1, F1) · 9 sezon (2017–2026)
- 18.216 maç oranlı · 5.752 maç xG'li
- Tüm maçlar H2H / puan durumu / form-5G / korner-kart ile zenginleştirildi (`historical_enricher.py`, sızıntısız temporal sıralama)

### Veri Kaynakları (bkz. `RAPOR/v3_API_REGISTRY.md`)
- **iddaa.com** — `sportsbookv2` (oran+program) + `statisticsv2` (6 sekme: match-card, H2H, lineup, player, card-corners, standings)
- **Football-Data.co.uk** — tarihsel sonuç + oranlar
- **Understat** — xG
- **BetRadar köprüsü** (`bri` ID) — gelecek genişleme

---

## 🤖 Otomasyon

| İş | Sıklık | Script |
|---|---|---|
| Canlı program çek + kupon kur + yerleştir | 09:00 & 18:00 | `02_VERI/auto_play.py` |
| Sonuç çek + kupon settle | her 90 dk | `02_VERI/auto_settle.py` |

(Windows Task Scheduler XML ile kayıtlı. Hedef: Railway 7/24 bulut.)

---

## 🎲 Kupon Motoru (iddaa kurallarına uygun)

iddaa.com tek-maç (TEK MAÇ) bahsine her maçta izin vermez → motor **minimum 2 bacak** üretir:
`K2_FAVORI` · `K2_VALUE` · `K2_KARISIK` · `K3_KOMBO`.
Aynı maç birden fazla açık kuponda kullanılmaz (cross-run + within-run dedup). VOID/push muhasebesi (iade, PnL=0) tam desteklenir.

## 💰 Para Yönetimi (hedefli dönem)
`manage_period()` — dönem başı bankroll, aylık %hedef, kilitlenen kâr, stop-loss; hedef/stop/30-gün ile yeni dönem.

---

## 📁 Klasör Yapısı

| Klasör | İçerik |
|---|---|
| `00_BAHIS_AGENT_MIMARI.md` | Ana mimari dokümanı |
| `01_LITERATUR/` | Akademik referanslar |
| `02_VERI/` | Veri ingest, enricher, paper engine, otomasyon |
| `03_MODELLER/` | Modeller + Model Registry/Catalog |
| `04_BACKTEST/` | Walk-forward backtest + sonuçlar |
| `05_RISK_YONETIMI/` | Kelly, bankroll, limitler |
| `06_PRODUCTION/` | Canlı pipeline |
| `07_LOG_VE_RAPORLAR/` | Backtest çıktıları, pick log'ları |
| `08_AI_TRADER/` | Birleşik Streamlit uygulaması |
| `RAPOR/` | Yönetici özetleri, API registry, mimari roadmap |

---

## 🗺️ Yol Haritası (v3)

- [x] 8503 + 8504 → tek `app_unified.py`
- [x] Enriched overlay (H2H + standings) → +%5.1 ROI (T1+E0+SP1)
- [x] GitHub'a taşıma
- [ ] SQLite → PostgreSQL
- [ ] Railway 7/24 deployment
- [ ] Versiyonlu adapter mimarisi (`data_sources/`)

Detay: `RAPOR/v3_MIMARI_VE_PRODUCTION_ROADMAP.md`

---

## ⚖️ Etik & Yasal

- ✅ iddaa.com Türkiye'de yasal/lisanslı (Spor Toto Teşkilatı)
- ✅ Yalnız açık veri + istatistiksel modelleme
- ❌ Maç sabitleme / içeriden bilgi / manipülasyon **ASLA**
- ❌ Gerçek-para otomatik bahis botu **YOK** — paper-trading + insan onayı
- ⚠️ Kumar bağımlılığı gerçek bir risktir; bu sistem **karar-destek** amaçlıdır

---

*Claude ile birlikte geliştirildi. Sırlar `.env`'de, repo'ya girmez.*
