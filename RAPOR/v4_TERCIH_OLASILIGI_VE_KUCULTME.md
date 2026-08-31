# 🎲 TERCİHİN OLASILIĞI — Skor Kümesi, Seçicinin Laneti ve k (2026-08-31)

Kullanıcı sorusu: *"Ajanlar tercihin NEDENİNİ söylüyor ama olasılık teorisiyle
söylemiyor. Ben de söyleyemiyorum, sezgi diyoruz. Sen ne diyorsun? Tercihin
olasılığını nasıl hesaplarız?"*

Bu rapor o sorunun cevabıdır. Tüm sayılar bu depodaki veriyle hesaplandı;
üretilen kod `02_VERI/shrinkage.py`, `02_VERI/measure_k.py` ve
`02_VERI/backtest.py` (KOLN konseptleri).

---

## 1. Skor kümesi tezinin formel hali — ve sınırı

### 1.1 Neden skor kümesi korelasyonu yendi (teori, ölçümden önce)

Skor uzayı `Ω = {(h,a)}` üzerinde bir olasılık ölçüsü `S` tanımlanırsa, **her
bahis seçimi Ω'nın bir alt kümesidir** ve her fiyat aynı `S`'in bir lineer
fonksiyonelidir:

    p(A) = Σ_{ω∈A} S(ω)          →      p = B·s   (B = 0/1 insidans matrisi)

| Seçim | Küme |
|---|---|
| "1" | {h > a} |
| "Üst 2.5" | {h+a ≥ 3} |
| "KG Var" | {h≥1, a≥1} |
| "0 ve Yok" | {(0,0)} |
| "1 ve Üst" | {h>a, h+a≥3} |

Yani tahtadaki bütün pazarlar **tek bir nesnenin projeksiyonlarıdır**.
Korelasyon katsayısı tablosu bu ortak dağılımın *ikili* (pairwise)
yaklaşımıydı — marjinallerin çarpımına hücre bazlı düzeltme. Skor kümesi tam
dağılımın kendisi. **%34.9'luk üstünlük (0.659 → 0.429) sürpriz değil,
kaçınılmazdı.** Ölçüm doğruladı, ama teori zaten söylüyordu.

### 1.2 Ama skoru BİLMEK mümkün değil — entropi duvarı

`score_sets.SCORE_DIST`'ten hesaplandı (11 profil, ~30 skor):

| profil | skor | entropi (bit) | perpleksite | mod | modP | top-3 | top-5 |
|---|---|---|---|---|---|---|---|
| 0\|0 | 27 | 3.886 | 14.8 | 1-1 | %15.1 | %38.4 | %57.4 |
| 0\|2 | 35 | 4.371 | 20.7 | 1-2 | %10.7 | %29.5 | %44.1 |
| 2\|0 | 25 | 3.842 | 14.3 | 1-1 | %17.6 | %40.8 | %57.9 |
| 3\|2 | 35 | 4.340 | 20.3 | 2-1 | %11.2 | %30.9 | %46.5 |
| **ORT** | | **4.129** | **17.7** | | **%13.3** | **%34.1** | **%50.3** |

**Asıl sonuç — λ'ları MÜKEMMEL bilsek bile** (bağımsız Poisson):

| λ (ev, dep) | profil | entropi | mod olasılığı |
|---|---|---|---|
| (1.35, 1.15) | dengeli | 4.131 | %12.7 |
| (2.00, 0.80) | ezici ev favorisi | 4.160 | %12.2 |
| (2.60, 0.60) | **aşırı favori** | 4.146 | **%13.8** |
| (1.00, 0.90) | düşük gol | 3.678 | %15.0 |
| (2.20, 1.90) | gol bombası | 4.955 | %7.6 |

2.60–0.60 gibi absürt bir favorilikte bile mod skorun olasılığı %13.8 — dengeli
maçtan sadece 1 puan iyi. Sebep: Poisson entropisi λ'ya logaritmik bağlıdır
(`H ≈ ½log₂(2πeλ)`).

Karşılıklı bilgi (bantlar kaba olduğu için ALT SINIR):
`I(skor ; piyasa fiyatı) ≈ 0.18 bit` — toplam 4.31 bitin ~%4'ü.

> **HÜKÜM:** Kesin skor tahmininde tavan **~%13-15**'tir ve bu tavan model
> kalitesiyle değil futbolun rastgeleliğiyle belirlenir. Daha iyi veri veya
> model bu duvarı aşamaz.

### 1.3 Kesin skor pazarı ayrıca iki kez cezalı

**(a) Marj merdiveni** (kendi ölçümümüz): 1X2/A-Ü/KG %16.4 · 1X2_OU %17.6 ·
TOTAL_GOALS/OU_BTTS %19.6 · 1X2_BTTS %21.9 · **HT_FT %25.8**. Pazar ne kadar
ince partisyonluysa vergi o kadar ağır. CORRECT_SCORE hiç ölçülmedi (tipik
%30-40 beklenir). Mod skor için adil oran 1/0.133 = **7.5**; tahtada muhtemelen
5.3-5.8 → %13.3 isabetle bile ROI ≈ **−%27**.

**(b) Varyans duvarı.** %3 edge'i z=2 ile tespit için gereken bahis
(`σ² = p(1-p)b²`):

| bahis | p | oran | σ | gereken n |
|---|---|---|---|---|
| A/Ü 2.5 | 0.52 | 1.90 | 0.95 | ~4.005 |
| 1X2 favori | 0.50 | 2.00 | 1.00 | ~4.444 |
| KOMBO 1X2_OU | 0.20 | 4.50 | 1.80 | ~14.400 |
| KESİN SKOR (mod) | 0.13 | 7.00 | 2.35 | **~24.631** |
| KESİN SKOR (uzun) | 0.04 | 22.0 | 4.31 | **~82.603** |

Günde 2 kupon → 24.631 bahse **33 yılda** ulaşılır. Kanıtlanamayan edge,
karar açısından yok hükmündedir.

> **KARAR: "kesin skor tahmin eden ajan" konsepti REDDEDİLDİ** — beraberlik ve
> gol-bandı tezleri gibi, kurulmadan.

### 1.4 Kapalı kalan kapı: fiyat yüzeyi aşırı-belirlenmiş

`market_book.py` aynı maç için ~55-60 fiyat topluyor (CORRECT_SCORE dahil), ama
skor simpleksi ~30 boyutlu → **~26 fazlalık kısıt**. iddaa CORRECT_SCORE'u
yayınladığı anda **kendi skor dağılımını yayınlamış** oluyor; diğer her fiyat
test edilebilir bir kısıt haline geliyor:

    Σ_{h>a, h+a≥3} S_kitap(h,a)   =?   q("1 ve Üst")

Bu eşitliğin bozulduğu her yer kitabın **kendi kendisiyle çelişmesidir** — ve
bulmak için maç tahmin etmek gerekmez, sadece aritmetik tutarlılık gerekir.
Doğru matematiksel araç: **KL-projeksiyonu (IPF/Sinkhorn)** — tarihsel skor
şeklini önsel al, maçın marjsız fiyatlarına en az bozarak oturt. Konveks, tek
çözümlü, Dixon-Coles τ düzeltmesini otomatik içerir.

⚠️ **Marj modeli seçimi burada belirleyici** (orantısal / toplamsal / güç /
Shin). Yanlış model SAHTE edge üretir; hakem CLV olmalı, edge değil (dairesel
olur). `CORRECT_SCORE` şu an toplanıyor ama **hiçbir yerde kullanılmıyor**.

---

## 2. Tercihin anatomisi — "olmayacakların olasılığı"

Kullanıcı tespiti: *"o tercih aslında bir şeylerin %100 olmama olasılığı
üzerinden gidiyor."* Formel olarak doğru: KOMBO/KAVŞAK'ın 6 hücresi **tam
bölüntüdür** (ayrık + tüketici, toplamı 1). Bir hücre seçmek = 5'ini elemek.

### KOMBO (1X2 × A/Ü) — 6 hücreli bölüntü, profil bazında

| profil | 1 Ü | 1 A | 0 Ü | 0 A | 2 Ü | 2 A | H(bit) |
|---|---|---|---|---|---|---|---|
| 1\|1 | %24.42 | %15.22 | %7.00 | %22.03 | %17.80 | %13.52 | 2.493 |
| 2\|1 | %32.25 | %20.79 | %6.29 | %20.69 | %11.11 | %8.87 | 2.381 |
| 3\|2 | %52.59 | %19.72 | %5.99 | %10.08 | %6.98 | %4.64 | 2.000 |

### KAVŞAK (1X2 × KG)

| profil | 1 V | 1 Y | 0 V | 0 Y | 2 V | 2 Y | H(bit) |
|---|---|---|---|---|---|---|---|
| 1\|1 | %19.99 | %19.65 | %21.35 | %7.68 | %14.59 | %16.73 | 2.522 |
| 2\|1 | %23.48 | %29.56 | %20.23 | %6.74 | %9.74 | %10.24 | 2.403 |

### Elenen kütlenin ayrıştırılması (gerçekten oynanmış bahisler)

```
KOMBO "0 ve Üst" — Lecce-Roma tipi (profil 2|1)
  KAZANDIRAN KÜME  :  %6.29   (3 skor · tek-skor payı %90 → KIRILGAN)
  ELENEN KÜTLE     : %93.71   → 3.99 bit bilgi iddiası
    ├─ sonuç TUTAR, gol ayağı tutmaz : %20.69  (elenenin %22.1'i)
    ├─ gol ayağı TUTAR, sonuç tutmaz : %43.36  (%46.3)  ← ZAYIF HALKA
    └─ tam ıska                      : %29.67  (%31.7)
  BAŞLICA KATİLLER : "1 ve Üst" %32.3 · "1 ve Alt" %20.8 · "0 ve Alt" %20.7

KAVŞAK "2 ve Var" — Banfield-River tipi (profil 2|1)
  KAZANDIRAN KÜME  :  %9.74   (7 skor · tek-skor payı %65)
  ELENEN KÜTLE     : %90.26   → 3.36 bit
    ├─ sonuç TUTAR, KG tutmaz : %10.24  (%11.3)
    ├─ KG TUTAR, sonuç tutmaz : %43.71  (%48.4)  ← ZAYIF HALKA
    └─ tam ıska               : %36.31  (%40.2)
  BAŞLICA KATİLLER : "1 ve Yok" %29.6 · "1 ve Var" %23.5 · "0 ve Var" %20.2
```

**İncelenen dört bahsin dördünde de zayıf halka SONUÇ (1X2) ayağı.** Kaybın
~yarısı, gol/KG ayağı tuttuğu hâlde 1X2 ayağının tutmamasından geliyor.

Bu, iki eski bulguyla birebir örtüşüyor:
* *"beraberlik tek başına her segmentte kaybettiriyor"* (−%12 / −%21)
* **SİMETRİ (OU_BTTS) sonuç ayağı taşımıyor** — ve tam da o pazarda model her
  bantta mükemmel kalibre çıkmıştı (53672f1). Tesadüf değil: **hata sonuç
  ayağında yaşıyor.**

→ Gerekçe defterinde yazılabilecek somut cümle:
*"Bu bahsi büyük ihtimalle ev sahibinin kazanması öldürür (%32.3), gol sayısı değil."*

---

## 3. Üç farklı olasılık — ajanlar sadece birini söylüyor

| | nesne | örnek | ajan söylüyor mu |
|---|---|---|---|
| **P₁** | `P(A)` olayın olasılığı | "0 ve Üst gerçekleşir" %6.29 | ✅ |
| **P₂** | tahminin isabeti | "%6.29 tahminim doğru" | ❌ |
| **P₃** | **seçimin isabeti** | "221 aday arasından bunu seçmem doğruydu" | ❌ |

Sorulan P₃'tü ve P₁'den bağımsız bir nesnedir.

### 3.1 Seçicinin laneti (optimizer's curse)

Ajan N aday arasından **argmax** alıyor. Her `p̂` hatalı; argmax hatanın yukarı
saptığı adayı sistematik tercih eder:

    E[max_{i≤N} ε_i] ≈ σ · Φ⁻¹((N − 0.375)/(N + 0.25))

| N | E[max]/σ | σ=0.08 ise şişme |
|---|---|---|
| 1 | 0.000 | ×1.000 |
| 6 | 1.282 | ×1.108 |
| 50 | 2.243 | ×1.197 |
| **221** (KOMBO) | 2.767 | **×1.248** |
| **299** (KAVŞAK) | 2.864 | **×1.258** |

> Raporlanan **%30 edge**, yalnızca seçim yanlılığından arındırıldığında
> `1.30/1.248 − 1 = **%4**`'e iner.

**Ve bu, ampirik 0.91 katsayısının teorik açıklamasıdır.** *"İkisi de zayıf →
oran 0.91, model fazla iyimser"* bulgusu (30cec21) seçicinin lanetinin
ölçülmüş hâliydi: zayıf hücrelerde `p̂` küçük, göreli gürültü büyük, argmax
oraya yığılıyor. Artık yamalanmıyor, **türetiliyor**.

### 3.2 Küçültme ve π* — aranan formül

    gerçek edge     e  ~ N(μ₀, τ²)
    gözlenen edge   ê  = e + N(0, σ²)

    r = α + k·ê   regresyonundan:   k = τ²/(τ²+σ²),  α = μ₀(1−k)

    E[e|ê]   = μ₀ + k(ê − μ₀)
    Var[e|ê] = k(1−k)·Var(ê)
    π*       = P(e>0 | ê) = Φ( E[e|ê] / sd[e|ê] )        ← TERCİHİN OLASILIĞI

**μ₀ negatif olmak zorunda** — bu tercih değil, projenin kendi ölçümü
(*"motorun TÜM dilimleri iddaa fiyatıyla −%11.6/−%12.7"*). Regresyonun kesme
teriminden türetilir, elle konmaz.

μ₀ = −0.12, Var(ê) = 0.01 ile:

| k | ham +%8 → sonsal (π*) | ham +%15 | ham +%30 |
|---|---|---|---|
| 0.15 | −9.0% (%1) | −7.9% (%1) | −5.7% (%6) |
| 0.25 | −7.0% (%5) | −5.2% (%11) | −1.5% (%36) |
| 0.35 | −5.0% (%15) | −2.5% (%30) | +2.7% (%71) |
| 0.50 | −2.0% (%34) | +1.5% (%62) | +9.0% (%96) |
| 0.70 | +2.0% (%67) | +6.9% (%93) | +17.4% (%100) |

**k < 0.35 ise mevcut %8 eşiği anlamsız.** Her şey tek bir ölçülebilir sayıya
bağlı.

### 3.3 Korunum testi — bağımsız ikinci kontrol

6 hücre tam bölüntü olduğu için hem `p` hem `q` 1'e toplanır: bir hücreye
"+%30" demek o kütleyi diğerlerinden almak demektir.

| hücre q | iddia | kütle kayması | kalanlarda | hüküm |
|---|---|---|---|---|
| 0.05 | +%30 | +1.50p | −%1.58 | makul |
| 0.08 | +%30 | +2.40p | −%2.61 | makul |
| 0.15 | +%30 | +4.50p | −%5.29 | dikkat |
| 0.30 | +%30 | +9.00p | **−%12.86** | **AĞIR İDDİA** |

Uzun bir hücrede +%30 ucuz iddiadır (kitap oraya fazladan marj yığmış olabilir).
Ana hücrede +%30, *"kitabın çekirdek fiyatı yanlış"* demektir — ekstra kanıt
istemeli. Bu, sabit `MAX_EDGE=%60` tavanının prensipli hâlidir.

---

## 4. k ÖLÇÜMÜ — vekil sonuç

⚠️ **Canlı `paper_bets` okunamadı** (uzak oturumda DB yok — `.gitignore`, doğru
karar). Ölçüm `07_LOG_VE_RAPORLAR/` CSV'leriyle yapıldı: **motor ailesinin A/Ü
sinyalleri, KOMBO bahisleri DEĞİL.**

```
oran kontrolsüz  k = −1.105 ±0.362  t = −3.06 ***
ORAN KONTROLLÜ   k = −0.921 ±0.385  t = −2.39 **     n = 990
                 γ(oran) = −0.090 (anlamsız)
```

| dilim | n | ort.tahmin | ort.GERÇEK | fark | ort.oran | isabet |
|---|---|---|---|---|---|---|
| Q1 | 198 | +%5.0 | **+%6.2** | +1.2p | 1.90 | %55.6 |
| Q2 | 198 | +%7.5 | −%7.2 | −14.6p | 1.92 | %51.5 |
| Q3 | 198 | +%9.7 | −%2.3 | −12.0p | 1.85 | %56.1 |
| Q4 | 198 | +%12.3 | −%8.2 | −20.4p | 1.93 | %51.5 |
| Q5 | 198 | +%23.0 | **−%8.4** | −31.4p | 2.15 | %46.5 |

**Tek düze azalan.** Oranlar dilimler arası düz (1.85-2.15) ve γ(oran) anlamsız
→ favori-uzunoran sapması **değil**.

### Kayıtlar (abartılmamalı)
* **Vekil veri** — motor ailesi. **Kombo ailesinin k'sı HİÇ ölçülmedi.**
* Backtest, canlı değil.
* Sinyalin çoğu `backtest_bets.csv`'den (t=−2.17); `multi_league` tek başına
  hiçbir şey söylemiyor (t=−0.31). Aralarında 105 satır kısmi örtüşme var.
* Tahminci doğrulandı (bilinen k, 30 tekrar × n=3.000): yanlılık her seviyede
  <1.3 SE → yansız. **Ama std 0.07-0.23** — birkaç yüz bahisle ölçülen k'ya
  kesinlik atfedilemez.

> **En temkinli okuma: k ≤ 0. Edge sıralamasının çalıştığına dair kanıt yok;
> zayıf kanıt ters çalıştığı yönünde.**

---

## 5. 💰 EKONOMİK ANALİZ

Bugüne kadarki nakit getiri: **0 TL** (kâğıt para). Aşağıdakiler kayıp
kaynaklarının nicelleştirilmesidir.

### 5.1 Sıralama maliyeti (küçük olan)

| | 100 TL ciro başına |
|---|---|
| en yüksek edge %20 (BUGÜNKÜ davranış) | −8.4 TL |
| sırasız | −4.0 TL |
| **fark** | **−4.4 TL** |

3 kırmızı ajan × 2 kupon/gün × 100 TL ≈ yıllık 219.000 TL ciro → **~9.600 TL/yıl**.
*Kâğıt para + vekil ölçüm + "kombo ailesine transfer eder" varsayımı.*

### 5.2 ⚠️ Bahis büyüklüğü (asıl olan — k'dan BAĞIMSIZ)

Ajanlar **sabit 100 TL**, kasa 1.000 TL → **f = %10**. 22.60 oranlı bir bahiste
Kelly'nin önerdiği %0.185 → **54 kat aşırı bahis**.

Lecce-Roma tipi (oran 22.60), **gerçekten +%4 edge'li** bir bahis:

| strateji | f | f/f* | log-büyüme | 30 bahis sonra |
|---|---|---|---|---|
| Kelly | %0.185 | 1.0x | +0.0037% | 1.001 TL |
| çeyrek Kelly | %0.046 | 0.2x | +0.0016% | 1.000 TL |
| **ŞU ANKİ (100 TL sabit)** | **%10** | **54x** | **−4.7565%** | **240 TL** |

**Bahis pozitif EV'li olduğu hâlde 30 bahiste kasanın %76'sı yok oluyor.**
Edge'i model değil, bahis büyüklüğü öldürüyor.

### 5.3 Sonuç: skor tablosu uzun oranlarda beceriyi ÖLÇEMİYOR

30 bahis sonra, sabit %10 stake:

| ajan | oran 22.60 | oran 4.35 | oran 2.00 |
|---|---|---|---|
| ÇOK İYİ (+%10 edge) | 265 TL | 844 TL | **1.162 TL** |
| iyi (+%4) | 240 TL | 717 TL | 970 TL |
| KÖTÜ (−%10) | 190 TL | 490 TL | 637 TL |
| BERBAT (−%20) | 161 TL | 373 TL | 471 TL |

Oran 22.60'ta mükemmel ajanla berbat ajan **ikisi de batıyor**; fark varyansın
içinde kayboluyor. Oran 2.00'de tablo tamamen ayrışıyor.

⚠️ Sabit 100 TL *kötü bir karar değil* — ajanları karşılaştırılabilir kılmak
için alındı (prop-firm modeli) ve o işi yapıyor. Ama bedeli ölçülmemişti:
**uzun oranlarda karşılaştırılabilirliği ölçülebilirlikle takas ediyor.**

---

## 6. KARARLAR VE AÇIK İŞLER

### Alınan kararlar
* ❌ **"Kesin skor tahmini" konsepti REDDEDİLDİ** — tavan %13-15, marj %30-40,
  kanıt için 25.000+ bahis gerek (33 yıl).
* ✅ **KOMBO/KAVŞAK DURDURULMADI** — bilerek. Kombo ailesinin k'sını ölçecek tek
  veri kaynağı onlar. Durdurmak, KÖLN'ü ölçülmemiş bir katsayı üzerine kurmak
  olurdu — 53672f1'de yakalanan "ölçülmemiş katsayı devralma" hatasının aynısı.
  **Rolleri değişti: kâr aracı değil, ÖLÇÜM ALETİ.**
* ✅ **KÖLN canlı ajan olarak KURULMADI** — kendi kuralımız (b52bc41):
  KONSEPT → BACKTEST → KARAR → CANLI AJAN. KÖLN şu an 2. aşamada.

### Üretilen kod
| dosya | ne yapar |
|---|---|
| `02_VERI/shrinkage.py` | saf matematik: `estimate_k`, `Shrinker.judge`, `required_edge`. scipy YOK (091ba54 dersi). Dejenere dallar (k≤0, k≥1) açıkça raporlanır. |
| `02_VERI/measure_k.py` | canlı `paper_bets`'ten k ölçer, **aile bazında ayrı**. `--proxy` ile CSV vekili. |
| `02_VERI/backtest.py` | `KOLN`, `KOLN_HAM`, `EDGE_Q5`, `EDGE_Q1` konseptleri. Walk-forward: k yalnız 2024 öncesinde ölçülür. |

Not: `paper_bets.edge` kolonu KULLANILMIYOR — motor ailesinde `mp − 1/oran`,
kombo ailesinde başka ölçek; iki aile karşılaştırılamaz hâle gelirdi. Tek tanım:
`e = oran × model_prob − 1`.

### Sıradaki adımlar
```bash
cd 02_VERI
python measure_k.py                                  # 1) gerçek k, aile bazında
python backtest.py KOLN KOLN_HAM EDGE_Q5 EDGE_Q1     # 2) 9 sezon sınavı
```
1. **`measure_k.py`** — KOMBO/KAVŞAK'ın gerçek k'sı. `n<30` çıkarsa cevap "daha
   çok bahis gerek"; ajanların çalışmaya devam etmesi tam bu yüzden.
2. **`backtest.py`** — KÖLN'ü PoC'den geçir. **`EDGE_Q1 > EDGE_Q5` çıkarsa**,
   bu kombolardan büyük bir bulgudur: edge'e göre sıralayan her ajanı ilgilendirir.
3. **Bahis büyüklüğü** — ayrı iş. Sıralama düzeltmesinden büyük etkisi var ve
   KÖLN'ü beklemiyor.
4. **Açık kapı:** `CORRECT_SCORE` toplanıyor ama kullanılmıyor. Önce marj ölçümü,
   sonra iç tutarlılık testi (bkz. §1.4).

---

*Analiz: bu depodaki `score_sets.SCORE_DIST`, `combo_tables`,
`07_LOG_VE_RAPORLAR/*.csv` verileriyle hesaplandı. Hesaplamaların tamamı
`02_VERI/shrinkage.py` ve `02_VERI/measure_k.py` ile yeniden üretilebilir.*
