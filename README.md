# Beşiktaş Maç Takvimi

[![Update calendars](https://github.com/trkenankement/besiktas-calendar/actions/workflows/update-calendar.yml/badge.svg)](https://github.com/trkenankement/besiktas-calendar/actions/workflows/update-calendar.yml)
[![Lisans: MIT](https://img.shields.io/badge/lisans-MIT-blue.svg)](LICENSE)

Beşiktaş **erkek A takım futbol ve basketbol** maçlarını her gün otomatik güncellenen takvim
aboneliklerine (ICS) dönüştürür. Bir kez abone olursunuz; yeni maçlar, saat değişiklikleri ve
sonuçlar takviminize kendiliğinden yansır.

## Abone ol

Web sayfası: **<https://trkenankement.github.io/besiktas-calendar/>**

| Takvim | Apple Takvim | Google Takvim / Outlook (URL ile ekle) |
| --- | --- | --- |
| Tüm maçlar | [webcal://…/besiktas-all.ics](webcal://trkenankement.github.io/besiktas-calendar/besiktas-all.ics) | `https://trkenankement.github.io/besiktas-calendar/besiktas-all.ics` |
| Futbol | [webcal://…/besiktas-football.ics](webcal://trkenankement.github.io/besiktas-calendar/besiktas-football.ics) | `https://trkenankement.github.io/besiktas-calendar/besiktas-football.ics` |
| Basketbol | [webcal://…/besiktas-basketball.ics](webcal://trkenankement.github.io/besiktas-calendar/besiktas-basketball.ics) | `https://trkenankement.github.io/besiktas-calendar/besiktas-basketball.ics` |

> Google Takvim abonelikleri kendi aralığında (genellikle 12–24 saat) yenilenir; Apple Takvim
> için yenileme aralığı akışta 12 saat olarak bildirilir.

## Nasıl çalışır?

GitHub Actions her gün 06:17'de (Türkiye saati) ve `main` dalına her gönderimde şunları yapar:

1. Testleri çalıştırır.
2. Aşağıdaki resmi kaynaklardan Beşiktaş maçlarını okur.
3. `docs/` klasöründeki ICS dosyalarını ve web sayfasını üretir; **yalnızca gerçekten değişen** dosyaları
   commit eder (her gün anlamsız commit oluşmaz).
4. Siteyi GitHub Pages'e yayınlar.

| Müsabaka | Kaynak |
| --- | --- |
| Trendyol Süper Lig | [TFF](https://www.tff.org/) fikstür sayfaları |
| Ziraat Türkiye Kupası | [TFF](https://www.tff.org/) kupa fikstürü |
| UEFA Şampiyonlar / Avrupa / Konferans Ligi | [UEFA](https://www.uefa.com/) maç verisi |
| EuroLeague (ve EuroCup) | [EuroLeague Basketball](https://www.euroleaguebasketball.net/) resmi API'si |
| Türkiye Sigorta Basketbol Süper Ligi | [TBF](https://www.tbf.org.tr/) web API'si |

Beşiktaş'ın resmi sitesi (bjk.com.tr) otomatik istemcilere Cloudflare doğrulaması uyguladığı için
kaynak olarak kullanılmaz; koruma aşılmaya çalışılmaz.

### Saat kesin değilse

Federasyonlar maç saatlerini genellikle 1–2 hafta önceden açıklar. Saati henüz belli olmayan (kaynakta
boş ya da `00:00` yer tutucusu olan) maçlar yanlış bir gece yarısı saati yazılmasın diye **tüm gün /
taslak** etkinlik olarak yayınlanır. Saat açıklanınca aynı etkinlik (aynı UID) güncellenir; takviminizde
çoğalmaz.

### Bir kaynak bozulursa

Kaynaklardan biri yanıt vermezse ya da sayfa yapısı değişirse çalışma **başarısız olur** ve GitHub sizi
bilgilendirir. Eksik veri yayınlanmaz; site bir önceki sağlam sürümle yayında kalır. Yalnızca kupa
kaynağı isteğe bağlıdır: bozulursa uyarı verilir, diğer müsabakalar yayınlanmaya devam eder.

### Kapsam ve bilinen sınırlar

- **Ziraat Türkiye Kupası:** ayrıştırıcı hazırdır; Beşiktaş'ın maçı TFF kupa sayfasında göründüğü anda
  takvime eklenir (kupada Beşiktaş henüz oynamıyor). Sayfa yalnızca güncel turu gösterir.
- **Basketbol kupaları** (Türkiye Kupası, Cumhurbaşkanlığı Kupası) ve **Süper Kupa** henüz kapsanmıyor.
- Yalnızca erkek A takımlar; altyapı ve kadın takımları yok.

## Geliştirme

```bash
python -m venv .venv
.venv\Scripts\activate          # macOS/Linux: source .venv/bin/activate
pip install -e ".[dev]"

pytest                          # çevrimdışı testler (gerçek yanıtlardan küçültülmüş örnekler)
besiktas-calendar               # canlı kaynaklardan docs/ klasörünü üretir (python -m besiktas_calendar de olur)
besiktas-calendar --out cikti   # başka bir klasöre yaz
```

```text
.github/workflows/update-calendar.yml   test → üret → gerekirse commit → Pages'e yayınla
src/besiktas_calendar/
  providers/                            tff.py · uefa.py · euroleague.py · tbf.py (her biri ortak Match modeli döndürür)
  models.py  names.py  http.py          veri modeli, Türkçe isim düzeltme, yeniden denemeli HTTP
  ics.py     site.py   build.py  cli.py ICS/HTML üretimi, doğrulama ve komut satırı
tests/                                  testler ve tests/fixtures (gerçek yanıt örnekleri)
docs/                                   yayınlanan site: ICS dosyaları + index.html (otomatik üretilir)
```

Yeni bir müsabaka eklemek için `providers/` altına Beşiktaş maçlarını `Match` listesi olarak döndüren
bir işlev yazıp `providers/__init__.py` içindeki `PROVIDERS` listesine eklemek yeterlidir.

## Lisans

[MIT](LICENSE)
