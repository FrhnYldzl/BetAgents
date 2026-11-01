# MAÇ İÇİ İSTATİSTİK · KORELASYON · CLV VE EDGE — Sprint Planı

**Tarih:** 2026-11-01
**Bağlam:** Kupon orkestratörü bitti. Ölçüldü ki **hiçbir ajan kanıt eşiğini
artı alt sınırla geçmiyor**; iddaa marjı %16,8. Yani bugünkü hâliyle sistem
fiyatı yenmiyor. Bu plan, yenmek için gereken tek şeyi hedefliyor:
**fiyatın bilmediği bilgi.**

> **Kullanıcının kuruluş amacı (kendi sözüyle):** "İnsanların duygusal
> engelleri ve önyargıları (bias) yüzünden… sayısal ve istatistikle, ancak
> veri bilimi metodolojisiyle problemleri çözerek bir makine yaratmak."
>
> Bu plan tam olarak o makinenin eksik yarısıdır. Elimizde **karar
> altyapısı** var (ajanlar, kontrol çizgisi, kanıt eşiği, kupon defteri,
> CLV). Eksik olan **girdi**: maç ve takım istatistikleri.

---

## 0 · ÖNCE TEŞHİS — elimizde gerçekte ne var

Plan varsayıma değil sayıma dayanıyor. Ölçüm 01.11.2026, anlık görüntü.

### matches_v2 — 10.587 satır, 112 sütun, **78'i boş**

| Durum | Sayı | İçerik |
|---|---|---|
| ≥%50 dolu | 34 | kimlikler, takım adları, **kapanış fiyatları**, skor (%72,6) |
| <%2 (boş) | **78** | aşağıdaki her şey |

**Boş olanlar — yani şema hazır, toplama yok:**

| Öbek | Sütunlar |
|---|---|
| Maç istatistiği | `home/away_shots`, `shots_on`, `shots_total`, `possession_pct`, `fouls`, `corners`, `yellows`, `reds`, `home/away_xg` |
| İlk yarı | `home_score_ht`, `away_score_ht` |
| **Açılış fiyatı** | `opening_1/X/2`, `opening_over25/under25`, `odds_move_1/x/2` |
| CLV (pazar bazlı) | `clv_home`, `clv_draw`, `clv_away`, `clv_over25`, `clv_under25`, `clv_avg_1x2` |
| Takım durumu | `home/away_league_pos`, `pts`, `gd`, `form_5g`, `title_gap`, `relegation_gap` |
| 5 maç ortalaması | `avg_goals_5g`, `clean_sheet_5g`, `corners_5g_avg`, `yc_5g_avg`, `rc_5g_avg` |
| H2H | `h2h_n`, `h2h_home_wins`, `h2h_draws`, `h2h_away_wins`, `h2h_avg_goals`, `h2h_btts_rate` |
| Bağlam | `referee`, `home/away_key_injuries`, `lineup_quality` |

**Bayraklar bunu doğruluyor:** `has_xg=0`, `has_match_stats=0`, `has_clv=0`,
`has_opening_odds=0` — **10.587 satırın tamamında**. `quality_score` her
satırda 0,5; yani hiç hesaplanmamış.

> ⚠️ **Dersi şimdi alalım:** Bu 78 sütun bir zamanlar iyi niyetle açıldı ve
> hiç doldurulmadı. Şema yazmak veri toplamak değildir. Bu planın her
> sprinti **doluluk ölçümüyle** biter; doldurulmayan sütun açılmaz.

### Canlı taraf — cl_anlik 751.445 satır

| Alan | Doluluk | Not |
|---|---|---|
| `oran`, `p_piyasa` | %67,9 | iddaa akışı, **ücretsiz ve çalışıyor** |
| `pazar` | %88,5 | ama yalnız **1X2 ve AU25** toplanıyor |
| `dakika`, `safha`, `ev_skor`, `dep_skor`, `kirmizi_*` | **%2,8** | API-Football askıda |

**Darboğaz net:** 751 bin fiyat anlık görüntüsü var ama **%97,2'sinde maçın
kaç kaç ve kaçıncı dakika olduğunu bilmiyoruz.** Skor ve dakika olmadan maç
içi istatistik kullanılamaz — "2-0 öndeyken şut sayısı" ile "0-0'da şut
sayısı" aynı şey değildir.

iddaa'nın bilinen uçları denendi (01.11.2026): canlı olay yanıtında 17 alan
var, skor/dakika **yok**. Başka ücretsiz uç olup olmadığı **araştırma
konusu** — plana varsayım olarak değil, zaman kutulu keşif olarak girdi.

### Elimizde ÇALIŞAN ne var

- **CLV ölçüm aleti doğrulandı** (z=5,69): CLV>0 bahisler −%0,6, CLV≤0 −%36,6.
  Yani CLV gerçekten sonucu öngörüyor ve **sonucu beklemeden** ölçüyor.
- 2.898 sonuçlanmış bahis, 13.972 ileri iddia (`ajan_iddia`), 10.587 maç.
- Kanıt eşiği, kontrol çizgisi (JOKER), kupon defteri, kalibrasyon karnesi.

---

## 1 · METODOLOJİ — üç kural, pazarlık yok

Bu üç kural plandan önce gelir; ihlal eden bulgu bulgu sayılmaz.

### Kural 1 — Sonuçla değil, ARTIKLA korele et

Şut sayısı kazanmayla korelasyonludur. **Fiyat bunu zaten biliyor.** Tek
anlamlı soru şu: özellik, **fiyatın kaçırdığını** açıklıyor mu?

```
artık = gerçekleşen sonuç − piyasanın MARJSIZ olasılığı
```

Korelasyon bu artığa karşı ölçülür. Ham sonuca karşı ölçmek, piyasanın
bildiğini keşif sanmaktır.

> Bu projede aynı hata iki kez yapıldı: `paper_bets.edge` sütunu daima eksi
> çıktı (çünkü marjın ta kendisiydi) ve Toto kârlılık şartı marjsız
> olasılıkla ham oranı karıştırdı. Üçüncüsü olmasın.

### Kural 2 — Sızıntı yok: aynı maçın istatistiği o maçı tahmin edemez

Maç sonu şut sayısı maç başlamadan bilinmez. Kullanılabilir tek biçim
**önceki maçlardan yuvarlanan** özelliktir (son 5 maç ortalaması, sezon
kümülatifi). Her özellik için "bu bilgi bahis anında var mıydı?" sorusu
kodda bir zaman damgası kontrolüyle cevaplanır, yorumla değil.

### Kural 3 — Çoklu test: 78 sütunda tesadüf garantidir

78 özellikte %5 eşikle test yaparsan ~4 tanesi **tesadüfen** anlamlı çıkar.
Korunma:
- Sprint başında **önceden yazılmış** hipotez listesi (kaç özellik test
  edilecek, hangisi).
- Veri **zaman bazlı** ikiye bölünür: geliştirme / dokunulmamış holdout.
- Holdout **bir kez** açılır.
- Kontrol özelliği: rastgele gürültü sütunu. Gerçek özellikler ondan ayırt
  edilemiyorsa bulgu yok. (JOKER mantığının özelliklere uygulanmışı.)

---

## 2 · SPRINTLER

Sıra kasıtlı: **önce bedava ve hızlı olan**, sonra pahalı olan. İlk üç
sprint **hiç yeni veri kaynağı gerektirmiyor** — elimizdeki veriden
türetiliyor.

---

### SPRINT 1 — Açılış fiyatı ve fiyat hareketi · *en yüksek kaldıraç*
**Süre:** 1 hafta · **Yeni kaynak:** yok · **Risk:** düşük

Literatürde fiyatı en iyi yenen tek şey fiyatın **kendi hareketidir**.
Elimizde kapanış var, **açılış yok** — yani hareketi hiç göremiyoruz.
Üstelik toplayıcı zaten her tur fiyat çekiyor; yapılacak iş **ilk görülen
fiyatı saklamak**.

**Yapılacak**
1. `opening_1/X/2`, `opening_over25/under25`, `opening_fetched_at` — maç ilk
   görüldüğünde yazılır, bir daha dokunulmaz (`cl_mac.oran_once` deseni
   zaten var, %76,7 dolu — oradan geriye dönük doldurulabilir).
2. `odds_move_1/x/2` = `closing / opening − 1`.
3. `has_opening_odds` bayrağı gerçekten bakımlı hâle gelir.

**Ölçüm (başarı ölçütü)**
- Fiyat hareketi, **kapanış fiyatının ötesinde** sonucu öngörüyor mu?
  (artık üzerinde regresyon, holdout'ta z ≥ 2)
- Hareketin yönünde bahis yapmak CLV üretiyor mu?

**Neden ilk:** bedava, mevcut toplamayla, geriye dönük 10.587 maç için
kısmen doldurulabilir. Çıkmazsa 1 hafta kaybedilir; çıkarsa her ajana girdi.

---

### SPRINT 2 — Form · sıralama · H2H, **kendi geçmişimizden**
**Süre:** 1-2 hafta · **Yeni kaynak:** yok · **Risk:** düşük

Elimizde 10.587 maçın %72,6'sında skor var. Bu, aşağıdakilerin tamamını
**dışarıdan hiçbir şey almadan** üretmeye yeter:

`home/away_form_5g`, `avg_goals_5g`, `clean_sheet_5g`, `league_pos`, `pts`,
`gd`, `h2h_n`, `h2h_home_wins`, `h2h_draws`, `h2h_away_wins`,
`h2h_avg_goals`, `h2h_btts_rate`

**Yapılacak**
1. Yuvarlanan özellik üreteci (`02_VERI/ozellik_uret.py`): her maç için
   **yalnız o maçtan ÖNCEKİ** maçlardan hesaplar.
2. Sızıntı testi: özellik üretimi `kickoff_utc` kesimiyle çalışır; test,
   geleceği gören bir satır bulursa kırmızı verir.
3. Doluluk raporu `11_BAKIM/bakim_kontrol.py`'ye kalıcı kontrol olarak.

**Ölçüm**
- Her özelliğin artık üzerindeki tek başına bilgi katkısı.
- Gürültü kontrol sütununu geçen kaç özellik var?

⚠️ **Beklenti düşük tutulmalı:** Form ve sıralama piyasanın en iyi bildiği
şeydir. Bunların fiyata ek bilgi taşıma ihtimali **düşüktür**. Yine de
yapılır, çünkü (a) bedava, (b) diğer özelliklerin kontrolü olarak gerekli:
yeni bir özellik "formdan fazlasını" söylemiyorsa değersizdir.

---

### SPRINT 3 — Pazar bazlı CLV sütunları ve CLV'nin özelliklerle ilişkisi
**Süre:** 1 hafta · **Yeni kaynak:** yok · **Risk:** düşük

`clv_home/draw/away/over25/under25/avg_1x2` boş. Oysa CLV bu projenin
**en hızlı ölçüm aleti** (z=5,69 ile doğrulandı) ve şu an yalnız bahis
başına (`paper_bets.clv`) tutuluyor — maç başına değil.

**Neden önemli:** Sonuç 0/1 zar atışıdır, yüzlerce örnek ister. CLV sürekli
bir sayıdır, **çok daha hızlı yakınsar**. Özellik taraması CLV hedefiyle
yapılırsa aylar yerine haftalar sürer.

**Yapılacak**
1. Her maç ve her pazar için CLV sütunlarını doldur.
2. **Çifte hedef altyapısı:** her özellik hem CLV'ye hem sonuca karşı
   ölçülür. CLV hızlı sinyal, sonuç nihai hakem.
3. İkisinin çeliştiği durumlar ayrı raporlanır (çelişki, sızıntı veya
   fiyatlama hatasının en sık işaretidir).

---

### SPRINT 4 — Maç istatistikleri: kaynak kararı ve entegrasyon
**Süre:** 2 hafta · **Yeni kaynak:** VAR · **Risk:** orta · **Maliyet:** var

Şut, isabetli şut, topla oynama, korner, faul, kart, xG. Bunlar
**dışarıdan** gelmek zorunda.

**Önce karar, sonra kod — 3 günlük keşif:**
| Seçenek | Not |
|---|---|
| API-Football yeniden etkinleştirme | Hesap askıda; maliyeti ve kota sınırı netleşmeli |
| Alternatif sağlayıcı | Kapsam (alt ligler!) ve fiyat karşılaştırması |
| Ücretsiz/kazıma | Hukuki ve kırılganlık riski — süreklilik şart |

⚠️ **Kapsam tuzağı:** Bültenimizin ağırlığı alt liglerde (Kazakistan,
Belarus, İran…). Çoğu istatistik sağlayıcısı bu ligleri **kapsamaz**.
Seçimden önce *bizim oynadığımız maçların kaçını kapsıyor* ölçülmeli —
"5 büyük ligi kapsıyor" bu proje için işe yaramaz.

**Yapılacak**
1. Kapsam ölçümü (bizim maç listemize karşı, yüzde olarak).
2. Toplama + geriye dönük doldurma.
3. Yuvarlanan takım özelliklerine dönüştürme (Sprint 2 altyapısıyla).

**Ölçüm:** Kapsanan maç yüzdesi + bu özelliklerin artık üzerindeki katkısı.

---

### SPRINT 5 — Canlı skor/dakika · *canlının kilidi*
**Süre:** 1 hafta keşif + 1 hafta entegrasyon · **Risk:** yüksek (kaynak belirsiz)

751 bin fiyat anlık görüntüsünün %97,2'si **maç durumu bilinmediği için**
kullanılamıyor. Bu çözülmeden canlı istatistik projesi başlayamaz.

**Zaman kutulu keşif (5 gün), sırayla:**
1. iddaa'nın diğer uçları (web arayüzü skoru gösteriyor — nereden alıyor?)
2. Ücretsiz canlı skor sağlayıcıları, kapsam ölçümüyle
3. API-Football'un yalnız skor/dakika için dar kullanımı (kota: günde 100)

**Çıkmazsa:** canlı kol, skor gerektirmeyen tek işe indirgenir — **fiyat
hareketinin kendisi** (Sprint 1'in canlı karşılığı). Bu bile değerlidir ve
skor istemez.

> Dürüstlük notu: canlı tarafta şimdiye dek ölçülen üç şeyin üçü de olumsuz
> çıktı (canlı modelimiz piyasayı geçmiyor, 45 sn çözünürlükte gol sonrası
> aşırı tepki yok, kâr kilitleme 16-20 puan kaybettiriyor). Canlı projesine
> girerken beklenti buna göre olmalı: **kilidi açmak ≠ kenar bulmak.**

---

### SPRINT 6 — Korelasyon taraması ve özellik seçimi
**Süre:** 2 hafta · **Önkoşul:** Sprint 1-4

Artık elde özellik var. Şimdi asıl soru: **hangisi fiyatın bilmediğini
biliyor?**

**Yapılacak**
1. Önceden yazılmış hipotez listesi (kaç özellik, hangi pazar, hangi yön).
2. Her özellik için: artık üzerinde tek değişkenli ölçüm → gürültü
   kontrolüyle karşılaştırma → holdout.
3. Hayatta kalanlarla çok değişkenli model; **kalibrasyon** birinci ölçüt
   (bu projede kalibrasyon hatası defalarca "kenar" sanıldı).
4. Çıktı: özellik → ölçülen katkı tablosu, kalıcı rapor.

**Başarı ölçütü:** Holdout'ta, gürültü kontrolünü geçen ve marjsız fiyata
**ek bilgi** taşıyan en az bir özellik. Çıkmazsa sonuç şudur: *"78 sütunun
hiçbiri iddaa fiyatını yenmiyor"* — bu da bir cevaptır ve ölçülmüş olur.

---

### SPRINT 7 — Ajanlaştırma
**Süre:** 1 hafta · **Önkoşul:** Sprint 6'da hayatta kalan özellik

Hayatta kalan özellik yeni bir ajana girdi olur ve **mevcut makineye**
bağlanır: kanıt eşiği (n≥30, alt güven sınırı), JOKER kontrol çizgisi,
kupon defteri, kalibrasyon karnesi. Yani ayrı bir sistem kurulmaz; var olan
sınavdan geçer.

---

## 3 · SIRALAMA ÖZETİ

| # | Sprint | Süre | Yeni kaynak | Beklenti |
|---|---|---|---|---|
| 1 | Açılış fiyatı + hareket | 1 hf | yok | **yüksek** |
| 2 | Form · sıralama · H2H | 1-2 hf | yok | düşük (ama kontrol olarak şart) |
| 3 | Pazar bazlı CLV | 1 hf | yok | altyapı (ölçümü hızlandırır) |
| 4 | Maç istatistikleri | 2 hf | **var, maliyetli** | orta |
| 5 | Canlı skor/dakika | 2 hf | **belirsiz** | kilit açıcı |
| 6 | Korelasyon taraması | 2 hf | yok | **asıl cevap burada** |
| 7 | Ajanlaştırma | 1 hf | yok | — |

**Toplam:** ~10-11 hafta. İlk 4 hafta hiç para harcamadan ilerliyor.

---

## 4 · BAŞARISIZLIK TANIMI — baştan yazılsın

Bu plan kenar bulacağını **garanti etmiyor**. Dürüst olasılıklar:

- İddaa marjı %16,8. Bunu yenmek için bahis başına **17 puandan fazla**
  kenar gerekir. Bu çok büyük bir sayıdır.
- Bulunacak kenar muhtemelen **her maçta değil**, dar bir nişte olacak
  (belirli lig, belirli pazar, belirli fiyat bandı).
- En olası iyi sonuç: pozitif kenar değil, **daha iyi kalibrasyon** —
  yani kuponun şansını doğru söylemek. Kupon orkestratörü bunu zaten
  yapıyor; istatistikler onu keskinleştirir.

**Her sprintin sonunda sorulacak tek soru:** *bu sprint, ölçülebilir bir
bilgi kattı mı?* Katmadıysa sütun silinir, sprint kapatılır, bir sonrakine
geçilir. Doldurulmayan 78 sütunun dersi budur.

---

# ■ GÜNCELLEME — 01.11.2026 akşamı

## Kullanıcı direktifi: **TEK KAYNAK İDDAA**

> "Nt: Tek kaynak iddaa olmalı!"

Bu, planın 4. ve 5. sprintini kökten değiştirir — ve **iyi yönde**:

- API-Football, dış istatistik sağlayıcısı, ücretli abonelik **yok**.
- Kapsam tuzağı kendiliğinden çözülür: iddaa, tanımı gereği **tam olarak
  bizim oynadığımız maçları** kapsar. "5 büyük ligi kapsıyor" sorunu biter.
- Maliyet sıfır, kota yok, hesap askıya alınmaz (API-Football'un başına
  gelen buydu ve canlı projeyi %2,8'e düşürdü).

## iddaa'nın gerçekte NE verdiği — tarandı, varsayılmadı

### 1 · Lig analizi — `iddaa.com/lig-analiz/...` ✅ DOĞRULANDI

Puan durumu sayfası şunları veriyor ve **Toplam / Ev Sahibi / Deplasman**
sekmeleriyle ayrışıyor:

`POZ · O · G · B · M · AG:YG · +/- · P · Form (son 5: G/B/M)`

Ayrıca aynı bölümde: **Fikstür**, **Sonuçlar**, **Liderler (gol, asist,
kart)**, **Takım Kadroları**.

Bu, boş duran şu sütunların doğrudan kaynağıdır:
`home/away_league_pos`, `pts`, `gd`, `form_5g`, `avg_goals_5g` ve
kullanıcının özellikle istediği **iç saha / dış saha ayrımı**.

→ **Sprint 2 artık dış kaynaksız DEĞİL, iddaa kaynaklı ve daha zengin.**
Kendi geçmişimizden türetmek yerine iddaa'nın kendi tablosu alınır; ev/dep
ayrımı bizim kısmi geçmişimizden güvenilir çıkarılamıyordu.

### 2 · Canlı skor — `iddaa.com/canli-skor/futbol` ✅ VAR

Lig listesi **tam bizim bültenimiz**: Belarus, Estonya, Tayland, Uganda,
Botsvana, Kosova, Nikaragua… yani dış sağlayıcıların kapsamadığı alt
ligler burada.

→ **Sprint 5'in kaynağı var.** Taşıma biçimi (WebSocket mi, arka uç API mi)
henüz belirsiz; veri istemci tarafında geliyor, `__NEXT_DATA__` boş.
İlk adres: ağ izinde görülen `mpc-prod-24-s6uit34pua-uw.a.run.app`.
Bu hâlâ zaman kutulu keşif, ama artık "kaynak var mı" sorusu değil
"hangi uçtan" sorusu.

### 3 · Pazarlar — kullandığımızdan ÇOK fazlası ⚠️ YENİ FIRSAT

`sportsbookv2.iddaa.com/sportsbook/event/{id}` tek maç için şunları
döndürüyor: Alt/Üst 2.5, Alt/Üst 4.5, Tek/Çift, handikaplar ve
devamı — her biri `odd` ve `wodd` (iki ayrı fiyat) ile.

**Biz yalnız 1X2 ve AU25 topluyoruz.** Bu, elimizdeki en büyük
kullanılmayan iddaa verisi ve hiçbir yeni kaynak gerektirmiyor.

→ **Yeni sprint eklendi (aşağıda S4b).**

---

## SPRINT 1 — TAMAMLANDI · ölçüm sonuçları

**Örneklem:** 4.037 maç (açılış + kapanış + skor), açılış medyan **36 saat**
önce görülmüş (%69'u 24 saatten erken).

| Sınav | Sonuç | Yorum |
|---|---|---|
| Kapanış, açılıştan iyi mi? | Brier −0,00487, **z = −4,04** | ✅ EVET — hareket **gerçek bilgi** taşıyor |
| Hareket, kapanışın kaçırdığını söylüyor mu? | r = +0,006, **z = +0,68** | ❌ HAYIR — bilgi kapanışta tam fiyatlanmış |
| Açılışın fiyat bandı yanlılığı var mı? | 60-70 bandında +6,3p | ⚠️ **ARTEFAKT** |

### ⚠️ Yakalanan tuzak

60-70 bandındaki "+6,3 puan favori ucuzluğu" bulgu **değil**. Aynı analiz
**kapanış** fiyatına uygulandığında aynı profil çıktı (10-20 bandı −2,58p,
40-80 bandı artı). Yani sapma piyasanın yanlılığı değil, **oransal
marjsızlaştırmanın** bilinen kusuru: marjı orantılı dağıtmak favoriyi
sistematik olarak düşük gösterir.

Bu projede aynı karışıklık üçüncü kez karşımıza çıktı (`kenar-sutunu-marj`,
`marjsiz-favori-sismesi`). Kontrol koşulmasaydı +6,3 puanlık sahte bir
kenar raporlanacaktı.

### Sprint 1 çıktısı: `cl_onmac_yol`

Ölçüm şunu gösterdi: açılış ile kapanış arasında piyasaya **bilgi giriyor**
(z=−4,04), ama o bilginin **ne zaman** girdiğini göremiyoruz — çünkü
`cl_mac` yalnız ilk (`oran_once`) ve son (`oran_kapanis`) fiyatı tutuyor,
aradaki yol atılıyor.

Oysa önmaç turu **zaten 15 dakikada bir fiyat çekiyor**. Eklenen:
`cl_onmac_yol` tablosu — her maç öncesi gözlemi biriktirir, **yalnız fiyat
değiştiğinde** (yol değişimlerle tanımlıdır; değişmeyen turu yazmak hacmi
boşuna şişirir).

Bu, hareketi erken yakalayıp iyi fiyattan girme (CLV) testinin **önkoşulu**.
O test ancak birkaç hafta yol biriktikten sonra yapılabilir.

**Sprint 1 hükmü:** hareket tek başına oynanacak bir sinyal **değil**
(ölçüldü). Ama hareketin *yolu* henüz ölçülmedi ve artık ölçülebilir hâle
geldi.

---

## REVİZE SIRALAMA

| # | Sprint | Durum | Kaynak |
|---|---|---|---|
| 1 | Açılış fiyatı + hareket | ✅ **bitti** — sinyal yok, yol toplanıyor | iddaa |
| 2 | Lig analizi: puan durumu · form · **ev/dep** | sıradaki | **iddaa lig-analiz** |
| 3 | Pazar bazlı CLV | hazır | iddaa |
| 4a | Maç istatistikleri (şut, korner, kart) | iddaa'da var mı — keşif | iddaa |
| **4b** | **Pazar genişletme (AU4.5, Tek/Çift, handikap…)** | **YENİ — en ucuz kazanç** | iddaa |
| 5 | Canlı skor/dakika | kaynak bulundu, uç aranıyor | **iddaa canli-skor** |
| 6 | Korelasyon taraması | önkoşullu | — |
| 7 | Ajanlaştırma | önkoşullu | — |

**S4b neden öne alınmalı:** yeni veri kaynağı yok, yeni model yok, yalnız
hâlihazırda çektiğimiz yanıttan daha fazla pazar okumak. Her yeni pazar
hem yeni bahis alanı hem yeni marjsızlaştırma çifti demek. Ayrıca `odd` /
`wodd` ikiliği incelenmeli: ikisi arasında ~%4 fark var ve hangisinin
gerçekte oynanabilir fiyat olduğu marj hesabımızı doğrudan etkiler.
