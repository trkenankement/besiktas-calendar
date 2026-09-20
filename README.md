# Beşiktaş Maç Takvimi

[![Update calendars](https://github.com/trkenankement/besiktas-calendar/actions/workflows/update-calendar.yml/badge.svg)](https://github.com/trkenankement/besiktas-calendar/actions/workflows/update-calendar.yml)
[![Lisans: MIT](https://img.shields.io/badge/lisans-MIT-blue.svg)](LICENSE)
[![Takipçi](https://img.shields.io/github/watchers/trkenankement/besiktas-calendar?label=takip%C3%A7i&style=flat)](https://github.com/trkenankement/besiktas-calendar)
[![Yıldız](https://img.shields.io/github/stars/trkenankement/besiktas-calendar?label=y%C4%B1ld%C4%B1z&style=flat)](https://github.com/trkenankement/besiktas-calendar)

Beşiktaş **erkek A takım futbol ve basketbol** maçlarını her gün otomatik güncellenen takvim
aboneliklerine (ICS) dönüştürür. Bir kez abone olursunuz; yeni maçlar, saat değişiklikleri ve
sonuçlar takviminize kendiliğinden yansır.

> Bağımsız bir projedir; Beşiktaş'ın, TFF'nin, UEFA'nın, EuroLeague'in ya da TBF'nin resmî bir ürünü değildir
> ve onlarla bir bağlantısı yoktur. Veriler bu kuruluşların herkese açık sayfalarından okunur.

## Abone ol

Web sayfası: **<https://trkenankement.github.io/besiktas-calendar/>**

| Takvim | Apple Takvim (iPhone, iPad, Mac) | Google Takvim (Android) | Outlook ve diğerleri (URL ile ekle) |
| --- | --- | --- | --- |
| Tüm maçlar | [webcal://…/besiktas-all.ics](webcal://trkenankement.github.io/besiktas-calendar/besiktas-all.ics) | [Google Takvim'e ekle](https://calendar.google.com/calendar/r?cid=webcal://trkenankement.github.io/besiktas-calendar/besiktas-all.ics) | `https://trkenankement.github.io/besiktas-calendar/besiktas-all.ics` |
| Futbol | [webcal://…/besiktas-football.ics](webcal://trkenankement.github.io/besiktas-calendar/besiktas-football.ics) | [Google Takvim'e ekle](https://calendar.google.com/calendar/r?cid=webcal://trkenankement.github.io/besiktas-calendar/besiktas-football.ics) | `https://trkenankement.github.io/besiktas-calendar/besiktas-football.ics` |
| Basketbol | [webcal://…/besiktas-basketball.ics](webcal://trkenankement.github.io/besiktas-calendar/besiktas-basketball.ics) | [Google Takvim'e ekle](https://calendar.google.com/calendar/r?cid=webcal://trkenankement.github.io/besiktas-calendar/besiktas-basketball.ics) | `https://trkenankement.github.io/besiktas-calendar/besiktas-basketball.ics` |

Web sayfasında her takvim için **Apple Takvim** ve **Google Takvim** düğmeleri ile ayrı bir **.ics indir** bağlantısı bulunur.

> **Android:** Google Takvim uygulaması telefonda URL ile abone olmayı desteklemez. Bu yüzden Google Takvim
> bağlantısı, ekleme onayının yapıldığı Google Takvim web sayfasını açar; telefonda açılmazsa tarayıcıda
> "Masaüstü sitesi"ni seçin ya da bağlantıyı bilgisayarda açın. Eklenen takvim telefona kendiliğinden gelir.
> Yalnızca telefonla tek dokunuşta abone olmak isteyenler için açık kaynaklı [ICSx⁵](https://icsx5.bitfire.at/)
> uygulaması `webcal://` bağlantılarını açabilir (F-Droid'de ücretsiz, Google Play'de küçük bir ücretle).
>
> **.ics indir:** dosyayı indirip açarsanız maçlar yalnızca bir kez eklenir, sonradan güncellenmez.

> Veriler günde bir kez, gece 00:07'de (Türkiye saati) kaynaklardan okunur. Takvim uygulamaları yayınlanan
> dosyayı kendi aralığında (Google genellikle 12–24 saat, Apple için akışta 12 saat önerilir) yeniden indirir;
> bu, kaynak sitelere gitmez, yalnızca hazır dosyayı okur.

**Abone sayısı neden yok?** Takvim abonelikleri anonimdir: Google, Apple ve Outlook takvimi kendi
sunucularından çeker ve GitHub Pages erişim kaydı vermez; bu yüzden gerçek abone sayısı ölçülemez. Yukarıdaki
rozetler ve web sayfasındaki sayı, GitHub'da projeyi **takip eden** ve **yıldızlayan** kişi sayısıdır; günlük
iş akışıyla kendiliğinden güncellenir. (Tahmini abone sayısı için takvim adresinin önüne sayaçlı bir ara
katman koymak gerekir; bu, adresi değiştirdiği ve bir dış hizmet gerektirdiği için şimdilik yapılmadı.)

## Nasıl çalışır?

GitHub Actions her gün gece 00:07'de (Türkiye saati) ve `main` dalına her gönderimde (yani kodu
değiştirdiğinizde) şunları yapar:

1. Testleri çalıştırır.
2. Aşağıdaki resmi kaynaklardan Beşiktaş maçlarını okur.
3. `docs/` klasöründeki ICS dosyalarını ve web sayfasını üretir; **yalnızca gerçekten değişen** dosyaları
   commit eder (her gün anlamsız commit oluşmaz).
4. Siteyi GitHub Pages'e yayınlar.

| Müsabaka | Kaynak |
| --- | --- |
| Trendyol Süper Lig | [TFF](https://www.tff.org/) fikstür sayfaları |
| Ziraat Türkiye Kupası, Süper Kupa | [TFF](https://www.tff.org/) kupa fikstürü ve Süper Kupa arşivi |
| UEFA Şampiyonlar / Avrupa / Konferans Ligi | [UEFA](https://www.uefa.com/) maç verisi |
| EuroLeague (ve EuroCup) | [EuroLeague Basketball](https://www.euroleaguebasketball.net/) resmi API'si |
| Basketbol Süper Ligi, Cumhurbaşkanlığı / Türkiye / Federasyon Kupası | [TBF](https://www.tbf.org.tr/) web API'si |

Beşiktaş'ın resmi sitesi (bjk.com.tr) otomatik istemcilere Cloudflare doğrulaması uyguladığı için
kaynak olarak kullanılmaz; koruma aşılmaya çalışılmaz.

### Saat kesin değilse

Federasyonlar maç saatlerini genellikle 1–2 hafta önceden açıklar. Saati henüz belli olmayan (kaynakta
boş ya da `00:00` yer tutucusu olan) maçlar yanlış bir gece yarısı saati yazılmasın diye **tüm gün /
taslak** etkinlik olarak yayınlanır. Saat açıklanınca aynı etkinlik (aynı UID) güncellenir; takviminizde
çoğalmaz.

### Bir kaynak bozulursa

Kaynaklardan biri yanıt vermezse ya da sayfa yapısı değişirse çalışma **başarısız olur** ve GitHub sizi
bilgilendirir. Eksik veri yayınlanmaz; site bir önceki sağlam sürümle yayında kalır. Yalnızca TFF'nin
editöryel kupa sayfaları (Türkiye Kupası ve Süper Kupa) isteğe bağlıdır: bozulurlarsa uyarı verilir, diğer
müsabakalar yayınlanmaya devam eder. Web sayfası da son kontrol 36 saatten eskiyse ekranda "güncel olmayabilir"
uyarısı gösterir.

### Elle çalıştırma ve sorun giderme

- Takvimi hemen yenilemek için GitHub'da **Actions → Update calendars → Run workflow**.
- Bir çalışma kırmızıysa çalışmayı açın: **Update calendars** adımı hangi kaynağın neden başarısız olduğunu
  yazar. Bu sürede site, son sağlam sürümle yayında kalır.
- Kaynakta tek bir maçın tarihi okunamazsa (ör. ertelenmiş maç) o maç atlanır ve çalışmada sarı bir uyarı
  görürsünüz; diğer maçlar etkilenmez. Kaynağın biçimi topluca bozulmuşsa çalışma yine başarısız olur.
- Bir kaynağın verisi mantıksız bir tarihe (bugünden 500 günden uzak) işaret ediyorsa yayın durdurulur.

### Kapsam ve bilinen sınırlar

- **Basketbol kupaları** (Cumhurbaşkanlığı, Türkiye ve Federasyon Kupası) TBF'den güncel sezonun turnuvası
  oluşturulur oluşturulmaz otomatik eklenir; henüz oluşturulmamış olanlar atlanır.
- **Ziraat Türkiye Kupası** (futbol): TFF sayfası yalnızca güncel turu gösterir; Beşiktaş'ın maçı listelenince
  eklenir (Beşiktaş kupaya henüz girmedi).
- **Süper Kupa** (futbol): TFF'nin arşiv tablosunda maç göründüğünde eklenir. Tabloda saat olmadığı için tüm gün
  etkinliği olarak yayınlanır.
- Yalnızca erkek A takımlar; altyapı ve kadın takımları yok.

## Güvenlik

Ayrıntılar [SECURITY.md](SECURITY.md) dosyasında. Kısaca: kaynak verisi ICS'e kaçışlanarak yazılır; web
sayfası sıkı bir içerik güvenlik politikasıyla (CSP) yayınlanır; iş akışı en az yetkiyle çalışır, kullanılan
Actions tam commit numarasına sabitlidir ve depo belirteci yalnızca güvenilir `gh`/`git` adımlarına verilir
(paket kurulumu, testler ve üretici kod onu hiç görmez). Bu kurallar
`tests/test_security.py` ile her çalışmada denetlenir. Bir açık bulursanız lütfen herkese açık issue yerine
[özel bildirim](https://github.com/trkenankement/besiktas-calendar/security/advisories/new) gönderin.

## Geliştirme

```bash
python -m venv .venv
.venv\Scripts\activate          # macOS/Linux: source .venv/bin/activate
pip install -e ".[dev,lint]"

pytest                          # çevrimdışı testler (gerçek yanıtlardan küçültülmüş örnekler)
ruff check src tests            # stil ve olası hatalar
bandit -r src -c pyproject.toml # güvenlik taraması
club-calendar                   # canlı kaynaklardan docs/ klasörünü üretir (python -m club_calendar de olur)
club-calendar --out cikti       # başka bir klasöre yaz
```

Hangi kulübün takip edildiğini kökteki `club.toml` belirler (`club = "besiktas"`); kulüp tanımları
`src/club_calendar/club.py` içindedir. `--club fenerbahce` gibi bir seçenek `club.toml`'u geçici olarak geçersiz kılar.

```text
.github/workflows/update-calendar.yml   test → üret → gerekirse commit → Pages'e yayınla
club.toml                               takip edilen kulüp
src/club_calendar/
  club.py  feeds.py                     kulüp profilleri (ad, UEFA/EuroLeague kimliği), yayınlanan takvim akışları
  providers/                            tff.py · uefa.py · euroleague.py · tbf.py (her biri ortak Match modeli döndürür)
  models.py  names.py  http.py          veri modeli, Türkçe isim düzeltme, yeniden denemeli HTTP
  ics.py  site.py  stats.py  donate.py  ICS üretimi, web sayfası, GitHub takipçi/yıldız sayısı, bağış bilgileri
  build.py  cli.py  console.py          doğrulama, çıktı yazma, komut satırı, konsol/Actions çıktısı
tests/                                  testler ve tests/fixtures (gerçek yanıt örnekleri); test_security.py güvenlik
                                        kuralları, test_workflow_scripts.py iş akışı betiklerini gerçekten çalıştırır
docs/                                   yayınlanan site: ICS dosyaları + index.html (otomatik üretilir)
SECURITY.md                             güvenlik politikası ve açık bildirme yolu
```

Yeni bir müsabaka eklemek için `providers/` altına kulübün maçlarını `Match` listesi olarak döndüren
bir işlev yazıp `providers/__init__.py` içindeki `providers_for` işlevine eklemek yeterlidir.

## Projeyi destekle

Takvim ücretsizdir ve öyle kalacak. Beğendiyseniz isteğe bağlı olarak **USDT (Tether)** ile destek
olabilirsiniz; herhangi bir borsa ya da cüzdandan gönderebilirsiniz.

| | |
| --- | --- |
| Coin | USDT (Tether) |
| Ağ | **BNB Smart Chain (BSC / BEP-20)** |
| Adres | `0x315f79cb95f784c18387c3009798d1a617dac8b2` |

<img src="docs/usdt-bsc.svg" alt="USDT (BSC) adresi için QR kod" width="180">

> ⚠ Yalnızca USDT'yi ve yalnızca **BSC (BEP-20)** ağı üzerinden gönderin. Başka bir ağdan ya da başka bir
> coin ile gönderilen tutarlar geri alınamaz.

## Lisans

[MIT](LICENSE)
