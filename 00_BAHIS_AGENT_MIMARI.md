# BAHİS AGENT — Mimari ve Yaklaşım Dokümanı

**Proje:** İddaa için kantitatif (Jim Simons tarzı) bahis karar destek sistemi
**Hedef:** iddaa.com üzerinde uzun vadede pozitif beklenen değer (EV+) üreten kararlar
**Kaynak Kural Dokümanı:** `../iddaa-oyun-kurallari.pdf` (77 madde)
**Tarih:** 2026-05-26
**Versiyon:** v0.1 (mimari taslak)

---

## 1. Gerçeklik Kontrolü (Atlanmamalı)

Bu proje "her hafta katlanan kupon" değil, "uzun vadede pozitif beklenen değer üreten karar makinesi" inşa etme çabasıdır.

### Beklenti Kalibrasyonu

| Gerçek | Sonuç |
|---|---|
| Renaissance Medallion %66 brüt getirdi — ama hisse piyasası ≠ spor bahisleri | Beklentiyi düşür |
| iddaa overround (margin) maç başına ~%6-12 | Fair odds'tan %6-12 düşük oranlar veriliyor |
| Profesyonel quant bettors %3-7 ROI hedefler (bet hacmi üzerinden, yıllık değil) | 100.000₺ çevirirsen ~5.000₺ net beklenti |
| Edge'in gerçek mi şans mı olduğunu anlamak için 1000+ bet lazım | İlk 100 bette her şey olabilir, panik yapma |
| iddaa Madde 6/6 ve 11/12: sistematik kazanana kısıt yetkisi var | Limit yeme riski gerçek — hesap stratejisi gerekli |

### Gerçekçi Yıllık Getiri Beklentisi

| Profil | Bet hacmi üzerinden ROI | 10.000₺ bankroll → yıllık net |
|---|---|---|
| Amatör | -%10 | -1.000 ile -3.000₺ |
| Disiplinli amatör (no edge) | -%6 | ~-600₺ |
| Marjinal sharp | +%2-3 | +500-1.500₺ |
| Sharp bettor | +%5-7 | +2.500-7.000₺ |
| Üst düzey sharp (Pinnacle seviyesi) | +%8-12 | +8.000-15.000₺ |

**Sonuç:** 10x katlamıyoruz. Edge ortaya çıkarıyor, varyansla yaşıyor, disiplinle banka ediyoruz.

---

## 2. iddaa Kural Setinden Çıkan Quant-Kritik Noktalar

PDF'in 77 maddesini quant açıdan tarayınca öne çıkanlar:

### 2.1 Oran 1.00'a (iade) çekilen durumlar — risk hesabında kritik
- Madde 11/22: doğrulanamayan bahisler → 1.00
- Madde 11/23: programdan önce başlayan maçlar → 1.00
- Madde 11/25: Risk Yönetim Merkezi takdiri → 1.00
- Madde 14/20: maç ertelenip ertesi gün oynanmazsa → 1.00
- Madde 14/31: kombo'da ertelenen maç → o leg 1.00, diğerleri yanlışsa kupon kaybeder
- **Quant sonuç:** Kombine kuponlarda "bir leg iade olursa diğer legler tutsun" beklentisi yanlıştır. Tek leg yanlışsa kupon kaybeder.

### 2.2 Risk Yönetim Merkezi'nin Yetkileri
- Madde 7/1: gerekçe göstermeksizin bahisi reddetme yetkisi
- Madde 6/5-6: şüpheli/kötü niyetli oyuncuya kısıt/limit getirme yetkisi
- Madde 5/6: oranları herhangi bir zamanda değiştirme yetkisi
- Madde 10/8-9: maksimum ikramiye limiti var (bahis tipi ve bilet başına)
- **Quant sonuç:** Sistematik kazanan oyuncu profili çizmemek için bet pattern çeşitlendirilmeli (sadece value bet değil, bazen normal popülerlik gösteren bet'ler de)

### 2.3 Minimum Bahis Sayısı (MBS) — Madde 5/7
- Varsayılan minimum 4 bahis
- Başbayi daha düşük sayı için yetkili
- **Quant sonuç:** Tek-bahis (single) opsiyonu varsa onu kullanmak değişkenliği düşürür

### 2.4 Quant-Friendly Bahis Türleri
PDF'i tarayınca kantitatif modellemeye en uygun pazarlar:

| Madde | Pazar | Quant uygunluğu |
|---|---|---|
| 14/22 | Futbol Toplam Gol Alt/Üst | ⭐⭐⭐⭐⭐ Dixon-Coles için ideal |
| 14/21 | Karşılıklı Gol | ⭐⭐⭐⭐⭐ xG modelleri çok iyi |
| 14/13 | Handikaplı Sonuç | ⭐⭐⭐⭐ Sharp piyasa |
| 14/37 | Toplam Korner | ⭐⭐⭐⭐ Daha verimsiz pazar, edge yüksek |
| 14/34 | Toplam Kart | ⭐⭐⭐ Hakem datası önemli |
| 14/55-56 | Oyuncu propları | ⭐⭐⭐⭐⭐ En yüksek edge |
| 18/x | Tenis (özellikle Challenger seviye) | ⭐⭐⭐⭐ Verimsiz pazar |
| 15/x | Basketbol pace/total | ⭐⭐⭐⭐ |

---

## 3. BAHİS AGENT Pipeline Mimarisi

```
┌─────────────────────────────────────────────────────────────┐
│                    BAHIS AGENT PIPELINE                      │
└─────────────────────────────────────────────────────────────┘

[1] DATA LAYER                    [2] FEATURE ENGINEERING
    ├─ iddaa.com oranları             ├─ Elo ratings
    ├─ Understat (xG)                 ├─ Form (son N maç ağırlıklı)
    ├─ FBRef (istatistik)             ├─ H2H ev/dep
    ├─ SofaScore (lineup,             ├─ xG için/aleyhte rolling
    │   injury, hakem)                ├─ Rest days, travel
    ├─ OddsPortal (closing line)      ├─ Hava durumu, saha
    └─ Hava durumu (OpenMeteo)        └─ Lineup gücü (FotMob rating)
              │                                  │
              ▼                                  ▼
[3] PROBABILITY MODEL (ENSEMBLE)
    ├─ Dixon-Coles (bivariate Poisson, futbol skor)
    ├─ Elo + logistic regression (1X2)
    ├─ xG-based Poisson (Alt/Üst, KG var/yok)
    └─ Gradient Boosting (LightGBM) meta-learner
              │
              ▼
[4] FAIR ODDS HESABI
    p_model = 0.52  →  fair_odds = 1/0.52 = 1.923
              │
              ▼
[5] EDGE DETECTION (Value Bet Filter)
    iddaa_odds = 2.10
    edge = (iddaa_odds × p_model) - 1 = 0.092 (%9.2 EV+)
    KOŞUL: edge > %3 VE p_model güven aralığı dar
              │
              ▼
[6] KELLY SIZING (Fractional Kelly, 0.25x)
    bet_size = bankroll × 0.25 × (edge / (odds - 1))
              │
              ▼
[7] PORTFOLIO CONSTRUCTION
    ├─ Tek maç tek kupon (NOT kombine — varyansı patlatır)
    ├─ Maksimum günlük risk: bankroll %3-5
    └─ Korelasyon kontrolü (aynı maçta KG var + Üst 2.5 → korele)
              │
              ▼
[8] EXECUTION & LOGGING
    ├─ Her bahisi kaydet: tarih, oran, p_model, iddaa_odds, edge
    ├─ CLV takibi (Closing Line Value): kapanış oranını yendin mi?
    └─ Aylık review: ROI, Sharpe-equivalent, drawdown
```

---

## 4. Matematiksel Çekirdek

### 4.1 Dixon-Coles Modeli (Futbol için)

Klasik Poisson maç sonucu modelinin geliştirilmiş hali. Düşük skorlu maçlarda (0-0, 1-0, 0-1, 1-1) görülen istatistiksel sapmaları düzelten `τ` parametresi ekler.

```
λ_home = exp(α_home + β_away + γ)   # ev sahibinin gol beklentisi
λ_away = exp(α_away + β_home)        # deplasman gol beklentisi

P(home=i, away=j) = τ(i,j) × Poisson(i; λ_home) × Poisson(j; λ_away)
```

Burada:
- `α`: takımın hücum gücü
- `β`: takımın savunma gücü
- `γ`: ev sahibi avantajı
- `τ`: düşük skor düzeltme faktörü

### 4.2 Kelly Criterion (Fractional)

```
f* = (b × p - q) / b
```

- `f*`: bankroll'un yatırılacak oranı
- `b`: net oran (iddaa_odds - 1)
- `p`: modelin tahmin ettiği kazanma olasılığı
- `q`: 1 - p

**Önemli:** Tam Kelly çok agresif. **0.25x Kelly (quarter Kelly)** kullan — drawdown'ı yarıdan fazla düşürür, beklenen getiri sadece %25 azalır.

### 4.3 Closing Line Value (CLV)

Uzun vadeli karlılığın en güvenilir erken sinyali. ROI'dan ÇOK daha hızlı yakınsar.

```
CLV = (oran_aldığında / kapanış_oranı) - 1
```

- CLV > 0 → senin bahsi koyduğun andaki oran, maç başlangıcındaki orandan daha iyiydi → piyasa sana doğru hareket etti → tahmin yönün doğru
- 100 bet'te ortalama CLV > %2 → uzun vadede karlı olma ihtimalin %90+

---

## 5. Veri Kaynakları

| Kaynak | Veri | Erişim |
|---|---|---|
| **iddaa.com** | Anlık oranlar, açılış oranları | Web scrape (dikkat: ToS) |
| **Understat** | xG, xA, shot maps (Avrupa 5 büyük lig) | Ücretsiz, scrape kolay |
| **FBRef** | Detaylı maç istatistikleri, oyuncu data | Ücretsiz, scrape |
| **SofaScore** | Lineup, sakatlık, hakem, canlı veri | API yarı-açık |
| **Football-Data.co.uk** | Tarihsel sonuçlar + oranlar (15+ sezon) | Ücretsiz CSV |
| **OddsPortal** | Çoklu bahis sitesi oran karşılaştırma | Scrape |
| **Pinnacle API** | Sharp piyasa oranı (referans) | API (kısıtlı) |
| **OpenWeatherMap** | Hava durumu | Free tier |
| **FotMob** | Oyuncu rating, lineup gücü | Scrape |

---

## 6. Çıkış Şartları (Bilimsel Disiplin)

Agent şu durumlarda ALARM verir veya DURAR:

| Durum | Aksiyon |
|---|---|
| Bankroll'un %20'si kayboldu | Sistem durur, model review zorunlu |
| 50 bet sonunda CLV < 0 | Modelin yön doğruluğu yok → revize |
| Edge < %3 hesaplandı | Bet koyma — varyans EV'yi yutar |
| iddaa hesabına limit geldi | Çeşitlendirme stratejisi devreye |
| Aynı gün 5+ value bet bulundu | Şüphelen — model muhtemelen yanlış kalibre |

---

## 7. Yasal ve Etik Notlar

- iddaa.com Türkiye'de Spor Toto Teşkilatı tarafından lisanslı, **yasal** bir platformdur
- 18 yaş altı katılım yasaktır (Madde 6/1)
- Kumar bağımlılığı riski gerçek — bu sistem **disiplinli karar destek aracıdır**, kumar tetikleyici değil
- Maç sabitleme, içeriden bilgi vb. ASLA kullanılmaz — sadece açık veri ve istatistiksel modelleme

---

## 8. Sonraki Adımlar

Geliştirme öncesi cevap bekleyen kalibrasyon soruları (bir önceki konuşmadan):

1. **Bankroll seviyesi** — Kelly sizing için kritik
2. **Pazar odağı** — futbol Alt/Üst mü, korner mü, oyuncu propu mu?
3. **Zaman taahhüdü** — günlük yarı-otomatik mi, tam otomasyon mu?
4. **İlk adım önceliği:**
   - MVP pipeline (1 lig için end-to-end)
   - Backtesting altyapısı önce
   - Akademik literatür özeti
   - Risk yönetimi sistemi önce

---

## 9. Klasör Yapısı (Planlanan)

```
YAZILIM/
├── 00_BAHIS_AGENT_MIMARI.md       (bu dosya)
├── 01_LITERATUR/                   (akademik kaynaklar, paper özetleri)
├── 02_VERI/                        (veri kaynakları, scraper'lar)
├── 03_MODELLER/                    (Dixon-Coles, Elo, xG modelleri)
├── 04_BACKTEST/                    (geçmiş veri ile test)
├── 05_RISK_YONETIMI/               (Kelly, bankroll, limit stratejisi)
├── 06_PRODUCTION/                  (canlı sistem kodu)
└── 07_LOG_VE_RAPORLAR/             (bet geçmişi, CLV takibi)
```
