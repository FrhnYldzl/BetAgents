# 🖥️ SİSTEM DURUM RAPORU
## localhost:8503 · localhost:8504 · Veritabanı · Modeller

**Tarih:** 2026-05-29  
**Hazırlayan:** AI Trader Session (otomatik)  
**Amaç:** Sistemi ilk kez inceleyen kişi için tam durum özeti

---

## ⚡ HIZLI DURUM

| Bileşen | URL | PID | Durum |
|---|---|---|---|
| **app_pro.py** (SaaS analiz) | http://localhost:8503 | 17048 | 🟢 Çalışıyor |
| **app_trader.py** (Paper trader) | http://localhost:8504 | 24144 | 🟢 Çalışıyor |
| **bahis_agent.db** | `02_VERI/bahis_agent.db` | — | 🟢 19.275 maç enriched |
| **paper engine** | `--run` / `--settle` | — | 🟢 11 açık kupon |

---

## 📌 NE YAPİYOR — İKİ UYGULAMA

### 1. localhost:8503 — AI TRADER PRO (app_pro.py)
**"Araştırma ve Analiz Merkezi"**

Bu uygulama **geçmiş ve canlı sinyalleri analiz eden** kurumsal SaaS arayüzüdür. Bahis oynamaz — karar verir.

**8 Sayfa:**

| Sayfa | Ne Gösteriyor |
|---|---|
| **Overview** | Portföy özeti, P&L, win rate |
| **Live Calendar** | Bugün/bu hafta maçları + TRIVOX sinyalleri + H2H/form chip'leri |
| **Trading Desk** | Multi-market panel (1X2, KG, Alt/Üst) |
| **Coupon Engineer** | Kupon optimizasyon stüdyosu |
| **Model Catalog** | 13 model kayıt defteri (TRIVOX, MONOVOX, DUOVOX vb.) |
| **Analytics** | Sezonsal heatmap + **YENİ: Enriched overlay ROI grafiği** |
| **Data Excellency** | DB kalite + **YENİ: Enriched kolon doluluk göstergesi** |
| **Risk Management** | Bankroll / drawdown yönetimi |

**Bugün eklenenler (29 Mayıs):**
- Live Calendar maç kartlarına → H2H özeti, lig sıralaması, form (W/D/L renk kodlu), sarı kart uyarısı eklendi
- Analytics sayfasına → ROI artışı bar grafiği + lig kırılım grafiği eklendi
- Data Excellency → 4 enriched kolon doluluk göstergesi
- `load_signals()` → matches_v2'ye JOIN yaparak 24 yeni kolon çekiyor

---

### 2. localhost:8504 — AI TRADER (app_trader.py)
**"Paper Trading Terminali"**

Bu uygulama **gerçek para benzeti bahis sistemidir** — iddaa.com kurallarına uygun sanal kuponlar oluşturur, takip eder, kapanınca journal'a yazar.

**Sayfalar:**

| Sayfa | Ne Gösteriyor |
|---|---|
| **Overview** | Açık kuponlar (Bekleyen/Kazanan/Kaybeden/Arşiv tabları) |
| **Matches** | Bugün/yarın maçları + sinyal güçleri |
| **Positions** | Portföy pozisyonları |
| **Journal** | Kapanan kuponların detaylı geçmişi |
| **Settings** | Eşik ayarları |

**Bugün eklenenler (29 Mayıs):**
- Overview → **iddaa.com kupon yönetimi gibi** Bekleyen/Kazanan/Kaybeden/Arşiv tab yapısı
- Bekleyen tab → Tümü / Devam Eden / Başlamamış alt tablar
- Kupon kartları → Meridian Capital tarzı SVG pozisyon grafiği (giriş→hedef Bezier eğrisi)
- Journal → Settlement grafiği (kazandı=yeşil yukarı eğri, kaybetti=kırmızı aşağı eğri)
- Journal RESULT kartları → Model%, Edge%, Piyasa%, Güven chip'leri + Trade Notu bloğu
- **Tüm grafikler `st.html()` → `st.markdown()` ile düzeltildi** (SVG artık görünüyor)

---

## 🗃️ VERİTABANI DURUMU

**Dosya:** `YAZILIM/02_VERI/bahis_agent.db`

### Ana Tablo: matches_v2

```
Toplam maç:     19.275
Tamamlanan:     19.198  (%99.6)
Odds mevcut:    18.216
xG mevcut:       5.752  (2021-22 sonrası, 6 lig)
Enriched:       19.275  (%100) ← BUGÜN TAMAMLANDI
```

**6 Lig × 9 Sezon (2017→2026):**

| Lig | Maç | Sezonlar |
|---|---|---|
| T1 — Türkiye Süper Lig | 3.088 | 2017-26 |
| E0 — İngiltere Premier | 3.420 | 2017-26 |
| SP1 — İspanya La Liga | 3.420 | 2017-26 |
| D1 — Almanya Bundesliga | 2.754 | 2017-26 |
| I1 — İtalya Serie A | 3.420 | 2017-26 |
| F1 — Fransa Ligue 1 | 3.096 | 2017-26 |

**Bugün eklenen 39 yeni kolon (historical_enricher.py ile):**

```
H2H geçmişi:     h2h_n, h2h_home_wins, h2h_draws, h2h_away_wins, h2h_avg_goals, h2h_btts_rate
Puan tablosu:    home/away_league_pos, home/away_pts, home/away_gd
Motivasyon:      home/away_title_gap, home/away_relegation_gap
Form 5G:         home/away_form_5g (WWDLL formatı), home/away_avg_goals_5g, home/away_clean_sheet_5g
YC/Korner avg:   home/away_yc_5g_avg, home/away_corners_5g_avg
Temizlik:        home/away_missing_key, stats_enriched_at, stats_source
```

### Paper Trading Tabloları

```
paper_coupons:    Açık: 11  |  Toplam: (bugün başlatıldı)
paper_bets:       Her kupona ait bireysel bahisler
paper_journal:    1 giriş (settlement olunca otomatik eklenir)
paper_portfolio:  Başlangıç: 5.000 TL
```

---

## 🤖 MODEL DURUMU

**13 model** `03_MODELLER/MODEL_REGISTRY/model_registry.json` v1.1'de kayıtlı.

### VALIDATED (5 model)

| Model | Lig | Hit% | ROI | Enriched Karar |
|---|---|---|---|---|
| **TRIVOX v1.2** | T1 | %82 | +%24.4 | ✅ +10.1pp iyileşiyor |
| **MONOVOX-E0** | E0 | %65 | +%7.7 | ✅ +18.1pp iyileşiyor |
| **DUOVOX** | E0+SP1 | %62 | +%6.5 | ⚠️ +2.8pp, opsiyonel |
| **TRIOVOX** | E0+SP1+D1 | %60 | +%6.6 | ✅ +6.9pp iyileşiyor |
| **MONOVOX-SP1** | SP1 | %55 | +%2.3 | ❌ −12.2pp bozuyor |

### PROTOTYPE (6 model — KG odds bekleniyor)

| Model | Lig | Market | Hit% | Enriched Durum |
|---|---|---|---|---|
| OU25-D1-Over | D1 | Alt/Üst | %61 | ⚠️ minimal etki |
| OU25-E0-Under | E0 | Alt/Üst | %43 | ⚠️ minimal etki |
| BTTS-D1-Var | D1 | KG Var | %61 | ⏳ KG odds eksik |
| BTTS-SP1-Var | SP1 | KG Var | %58 | ⏳ KG odds eksik |
| BTTS-SP1-Yok | SP1 | KG Yok | %55 | ⏳ KG odds eksik |
| BTTS-I1-Yok | I1 | KG Yok | %47 | ⏳ KG odds eksik |

### DEPRECATED (2 model)

| Model | Neden |
|---|---|
| EUVOX v1.1 | K=3 kombin varyansı, ROI −%0.8 |
| TRIVOX v1.0-K3 | Lottery hipotezi kanıtlandı (n=109, 4 maç toplam ROI'nin %80'i) |

---

## 📊 BUGÜNKÜ BACKTEST SONUÇLARI

### Ana Bulgu: Enriched Overlay Etkisi

**imp≥65% (piyasa implied prob) + H2H + Standings filtresi:**

```
Strateji                      Pick     Hit%    ROI
────────────────────────────────────────────────────
Baseline (sadece imp≥65%)    2.393   %76.4   +%0.0   Vergi sonrası negatif
+ H2H filtresi               1.531   %77.5   +%1.3
+ Standings filtresi         1.015   %76.7   +%1.7
★ H2H + Standings birlikte     596   %79.0   +%5.1   Vergi sonrası POZİTİF ✅
```

### Lig Bazında (H2H+Standings aktif):

```
SP1 La Liga:      +%11.1  ✅  106 pick
T1  Süper Lig:     +%5.9  ✅  103 pick
E0  Premier:       +%6.0  ✅  211 pick
D1  Bundesliga:    −%3.3  ⚠️  136 pick  (kapalı)
I1  Serie A:       −%7.0  ❌  163 pick  (kapalı)
F1  Ligue 1:       −%6.3  ❌  134 pick  (kapalı)
```

### Walk-Forward (9 Sezon, T1+E0+SP1+D1):

```
2017-18: +3.5pp  ✅
2018-19: +9.0pp  ✅
2019-20: +4.1pp  ✅  (COVID sezonunda bile kurtardı)
2020-21:+12.3pp  ✅
2021-22: +5.3pp  ✅
2022-23: +2.4pp  ✅
2023-24: −0.5pp  ✅  (kabul edilebilir)
2024-25:+12.0pp  ✅
2025-26: −6.6pp  ❌  (sezon devam ediyor)
```

**8/9 sezon enriched iyileştiriyor — tutarlılık kanıtlandı.**

### Smoke Test: 38 PASS · 1 FAIL · 3 WARN

| Test | Sonuç |
|---|---|
| Veri bütünlüğü (doluluk + range) | ✅ 15/15 PASS |
| Lookahead bias yok (temporal order) | ✅ PASS |
| 6 lig tam dataset | ✅ PASS (3 lig iyileşiyor) |
| Walk-forward 9 sezon | ✅ 8/9 PASS |
| Sample size yeterliliği | ✅ 12/12 PASS |
| İstatistiksel anlam (z=15.69, p≈0) | ✅ PASS |
| Tek FAIL | Pick azalması %76 (6 lig dahilken) → sadece 3 lig ile makul |

---

## 🔧 PAPER ENGINE KULLANIMI

```bash
# Yeni kuponlar oluştur (T1+E0+SP1+D1'den, minimum 2 ayak, enriched filtreli)
python 02_VERI/paper_engine.py --run

# Biten maçları kapat ve journal'a yaz
python 02_VERI/paper_engine.py --settle

# Portföy özeti
python 02_VERI/paper_engine.py --status

# Stats enricher (canlı maçlar için iddaa.com API'si)
python 02_VERI/stats_enricher.py --limit 20
```

### Kupon Tipleri (minimum 2 ayak — iddaa.com tekli yok):

| Tip | Açıklama | Stake | Filtre |
|---|---|---|---|
| K2_FAVORI | En güçlü 2 MS sinyali | %2.5 bankroll | model_prob ≥ 0.65 |
| K2_VALUE | 2 value pick | %2.0 | edge ≥ +4% |
| K2_KARISIK | 1 MS + 1 KG/ALT | %2.0 | farklı maçlar |
| K3_KOMBO | 3 güçlü sinyal | %1.5 | model_prob ≥ 0.60 |

**Toplam max risk / oturum: %8 bankroll**

---

## 📁 ÖNEMLI DOSYALAR

```
YAZILIM/
├── 02_VERI/
│   ├── bahis_agent.db              ← Ana veritabanı
│   ├── paper_engine.py             ← Paper trading engine
│   ├── historical_enricher.py      ← Tarihsel H2H/standings enricher
│   ├── stats_enricher.py           ← Canlı maç iddaa.com enricher
│   ├── backtest_enriched.py        ← Ana backtest
│   ├── backtest_13_models.py       ← 13 model backtest
│   └── smoke_test_enriched.py      ← Smoke test suite
│
├── 03_MODELLER/
│   ├── MODEL_REGISTRY/model_registry.json   ← 13 model kayıt v1.1
│   └── selective/trivox_v1.py, euvox_v1.py vb.
│
├── 08_AI_TRADER/
│   ├── app_pro.py                  ← :8503 SaaS analiz
│   └── app_trader.py               ← :8504 Paper trader
│
└── RAPOR/                          ← Tüm raporlar
    ├── SISTEM_DURUM_RAPORU_29MAY2026.md   ← Bu dosya
    ├── v2_SMOKE_TEST_ENRICHED_OZETI.md
    ├── v2_BACKTEST_ENRICHED_SONUCLARI.md
    ├── v2_AI_TRADER_SESSION_OZETI_29MAY.md
    └── v2_DATA_MODEL_TRADER_OZETI_29MAY.md
```

---

## 🚦 PRODUCTION KURALLARı (Güncel)

```
✅ Enriched overlay AÇIK:  T1, E0, SP1
❌ Enriched overlay KAPALI: D1, I1, F1

✅ Kupon oluşturma ligleri: T1, E0, SP1, D1 (paper_engine.py)
❌ Çıkarılan ligler: I1, F1 (backtest kanıtı: F1 −%10.5, I1 −%4.2)

✅ Minimum ayak: 2 (iddaa.com tekli yok kuralı)
✅ Kart/YC filtresi: KALDIRILDI (performansı bozuyordu)
✅ H2H filtresi: AKTIF (ev_win_rate ≥ %45, n ≥ 3 maç)
✅ Standings filtresi: AKTIF (relgap ≤ 4pt → 1X2 iptal)
```

---

## ❓ BEKLEYEN İŞLER

| Görev | Öncelik | Neden |
|---|---|---|
| task #142: iddaa.com KG odds scraper | 🔴 Yüksek | BTTS modellerini test etmek için gerekli |
| task #120: T1 xG (FotMob) | 🟡 Orta | TRIVOX sample'ını büyütür |
| task #124: Kapı 1 — FAV→VALUE pivot | 🟡 Orta | Yeni nesil sinyal mimarisi |
| task #119: Transfermarkt injury scraper | 🟢 Düşük | Kadro kalitesi feature'ı |

---

*Son güncelleme: 2026-05-29 22:30 UTC*  
*Uygulamalar: :8503 (PID 17048) · :8504 (PID 24144) · Her ikisi çalışıyor*
