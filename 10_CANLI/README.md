# CANLI — maç içi veri, model ve ölçüm

Üçüncü ürün. BetAgents ve Süper Toto'dan **ayrı**: kendi tabloları (`cl_*`), kendi
toplayıcı süreci, kendi panel bölümü. Ortak olan tek şey bağlantı yardımcısı
(`02_VERI/db.py`). CANLI, `toto_*` ve BetAgents tablolarını yalnız **okur**.

## Akış

```
DATA    canli_kaynak.py   iddaa canlı akışı (fiyat) + API-Football fixtures?live=all (skor/dakika)
                          ikisi takım adı + başlangıç saatine göre eşleşir
        canli_db.py       cl_mac · cl_anlik · cl_kupon · cl_kayit
MODEL   canli_model.py    maç öncesi fiyattan (λ_ev, λ_dep) çöz → kalan süreye ölçekle
                          → skor ve kırmızı karta göre nihai 1/0/2
PANEL   canli_panel.py    Canlı Maçlar: fiyat · model · sapma
```

## Neden iki kaynak

iddaa akışı **oranı verir, skoru ve dakikayı vermez** (ölçüldü: 330 canlı olayda
durum alanı yok). API-Football `fixtures?live=all` ise **tek istekte** bütün canlı
maçların skorunu, dakikasını ve kırmızı kartını veriyor. Bu yüzden fiyat sık
(120 sn), durum seyrek (300 sn) çekilir — ücretsiz planın günlük 100 istek kotası
bunu gerektiriyor.

## Maç öncesi fiyat neden kritik

Model gol beklentisini maç öncesi 1/0/2 fiyatından çözer. Maç canlıya geçtiğinde
o fiyat akışta **kalmaz**; bu yüzden toplayıcı başlamamış maçların fiyatını da
kaydeder (`cl_mac.oran_once`, bir kez yazılır). Fiyatı olmayan maçlarda model
lig-nötr varsayıma düşer, aynı skor/dakikadaki maçlara aynı olasılığı verir ve
panelde `*` ile işaretlenir — o satırlar ölçüme katılmamalıdır.

## Dürüstlük sınırı

Model maçın **gidişatını görmez** (üstünlük, şut, xG yok); yalnız skor, dakika ve
kırmızı kart bilir. Piyasa bunlardan fazlasını gördüğü için modelin piyasayı
yenmesi **beklenmiyor**. Canlıda marj ön maçtan yüksektir ve ön maçta piyasayı
yenemediğimiz ölçüldü (+%0,06 üstünlük, gereken %13). Bu bölümün amacı bahis
üretmek değil, **sapmayı ölçmek**: bir maç tek fiyat değil 90 dakikalık fiyat
serisidir, yani kanıt biriktirmenin en hızlı yolu.

## Çalıştırma

```
python 10_CANLI/canli_worker.py --bir-kez    # tek tur (yerel deneme)
python 10_CANLI/canli_worker.py              # sürekli toplama
python 10_CANLI/canli_kaynak.py              # kaynakları görüntüle (yazma yok)
python 10_CANLI/canli_model.py               # modelin kendi sınaması
```

Üretimde `start.py` toplayıcıyı ayrı süreç olarak başlatır; `CANLI_WORKER=0` ile
kapanır. Yerelden üretim veritabanına yazma engellidir (`CANLI_URETIM_ONAY=1`
olmadıkça) — yerel deneme için `BETAGENTS_DB=sqlite` kullan.

Ayarlar: `CANLI_FIYAT_SN` (120), `CANLI_DURUM_SN` (300), `CANLI_ONMAC_SN` (900).
