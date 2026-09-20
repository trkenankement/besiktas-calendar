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

- **Tüm maçlar** <a href="https://trkenankement.github.io/besiktas-calendar/#all"><img src="https://img.shields.io/static/v1?label=&message=Takvime%20abone%20ol&color=2ea44f" alt="Takvime abone ol" height="28"></a> <a href="https://trkenankement.github.io/besiktas-calendar/besiktas-all.ics"><img src="https://img.shields.io/static/v1?label=&message=.ics%20indir&color=555555" alt=".ics indir" height="28"></a>
- **Futbol** <a href="https://trkenankement.github.io/besiktas-calendar/#football"><img src="https://img.shields.io/static/v1?label=&message=Takvime%20abone%20ol&color=2ea44f" alt="Takvime abone ol" height="28"></a> <a href="https://trkenankement.github.io/besiktas-calendar/besiktas-football.ics"><img src="https://img.shields.io/static/v1?label=&message=.ics%20indir&color=555555" alt=".ics indir" height="28"></a>
- **Basketbol** <a href="https://trkenankement.github.io/besiktas-calendar/#basketball"><img src="https://img.shields.io/static/v1?label=&message=Takvime%20abone%20ol&color=2ea44f" alt="Takvime abone ol" height="28"></a> <a href="https://trkenankement.github.io/besiktas-calendar/besiktas-basketball.ics"><img src="https://img.shields.io/static/v1?label=&message=.ics%20indir&color=555555" alt=".ics indir" height="28"></a>

Düğmeler siteye götürür; oradaki düğme cihazınıza göre Apple Takvim'e ya da Google Takvim'e ekler.

**Abone sayısı neden yok?** Takvim abonelikleri anonimdir: Google, Apple ve Outlook takvimi kendi
sunucularından çeker ve GitHub Pages erişim kaydı vermez; bu yüzden gerçek abone sayısı ölçülemez. Yukarıdaki
rozetler ve web sayfasındaki sayı, GitHub'da projeyi **takip eden** ve **yıldızlayan** kişi sayısıdır; günlük
iş akışıyla kendiliğinden güncellenir. (Tahmini abone sayısı için takvim adresinin önüne sayaçlı bir ara
katman koymak gerekir; bu, adresi değiştirdiği ve bir dış hizmet gerektirdiği için şimdilik yapılmadı.)

## Kapsam ve bilinen sınırlar

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
