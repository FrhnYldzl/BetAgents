# YOL HARİTASI — 3 EKSEN: DATA · MODEL · TRADE

**Tarih:** 2026-06-03
**Bağlam:** Sistem canlı, otonom (paper), Railway 24/7, PostgreSQL. 19.315 maç · 6 lig · 2017-2025.
**Amaç:** Veri (derinlik+genişlik+kalite), model ve trade uygulamasını *anlamlı* şekilde geliştirmek.

---

## 0) PUSULA — neden her şey CLV'ye bağlanmalı

Bu sezon **kanıtladık**: model kapanış oranlarına karşı **~0/negatif edge**. Naive xG modeli
kapanışı yenmedi. Yani:

- Sorun **veri HACMİ değil** → daha çok lig/satır eklemek tek başına edge getirmez.
- Tek dürüst ölçüt = **CLV** (girdiğimiz oran vs. kapanış oranı). +CLV = uzun vadede kâr;
  −CLV = ne kadar P&L iyi görünse de şanstır.
- **P&L gürültülü, CLV hızlı yakınsar.** 2-4 haftada CLV bize "edge var mı yok mu"yu söyler;
  P&L'in aynı şeyi söylemesi aylar/binlerce bahis alır.

> **Kural: Her geliştirme tek soruyla yargılanır — "CLV'yi pozitife taşıyor mu?"**
> Taşımıyorsa cila, taşıyorsa altın.

Bu yol haritası 3 ekseni bu pusulaya bağlar ve tek bir **KAPI**ya kilitler.

---

## EKSEN 1 — DATA (derinlik · genişlik · kalite)

Felsefe: **integrity-first, edge-relevant depth, selective breadth.** Genişlik en düşük öncelik.

### 1A — KALİTE (önce bütünlük) ⭐ yüksek ROI, düşük maliyet
| İş | Çıktı | Neden |
|---|---|---|
| **Data-quality scorecard** | lig×sezon×kolon doluluk + anomali skoru tablosu (UI'da "Veri Kalitesi" sayfasını besler) | tek bakışta nerede çürük olduğunu gör |
| **Leak-free garantisi testi** | rolling rating/feature üretiminde "gelecek sızıntısı yok" otomatik testi | backtest yalanını önler (en sinsi hata) |
| **Cross-source audit** | Football-Data ↔ (Mackolik/Sofascore örneklem) skor/oran tutarlılık kontrolü | tek-kaynak riskini kır |

### 1B — DERİNLİK (edge ile ilgili olan) ⭐⭐ asıl yatırım
| İş | Çıktı | Neden |
|---|---|---|
| **Kapanış-oranı snapshot pipeline** | her maç için açılış→kapanış oran zaman serisi (timestamp'li) | **CLV'nin ham maddesi** — bu olmadan hiçbir şeyi ölçemeyiz |
| **T1 xG backfill** (FotMob/Sofascore) | T1 xG %30 → hedef %90+ | en büyük *model-relevant* boşluk; xG odds'tan daha "gerçek" sinyal |
| **Kadro + sakatlık** (#119) | maç-öncesi 11 + eksikler | kitabın *yavaş* fiyatladığı ortogonal bilgi = nadir gerçek edge kaynağı |
| **Hakem DB** (Mackolik) | referee %18 → tam | kart/korner niş pazarını açar |

### 1C — GENİŞLİK (seçici) ⚠️ en düşük öncelik
- Yeni lig EKLEME kuralı: **sadece** (a) xG/kadro alınabiliyorsa VE (b) pazar daha *yumuşaksa*
  (düşük likidite = daha az verimli = edge ihtimali). Top-5 Avrupa + T1 zaten en verimli pazarlar.
- Aday: alt ligler / daha az izlenen ligler — ama veri kalitesi düşer (denge).

---

## EKSEN 2 — MODEL

Felsefe pivotu: **"kitaptan daha iyi tahmin et" değil → "kitabın yanlış fiyatladığı yeri bul".**
Verimli pazarda daha iyi forecaster olmak zor (kanıtlandı). Edge nişlerde ve fiyat hatalarında.

### 2A — OBJEKTİF YENİDEN ÇERÇEVELEME ⭐⭐⭐ en kritik
| İş | Çıktı | Neden |
|---|---|---|
| **CLV backtest harness** | model seçimini accuracy/Brier yerine **CLV** üzerinden yargılayan test | "kazanan model" tanımını düzeltir |
| **Kalibrasyon → Kelly bağı** | Platt kalibre olasılık → fractional Kelly stake | kalibrasyon = doğru stake = hayatta kalma |

### 2B — NİŞ PAZAR UZMANLARI ⭐⭐ gerçek edge ihtimali burada
| İş | Çıktı | Neden |
|---|---|---|
| **Kart/korner modeli** | referee + takım stiliyle disiplin/korner üst-alt | yumuşak pazar, az model rekabeti |
| **İlk Yarı / AH uzmanı** | 1X2 dışı pazarlarda ayrı kalibrasyon | ana pazardan daha az verimli olabilir |

### 2C — ORTOGONAL SİNYALLER ⭐⭐
| İş | Çıktı | Neden |
|---|---|---|
| **Line-movement modeli** | açılış→kapanış drift = "sharp money" feature | hareketin yönü CLV'yi öngörebilir |
| **Disagreement skoru** | modelin kitapla *en çok ayrıştığı* maçlar + bu ayrışma CLV öngörüyor mu testi | edge'in nerede yoğunlaştığını bulur |
| **Kadro-ayarlı güç** | eksik oyuncuya göre takım rating düzeltme | 1B kadro verisini sinyale çevirir |

---

## EKSEN 3 — TRADE UYGULAMASI

Felsefe: uygulama bir **karar-destek + dürüstlük aynası** olmalı; gürültülü P&L'i değil
"çizgiyi yeniyor muyuz"u öne çıkarmalı.

### 3A — TRUTH METER (CLV dashboard) ⭐⭐⭐ uygulamadaki #1 ekleme
| İş | Çıktı | Neden |
|---|---|---|
| **Bahis başına CLV kaydı** | her paper-leg için: giriş oranı vs kapanış oranı → CLV% | sistemin gerçek karnesi |
| **CLV dashboard sayfası** | toplam/pazar-bazlı CLV dağılımı, +CLV oranı, trend | 2-4 haftada karar verdirir |
| **Journal zenginleştirme** | settle anında her bacağa CLV yaz | geriye dönük analiz |

### 3B — RİSK MOTORU ⭐⭐
| İş | Çıktı | Neden |
|---|---|---|
| **Fractional Kelly stake** | kalibre olasılık + bankroll → stake | düz 100 TL yerine matematiksel sizing |
| **Exposure + drawdown breaker** | gün/pazar maruziyet tavanı, kayıp serisinde duraklat (kısmen var) | ruin riskini kes |

### 3C — KARAR DESTEK + BACKTEST ⭐
| İş | Çıktı | Neden |
|---|---|---|
| **In-app backtest/replay** | strateji geçmişte koştur → equity curve, deploy öncesi | "canlıda öğrenme" maliyetini düşür |
| **Pick açıklanabilirliği** | her öneride: model prob · edge · line-movement · kalibrasyon güveni | neden-niçin şeffaf |
| **+CLV alarm** | yüksek-güven/+CLV fırsat çıkınca bildirim | fırsat kaçırma |

---

## FAZLAMA & TEK KAPI

```
KAPI (her şey buna kilitli):
  "Anlamlı örneklemde (≥150-200 bahis) CLV pozitif mi?"
   ├─ EVET, bir nişte → o nişe yüklen (2B), genişlet
   └─ HAYIR, her pazarda ≤0 → dürüst sonuç: verimli-pazar duvarı;
                                proje 'araştırma/eğitim' moduna geçer, kayıp büyütülmez
```

| Faz | Süre | Odak | Çıktı |
|---|---|---|---|
| **Faz 0 — ÖLÇ** (ŞİMDİ) | gözlem dönemiyle paralel | 1B kapanış-snapshot + 3A CLV kaydı/dashboard | Her paper-bahis CLV'li → karne başlar |
| **Faz 1 — BESLE** | 1-3 hafta | 1A kalite scorecard · 2A CLV harness + Kelly · 1B T1 xG | Doğru ölçüm + doğru objektif + en büyük boşluk kapanır |
| **Faz 2 — NİŞ AVI** | CLV umut verirse | 1B kadro/hakem · 2B kart/korner · 2C line-movement/disagreement | Edge'in *nerede* olduğunu bul |
| **Faz 3 — ÖLÇEKLE/CİLA** | edge doğrulanırsa | 3B risk motoru · 3C backtest+alarm · 1C seçici genişlik | Üretim disiplini |

---

## EFOR / ETKİ ÖZETİ (ilk dalga)

| İş | Efor | CLV'ye etki | Sıra |
|---|---|---|---|
| Kapanış-oranı snapshot (1B) | Orta | **Kritik** (ölçüm mümkün olur) | 1 |
| Bahis-başına CLV + dashboard (3A) | Orta | **Kritik** (karne) | 2 |
| CLV backtest harness + Kelly (2A) | Orta | Yüksek | 3 |
| Data-quality scorecard (1A) | Düşük | Orta (dolaylı) | 4 |
| T1 xG backfill (1B) | Orta | Orta-Yüksek | 5 |
| Niş pazar (kart/korner) (2B) | Yüksek | ? (umut) | Faz 2 |

> **Çıkış cümlesi:** Faz 0+1, "edge var mı?" sorusunu **haftalar içinde** ve **dürüstçe**
> cevaplar. Cevap evetse nereye yükleneceğimizi biliriz; hayırsa parayı korur, projeyi
> bilgi-üretimi olarak konumlandırırız. Her iki sonuç da kazançtır.
