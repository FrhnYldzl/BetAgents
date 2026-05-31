# 05_RISK_YONETIMI — Bankroll, Kelly ve Limit Stratejisi

Bu klasör, bir bahisçinin canlı kaldığını belirleyen tek şeyi içerir: **risk yönetimi**.

> "Edge'in olmadan kaybedersin. Risk yönetimin olmadan yine kaybedersin." — Joseph Buchdahl

## Üç Katman

```
┌─────────────────────────────────────────────┐
│  1. BAHIS SEVIYESI (her bahis için)         │
│     - Kelly Criterion (fractional)          │
│     - Max stake cap                          │
│     - Edge filter (< %3 → bet etme)          │
└─────────────────────────────────────────────┘
                    ▼
┌─────────────────────────────────────────────┐
│  2. PORTFOLIO SEVIYESI (günlük/haftalık)    │
│     - Maksimum açık pozisyon                 │
│     - Korelasyon kontrolü                    │
│     - Sektör/lig çeşitlendirmesi             │
└─────────────────────────────────────────────┘
                    ▼
┌─────────────────────────────────────────────┐
│  3. SİSTEM SEVIYESI (bankroll + güvenlik)   │
│     - Drawdown stop-loss                     │
│     - Hesap limit yönetimi                   │
│     - Performance review tetikleri           │
└─────────────────────────────────────────────┘
```

## 1. Kelly Criterion (Fractional)

### Formül
```
f* = (b × p - q) / b

burada:
  f* = bankroll'un yatırılacak oranı
  b  = net oran (iddaa_odds - 1)
  p  = modelin kazanma olasılığı
  q  = 1 - p
```

### Örnek
- iddaa oran: 2.50 → b = 1.50
- Model olasılığı: %45 → p = 0.45, q = 0.55
- f* = (1.50 × 0.45 - 0.55) / 1.50 = 0.083 = **bankroll'un %8.3'ü**

### Neden FRACTIONAL Kelly?
- Tam Kelly matematiksel olarak optimal ama **drawdown'ı korkunç**.
- 0.25x Kelly:
  - Beklenen büyüme: tam Kelly'nin %75'i
  - Drawdown: tam Kelly'nin yarısından az
- **Anlaşma:** Daima 0.25x (quarter) Kelly. Bazı çevreler 0.5x kullanır ama bizim modelimiz daha yeni → konservatif.

### Ek Filtreler
- `f* < 0.005` → bet etme (komisyon yutuyor)
- `f* > 0.05` → 0.05'e cap'le (model fazla agresif, varyans yutar)
- Edge < %3 → bet etme (model hatası varyansı kapatamaz)

## 2. Portfolio Kuralları

### Korelasyon
Aynı maçta birden fazla bahis tehlikelidir:
- **"KG var" + "Üst 2.5"** — yüksek korelasyon (her ikisi gol bekler)
- **"Ev Sahibi Galip" + "Ev Sahibi -1 Handikap"** — yüksek korelasyon

Kural: Aynı maçta max **1 ana bet + 1 düşük-korelasyon ek bet**.

### Kombine (Akümülatör) Bahisler
**Genel kural: KOMBINE YAPMA.**

Neden:
- iddaa'nın margin'i kombine'de katlanır (her leg %6-12 margin)
- Varyans katlanır
- Tek leg yanlış → tüm kupon ölür
- iddaa'nın yüksek oran kuponlara verdiği bonusa rağmen, beklenen değer çoğunlukla negatif

İstisna: **Bonus eşiği** civarında yapılırsa ve her leg bağımsız EV+ ise hesaplanabilir.

### Günlük Limit
- Toplam açık pozisyon < bankroll'un %10'u
- Günlük max kayıp limiti: bankroll'un %5'i
- 5 ardışık kaybedilen gün → 1 hafta ara, model review

## 3. Sistem Seviyesi Güvenlik

### Drawdown Stop-Loss
| Bankroll kaybı | Aksiyon |
|---|---|
| -%10 | Uyarı, log review |
| -%15 | Stake yarıya in (Kelly carpani 0.25 → 0.125) |
| -%20 | DUR. Model review zorunlu. |
| -%30 | Projeyi durdur, üst düzey gözden geçir |

### iddaa Hesap Limit Stratejisi
iddaa Madde 6/6 sistematik kazanana limit yetkisi veriyor. Riski azaltmak için:
1. **Bet pattern çeşitlendir** — sadece value bet değil, bazen popüler maçlara da bet (mimari koruma)
2. **Stake boyutu sabit görünsün** — Kelly'yi yuvarla (örn 50, 100, 150₺ gibi)
3. **Pazar çeşitlendir** — sadece Alt/Üst değil, farklı pazarlar
4. **Çoklu hesap ETIK SORU** — bayi nezdinde 1 kişi 1 hesap ilkesi var; bu yola sapmıyoruz

### Performance Tetikleri
| Sinyal | Tetik |
|---|---|
| 100 bet sonu CLV < %0 | Model yön doğruluğu yok → revize |
| 200 bet sonu ROI < -%5 | Stratejiyi durdur |
| 50 ardışık bet drawdown > %15 | Pazar değişmiş olabilir → re-train |
| Tek günde 5+ value bet bulundu | Şüphelen — model muhtemelen yanlış kalibre |

## Klasör Yapısı (Planlanan)

```
05_RISK_YONETIMI/
├── kelly_calculator.py
├── bankroll_tracker.py
├── correlation_matrix.py        (bahisler arası korelasyon)
├── drawdown_monitor.py
├── risk_dashboard.py            (gerçek zamanlı görsel panel)
└── safety_rules.yaml            (tüm limit eşikleri tek dosyada)
```

## Altın Kurallar (Ezbere)

1. **Edge'in büyüklüğü kadar bet, hissin kadar değil.**
2. **Kazanç streak'i şanstır, kayıp streak'i de.** Hareket etme.
3. **Bankroll = paranın değil, kararlarının ölçüsü.**
4. **Soğukkanlılığı kaybettiğin gün, edge'i kaybedersin.**
5. **Her bahisi defterle. Hafızanda değil.**
