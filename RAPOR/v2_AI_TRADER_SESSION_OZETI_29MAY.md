# 🤖 AI TRADER — SESSION ÖZETİ v1.0
## Bilimsel · Uygulama · Test Raporu

**Tarih:** 2026-05-29  
**Session:** AI Trader Paper Trading Terminal — görsel + kural düzeltmeleri  
**Önceki Rapor:** [`v2_SPRINT_OZETI_28_MAY.md`](./v2_SPRINT_OZETI_28_MAY.md)  
**Uygulama:** [`app_trader.py`](../08_AI_TRADER/app_trader.py) · port 8504  
**Engine:** [`paper_engine.py`](../02_VERI/paper_engine.py)  
**Test Dosyası:** [`test_session_fixes.py`](../08_AI_TRADER/test_session_fixes.py)

---

## 📄 ABSTRACT

Bu session'da üç bağımsız problem teşhis edildi ve çözüldü:

1. **Render Bug (SVG):** `st.html()` iframe sandbox'ı SVG gradient fill'i engelliyordu → grafikler tamamen görünmüyordu
2. **Kural İhlali (iddaa.com):** K1 tekli kuponlar iddaa.com'da her maça izin verilmediği için geçersizdi → odds/getiri değerleri gerçeği yansıtmıyordu
3. **Journal Eksikliği:** Kapanan kuponların journal kaydı model bilgisi, edge ve reasoning içermiyordu → öğrenme döngüsü kırıktı

**Sonuç:** 17/17 smoke test geçti. Sistem artık gerçek iddaa.com kurallarına uygun, görsel grafikler çalışıyor, journal her kapanışta eksiksiz trade notu yazıyor.

---

## 1. VERİ KATMANI (DATA)

### 1.1 Journal İçeriği — Önceki vs. Sonraki

**Önceki format** (`paper_engine.py` → `settle_coupons()`):

```
Tip: K2_COMBO | Oran: 3.052 | Stake: 125 TL | Getiri: 381 TL
Galatasaray vs Fenerbahçe | 1X2 1 @1.85 (model: %70) | Skor: 1-0 | WON
```

**Yeni format** (her bet satırında 4 model metriği + koşullu trade notu):

```
Tip: K2_FAVORI | Oran: 3.052 | Stake: 125 TL | Getiri: 381 TL
Galatasaray vs Fenerbahçe | 1X2 1 @1.85 | Model:%70 Piyasa:%55 Edge:+15.0% Güven:0.88 | Skor:1-0 | WON
Trade Notu: Galatasaray son 5 maçta 4 galibiyet, rakip form kötü.
```

**Eklenen alanlar:**

| Alan | Kaynak | Açıklama |
|---|---|---|
| `Model:%X` | `paper_bets.model_prob × 100` | Modelimizin kazanma olasılığı tahmini |
| `Piyasa:%X` | `paper_bets.implied_prob × 100` | Vig-soyulmuş piyasa olasılığı |
| `Edge:±X%` | `paper_bets.edge × 100` | Model−Piyasa farkı (pozitif = value bet) |
| `Güven:X` | `paper_bets.signal_score` | Bileşik sinyal güven skoru [0–1] |
| `Trade Notu:` | `paper_coupons.reasoning` | AI açıklaması (varsa) |

### 1.2 Edge Formülü

Sistematik edge tanımı değişmedi, ancak artık her journal satırında **kayıt altına alınıyor**:

```
Edge = model_prob − implied_prob
     = model_prob − (raw_implied / overround)

Örnek: model_prob=0.70, odds=1.85 → implied=0.541 → edge=+15.9%
```

Pozitif edge → value bet. Negatif edge → piyasa daha iyi biliyor → sinyal zayıf. Bu bilgi artık journal'da görünür olduğu için **post-settlement analiz** yapılabilir.

---

## 2. MODEL KATMANI

### 2.1 Kupon Engine Yeniden Tasarımı

**Temel sorun:** K1 tekli kuponlar iddaa.com'da her maçta geçerli değil.

> *"TEK MAÇ izin vermiyorsa iddaa.com, o zaman öyle bir oran ve kazanç da olmaz."*

**iddaa.com tekli bahis kuralı:** Tüm maçlar tekli oynanamazı; seçili maçlara özel "T" işareti gerekir. Sistemimizin bu bilgiye erişimi yok → güvenli yol: **minimum 2 ayak zorunluluğu**.

**Eski mimari (KALDIRILDI):**

| Tip | Ayak | Sorun |
|---|---|---|
| K1_FAVORITE | 1 | Tekli bahis kısıtı |
| K1_KG | 1 | Tekli bahis kısıtı |
| K1_ALT | 1 | Tekli bahis kısıtı |
| K2_COMBO | 2 | ✅ Kalıcı |

**Yeni mimari (MİN 2 AYAK):**

| Tip | Ayak | Filtre | Stake |
|---|---|---|---|
| `K2_FAVORI` | 2 | `1X2`, `model_prob ≥ 0.65`, `odds ≥ 1.25` | %2.5 bankroll |
| `K2_VALUE` | 2 | Herhangi pazar, `model_prob ≥ 0.60`, **`edge ≥ +4%`** | %2.0 |
| `K2_KARISIK` | 2 | 1 MS + 1 KG/ALT, farklı maçlar | %2.0 |
| `K3_KOMBO` | 3 | En güçlü 3 sinyal, `model_prob ≥ 0.60` | %1.5 |

**Combined odds her zaman gerçekçi:**
```python
combined_odds = pick₁.odds × pick₂.odds × ... × pickₙ.odds
potential_return = stake × combined_odds
```

**Risk dağılımı (5000 TL bankroll):**
```
K2_FAVORI  : 125 TL  (2.5%)
K2_VALUE   : 100 TL  (2.0%)
K2_KARISIK : 100 TL  (2.0%)
K3_KOMBO   :  75 TL  (1.5%)
─────────────────────────────
TOPLAM     : 400 TL  (8.0%)  ← max risk / oturum
```

Aşırı temerküz riski yok: tek sefer yanlış sinyal seti tüm bankroll'u erimez.

### 2.2 Sinyal Filtresi Değişmedi

`evaluate_match()` içindeki sinyal üretimi değişmedi — sadece kupon oluşturma mantığı güncellendi:

```
1X2     → calc_true_prob(o1, oX, o2) → vig-soyulmuş implied_prob
KG_VAR  → Poisson P(hem ev hem deplasman gol atar)  
ALT_25  → Poisson P(toplam gol < 2.5)
UST_25  → Poisson P(toplam gol ≥ 2.5)
```

---

## 3. TRADE UYGULAMASI (AI)

### 3.1 SVG Render Fix — Teknik Detay

**Sorun:** `st.html()` her çağrıda ayrı bir `<iframe>` oluşturur. SVG içindeki:
```html
<linearGradient id="pcg1a2b3c4d">...</linearGradient>
<path fill="url(#pcg1a2b3c4d)"/>
```
`fill="url(#id)"` çağrısı iframe DOM'una çapraz referans yapamaz → **gradient fill boş kalır → grafik görünmez**.

**Çözüm:**
```python
# ÖNCE (gradient görünmüyor):
st.html(card_html)

# SONRA (doğrudan sayfa DOM'una render):
st.markdown(card_html, unsafe_allow_html=True)
```

`st.markdown()` Streamlit'in ana DOM'una yazar — iframe izolasyonu yok. SVG gradient, circle, path hepsi çalışır.

**Değiştirilen 4 nokta:**

| Fonksiyon | Eski | Yeni |
|---|---|---|
| `page_overview()` — kupon kartı | `st.html(card_html)` | `st.markdown(card_html, ...)` |
| `_show_today_preview()` — sinyal listesi | `st.html(rows_html)` | `st.markdown(rows_html, ...)` |
| `page_matches()` — maç kartı | `st.html(card)` | `st.markdown(card, ...)` |
| `page_journal()` — journal girişi | `st.html(entry_html)` | `st.markdown(entry_html, ...)` |

### 3.2 Meridian-Style Position Chart

Her açık kupon kartında `_svg_position_chart(stake, potential_return, color, uid)`:

```
HEDEF 381 TL ●
            ╱
           ╱  +205%
          ╱
●────────╱
GİRİŞ 125 TL
```

- **Bezier S-eğrisi:** `M x0,y0 C bx1,by1 bx2,by2 x1,y1` — düz başlayıp dik çıkış
- **Gradient fill:** Eğri altı renk doldurma (hafif opaklık)
- **Gradient ID benzersizliği:** `f"pcg{uid[:8]}"` — aynı sayfada çakışma yok
- **Boyut:** 170×68 px — kupon kartının istatistik satırında inline

### 3.3 Settlement Chart (Kapanış Grafiği)

`_svg_settlement_chart(stake, pnl, uid)` → Journal'a otomatik eklenir:

```
WON  (+pnl):   ● ────╱╱╱──── ●   (yeşil yukarı eğri)
LOST (-stake): ● ────╲╲╲──── ●   (kırmızı aşağı eğri)
```

| Senaryo | Renk | Eğri Yönü | Son Dot |
|---|---|---|---|
| `pnl ≥ 0` (kazandı) | `#10d48e` (yeşil) | Yukarı Bezier | Hedef seviyede ✓ |
| `pnl < 0` (kaybetti) | `#ef4444` (kırmızı) | Yatay/düz | Başlangıç seviyesinde ✗ |

### 3.4 Journal RESULT Kartı — Yeni Yapı

```
┌─ ✓ KAZANDI ─────────────────────────────────── 2026-05-29 ─┐
│  K2_FAVORI — ✓ KAZANDI +256 TL                               │
├──────────────────────────────────────────────────────────────┤
│  Tip: K2_FAVORI | Oran: 3.052 | Stake: 125 TL | Getiri: 381│
│  ┌───────────────────────────────────────────────┐          │
│  │ GS vs FB   1X2 1 @1.85   Skor:1-0   [WON]   │   SVG    │
│  │ Model %70  Piyasa %55  Edge +15.0%  Güven 0.88│  chart   │
│  └───────────────────────────────────────────────┘  (yeşil) │
│  ┌─ ✎ TRADE NOTU ──────────────────────────────────────────┐│
│  │ "GS son 5 maçta 4 galibiyet, rakip form düşük"         ││
│  └──────────────────────────────────────────────────────────┘│
│  → KEEP                                                       │
└──────────────────────────────────────────────────────────────┘
```

**Parse mantığı:** Journal content'i `|` ile bölünür, her parçadan regex ile model metrikleri çıkarılır ve renkli chip'lere dönüştürülür (yeşil/sarı/gri model olasılık rengi, kırmızı/yeşil edge rengi).

---

## 4. TEST SONUÇLARI — 17/17 ✅

**Dosya:** [`test_session_fixes.py`](../08_AI_TRADER/test_session_fixes.py)  
**Çalıştır:** `python -X utf8 test_session_fixes.py`

### Grup A: SVG Charts (T01–T03)

| # | Test | Senaryo | Sonuç |
|---|---|---|---|
| T01 | Position chart yapı + etiket | 150→312 TL, +108% ROI | ✅ |
| T02 | Settlement chart renk ayrımı | WON=`#10d48e`, LOST=`#ef4444` | ✅ |
| T03 | Gradient ID benzersizliği | 5 kart, çakışma yok | ✅ |

### Grup B: Kupon Engine Logic (T04–T08)

| # | Test | Senaryo | Sonuç |
|---|---|---|---|
| T04 | K1 tipleri kaldırıldı | Kaynak kod tarama | ✅ K2/K3 tanımlı |
| T05 | Min 2 leg + farklı maç | 5 sinyal → 2 pick | ✅ |
| T06 | Combined odds | 1.85×1.65=3.052 | ✅ |
| T07 | Edge = model−implied | +0.145 | ✅ |
| T08 | Yetersiz sinyal guard | 1 sinyal → kupon üretilmez | ✅ |

### Grup C: Journal Format (T09–T11)

| # | Test | Senaryo | Sonuç |
|---|---|---|---|
| T09 | 4 model alanı mevcut | Model/Piyasa/Edge/Güven regex | ✅ |
| T10 | Trade Notu koşullu | Dolu=eklenir, Boş=eklenmez | ✅ |
| T11 | Stake regex parse | "Stake: 125 TL" → 125.0 | ✅ |

### Grup D: Hesaplamalar (T12–T15)

| # | Test | Senaryo | Sonuç |
|---|---|---|---|
| T12 | Stake oranları | Toplam=%8.0 bankroll | ✅ |
| T13 | calc_true_prob vig | Ham=1.0481 → Normalize=1.0000 | ✅ |
| T14 | Edge=0 kontrolü | model=piyasa → edge sıfır | ✅ |
| T15 | SVG ROI hesabı | 108%/100%/25%/80% (4 senaryo) | ✅ |

---

## 5. SONUÇ & DURUM

### Tamamlanan ✅

- [x] SVG position chart görünür (st.html → st.markdown)
- [x] Settlement chart Journal'a otomatik ekleniyor
- [x] K1 tekli kuponlar kaldırıldı (iddaa.com kural uyumu)
- [x] K2_FAVORI / K2_VALUE / K2_KARISIK / K3_KOMBO tanımlandı
- [x] Journal: Model%, Edge%, Piyasa%, Güven, Trade Notu
- [x] 17/17 smoke test geçti

### Devam Eden ⏳

- [ ] [`task #142`] iddaa.com odds scraper (future fixtures + KG)
- [ ] [`task #124`] Kapı 1 — V2 sinyal & mimari tasarım (FAV → VALUE pivot)
- [ ] [`task #119`] A2 — Transfermarkt injury scraper
- [ ] [`task #120`] A1 — T1 xG (FotMob)

### Mimari Durumu

```
[paper_engine.py --run]
        ↓
  build_session_coupons()
  • K2_FAVORI (2 ayak, min model≥0.65)
  • K2_VALUE  (2 ayak, edge≥+4%)
  • K2_KARISIK(2 ayak, MS+KG/ALT)
  • K3_KOMBO  (3 ayak, model≥0.60)
        ↓
  place_coupons() → paper_coupons + paper_bets (DB)
        ↓
[app_trader.py :8504]
  Overview → position chart (Bezier SVG, inline DOM)
        ↓
[paper_engine.py --settle]
        ↓
  settle_coupons()
  • pnl hesapla
  • journal: Model% / Edge% / Güven / Trade Notu
        ↓
  _write_journal_entry() → paper_journal (DB)
        ↓
[app_trader.py — Journal page]
  RESULT kart: settlement chart + model chip'leri + trade notu
```

---

## 6. İLERİ ADIMLAR

### Kısa Vadeli (bir sonraki session)
1. **task #142 bitir:** iddaa.com odds scraper → `closing_btts_yes/no` doldur → K2_KARISIK daha fazla sinyal
2. **Paper run test:** `python paper_engine.py --run --dry-run` ile yeni kupon tiplerini gerçek veriyle kontrol et

### Orta Vadeli
3. **Kapı 1 — FAV→VALUE pivot:** Model v2 sinyal mimarisi (bakınız [`v2_MASTER_ROADMAP.md`](./v2_MASTER_ROADMAP.md))
4. **Live shadow:** Her gün otomatik `--run` + `--settle` cron job (Windows Task Scheduler)

---

*Rapor otomatik oluşturuldu — AI Trader session 2026-05-29*  
*Önceki:* [`v2_SPRINT_OZETI_28_MAY.md`](./v2_SPRINT_OZETI_28_MAY.md) · *Sonraki:* TBD
