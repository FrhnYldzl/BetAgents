# İDDİA KURALLARI + KUPON TEKNİKLERİ — Teknik Referans

**Tarih:** 2026-05-28
**Amaç:** AI Trader Destek modelinin "iddia mekaniğini" tam anlaması için
**Bağlam:** Digital Twin Trader projesi — Trader'ın yanında olan AI

---

## 1) İDDİA TÜRLERİ (TÜRKİYE)

### A) Tek Bahis (Single Bet / K=1)
- 1 maç, 1 pazar, 1 yön
- Kupon kazanır = pick doğru olursa
- Stake × odd = kazanç (vergi öncesi)
- Min stake: 1 TL, Max stake: dinamik (limit yenme noktası)

**AI Trader örneği:**
```
Pick: Liverpool 1 @ 1.55
Stake: 500 TL
Kazanırsa: 500 × 1.55 = 775 TL gross
Vergi: (775 − 500) × %10 = 27.5 TL
Net kazanç: 747.5 TL → 247.5 TL kâr
Kaybederse: -500 TL
```

### B) Kombine Bahis (Combination / K≥2)
- 2+ leg (maç + pazar), tüm bacaklar tutmalı
- Kombo odd = Π(legs) ; her leg odd'unun çarpımı
- **Tüm bacaklar tutarsa** kazanır; bir tanesi bile yanlışsa → tüm kupon kayıp
- Vergi: kombi kazancı 66,935 TL üstüyse %20 stopaj eklenir

**Vergi dilim kuralı (2026):**
```
İkramiye        Vergi
< 6,935 TL      %0 (muafiyet alt sınırı)
6,935 - 66,935  %10 stopaj
> 66,935        %20 stopaj (+ önceki dilim)
```

**AI Trader örneği (K=3):**
```
Pick 1: Liverpool 1 @ 1.55  (Q5+a2)
Pick 2: Real Madrid 1 @ 1.45 (Q5+a2)
Pick 3: Galatasaray 1 @ 1.85 (Q4)

Kombo odd: 1.55 × 1.45 × 1.85 = 4.16
Stake: 500 TL
Kazanırsa: 500 × 4.16 = 2,080 TL (vergisiz dilim)
Vergi: (2,080 − 500) × %10 = 158 TL
Net: 1,922 TL → 1,422 TL kâr
Kaybederse: -500 TL

UYARI:
Tüm picks bağımsız varsayımıyla:
P(hepsi tut) = 0.78 × 0.78 × 0.65 = 39.5%
ROI tahmini: 39.5% × 1,422 - 60.5% × 500 = 561.7 - 302.5 = +259.2 TL
ROI per stake: +%52 (in-sample backtest tahmini)
```

### C) Sistem Bahis (System Bet)

Türkiye'de **n/m sistem** formatı:
- n = minimum doğru tahmin sayısı
- m = toplam maç sayısı

**2/3 SISTEM** (3 maç, en az 2'si tut):
```
3 maç seçilir: A, B, C
C(3,2) = 3 farklı 2'li kombin oluşur:
  Kupon 1: A + B
  Kupon 2: A + C
  Kupon 3: B + C
Toplam stake: 3 × tek_kupon_stake

Eğer 3'ü de tutarsa: 3 kupon kazanır (max payoff)
Eğer 2'si tutarsa: 2 kupon kazanır (kısmi)
Eğer 1'i tutarsa: 0 kupon kazanır (full loss)
Eğer 0'ı tutarsa: 0 kupon kazanır (full loss)
```

**3/4 SISTEM** (4 maç, en az 3'ü tut):
```
C(4,3) = 4 farklı 3'lü kombin
Toplam stake: 4 × tek_kupon_stake
- 4'ü tutar: 4 kupon kazanır
- 3'ü tutar: 3 kupon kazanır
- 2'si tutar: 0 kupon
- 1'i tutar: 0 kupon
```

**2/4 SISTEM** (4 maç, en az 2'si tut):
```
C(4,2) = 6 farklı 2'li kombin
Toplam stake: 6 × tek_kupon_stake
- 4'ü tutar: 6 kupon kazanır
- 3'ü tutar: 3 kupon kazanır
- 2'si tutar: 1 kupon kazanır
- 1'i veya 0'ı tutar: 0 kupon
```

**Matematiksel Karşılaştırma (Q5+a2 picks, p=0.78):**

| Strateji | Stake | E[kazanç] | E[kayıp] | σ (varyans) | EV |
|---|---|---|---|---|---|
| 3 ayrı K=1 | 1500 | %78×3×900 | %22×3×500 | yüksek | +%4 |
| K=3 kombin | 500 | %47×2080 | %53×500 | çok yüksek | +%51 |
| 2/3 sistem | 1500 | karışık | düşük | **düşük** | +%4-5 |
| 3/3 sistem (=K=3) | 500 | %47×2080 | %53×500 | çok yüksek | +%51 |

**Sistem Bahsin Asıl Faydası:**
- **EV teorik olarak aynı** (no free lunch)
- **Ama varyans ÇOK düşük** → "tüm kayıp" senaryosu nadir
- Trader psikolojisi için kritik
- Düşük varyans → sürdürülebilir trading → daha fazla denemek için cesaret

### D) Canlı Bahis (Live / In-Play)
- Maç başladıktan sonra dinamik odds
- Hacim Türkiye'de %60-70 (büyük market)
- Bizim modelimiz pre-match — canlı için **şu an kapsam dışı**
- **V3 planı:** Bayesian update (pre-match → in-play prior güncelleme)

---

## 2) İDDİA PAZARLARI (5 ANA PAZAR)

### Pazar 1: Maç Sonucu (1X2) — MS
- 1 = Ev sahibi kazanır
- X = Beraberlik
- 2 = Deplasman kazanır
- **Marj (overround):** %5-8
- **Likitide:** En yüksek (her bahisçinin oynadığı)
- **Mevcut model gücü:** Yüksek (TRIVOX, DUOVOX vs.)

### Pazar 2: İlk Yarı Sonucu (İY)
- 1, X, 2 (ilk 45 dakika sonucu)
- Beraberlik (X) **çok yaygın** (~%40 ilk yarı), yüksek odd (1.95-2.10)
- **Marj:** %8-12 (daha gevşek piyasa)
- **Value alanı potansiyeli:** YÜKSEK
- **Mevcut model:** Yok — V2'de eklenecek (DC Poisson × 0.45 → İY proj)

### Pazar 3: Handikaplı Maç Sonucu (AH/HMS)
- Sanal handikap: H ev (−1), A dep (+1) gibi
- Türk iddaa'da genellikle ±0.5 ve ±1
- **Marj:** %4-7 (sharp piyasa, sharp bettor'lar burada)
- **Edge bulma:** Zor
- **Mevcut model:** Yok — V2'de eklenecek

### Pazar 4: Alt/Üst 2.5 Gol (A/Ü)
- Üst 2.5 = toplam gol ≥3
- Alt 2.5 = toplam gol ≤2
- **Marj:** %5-9
- **Likitide:** Yüksek
- **Bizim test sonucu (T11b):** Piyasa kalibre ama p_over 0.60-0.65 bandında %2.4 underestimate → **value var**
- **Mevcut model:** Kısmen (closing odds var, model yok) — V2'de eklenecek

### Pazar 5: Karşılıklı Gol (KG / BTTS)
- Var = her iki takım gol attı (≥1 / ≥1)
- Yok = en az bir takım gol atamadı
- **Marj:** %9-14 (yüksek!)
- **Value alanı potansiyeli:** ÇOK YÜKSEK
- **Mevcut model:** Yok — V2'de eklenecek

### Diğer Pazarlar (V3+)
- İY/MS (kombine ilk yarı + maç sonucu) — 9 outcome
- Alt/Üst 1.5, 3.5
- Tek/Çift (Tek toplam, Çift toplam)
- Takım gol Alt/Üst
- İlk gol kim atar
- Köşe sayısı, Kart sayısı, vs.

---

## 3) KORELASYON HARİTASI (V2 Çekirdek Kural)

5 pazar arasında **bağımsızlık varsayımı YANLIŞ**. Aynı maçta birden fazla pazar oynanırsa korelasyon yönetilmeli:

```
        MS-1  İY-1  AH-1  Üst2.5  KGVar
MS-1     1.0   0.70  0.65   0.30    0.20
İY-1     0.70  1.0   0.55   0.40    0.20
AH-1     0.65  0.55  1.0    0.30    0.20
Üst2.5   0.30  0.40  0.30   1.0     0.70
KGVar    0.20  0.20  0.20   0.70    1.0
```

### Kombin Kuralı (AI Trader Otomatik Kontrol)

**✅ İZİN VERİLEN (|r| < 0.4):**
- MS + KG (r=0.20)
- MS + Üst 2.5 (r=0.30)
- AH + Üst 2.5 (r=0.30)
- MS + İY-X (r=-0.20)

**❌ YASAK (|r| ≥ 0.4):**
- MS-1 + İY-1 (r=0.70) → çift bahis
- MS-1 + AH-1 (r=0.65) → çift bahis
- Üst 2.5 + KG Var (r=0.70) → çift bahis
- İY + AH (r=0.55) → çift bahis

### AI Trader Korelasyon Uyarısı (Örnek)

**Trader:** "Liverpool 1 + Liverpool 1.yarı 1 kombine yapayım?"

**AI Trader:**
> "**UYARI:** MS-1 ve İY-1 korelasyonu %70. Kombo odd 1.55 × 2.10 = 3.26 görünüyor, ama gerçek 'bağımsız' kombo ~2.50 olmalı. Bu kuponla overpaying yapıyorsun. Önerim:
> - Tek bahis MS-1 (Q5+a2): 500 TL @ 1.55
> - Veya İY-1 ayrı 100 TL @ 2.10 (denemek için)
> - Kombin yapma, çift bahisi olur."

---

## 4) KALDIRAÇ (Pozisyon Mantığı)

Türkiye iddaa'da **resmi kaldıraç yok** ama AI Trader pozisyon büyüklüğü ile **etkili kaldıraç** uygular:

```
TRADER PROFILE: Bankroll 10,000 TL, max %5 single bet

GÜVEN SEVİYESİ → POZİSYON ÇARPANI
─────────────────────────────────
Q5+agree2 (ULTRA)    : 5x (500 TL)  ← bankroll %5
Q5+agree1 (BÜYÜK)    : 3x (300 TL)  ← bankroll %3
Q4 (STANDART)        : 1x (100 TL)  ← bankroll %1
Q3+agree2 (KÜÇÜK)    : 0.5x (50 TL) ← bankroll %0.5
Q3+agree1 (MİNİMAL)  : 0.25x (25)   ← bankroll %0.25
Q1-Q2 (PAS)          : 0            ← oynama
```

### Dynamic Kelly (V2 Implementation)

Klasik Kelly formula:
```
f* = (p × b - q) / b
  p = win probability
  q = 1 - p
  b = decimal odds - 1
```

Half-Kelly (güvenli yarı):
```
stake = bankroll × 0.5 × f*
```

**AI Trader Kelly Örneği:**
```
Liverpool 1 @ 1.55
Model p (Q5+a2): 0.78
b = 1.55 - 1 = 0.55
f* = (0.78 × 0.55 - 0.22) / 0.55 = 0.40 (yani %40 of bankroll!)

ÇOK YÜKSEK — Kelly tam uygulanırsa overconfident.
Half-Kelly: 0.20 → 2,000 TL (still high)
Quarter-Kelly: 0.10 → 1,000 TL (makul)

AI Trader önerisi: %10 cap (1,000 TL max)
Eğer trader bunu kabul etmezse → %5 (500 TL) STANDART
```

---

## 5) İDDİA OPERASYONEL KISITLAR

### Max Stake / Maç (iddaa.com)
- 1X2 ana pazarda: ~5,000-10,000 TL tek kuponda
- Niş pazarlarda: ~1,000-3,000 TL
- Limit yenirse hesap kısıtlı

### Limit Yenme Riski (Pratikçi Bahisçi Gerçeği)
- Sistemli pozitif EV oyuncusu → 30-60 günde limit
- Belirti: max-stake düşer, tek-pazar kısıtlanır, hesap "kontrol altında"
- **AI Trader stratejisi:**
  - Stake variation (sabit değil)
  - "Lottery" picks ekleme (görüntü için, %5 stake)
  - Multi-account (etik gri alan, kullanıcı kararı)

### Tax Optimizasyonu (Yeniden)
- Tek kupon ikramiye 66,935 TL altında kalmaya çalış
- TRIVOX K=1 ortalama 1.65 odd → stake 40K altında olursa safe
- K=3 kombin riskli: 500 × 8 = 4,000 TL safe, ama 500 × 50 = 25,000 TL hala safe
- K=4+ veya yüksek tek-leg odd ile dikkat

### Lisans / Yasal (Sadece Bilgi)
- 7258 sayılı kanun: yurtdışı bahis yasal değil
- iddaa.com (Spor Toto) tek yasal kanal
- AI Trader iddaa.com format'a uyumlu önerir
- B2C ticarileştirme yasal mayın — kapsam dışı

---

## 6) AI TRADER İŞLEM TANIMI

### Karar Akış Şeması

```
[1] HAFTA AÇILDI
     ↓
[2] 5 MODEL × 5 PAZAR × N MAÇ = adaylar
     ↓
[3] Her aday için: Q-quintile + agree_count + Kelly
     ↓
[4] FİLTRE: Q5+a2 (ULTRA), Q5+a1 (BÜYÜK), Q4 (STANDART)
     ↓
[5] Korelasyon kontrol: aynı maç birden fazla pazar?
     ↓
[6] Stake hesaplama: Dynamic Kelly × profile
     ↓
[7] Kupon strateji optimize:
     a) Tek bahis K=1 (sniper)
     b) Kombine K=2-3 (cesaret)
     c) Sistem 2/3 veya 3/4 (varyans düşürme)
     ↓
[8] EV + max stake check
     ↓
[9] Trader'a 3 SEÇENEK sun (A/B/C)
     ↓
[10] Trader seçer → bahis konur (manuel veya semi-auto)
     ↓
[11] Sonuç bekle → log
     ↓
[12] Learning: hit/miss + CLV güncellemesi
```

---

## 7) AI TRADER OPERASYONEL ÖRNEK (Bu Hafta Senaryosu)

```
═════════════════════════════════════════════════════════════════
HAFTA: 2026-09-12 / 2026-09-14
═════════════════════════════════════════════════════════════════

[Adaylar — Q5+a2 sinyalleri]
  1. Liverpool - Tottenham   MS-1 @ 1.55  Q5  agree=2  (MONOVOX-E0)
  2. Real Madrid - Betis     MS-1 @ 1.45  Q5  agree=2  (DUOVOX+MONOVOX-SP1)
  3. Galatasaray - FB        MS-1 @ 1.85  Q5  agree=2  (TRIVOX)

[Adaylar — Q5+a1 (STANDART)]
  4. Arsenal - Chelsea       MS-1 @ 1.70  Q5  agree=1
  5. Marseille - Lyon        A/Ü Üst @ 1.78 Q4  agree=2  (DUOVOX-A/Ü)

[Korelasyon Kontrol]
  ✓ 3 ALL-IN farklı maç, korelasyon yok
  ✓ Arsenal MS-1 ile A/Ü Üst: r=0.30, kombin OK
  ⚠ Liverpool MS-1 + Üst 2.5 var mı? Henüz yok, OK

[Strateji Seçenekleri]

  SEÇENEK A — Sniper Spread (3 ayrı K=1)
    Liverpool 1 @ 1.55 → 500 TL (ALL-IN)
    Real Madrid 1 @ 1.45 → 500 TL (ALL-IN)
    Galatasaray 1 @ 1.85 → 500 TL (ALL-IN)
    Toplam stake: 1500 TL
    Beklenen kazanç (Q5+a2 hit %78):
      E[3 tut] = 47% × (500×0.55 + 500×0.45 + 500×0.85)
              = 47% × 925 = +435 TL
      E[2 tut] = ~36% × 542 ortalama = +195
      E[1 tut] = ~14% × -300 = -42
      E[0 tut] = ~3% × -1500 = -45
    NET EV: +543 TL → ROI +%36 (in-sample)

  SEÇENEK B — Kombo K=3
    Liverpool 1 × Real Madrid 1 × Galatasaray 1
    Kombo odd: 1.55 × 1.45 × 1.85 = 4.16
    Stake: 500 TL
    Kazanırsa: 2,080 TL gross
    Vergi: 158 TL
    Net: 1,422 TL kâr
    P(3 tut): %47
    EV: 47% × 1,422 - 53% × 500 = +403 TL
    ROI per stake: +%81 (in-sample)
    Varyans: ÇOK YÜKSEK

  SEÇENEK C — Sistem 2/3
    3 maç, en az 2'si tut
    3 farklı 2'li kupon (2.25, 2.87, 2.68)
    Stake: 500 TL × 3 = 1500 TL
    Senaryolar:
      3 tut: 3 kupon kazan = 500×(2.25+2.87+2.68) = 3,900 TL
      2 tut: 1 kupon kazan = 500 × 2.5 = 1,250 TL
      1 tut: 0 kupon = -1500
      0 tut: 0 kupon = -1500
    P(3 tut): 47%
    P(2 tut): 36%
    P(1 tut): 14%
    P(0 tut): 3%
    EV: 47%×2,400 + 36%×(-250) + 14%×(-1500) + 3%×(-1500)
      = 1,128 + (-90) + (-210) + (-45)
      = +783 TL net
    ROI: +%52
    Varyans: ORTA (asla full loss değil, en az 2 tutarsa)

[AI Trader Önerisi]

  Karşılaştırma:
                     EV       Varyans    Max Kayıp
  Seçenek A          +543     ORTA       -1500
  Seçenek B          +403     YÜKSEK     -500 (ama %53 ihtimal)
  Seçenek C          +783     DÜŞÜK      -1500 (ama %17 ihtimal)

  Öneri: **SEÇENEK C (2/3 sistem)** — en yüksek EV + en düşük varyans.

  Trader confirm bekleniyor...
═════════════════════════════════════════════════════════════════
```

---

## 8) AI TRADER İŞLEM TANIMI — Özet

| Mod | Strateji | Frekans | Varyans |
|---|---|---|---|
| **SNIPER** | Tek bahis K=1, Q5+a2 | Ayda 5-7 | Düşük |
| **DAILY** | Tek bahis K=1, Q4-Q5 | Haftada 1-2 | Orta |
| **SİSTEM 2/3** | 3 maç sistem | Ayda 2-3 (Q5+a2 3+ aday) | Düşük |
| **KOMBO K=3** | 3-leg, korelasyonsuz | Çok nadir (Q5+a2 × 3) | Yüksek |
| **MULTI-MARKET** | Tek maç 2 pazar | Aydan 1-2 (V2 sonrası) | Orta |

---

## 9) İLK V2 ENTEGRASYON ADIMI

Bu doküman AI Trader'ın **kural seti**. Şimdi yapılması gereken:

1. **AI Trader Decision Engine kod** (Python modülü)
2. **Kupon Optimizer modülü** (A/B/C seçenek üretici)
3. **Korelasyon Matrix** (5 pazar)
4. **Telegram/WhatsApp notifier**

Bu mantık V2 inşaatının çekirdeği olmalı. Modeli iyileştirmek yetmez — **karar destek motoru** olmalı.

---

## 10) TEK SAYFA ÖZET

```
┌──────────────────────────────────────────────────────────────────┐
│            İDDİA MEKANİĞİ — AI TRADER KILAVUZ                    │
├──────────────────────────────────────────────────────────────────┤
│  Tek Bahis (K=1)      Sniper, en düşük varyans, Q5+a2 ideal       │
│  Kombine (K≥2)         Tüm bacaklar tutmalı, çarpık varyans        │
│  Sistem n/m            Min n doğru tut, varyans azaltıcı           │
│                                                                  │
│  Vergi                 Stake-ikramiye<6.9K: %0                    │
│                        İkramiye 6.9-66.9K: %10                    │
│                        İkramiye >66.9K: %20                       │
│                                                                  │
│  5 Pazar              MS, İY, AH, A/Ü, KG                         │
│  Niş Pazarlar         İY (%8-12), KG (%9-14) → value zengin       │
│  Korelasyon Kuralı    |r|<0.4 ise kombin OK                        │
│                                                                  │
│  Stake Çarpanı        Q5+a2:5x, Q5+a1:3x, Q4:1x, Q3:0.5x, Q1-2:0  │
│  Kelly Cap            %10 bankroll (Quarter-Kelly)                │
│  Dynamic Kelly        Drawdown %15+: ×0.5 ; %25+: PAS               │
│                                                                  │
│  Limit Yeme Risk      30-60 gün sistemli profit → uyarı            │
│  Multi-Account        Etik gri, trader kararı                       │
└──────────────────────────────────────────────────────────────────┘
```
