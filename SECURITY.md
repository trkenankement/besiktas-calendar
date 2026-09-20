# Güvenlik Politikası

## Güvenlik açığı bildirme

Bir güvenlik sorunu fark ederseniz lütfen herkese açık bir issue **açmayın**. Bunun yerine GitHub'ın
özel bildirim özelliğini kullanın:
[Güvenlik açığı bildir](https://github.com/trkenankement/besiktas-calendar/security/advisories/new)
(depo sayfasında **Security → Report a vulnerability**).

Bildirimlere en kısa sürede yanıt verilmeye çalışılır.

## Kapsam

Bu proje herkese açık müsabaka verilerini okuyup statik dosyalar (ICS takvimleri ve bir HTML sayfası)
üretir. Kullanıcı hesabı, form, veritabanı ya da gizli anahtar içermez.

## Alınan önlemler

- **Girdi güvenliği:** Kaynak sitelerden gelen metinler ICS'e RFC 5545'e göre kaçışlanarak yazılır
  (denetim karakterleri silinir); yeni bir özellik ya da etkinlik enjekte edilemez. Web sayfasında tüm
  dinamik alanlar HTML kaçışından geçer ve sayfa, yalnızca kendi satır içi kodunun özet değerine izin
  veren sıkı bir içerik güvenlik politikasıyla (CSP) yayınlanır.
- **İş akışı (GitHub Actions):** En az yetkiyle çalışır; kullanılan tüm eylemler tam commit numarasına
  sabitlidir; depo belirteci (token) diskte bırakılmaz ve yalnızca güvenilir `gh`/`git` adımlarına verilir
  (paket kurulumu, testler ve üretici kod onu görmez); iş akışı
  yalnızca `main` dalına gönderimde, zamanlanmış ve elle tetiklemede çalışır (`pull_request_target`
  yok). Bu kurallar `tests/test_security.py` ile her çalışmada denetlenir.
- **Depo ayarları:** Gizli anahtar taraması ve push koruması, bağımlılık uyarıları ve otomatik
  güvenlik güncellemeleri, CodeQL taraması ve özel güvenlik bildirimi açıktır.
- **Bağımlılıklar:** Yalnızca `requests` ve `beautifulsoup4` çalışma zamanında kullanılır.
