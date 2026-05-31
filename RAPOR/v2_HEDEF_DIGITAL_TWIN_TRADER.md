# DIGITAL TWIN TRADER — Yeni Vizyon Dokümanı

**Tarih:** 2026-05-28
**Pivot:** "Model üreten proje" → **"AI Trader Destek Sistemi"**
**Hedef sezon:** 2026-27 lig fixture'ları

---

## 1) BÜYÜK PIVOT — Hedef Yeniden Tanımı

### ESKİ HEDEF (Geçersiz)
> "+%60 ROI üreten futbol bahis modeli"

**Sorun:** Tek metrik (ROI), tek pazar (1X2), statik strateji, trader'ın gerçek ihtiyaçları görmezden geliniyor.

### YENİ HEDEF (Doğru)
> **DIGITAL TWIN TRADER** — Sezonun her haftasında, her maçta, her pazarda Trader'ın yanında olan, ona ne yapacağını söyleyen, kararlarından öğrenen, kendi edge'ini sürekli geliştiren bir **AI Trader Destek Sistemi**.

**Anahtar Kelimeler:**
- **Twin** — Trader'ın dijital ikizi (profilini, alışkanlıklarını, tercihlerini biliyor)
- **Trader** — Akademisyen değil, **operasyonel bahisçi** mantığıyla düşünüyor
- **Destek** — Karar verici değil, **danışman**; trader son sözü söyler
- **Sürekli** — Sezon başından sonuna, her hafta yanında

---

## 2) ÜRÜN VİZYONU — Trader'ın Yıllık Hikayesi

### Sezon Başı (Ağustos-Eylül 2026)

**AI Trader:**
> "Merhaba. 2026-27 sezonu başlıyor. Bankrolm 10,000 TL. Geçen sezon TRIVOX Q5+a2 ile %78 hit yakalandı. Bu sezon profil ayarın:
> - **Hedef:** Aylık %5-8 net ROI
> - **Maksimum drawdown:** %15
> - **Aktif modeller:** TRIVOX, DUOVOX, MONOVOX-E0
> - **Aktif pazarlar:** 1X2 (canlı), A/Ü 2.5 (canlı), KG (V2 beta)
> - **Devre arası (Hafta 10-18) için:** ihtiyatlı, küçük pozisyon (T07 bulgusu)
> - **2025-26 hatırlatması:** Sezon başı 4-5 hafta beklemek faydalı (yeni transferler oturma süresi)
>
> Bu hafta T1, E0, SP1 fixture'ları açıklandı. İlk 8 haftada model güveni kademeli artacak. Şimdilik sadece **Q5+agree2** ALL-IN sinyallerini öner."

### Hafta İçi (Pazartesi Akşamı)

**Trader (telefonda):**
> "Bu hafta ne var?"

**AI Trader:**
> "Cumartesi-Pazar 32 maç var. 3 ALL-IN aday, 5 STANDART aday. Detaylar:
> - **Liverpool-Tottenham** [MONOVOX-E0 + DUOVOX, Q5+a2]: Ev 1 @ 1.55 → ALL-IN 500 TL
> - **Real Madrid-Betis** [DUOVOX + MONOVOX-SP1, Q5+a2]: Ev 1 @ 1.45 → ALL-IN 500 TL
> - **Galatasaray-Trabzonspor** [TRIVOX, Q5+a2]: Ev 1 @ 1.95 → ALL-IN 500 TL
>
> İki seçenek var:
>
> **Seçenek A: 3 ayrı kupon (K=1)** — Varyans dağıtık
>   Toplam: 1500 TL, beklenen kazanç +%19 (Q5+a2 %78 hit)
>
> **Seçenek B: 3/3 Sistem** — 3 maç, ya hep ya hiç
>   Toplam: 500 TL, kombo @ 4.39 → ya 2000 TL ya 0
>   Beklenen: %78³ = %47 olasılık (Bağımsız varsayımla; %2 korelasyon var)
>
> **Seçenek C: 2/3 Sistem** — 3 maç, en az 2'si tutarsa kazan
>   Toplam: 500 TL × 3 kupon = 1500 TL
>   Olasılık: %96 tek kazan
>   Beklenen kazanç: orta
>
> **Önerim:** Seçenek C (2/3 sistem). Q5+a2 picks bağımsız olmadığından kombi risk yüksek. 2/3 sistem hem güveni hem getirisini dengeler."

### Sonuç Sonrası (Pazartesi Sabah)

**AI Trader:**
> "Geçen hafta:
> - Liverpool 2-1 ✓ kazandı (Q5+a2 hit)
> - Real Madrid 3-0 ✓ kazandı
> - Galatasaray 1-1 ✗ kaybetti
> - 2/3 sistem: 2 doğru, 1 yanlış → +850 TL net
> - Bankroll: 10,000 → 10,850 (+%8.5)
>
> Bu hafta için öğrenme:
> - Galatasaray-Trabzonspor hatası: kart anomaly sinyali zayıftı, dikkat ettim ama bu yön drift'ti. **Bir sonraki Galatasaray maçında kart sinyali güvenilirliğini -%5 düşür.**
> - Liverpool consensus mükemmel: 2 model + Q5+a2 + sezon başı momentum.
>
> Önümüzdeki hafta için profil güncellendi."

### Sezon Ortası (Aralık 2026)

**AI Trader:**
> "Devre arası geliyor. T07 bulgusuna göre Hafta 10-18 modelin en zayıf olduğu dönem. **Önerim:**
> - Hafta 10-14: ALL-IN dondur, sadece ULTRA-konsensus (3+ model Q5+a2) oyna
> - Hafta 15-18: Q5+a2 ama 2x stake'i 1x'e düşür
> - Hafta 19+: Normal düzen
>
> 4 ayda bankroll 10,000 → 13,200 (%32). Drawdown −%6 (kontrollü). Smoke test geçildi.
> Yeni 19K data toplandı, model retrain Aralık'ta yapılacak."

### Sezon Sonu (Mayıs 2027)

**AI Trader:**
> "Sezon raporu:
> - Toplam pick: 156
> - Hit rate: %66 (beklenen %65)
> - Realize CLV: −%0.3 (beklenenin üstünde, neredeyse pozitif!)
> - Bankroll: 10,000 → 17,400 (**%74 yıllık**)
> - En iyi ay: Mart (transfer dönemi etkisinden bağışık)
> - En kötü ay: Aralık (devre arası riski)
>
> Sonraki sezon için strateji:
> - Devre arası penaltısı doğrulandı, V3'te otomatik pause kuralı eklenecek
> - DUOVOX en sürdürülebilir, ana ürün
> - TRIVOX volatil ama Q5+a2 sniper olarak güçlü, %20 portföy"

---

## 3) DIGITAL TWIN TRADER — Bileşenler

```
┌────────────────────────────────────────────────────────────────────┐
│              AI TRADER DESTEK SİSTEMİ (Digital Twin)                │
├────────────────────────────────────────────────────────────────────┤
│                                                                    │
│  [1] TRADER PROFILE      [2] MARKET BRAIN      [3] STRATEGY MEMORY │
│  ──────────────────      ─────────────────     ─────────────────── │
│  - Bankroll              - 5 model (V2)        - Hangi haftada     │
│  - Risk toleransı        - 5 pazar             - Hangi maç         │
│  - Lig tercihi           - CLV tracker         - Hangi pozisyon    │
│  - Frekans tercihi       - Korelasyon mat.     - Hangi sistem      │
│  - Drawdown geçmişi      - Sezon-içi patern   - Sonuç → öğren     │
│                                                                    │
│  [4] DECISION ENGINE     [5] LEARNING LOOP    [6] RISK MANAGER     │
│  ──────────────────      ─────────────────     ─────────────────── │
│  - Pick → score          - Hit/Miss kaydı      - Dynamic Kelly     │
│  - Quintile + agree      - Calibration update  - Stop-loss enforce │
│  - Sistem önerisi        - Aylık retrain       - PSI/drift alarm  │
│  - Kupon optimizer       - Trader feedback     - Position sizing   │
│                                                                    │
│  [7] EXPLAINABILITY      [8] AUTOMATION                            │
│  ──────────────────      ─────────────────                         │
│  - "Neden bu pick?"      - Otomatik picks                          │
│  - Sinyal breakdown      - Telegram bildirim                       │
│  - Risk transparency     - Voice komut                              │
│  - Anlaşılır rapor       - Bahis girişi (semi-auto)                │
│                                                                    │
└────────────────────────────────────────────────────────────────────┘
```

### 8 Bileşenin Detayı

**[1] Trader Profile** (kişiselleştirme)
- Bankroll, risk, lig tercihi
- Geçmiş kararlar → kişisel ayarlama
- "Trader X agresif, %5+ Kelly kabul ediyor" / "Trader Y konservatif, %1 Kelly"

**[2] Market Brain** (model + pazar zekası)
- 5 model paralel (TRIVOX, DUOVOX, TRIOVOX, MONOVOX-E0, MONOVOX-SP1)
- 5 pazar (MS, İY, AH, A/Ü, KG)
- Lig × pazar matrisinde her hücre için Q1-Q5 quintile

**[3] Strategy Memory** (geçmiş kararlar)
- "2024-25 Hafta 12'de TRIVOX hatası" — log
- "Devre arası dönemi PAS" — kural
- "Hangi takım hangi hafta nasıl davranır" — pattern memory

**[4] Decision Engine** (öneri motoru)
- Her hafta için ranked öneri listesi
- ALL-IN / STANDART / KÜÇÜK / PAS
- Sistem bahis vs Tek kupon önerisi (otomatik karşılaştırma)

**[5] Learning Loop** (öğrenme döngüsü)
- Her sonuç → calibration güncelle
- Aylık model retrain (yeni veri)
- Trader'ın "neden bu pick'i atladım" feedback'i → model

**[6] Risk Manager** (canlı koruma)
- Drawdown −%15: stake/2
- Drawdown −%25: 1 hafta PAS
- Loss streak: dynamic pause
- Concentration risk: aynı yön 3+ aday → uyarı

**[7] Explainability** (anlaşılabilirlik)
- "Liverpool için ALL-IN çünkü:
  - MONOVOX-E0 + DUOVOX konsensüsü
  - Q5 (score 0.93)
  - 2 sinyal agree (anomaly + DC model)
  - Ev avantajı + Tottenham sakatlık var"

**[8] Automation** (operasyonel araçlar)
- Telegram / WhatsApp bildirim
- Voice "Hey AI Trader, bu hafta ne öneriyorsun?"
- Yarı-otomatik bahis (iddaa.com formuna fill)
- Sezon planı PDF export

---

## 4) İDDİA MEKANİKLERİ — Kupon, Sistem, Kaldıraç

### A) Tek Bahis (K=1)
- 1 maç, 1 pazar → 1 leg
- En düşük varyans, en yüksek hit (Q5+a2 ile %70-84)
- Vergi: kazanç üzerinden %10
- **Trader için ana strateji** (sniper)

### B) Kombine Bahis (K≥2)
- 2+ leg, hepsi tutmalı
- Marjlar **çarpılır** (eff. marj %20+)
- Varyans **patlar**
- Vergi: 66,935 TL üstü +%20 stopaj
- **DİKKAT:** Korelasyonlu leg'leri birleştirme (Üst 2.5 + KG Var = çift bahis)

### C) Sistem Bahis (örn. 2/3, 3/4, 4/5)
**Sistem 2/3 açıklama:**
- 3 maç seçilir
- 3 ayrı 2'li kombin oluşur: (1+2), (1+3), (2+3)
- Stake = 3 × kupon_stake
- Eğer 3 maçtan en az 2'si tutarsa **en az 1 kupon kazanır**
- Eğer 3'ü tutarsa **3 kupon kazanır** (max kazanç)

**Sistem 3/4:**
- 4 maç, 4 farklı 3'lü kombin (C(4,3)=4)
- Stake = 4× kupon_stake
- 4'ü tutarsa 4 kupon, 3'ü tutarsa 3 kupon, 2'si tutarsa 0 kupon

**Matematiksel olarak:**
- EV teorik olarak tek-bahisle aynı (no free lunch)
- AMA **varyans azaltılır** — full miss riski düşer
- Trader için **psikolojik** avantaj büyük (toplu kayıp yerine kısmi kayıp)

**Q5+a2 picks için sistem önerisi:**
- 3 ALL-IN aday varsa → **2/3 sistem**: %96 ihtimal en az 2'si tutturur, varyans çok düşük
- 4 ALL-IN aday varsa → **3/4 sistem**: %88 ihtimal en az 3 tutturur
- Ayrı kuponlar (K=1) versus sistem trade-off:
  - Ayrı kupon: max kazanç yüksek, max kayıp tüm stake
  - Sistem: max kazanç orta, max kayıp tüm stake (ama nadir)

### D) Kaldıraç (Türkiye İddaa'da YOK)
- Geleneksel finansta kaldıraç: 10x emir = %1 hareket 10% getiri
- İddaa'da yapısal kaldıraç yok
- **Ama kombin = doğal kaldıraç:** K=3 kombin tek maça göre %200+ leverage
- **Sistem bahis = anti-leverage:** Varyansı düşürür, getiri kapasitesi de düşer

**AI Trader'ın "kaldıraç" yorumu:**
> Aslında **pozisyon büyüklüğü = kaldıraç**. Bankroll'un %1'i (1x) vs %10'u (10x) farkı.
> Yüksek güven (Q5+a2) → yüksek kaldıraç (5x stake)
> Düşük güven (Q3) → düşük kaldıraç (0.5x)

### E) Multi-Market Kombin Mantığı
- Tek maçta 5 pazar arasından **bağımsız** olanları kombine et
- İzin verilen: MS + İY-X (r=−0.2), MS + AH-1 (r=0.3)
- Yasak: Üst 2.5 + KG Var (r=0.7), MS-1 + İY-1 (r=0.7)
- AI Trader otomatik korelasyon kontrol → "Bu kombin riskli, ayrı yat" uyarısı

### F) Vergi Optimizasyonu
- Tek kupon ikramiye > 66,935 TL → %20 stopaj kicks in
- TRIVOX/DUOVOX K=1 ortalama odd ~1.60-1.85
- Tek kupon 500 TL × 1.85 = 925 TL → vergisiz
- K=3 odd × 7 → 3,500 TL → hala vergisiz
- **K=4 sistem 3/4 stake 500 TL × ortalama 16 odd = 8,000 TL** → vergisiz
- **K=5+ tehlikesi** (kombin odd > 70x, ikramiye > 66K)

---

## 5) ROADMAP — 12 Ay

### Faz 1: Foundation (Ay 1-3) — Şu an buradayız
- ✅ Kapı 0 — kanıt restorasyonu
- ✅ Tarihsel model arena (15 model)
- ⏳ Yeni 19K matches_v2 üzerinde smoke test
- ⏳ Multi-market V2 (5 pazar) — DC Poisson projector
- ⏳ V2 sinyal genişletme (sharp_money, clv_historical)

### Faz 2: Digital Twin v0.1 (Ay 4-6)
- Trader Profile DB
- Decision Engine (Q5+a2 + sistem önerisi)
- Explainability layer (her pick için "neden" açıklaması)
- Telegram/WhatsApp bildirim
- 6 ay paper trading başlat

### Faz 3: Learning Loop (Ay 7-9)
- Trader feedback ingestion ("Bu pick'i atladım çünkü...")
- Aylık model retrain
- Calibration update otomatik
- Risk Manager v1 (dynamic Kelly + drawdown enforce)
- Multi-market full release (5 pazar)

### Faz 4: 2026-27 Sezon Hazırlığı (Ay 10-12)
- Sezon planlaması özelliği (hangi haftadan başla, hangi haftada PAS)
- Otomatik fixture analysis
- Voice komut entegrasyonu
- Beta launch — 5-10 trader (kapalı çevre)

### Faz 5: V1.0 Public (Ay 12+)
- Production release
- Multi-trader support
- API erişim
- Sürekli iyileştirme döngüsü

---

## 6) BAŞARI METRİKLERİ — Yeni Hedef

| Metrik | Eski Hedef | Yeni Hedef |
|---|---|---|
| Birincil | ROI %60 | **Trader memnuniyeti** |
| Sample | Backtest | Live shadow + canlı |
| Karar | Statik | **Dinamik (her hafta)** |
| Pazar | 1X2 | **5 pazar** |
| Kullanıcı | "Sonra yatırımcı" | **Trader (1 kişi, sonra çoğul)** |
| Çıktı | Rapor | **Anlık karar desteği** |
| Validasyon | Backtest ROI | **Live CLV + Trader feedback** |
| Sürdürülebilirlik | Tek model | **Sürekli iyileşen sistem** |

---

## 7) TEK CÜMLE ÖZET

> **"Trader'ın yanında olan, her hafta ne yapacağını söyleyen, kararlarından öğrenen, kendi edge'ini sürekli geliştiren AI Trader Destek Sistemi — Digital Twin Trader."**

Bu, BAHIS AGENT'ın gerçek hedefi. Modeller araç, edge yakıt, ürün **DESTEK SİSTEMİ**.

---

## 8) İLK ADIM (Bu Hafta)

1. **Yeni 19K matches_v2 üzerinde Kapı 0 smoke test** (T01-T12 yeni paradigma ile)
2. **Yönetici Özeti** — Komite raporundaki tüm endişelere yeni paradigma cevabı
3. **Multi-market V2 inşa başlat** — A/Ü 2.5 ilk pazar (mevcut FD veri yeterli)
4. **AI Trader v0.1 mockup** — Hafta planı çıktısı şablonu

İlk 3 madde teknik, 4 stratejik. Önce 1-2 ile başlayıp Smoke Test geçince 3-4'e geçelim.
