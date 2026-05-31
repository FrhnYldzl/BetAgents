# ⚽ Akıllı Bahis Asistanı

## Türkiye ve Avrupa Futbol Liglerine Bilimsel Yaklaşım

**Sayın yatırımcı,**

Futbol kuponu oynamak istiyorsunuz ama "hangi maç tutar?" sorusunun cevabı yok.
Önsezi ve kulaktan dolma bilgi yerine **matematik ve veri konuşur** mu?

Evet — bu üründe konuşuyor.

---

## 🎯 ÜRÜN

**Akıllı Bahis Asistanı**, profesyonel bir takımın geliştirdiği iki "motor" üzerine kurulu:

### Motor 1: TRIVOX — Türkiye Süper Lig Uzmanı

Sadece **Türk Süper Lig**'i en derin şekilde tanır.
Haftada 1 kupon önerir, **3 maçlık kombin** olarak.

**Sayılar (4 sezon = 109 kupon backtest):**
- ROI %51 (vergi öncesi)
- ROI %38 (vergi sonrası)
- 1000 TL kuponla 4 sezon → **42.000 TL net**
- Aylık ortalama: **+875 TL**

### Motor 2: EUVOX — 6 Avrupa Ligi Geniş Kapsam

Türkiye + Premier League (İngiltere) + Bundesliga (Almanya) +
La Liga (İspanya) + Serie A (İtalya) + Ligue 1 (Fransa) — toplam **6 lig**.

**Sayılar (4 sezon = 956 kupon backtest):**
- ROI %18 (vergi öncesi)
- ROI %10 (vergi sonrası)
- 1000 TL/kupon flat → **94.000 TL net**
- Aylık ortalama: **+1.960 TL**

---

## 🔍 PEKİ NEDEN ÇALIŞIYOR?

Profesyonel bahisçiler bilir: bookmaker'lar (Pinnacle, Bet365) dünya çapında
matematikçiler tarafından fiyatlanır. Onları "yenmek" çok zor.

**Ama her hafta bazı maçlarda 3 farklı analiz aynı şeyi söyler:**
- Geçmiş skorlardan istatistiksel model (Dixon-Coles)
- Cross-market anomaly (oran tutarsızlıkları)
- xG (atılması beklenen gol — Understat verisi)
- Form (son 5 maç sonucu)

İşte o zaman, **3 bağımsız sesin söylediği şey "dinlenmesi gereken sestir".**

Bu vizyon literatürde de yer alıyor:
- Dixon & Coles (1997) — bivariate Poisson model
- Kelly (1956) — optimum yatırım
- Benjamini-Hochberg (1995) — multiple-testing düzeltmesi

---

## 💡 KULLANICI DENEYIMI (Ne Yapacaksın?)

**Pazartesi:**
- Telefondan Streamlit web arayüzünü aç (bilgisayar gerek yok)
- "Bu haftanın kuponu" sekmesine bak
- TRIVOX veya EUVOX modu seç

**Pazartesi öğleden sonra:**
- 3 maç önerisi ekranda
- Tahmini oran ve hangi sinyallerin teyit ettiği gösterilir
- iddaa.com'a gir, aynı maçları seç, 1000 TL stake et

**Hafta sonu sonrası:**
- Kupon tuttu mu otomatik kontrol edilir
- Bankroll güncellenir
- Stat panelinde uzun-vadeli performans takip

---

## 📊 ÖZELLİKLER

### TRIVOX (Türkiye Uzmanı)

| Özellik | Açıklama |
|---|---|
| **Lig** | Türk Süper Lig |
| **Kupon türü** | 3 maç kombin |
| **Stake** | 1000 TL flat |
| **Sıklık** | 4 haftada ~1 kupon (selektif!) |
| **Beklenen ROI** | %38 (vergi sonrası) |
| **Aylık net** | ~875 TL |
| **En kötü kayıp serisi** | 14 ardışık kupon |
| **Max bankroll kaybı** | 14.000 TL |
| **İdeal bütçe** | 5-15K TL |

### EUVOX (6-Lig Kapsamı)

| Özellik | Açıklama |
|---|---|
| **Ligler** | T1 + E0 + D1 + SP1 + I1 + F1 |
| **Kupon türü** | Lige göre 2-3 maç kombin |
| **Stake** | 1000 TL flat/kupon |
| **Sıklık** | Haftada 2-3 kupon (yüksek hacim) |
| **Beklenen ROI** | %10 (vergi sonrası) |
| **Aylık net** | ~1.960 TL |
| **En kötü kayıp** | 10 hafta -10K toplam |
| **Max bankroll kaybı** | 35.000 TL |
| **İdeal bütçe** | 30-100K TL |

---

## ✅ FAYDALAR

### 1. Bilim-Tabanlı, Önsezi Değil

20 ayrı bilimsel test, 16 farklı senaryo. Her parametre **veri ile sınanmış**.

### 2. Akademik Disipline Uygun

- Out-of-sample test (görmediği veride sınama)
- Bonferroni + Benjamini-Hochberg multiple-test düzeltmesi
- Bootstrap %95 güven aralığı
- 8.500 maçlık simülasyon

### 3. Dürüstlük

Sonuçlar hem **olumlu** hem **olumsuz** raporlanıyor:
- ✅ TRIVOX 5/5 yıl pozitif, EUVOX 4/5
- ⚠️ TRIVOX outlier-dependent (kazançlar büyük tutuşlarda yoğun)
- ⚠️ %20 vergi senaryosunda EUVOX marjı incelir
- ⚠️ Bonferroni geçemiyor (B-H FDR ile 4 bulgu anlamlı)

### 4. Risk-Bilinçli

- Maksimum bahis: Kelly Half formülü ile bankrollu koruyarak
- Compound vs Flat stake seçenekleri
- Kayıp serileri için uyarı sistemi

---

## ❓ SORULAR

### "Garanti mi?"

**Hayır.** Backtest 4 sezonda pozitif, ama gelecek garantili değildir.
"Kesin %38 kazanırsın" demiyoruz. **Beklenen değer** veriyoruz.

### "Ne zaman zarar ederim?"

- Kayıp serileri 14 kupona kadar uzayabilir (TRIVOX'ta)
- Drawdown 14K (TRIVOX) ile 35K (EUVOX) arası
- Bu rakamlar 4 sezon backtest'in **en kötü** durumları

### "Kanıt ne?"

- 4-5 sezon × 6 lig = 8.500+ maç simülasyon
- 20 smoke test her iki model için
- Benjamini-Hochberg FDR ile 4 bulgu istatistiksel anlamlı
- Tüm kod ve veri **açık** (incelenebilir)

### "Ne kadar para gerek?"

| Senaryo | Bütçe | Beklenen Aylık Net |
|---|---|---|
| Test (1 kupon/hafta) | 5K TL | +875 TL (TRIVOX) |
| Orta (2-3 kupon/hafta) | 20K TL | +1.960 TL (EUVOX) |
| Yatırım hacmi | 50K+ TL | EUVOX hibrit, +3-5K TL |

---

## 🎯 NEDEN YATIRIM YAPMALI?

### Akıllı Bahis Asistanı Bir Üründür

Diğer kupon servisleri "uzman tahmin" satar — bu **algoritmik**, denetlenebilir,
şeffaf bir motor sunar.

### Pazar Büyük

- Türkiye iddaa pazarı yıllık ~50 milyar TL hacim
- Sadece %0.001'i = 500 bin TL yıllık potansiyel
- 100 kullanıcı × 1000 TL/ay abonelik = +100K TL aylık gelir
- 1000 kullanıcı için 10x daha fazla

### Defansif Yetenek

- Bilim-tabanlı: rekabet için yüksek bariyer
- Veriye dayalı: zamanla iyileşen sistem (yeni veriler eklendikçe)
- Şeffaflık: kullanıcı kararı kendi verir, biz kanıt sunarız

### Çıkış Stratejileri

- B2C abonelik modeli (1000 TL/ay TRIVOX, 3000 TL/ay EUVOX)
- B2B API entegrasyonu (bahis siteleri kendi kullanıcıları için)
- Lisanslama (model + altyapı diğer pazarlara)

---

## 🚀 NASIL YATIRIM YAPILIR?

### Adım 1: Anla

Bu doküman ve `MODEL_v1_2_FINAL.md` raporunu oku.
Tüm test sonuçları ve risk profili açık.

### Adım 2: Test Et

- Streamlit web arayüzü üzerinden 1-2 hafta **küçük stake** ile dene
- TRIVOX modu (500-1000 TL bankroll, 50 TL/kupon)
- Kendi kararınla başla, model sadece **öneri** verir

### Adım 3: Ölçeklendir

Validate ettikten sonra:
- TRIVOX → 1000 TL/kupon
- EUVOX → 1000 TL/kupon × 2-3 lig

### Adım 4: Yatırım Yap

Eğer ürün modeline yatırım yapmak istersen:
- Şu an pre-revenue (henüz canlı kullanıcı yok)
- 4-8 haftalık live shadow run sonrası beta launch
- İlk yatırımcılar 1. çevrede özel şartlarla

---

## 📞 İLETİŞİM & SONRAKİ ADIM

Bu ürün **bilimsel bir araştırma projesinin meyvesidir**. Beta için:

1. **Replikasyon test** — 2025-26 sezonu Mayıs'ta biter
2. **Live shadow run** — 4-8 hafta canlı veriyle doğrulama
3. **Beta launch** — Yaz 2026
4. **Public** — Sonbahar 2026 (yeni sezon başı)

---

## ⚠️ ÖNEMLİ UYARILAR

1. **18 yaş altı için değildir.** Yasal bahis yaşı +18.
2. **Bahis bağımlılığı** ciddi bir sorundur. Sınırlı bütçeyle başlayın.
3. **Tüm yatırımlar risk içerir.** Geçmiş performans gelecek garantisi değildir.
4. **Türkiye'de yasal bahis sadece iddaa.com üzerinden yapılır.**
5. Backtest sonuçları gerçek paranın olmadığı simülasyonlardır. Live performans farklı olabilir.

---

## 🎓 ÖZ

> "İki motor, iki strateji. Türkiye'ye derinlemesine veya 6 lige geniş.
> Veri konuşur, bilim disipline eder, model adapte olur. Sezgi yerine matematik."

**TRIVOX:** Selektif, yüksek-ROI, düşük-volume.
**EUVOX:** Geniş kapsam, orta-ROI, yüksek-volume.

İkisi de aynı ortak temele dayanır: **3 bağımsız sinyal konsensüsü**.

Bu duyulması gereken sestir.

---

**Teknik detay için:** `RAPOR/MODEL_v1_2_FINAL.md`
**Akademik özet için:** `RAPOR/YONETICI_OZETI_v5.md`
**Kod incelemesi:** `03_MODELLER/selective/trivox_v1.py` + `euvox_v1.py`
