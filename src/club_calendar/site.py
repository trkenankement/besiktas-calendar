"""Web sitesinin (GitHub Pages) ana sayfası: abonelik bağlantıları ve sıradaki maçlar."""

from __future__ import annotations

import base64
import hashlib
from datetime import datetime
from html import escape

from .club import Club
from .donate import ANCHOR, NETWORK_NAME, QR_FILENAME, USDT_ADDRESS
from .feeds import feeds_for
from .models import MATCH_DURATION, SPORT_LABELS, TURKEY_TZ, Match
from .stats import RepoStats

UPCOMING_LIMIT = 10
STALE_AFTER_HOURS = 36  # son kontrol bundan eskiyse sayfa "güncel olmayabilir" uyarısı gösterir
WEEKDAYS = ("Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma", "Cumartesi", "Pazar")

CSS = """
:root{--bg:#fff;--fg:#111;--muted:#666;--line:#e3e3e3;--card:#f7f7f7;--btn-bg:#111;--btn-fg:#fff;--warn:#b3261e}
@media (prefers-color-scheme:dark){:root{--bg:#0e0e0e;--fg:#f2f2f2;--muted:#a0a0a0;--line:#2a2a2a;--card:#171717;--btn-bg:#f2f2f2;--btn-fg:#111;--warn:#ff8a80}}
body{margin:0;background:var(--bg);color:var(--fg);font:16px/1.55 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif}
main{max-width:760px;margin:0 auto;padding:32px 16px 48px}
h1{font-size:1.8rem;margin:0 0 .4rem}
h2{font-size:1.15rem;margin:2rem 0 .6rem}
h3{margin:0;font-size:1.05rem}
a{color:inherit}
.feed{border:1px solid var(--line);background:var(--card);border-radius:12px;padding:14px 16px;margin:10px 0}
.feed p{margin:.15rem 0 .7rem;color:var(--muted)}
.btn{display:inline-block;padding:9px 14px;border-radius:10px;background:var(--btn-bg);color:var(--btn-fg);text-decoration:none;font-weight:600}
.actions{display:flex;flex-wrap:wrap;align-items:center;gap:8px 14px}
[data-platform="android"] .for-apple,[data-platform="apple"] .for-google{display:none}
ul.how{margin:.2rem 0 .6rem;padding-left:1.2rem}
.how li{margin:.35rem 0}
a:focus-visible{outline:3px solid #888;outline-offset:2px}
code{display:block;margin-top:.7rem;padding:8px 10px;border-radius:8px;background:var(--bg);border:1px solid var(--line);font-size:.85rem;word-break:break-all}
ul.matches{list-style:none;margin:0;padding:0}
.matches li{padding:10px 0;border-bottom:1px solid var(--line)}
.when{font-weight:600}
.teams{font-size:1.05rem}
.meta,.muted{color:var(--muted);font-size:.9rem}
.warn{margin:1rem 0;padding:10px 12px;border:1px solid var(--warn);border-radius:10px;color:var(--warn);font-weight:600}
.donate-row{display:flex;gap:18px;align-items:center;flex-wrap:wrap}
.donate-row img{width:176px;height:176px;background:#fff;border-radius:8px}
.donate-row div{flex:1;min-width:220px}
button.btn{border:0;font:inherit;font-weight:600;cursor:pointer;margin-top:.7rem}
.feed .note{margin:1rem 0 0;font-size:.9rem}
"""

SCRIPT = """
const ua = navigator.userAgent;
const platform = /iPhone|iPad|iPod/.test(ua) || (/Macintosh/.test(ua) && navigator.maxTouchPoints > 1) ? 'apple'
  : /Android/.test(ua) ? 'android' : 'other';
document.documentElement.dataset.platform = platform;
if (platform !== 'other') {
  for (const a of document.querySelectorAll('[data-feed], [data-google]')) a.textContent = 'Takvime abone ol';
}
for (const a of document.querySelectorAll('[data-feed]')) {
  const url = new URL(a.dataset.feed, location.href);
  a.href = 'webcal://' + url.host + url.pathname;
}
for (const a of document.querySelectorAll('[data-google]')) {
  const url = new URL(a.dataset.google, location.href);
  a.href = 'https://calendar.google.com/calendar/r?cid=webcal://' + url.host + url.pathname;
}
for (const c of document.querySelectorAll('[data-url]')) {
  c.textContent = new URL(c.dataset.url, location.href).href;
}
const checked = document.getElementById('checked');
fetch('last_check.txt', { cache: 'no-store' })
  .then(r => (r.ok ? r.text() : Promise.reject(new Error(r.status))))
  .then(text => {
    checked.textContent = text.trim();
    const m = /^(\\d{2})\\.(\\d{2})\\.(\\d{4}) (\\d{2}):(\\d{2})/.exec(text.trim());
    if (!m) return;
    const when = Date.UTC(+m[3], +m[2] - 1, +m[1], +m[4] - 3, +m[5]); // TSİ = UTC+3
    const hours = (Date.now() - when) / 36e5;
    if (hours > __STALE_AFTER_HOURS__) {
      const warn = document.getElementById('stale');
      warn.textContent = '\\u26a0 Son kontrol ' + Math.floor(hours / 24) + ' g\\u00fcn \\u00f6nce yap\\u0131ld\\u0131; ' +
        'otomatik g\\u00fcncelleme \\u00e7al\\u0131\\u015fm\\u0131yor olabilir, takvim g\\u00fcncel olmayabilir.';
      warn.hidden = false;
    }
  })
  .catch(() => { checked.textContent = 'bilinmiyor'; });
const copyButton = document.getElementById('copy-address');
if (copyButton) {
  copyButton.addEventListener('click', () => {
    const address = document.getElementById('usdt-address').textContent.trim();
    navigator.clipboard.writeText(address).then(
      () => { copyButton.textContent = 'Kopyaland\\u0131'; },
      () => { copyButton.textContent = 'Kopyalanamad\\u0131; adresi se\\u00e7ip kopyalay\\u0131n'; }
    );
  });
}
if (location.hostname.endsWith('.github.io')) {
  const owner = location.hostname.split('.')[0];
  const repo = location.pathname.split('/').filter(Boolean)[0];
  if (repo) {
    const link = document.getElementById('repo');
    link.href = 'https://github.com/' + owner + '/' + repo;
    link.hidden = false;
  }
}
""".replace("__STALE_AFTER_HOURS__", str(STALE_AFTER_HOURS))


def _csp_hash(inline_source: str) -> str:
    digest = hashlib.sha256(inline_source.encode("utf-8")).digest()
    return "'sha256-" + base64.b64encode(digest).decode("ascii") + "'"


# Satır içi betik ve stil yalnızca kendi özet değerleriyle çalışır; dışarıdan hiçbir şey yüklenmez.
CONTENT_SECURITY_POLICY = "; ".join(
    [
        "default-src 'none'",
        f"script-src {_csp_hash(SCRIPT)}",
        f"style-src {_csp_hash(CSS)}",
        "img-src 'self' data:",
        "connect-src 'self'",
        "base-uri 'none'",
        "form-action 'none'",
    ]
)


def upcoming(matches: list[Match], now: datetime) -> list[Match]:
    """Henüz bitmemiş maçları tarih sırasıyla döndürür."""
    today = now.astimezone(TURKEY_TZ).date()
    result = []
    for match in sorted(matches, key=lambda m: m.sort_key):
        over = match.start + MATCH_DURATION[match.sport] <= now if match.time_confirmed else match.day < today
        if not over:
            result.append(match)
    return result[:UPCOMING_LIMIT]


def format_when(match: Match) -> str:
    day = match.day
    text = f"{WEEKDAYS[day.weekday()]} {day:%d.%m.%Y}"
    if match.time_confirmed:
        return f"{text} · {match.start.astimezone(TURKEY_TZ):%H:%M}"
    return f"{text} · saat belli değil"


def _match_item(match: Match) -> str:
    meta = " · ".join(p for p in (SPORT_LABELS[match.sport], match.competition, match.round_label, match.venue) if p)
    return (
        f'<li><div class="when">{escape(format_when(match))}</div>'
        f'<div class="teams">{escape(match.home)} - {escape(match.away)}</div>'
        f'<div class="meta">{escape(meta)}</div></li>'
    )


def _feed_card(feed) -> str:
    # Betik cihazı tanır: iPhone/iPad/Mac'te yalnızca Apple, Android'de yalnızca Google düğmesi kalır ("Takvime abone ol");
    # bilgisayarda ikisi de görünür. Betik çalışmazsa iki düğme de dosyanın kendisine gider (indirme/açma).
    return (
        f'<section class="feed" id="{feed.slug}"><h3>{escape(feed.label)}</h3><p>{escape(feed.description)}</p>'
        '<div class="actions">'
        f'<a class="btn for-apple" data-feed="{feed.filename}" href="{feed.filename}">Apple Takvim\'e abone ol</a>'
        f'<a class="btn for-google" data-google="{feed.filename}" href="{feed.filename}" target="_blank" rel="noopener noreferrer">Google Takvim\'e abone ol</a>'
        f'<a class="dl" href="{feed.filename}" download>.ics indir</a>'
        '</div>'
        f'<code data-url="{feed.filename}">{feed.filename}</code></section>'
    )


def _how_to_subscribe() -> str:
    return """<ul class="how muted">
<li class="for-apple"><strong>iPhone, iPad, Mac:</strong> düğme takvimi Apple Takvim'e doğrudan ekler.</li>
<li class="for-google"><strong>Android:</strong> Google Takvim uygulaması telefonda URL ile abone olmayı desteklemez; düğme, ekleme onayının yapıldığı Google Takvim web sayfasını açar. Telefonda açılmazsa tarayıcı menüsünden "Masaüstü sitesi"ni seçin ya da sayfayı bilgisayarda açın. Eklenen takvim telefonunuza kendiliğinden gelir.</li>
<li><strong>Outlook ve diğerleri:</strong> "URL ile takvim ekle" seçeneğine aşağıdaki bağlantıyı yapıştırın.</li>
<li><strong>.ics indir:</strong> maçları yalnızca bir kez ekler, sonradan güncellenmez.</li>
</ul>"""


def _donate_section() -> str:
    return f"""<h2 id="{ANCHOR}">Projeyi destekle</h2>
<p class="muted">Takvim ücretsizdir ve öyle kalacak. Beğendiyseniz isteğe bağlı olarak USDT (Tether) ile destek olabilirsiniz; herhangi bir borsa ya da cüzdandan gönderebilirsiniz.</p>
<section class="feed">
<div class="donate-row">
<img src="{QR_FILENAME}" alt="USDT (BSC) adresi için QR kod" width="176" height="176">
<div>
<p><strong>Coin:</strong> USDT (Tether)<br><strong>Ağ:</strong> {escape(NETWORK_NAME)}</p>
<code id="usdt-address">{USDT_ADDRESS}</code>
<button type="button" class="btn" id="copy-address">Adresi kopyala</button>
</div>
</div>
<p class="note">⚠ Yalnızca USDT'yi ve yalnızca <strong>BSC (BEP-20)</strong> ağı üzerinden gönderin. Başka bir ağdan ya da başka bir coin ile gönderilen tutarlar geri alınamaz.</p>
</section>
"""


def _stats_line(stats: RepoStats | None) -> str:
    if stats is None:
        return ""
    return f'<p class="muted" id="stats">GitHub\'da <strong>{stats.watchers}</strong> takipçi · <strong>{stats.stars}</strong> yıldız</p>\n'


def _sources_text(club: Club) -> str:
    names = ["TFF", "UEFA", *(["EuroLeague Basketball"] if club.euroleague_code else []), "TBF"]
    return f"{', '.join(names[:-1])} ve {names[-1]}"


def render_index(matches: list[Match], now: datetime, club: Club, stats: RepoStats | None = None) -> str:
    feeds = "\n".join(_feed_card(feed) for feed in feeds_for(club))
    coming = upcoming(matches, now)
    items = "\n".join(_match_item(m) for m in coming) or "<li>Yaklaşan maç bulunamadı.</li>"
    name = escape(club.name)
    title = f"{name} Maç Takvimi"
    summary = f"{name} erkek futbol ve basketbol maçları için her gün otomatik güncellenen takvim aboneliği."
    return f"""<!doctype html>
<html lang="tr">
<head>
<meta charset="utf-8">
<meta http-equiv="Content-Security-Policy" content="{CONTENT_SECURITY_POLICY}">
<meta name="referrer" content="no-referrer">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="color-scheme" content="light dark">
<title>{title}</title>
<meta name="description" content="{summary}">
<meta property="og:title" content="{title}">
<meta property="og:description" content="{summary}">
<meta property="og:type" content="website">
<meta property="og:locale" content="tr_TR">
<link rel="icon" href="data:,">
<style>{CSS}</style>
</head>
<body>
<main>
<h1>{title}</h1>
<p>Erkek A takım futbol ve basketbol maçları. Takvim her gün otomatik güncellenir; bir kez abone olmanız yeterli.</p>
{_stats_line(stats)}<p id="stale" class="warn" role="alert" hidden></p>
<h2>Takvime abone ol</h2>
{_how_to_subscribe()}
{feeds}
<h2>Sıradaki maçlar</h2>
<ul class="matches">
{items}
</ul>
<p class="muted">Saati henüz açıklanmamış maçlar, yanlış bir gece yarısı saati yazılmasın diye tüm gün etkinliği olarak gösterilir; saat kesinleşince aynı etkinlik güncellenir.</p>
{_donate_section()}<p class="muted">Son kontrol: <span id="checked">yükleniyor…</span></p>
<p class="muted">Kaynaklar: {_sources_text(club)}. <a id="repo" rel="noopener noreferrer" hidden>Kaynak kod (GitHub)</a></p>
</main>
<script>{SCRIPT}</script>
</body>
</html>
"""
