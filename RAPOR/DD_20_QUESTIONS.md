# 🔍 DUE DILIGENCE — 20 Soru, İki Model

**Tarih:** 2026-05-27
**Perspektif:** Mackolik / iddaa.com acquirer ekibi
**Soru türü:** Yatırım/satın alma sonrası ne göreceğim?
**Cevap kuralı:** Dürüst, eleştirel, veri-bazlı

---

## YÖNETICI ÖZETİ (Önce kötü haber)

**Backtest (4 sezon):** TRIVOX +51% ROI, EUVOX +18% ROI ✅
**Canlı 2025-26 sezonu:** TRIVOX -100% ROI (n=6), EUVOX -0.8% ROI (n=92) ❌

**Bu kritik bir bulgu.** Canlı performans backtest'in çok altında.
Olası sebepler: edge erosion, overfitting, sezon-spesifik dinamik, sample küçüklüğü (TRIVOX).

---

## SECTION A — STRATEJİK (Q1-5)

### Q1: "Pazar büyüklüğü ve büyüme oranı?"

| Pazar | Büyüklük (2024 tahmin) |
|---|---|
| Türkiye iddaa hacmi | ~50 milyar TL/yıl |
| Avrupa online sports betting | ~50 milyar EUR |
| Tip ster/predicting servisi | Türkiye'de ~2-5 milyon kullanıcı potansiyel |

**Cevap:** Pazar büyük, ama doygun. Mackolik/iddaa zaten dominant.

---

### Q2: "Rakipler kim?"

- **Mackolik tahminleri** (insan tipster)
- **iddaa.com Yazar Yorumları** (12 yazar)
- **Tipstrr / Blogabet** (uluslararası tipster)
- **AnaliyzeYourBet / VeriBahis** (algorithmic)
- **Sharp money trackers** (RebelBetting, ProfitBetting)

**TRIVOX/EUVOX rekabet avantajı:**
- ✅ Şeffaf metodoloji (16+ test, akademik makale standardı)
- ✅ Veri-bazlı (insan önsezisi değil)
- ❌ Canlı performans henüz kanıtlanmamış (yukarıdaki bulgu)
- ❌ Replikable — rakip aynı yöntemi kullanabilir

---

### Q3: "Defansif moat?"

| Moat Kaynağı | Var mı? |
|---|:---:|
| Proprietary data | ❌ (tüm veri public: Football-Data, Understat, iddaa API) |
| Algoritma karmaşıklığı | ⚠️ (Dixon-Coles + cross-market — uzman replike edebilir) |
| Brand/güven | ❌ (henüz user base yok) |
| Network effects | ❌ (B2C model) |
| Switching cost | ❌ (kullanıcı kolayca bırakır) |

**Cevap:** Moat **zayıf**. İlk-çıkan avantajı + brand kurarsa savunulabilir.

---

### Q4: "Customer acquisition cost (CAC)?"

Bilinmiyor — henüz canlı kullanıcı yok. Tahmin:
- Google/Facebook ads CTR ~%2, CPC ~10-20 TL
- Aylık abonelik 1000-3000 TL
- CAC tahmin 200-500 TL
- LTV: 12 ay × 1500 TL = 18K TL
- LTV/CAC = 36-90x (eğer tahmin doğruysa)

**Cevap:** **Spekülatif.** Beta test edilmeden gerçek CAC bilinmez.

---

### Q5: "TAM / SAM / SOM?"

- **TAM** (Total Addressable Market): 2-5M Türkiye spor bahisçisi
- **SAM** (Serviceable Available Market): 100K-500K düzenli kullanıcı (orta üst seviye)
- **SOM** (Serviceable Obtainable Market): İlk yıl 1K-10K kullanıcı
- Yıllık potansiyel gelir: 10K × 1500 TL = 15M TL (orta senaryo)

**Cevap:** **Görece küçük ama nakit-yoğun pazar.**

---

## SECTION B — TEKNİK EDGE (Q6-10)

### Q6: "Edge'in matematiksel kanıtı?"

**Olumlu:**
- Backtest 4 sezon, 956 kupon, ROI +18.4% (EUVOX)
- Benjamini-Hochberg FDR Q=0.05 ile 4 bulgu kabul edildi
- Bootstrap CI95 tamamen pozitif

**Olumsuz:**
- Bonferroni 0/19 geçti (çok konservatif ama uyarıcı)
- Canlı 2526 ROI -0.8% (sample dışı zayıf)
- Pinnacle CLV ölçülmedi (en sharp markete karşı edge?)

**Cevap:** Backtest evidence-based AMA canlı doğrulama eksik.

---

### Q7: "Bookmaker'ı NEDEN yenebiliyor?"

İddia: 4 ortogonal sinyalin konsensüsü bookmaker'ın global modelinde yakalanmıyor.

**Doğrulanabilir mi?**
- Teorik olarak makul (Bayes)
- Pratikte canlı edge YOK (2526'da)
- → Bookmaker'lar son 2-3 yılda **adapte** olmuş olabilir

**Cevap:** Teori sağlam ama **bookmaker'lar zamanla öğrenir**. Edge azalıyor olabilir.

---

### Q8: "Metodoloji replicate edilebilir mi?"

- ✅ Kod açık ve okunabilir
- ✅ Veri kaynakları public
- ✅ Akademik referanslar mevcut (Dixon-Coles 1997, Kelly 1956)
- ⚠️ Sinyal kombinasyonu unique ama trivially copyable

**Cevap:** Rakipler bunu **3 ay içinde replike edebilir**.

---

### Q9: "Data sources — proprietary mu?"

- Football-Data.co.uk (free)
- Understat.com (free)
- api-football.com (10 RPM free, paid plans var)
- iddaa.com (public, reverse-engineered API)

**Cevap:** **Sıfır proprietary**. Defansif avantaj sıfır.

---

### Q10: "Code/model lisans yapısı?"

- Kod kullanıcı bilgisayarında Python script
- Lisans yapısı tanımlı değil
- Modeller JSON formatında (kopyalanabilir)
- Streamlit dashboard açık kaynak

**Cevap:** **Lisans defansif değil.** Reverse-engineering trivial.

---

## SECTION C — PERFORMANS VALİDASYON (Q11-15)

### Q11: "Out-of-sample ROI?"

| Test | Sample | ROI |
|---|---|---:|
| 4-sezon backtest | 109 kupon | +51.5% (TRIVOX) |
| 4-sezon backtest | 956 kupon | +18.4% (EUVOX) |
| **2526 LIVE** | **6 kupon** | **-100%** (TRIVOX) ⚠️ |
| **2526 LIVE** | **92 kupon** | **-0.8%** (EUVOX) ⚠️ |
| Cross-validation rolling | 4 split | 3 pozitif, 1 prelim |

**Cevap:** Backtest pozitif, **canlı zayıf**. Replikasyon kritik.

---

### Q12: "Sharpe ratio?"

- TRIVOX backtest annual Sharpe: 1.38 (iyi)
- EUVOX backtest annual Sharpe: tahmini 1.20
- 2526 Sharpe hesaplanmadı (n çok küçük)

**Cevap:** Backtest Sharpe iyi ama **canlı sapma var**.

---

### Q13: "Max drawdown + worst case?"

- TRIVOX max DD: 14K TL (4 sezon backtest)
- EUVOX max DD: 35K TL
- En uzun kayıp serisi: 14 ardışık kupon (TRIVOX)
- **2526'da TRIVOX 6/6 kayıp** — bu **YENI WORST CASE**

**Cevap:** Backtest worst-case'i canlıda **dışına çıktı**.

---

### Q14: "CLV — Pinnacle closing'i geçiyor mu?"

- **Ölçülmedi.** Football-Data sadece Pinnacle closing veriyor, opening yok.
- Profesyonel bahisçilerin **en kritik metriği** bu.

**Cevap:** **Bilmiyoruz**. Acquirer için kırmızı bayrak.

---

### Q15: "Strateji robust mu?"

Smoke test 20/20 PASS:
- Bootstrap CI95 pozitif
- 5/5 sezon pozitif (backtest)
- Volume linear scaling
- ⚠️ Sezon sonu performance degradation
- ⚠️ Vergi %20'de marjı incelir

**Cevap:** Backtest'te robust, **canlı testte değil** (yukarıdaki bulgu).

---

## SECTION D — LİVE PREDICTION CAPABILITY (Q16-20)

### Q16: "Bu hafta ne öneriyorsun?"

2026-05-17 (son matchday) için:
- TRIVOX: Veri eksik (closing odds çoğu yok)
- EUVOX: Önerilerden son kupon **2026-01-13 D1** → TUTTU (+3,111 TL)

**Cevap:** Sezon ortası closing odds eksik → real-time data pipeline'ı yok.

---

### Q17: "Geçen hafta tahminin + actual?"

Yukarıdaki tabloya bak. Son birkaç hafta:

| Tarih | Lig | Combo | Sonuç | PnL |
|---|---|---:|:---:|---:|
| 2026-01-13 | D1 | 4.11 | TUTTU | +3,111 |
| 2026-01-11 | SP1 | 4.65 | tutmadı | -1,000 |
| 2026-01-10 | SP1 | 3.04 | tutmadı | -1,000 |
| 2026-01-07 | E0 | 2.66 | tutmadı | -1,000 |
| 2026-01-04 | E0 | 2.50 | tutmadı | -1,000 |

**Son 5 kupon: 1 tutuş, 4 kayıp = -855 TL net**

---

### Q18: "Multi-week forward — hafta hafta?"

Backtest'te tüm hafta tahminleri yapılabilir.

**Asıl test:** Önce tahmin yap, sonra hafta gelince sonucu gör.
Bu **canlı shadow run** gerekir → henüz yapılmadı.

**Cevap:** Forward prediction capability **var**, ama **doğrulanmadı**.

---

### Q19: "Düşük güven zamanları belirleyebilir mi?"

- score_v13 < 0.5 ise "düşük güven" sinyali
- agree_count < 2 ise zayıf konsensüs
- Sezon sonu (week 26+) ROI degradation gözlendi

**Cevap:** Evet, **score** ve **agree_count** ile düşük güven flag'i konabilir.

---

### Q20: "Edge zamanla degrade mi?"

**EVET — açık bir trend var:**

| Sezon | TRIVOX ROI | EUVOX ROI |
|---|---:|---:|
| 2122 | +39% | +2% |
| 2223 | +49% | +30% |
| 2324 | +58% | +17% |
| 2425 | +131% | +35% |
| **2526 (LIVE)** | **-100%** | **-0.8%** |

**Cevap:** Sezonlar arası tutarsız, ve **2526 ciddi düşüş**.
Bu, bookmaker adaptasyonu veya overfit göstergesi olabilir.

---

## TÜM SORULARIN BİRLEŞİK CEVABI

### Güçlü Yanlar ✅
1. Akademik standart metodoloji
2. Backtest robust (16 test, smoke test 40/40 PASS)
3. Şeffaflık ve replikability
4. İki farklı profil (TRIVOX selective vs EUVOX volume)
5. Veri audit + düzeltmeler dürüstçe raporlandı

### Zayıf Yanlar ❌
1. **Canlı 2526 performance dramatik kötü** (TRIVOX -100%, EUVOX ~0%)
2. Edge erosion belirtisi (sezonlar arası inip çıkıyor)
3. Defansif moat yok
4. CLV ölçülmedi
5. Live shadow run YOK (en kritik eksiklik)
6. Proprietary data yok
7. Sample size küçük (TRIVOX 109 kupon = 4 sezon)
8. Bonferroni geçemiyor (B-H ile 4 kabul)

### Acquirer'a Net Cevap

**Eğer Mackolik/iddaa.com**:
- **Şu an satın alma riski yüksek** — canlı edge kanıtlanmadı
- **Ürün konsepti güzel** ama execution unvalidated
- **6 ay shadow run** sonrası tekrar değerlendirilebilir
- **Yatırım miktarı**: pre-revenue, sadece IP + ekip değeri

### Önerilen Acquisition Stratejisi

1. **Earnout-based deal**: Performans-bağlı ödeme
2. **Aşamalı satın alma**: Aylık 1000 TL/100 kullanıcı milestone'ları
3. **Lisanslama**: Kod + metodoloji lisansı (full acquisition yerine)
4. **Bekle ve gör**: 6 ay sonra tekrar değerlendir

---

## 🎯 ACQUIRER İÇİN ANA MESAJ

> **Bu ürün bilim disiplini ile geliştirildi, dürüstçe raporlanıyor.**
> Backtest sonuçları güçlü, **ama canlı edge henüz kanıtlı değil**.
>
> **Şu anki değer:** IP + metodoloji + ekip + dokümantasyon
> **Risk:** Live performance, edge erosion, replikasyon kolaylığı
> **Tavsiye:** Aşamalı acquisition, milestone-based, 6 ay shadow run sonrası
