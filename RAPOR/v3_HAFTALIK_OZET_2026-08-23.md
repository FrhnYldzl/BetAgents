# 📋 YÖNETİCİ ÖZETİ — 23 Ağustos 2026
### BetAgents · sezonun 1. tam haftası · "sessizliğin nedeni ölçüldü" haftası

---

## 1) İYİ GİDEN İŞLER

**🩺 Teşhis sistemi ilk haftasında sistemin en büyük hatasını yakaladı.**
Geçen hafta kurduğumuz günlük tıkanıklık teşhisi, KALECİ için `🔴 TIKANIKLIK —
No module named 'scipy'` yazdı. İzini sürünce ortaya haftalardır süren, hiçbir
log'a yansımayan bir kök neden çıktı (bkz. bölüm 2). Teşhis olmasaydı bu hata
"ajanlar tembel" diye yorumlanmaya devam edecekti.

**🎫 Sabit bidding (100 TL) devrede ve ölçüm temiz.** Son 4 günün tüm kuponları
tam 100 TL — beceri artık stake politikasından arınmış ölçülüyor. Skor tablosu
varsayılan olarak **Flat-LCB** (ortalama birim-kâr − 1σ/√n şans cezası) ile
sıralanıyor; lisans merdiveni (100 → 500 → 1000 TL) kurulu ve kimse henüz
barajı geçmediği için herkes 🎫 ÇAYLAK.

**Sezon hacmi normale döndü.** Günlük 7-8 kupon (14-15 Ağu'da 13-15, off-season
3'e kadar düşmüştü). 192 yaklaşan maçta closing oran mevcut; settle zinciri
sağlıklı (48+ saatlik takılı maç: 0, sadece 8 maç normal 6 saatlik pencerede).

**Sahadaki 3 ajan çalışıyor:** son 7 günde TERS 8/11 kupon **+393 TL**, JOKER
7/10 **+307 TL**, CESUR 7/15 **−368 TL**. TERS'in ilk terslemeleri geldi ve
kazanıyor; JOKER (rastgele kontrol) da pozitif — bu ikisinin farkı henüz
gürültü seviyesinde, örneklem büyümeden yorum yok.

---

## 2) KÖTÜ GİDEN İŞLER — asıl mesele

### 🔴 P1 · Kök neden: scipy çöküşü tüm motor ailesini öldürüyordu

`agents._engine_candidates` içinde **koşulsuz** `import independent_model`
duruyordu; bu modül `scipy.stats` çekiyor. Railway runtime'ı bilinçli olarak
SLIM (`requirements-railway.txt`'te scipy yok) → import her seferinde
`ModuleNotFoundError` fırlatıyor, aday üretimi daha başlamadan çöküyordu.

Etkilenenler: **TEMKİNLİ · MEMUR · AVCI · KALECİ · ERKENKUŞ · TRIVOX · EUVOX**
(+ KONSEY'in motor-aile oyları, + HOCA/SİMYACI model hattı). Ayakta kalanlar,
tam da motoru kullanmayanlar: CESUR (midband), TERS (fade), JOKER (random),
POPÜLER (pundit).

**Düzeltildi ve deploy edildi (23 Ağu):**
- `independent_model`: scipy → **numpy-only Poisson** (pmf/cdf birebir aynı,
  fark 1e-17). Slim runtime korundu, üstelik HOCA/SİMYACI model hattı da
  Railway'de ilk kez çalışabilir hâle geldi.
- `_engine_candidates`: import artık **tembel** (yalnız confirm/value modunda).
- **Kanıt** (scipy bloklanmış simülasyon, 192 maç): TEMKİNLİ 34 aday/2 kupon ·
  MEMUR 45/2 · AVCI 75/3 · KALECİ 15/2 · EUVOX 5/2 · HOCA 3/1 · ERKENKUŞ 1/1.
  Öncesinde hepsi sıfırdı.

### 🔴 P2 · Lig, bug'ı "tembellik" sanıp 7 ajanı kadro dışı bıraktı

22 Ağustos değerlendirmesinde **pasiflik** gerekçesiyle:

| Ajan | Gerekçe | Devredilen kasa |
|---|---|---|
| TEMKİNLİ | pasiflik | 935 TL |
| AVCI | pasiflik | 932 TL |
| MEMUR | pasiflik + rota (−21,4%) | 786 TL |
| ERKENKUŞ | pasiflik | 1.000 TL |
| TRIVOX | pasiflik | 1.000 TL |
| EUVOX | pasiflik | 1.000 TL |
| **KURUCU** | **performans (−83%) + rota** | 170 TL |

Toplam **5.823 TL** lig lideri TERS'e geçti — TERS'in kasası 6.823 TL'ye çıktı
ve "lider" görüntüsü büyük ölçüde bu devirlerden doğdu (kendi flat becerisi
−0,6%). HOCA · SİMYACI · KALECİ · KONSEY de aynı sebeple 1'er ihtar aldı; bir
sonraki değerlendirmede onlar da kadro dışı kalacaktı.

**Kural düzeltildi:** pasiflik ihtarı artık yalnız 🩺 teşhis o ajan için
`🟢 OYNAYABİLİR` dediğinde kesilir. 🔴 tıkanıklık / ⚪ meşru PAS / limit /
dönem / uyku hâllerinde ihtar düşer ve log'a "teşhis: oynayabileceği pozisyon
yoktu" yazılır.

**Telafi ONAY BEKLİYOR** (canlı DB'de toplu kasa/statü değişikliği olduğu için
otomatik uygulanmadı): 6 ajanın kadro dışılığı iptal + kasaları iade (5.653 TL
TERS'ten geri), MEMUR'un gerçek rota ihtarı korunur, HOCA/SİMYACI/KALECİ/KONSEY
ihtarları sıfırlanır. TERS'in kupon P&L'i ve flat becerisi etkilenmez (sabit-100
metrikler kasadan bağımsız).

### 🟠 P3 · KURUCU'nun kadro dışılığı hak edilmiş — ama ana hesap sustu

KURUCU motor ailesini kullanmıyor (kendi `paper_engine` hattı), yani −83%'lük
düşüş **gerçek**: 103 karar kuponu, flat ROI −23,5%, LCB −32,6%. Kasası 0'a
indiği için 🛑 TABAN FRENİ de devrede — yeni kupon açmıyor. Karar senin:
(a) emekli kalsın, (b) Era-3 olarak 1.000 TL ile taze başlasın (arşiv korunur),
(c) affedilip devam etsin.

### 🟠 P4 · Lig etiketleme sezonda zayıf kaldı

Yaklaşan 192 maçın **146'sı `ALL`** (etiketsiz); T1 sadece 5, E0 2, SP1 7, I1 18.
TRIVOX (yalnız T1) bu yüzden hâlâ aç kalıyor — teşhis onu ⚪ meşru PAS gösteriyor,
doğru ama sebebi veri tarafında. TEAM_MARKERS sözlüğünün sezon kadrolarıyla
genişletilmesi gerekiyor.

---

## 3) ÖNERİLER (öncelik sırası)

1. **Telafiyi onayla** — ölçümün doğru olması için şart; aksi hâlde 6 ajan
   bug yüzünden ölü, TERS de şişmiş kasayla "lider".
2. **48 saat gözlem** — düzeltme sonrası motor ailesinin gerçekten kupon
   kurduğunu 🩺 panelden doğrula (beklenen: 9 ajan sahada, günlük ~15-20 kupon).
3. **KURUCU kararı** (yukarıdaki 3 seçenek).
4. **Lig etiketleme genişletmesi** — TEAM_MARKERS'a 2026/27 kadroları; TRIVOX
   ve EUVOX'un ölçülebilmesi buna bağlı.
5. **Lisans barajı gözlemi** — CESUR n=38 (flat −9,2%), en yakın aday hâlâ o
   değil; ilk 🥈 USTA terfisi için n≥30 + LCB>0 şartını sağlayan çıkmadı.
   Bu iyi haber: baraj gerçekten kanıt istiyor.

---

## 4) DERS (kalıcı)

> **Sessizlik veri değildir — nedeni ölçülmedikçe.**
> Bir ajanın oynamaması üç ayrı şey olabilir: doğru karar (meşru PAS),
> yanlış filtre, ya da çöken kod. Üçünü ayırmadan verilen her ceza, ölçtüğünü
> sandığın şeyi bozar. Bu hafta ceza sistemimiz bug'ı tembellik sandı ve
> 5.823 TL'yi yanlış ajana verdi. Teşhis katmanı olmasaydı bunu asla
> göremezdik.

---

# 🗓 EK — AYNI GÜN ALINAN KARAR: ERA-2 BAŞLADI

Telafi (para iadesi) yerine **Era-2** seçildi. Gerekçe: iade kasayı düzeltir,
**kıyası düzeltmez**. Era-1'de kimi ajan %-stake ile, kimi köprü yarım stake ile,
kimi de çöken motorla "oynamamış" sayılarak yarıştı — bu veriden hangi yöntemin
işe yaradığı çıkarılamaz. Era-2'de **15 oyuncu aynı gün, 1.000 TL kasa, sabit
100 TL bahis** ile başladı; Era-1 kuponları/journal arşivde aynen duruyor.

**Arşivlenen Era-1 karneleri (flat ROI):** KURUCU 103 kupon −23,5% · CESUR 39
−11,5% · POPÜLER 26 −71,4% · JOKER 25 −17,4% · TERS 17 −0,6% · AVCI 12 +5,2% ·
MEMUR 8 −67,6% · TEMKİNLİ 4 −26,3% · KONSEY 2 +30,0% · SİMYACI 2 +33,5% ·
HOCA 1 +36,0% · ERKENKUŞ/KALECİ/TRIVOX/EUVOX 0.

## Tıkanıklık kalkanı (kalıcı)

| Katman | Ne yapar |
|---|---|
| `preflight()` | Her koşuda **ve worker açılışında** tüm ajanların aday üretebildiğini kuru koşuyla doğrular |
| Fail-loud `run_profile` | Çöken ajan sessiz kalamaz → anında `🔴 TIKANIKLIK` satırı |
| `selftest_agents.py` | **Railway SLIM taklidi** (scipy/sklearn/lightgbm import edilemez) — deploy öncesi zorunlu test |
| Ölçüm şartlı lig | Pasiflik ihtarı yalnız teşhis `🟢 OYNAYABİLİR` derse |
| Era-farkındalı limitler | Önceki eranın kuponları yeni eranın günlük/açık limitini ve mola sayacını yiyemez |
| UI alarmı | Sistem Sağlığı'nda **🩺 Tıkalı Ajan** kutusu (24 saatlik teknik çöküş sayısı) |

## Era-2 ilk gün — tam kadro sahada

22 kupon kuruldu; teşhis paneli: 9 ajan 🟢 OYNADI (TEMKİNLİ 2 · MEMUR 2 · AVCI 3 ·
POPÜLER 2 · CESUR 3 · TERS 2 · KALECİ 2 · JOKER 2 · EUVOX 2), HOCA/ERKENKUŞ/KONSEY
🟢 oynayabilir (limit içinde), TRIVOX ⚪ meşru PAS, SİMYACI 🟠 montaj engeli
(2 adayın da MBS=3 → iddaa kuralı 3 ayak istiyor, 2 aday var: yapısal), KURUCU
⚪ auto_play penceresinde. **🔴 tıkanıklık: 0.**

## Düzeltme: P4 yanlış teşhisti

`ALL` etiketli 146 maç veri hatası değil — Danimarka 2. lig, U19, Kanada,
El Salvador gibi küçük/egzotik ligler. Büyük ligler doğru tanınıyor
(I1 66 · E0 44 · USA1 43 · SP1 28 · T1 27 · BRA1 20 · D1 20 · F1 8).
TRIVOX'un boş dönmesi eşik meselesi, etiket meselesi değil.
