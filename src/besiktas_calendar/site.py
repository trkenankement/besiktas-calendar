"""Web sitesinin (GitHub Pages) ana sayfası: abonelik bağlantıları ve sıradaki maçlar."""

from __future__ import annotations

from datetime import datetime
from html import escape

from .feeds import FEEDS
from .models import MATCH_DURATION, SPORT_LABELS, TURKEY_TZ, Match

UPCOMING_LIMIT = 10
WEEKDAYS = ("Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma", "Cumartesi", "Pazar")

CSS = """
:root{--bg:#fff;--fg:#111;--muted:#666;--line:#e3e3e3;--card:#f7f7f7;--btn-bg:#111;--btn-fg:#fff}
@media (prefers-color-scheme:dark){:root{--bg:#0e0e0e;--fg:#f2f2f2;--muted:#a0a0a0;--line:#2a2a2a;--card:#171717;--btn-bg:#f2f2f2;--btn-fg:#111}}
body{margin:0;background:var(--bg);color:var(--fg);font:16px/1.55 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif}
main{max-width:760px;margin:0 auto;padding:32px 16px 48px}
h1{font-size:1.8rem;margin:0 0 .4rem}
h2{font-size:1.15rem;margin:2rem 0 .6rem}
h3{margin:0;font-size:1.05rem}
a{color:inherit}
.feed{border:1px solid var(--line);background:var(--card);border-radius:12px;padding:14px 16px;margin:10px 0}
.feed p{margin:.15rem 0 .7rem;color:var(--muted)}
.btn{display:inline-block;padding:9px 14px;border-radius:10px;background:var(--btn-bg);color:var(--btn-fg);text-decoration:none;font-weight:600}
.dl{margin-left:12px}
a:focus-visible{outline:3px solid #888;outline-offset:2px}
code{display:block;margin-top:.7rem;padding:8px 10px;border-radius:8px;background:var(--bg);border:1px solid var(--line);font-size:.85rem;word-break:break-all}
ul.matches{list-style:none;margin:0;padding:0}
.matches li{padding:10px 0;border-bottom:1px solid var(--line)}
.when{font-weight:600}
.teams{font-size:1.05rem}
.meta,.muted{color:var(--muted);font-size:.9rem}
"""

SCRIPT = """
for (const a of document.querySelectorAll('[data-feed]')) {
  const url = new URL(a.dataset.feed, location.href);
  a.href = 'webcal://' + url.host + url.pathname;
}
for (const c of document.querySelectorAll('[data-url]')) {
  c.textContent = new URL(c.dataset.url, location.href).href;
}
fetch('last_check.txt').then(r => r.ok ? r.text() : Promise.reject())
  .then(t => { document.getElementById('checked').textContent = t.trim(); })
  .catch(() => { document.getElementById('checked').textContent = 'bilinmiyor'; });
if (location.hostname.endsWith('.github.io')) {
  const owner = location.hostname.split('.')[0];
  const repo = location.pathname.split('/').filter(Boolean)[0];
  if (repo) {
    const link = document.getElementById('repo');
    link.href = 'https://github.com/' + owner + '/' + repo;
    link.hidden = false;
  }
}
"""


def upcoming(matches: list[Match], now: datetime) -> list[Match]:
    """Henüz bitmemiş maçları tarih sırasıyla döndürür."""
    today = now.astimezone(TURKEY_TZ).date()
    result = []
    for match in sorted(matches, key=lambda m: m.sort_key):
        if match.time_confirmed:
            over = match.start + MATCH_DURATION[match.sport] <= now
        else:
            over = match.day < today
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
    return (
        f'<section class="feed"><h3>{escape(feed.label)}</h3><p>{escape(feed.description)}</p>'
        f'<a class="btn" data-feed="{feed.filename}" href="{feed.filename}">Takvime abone ol</a>'
        f'<a class="dl" href="{feed.filename}" download>.ics indir</a>'
        f'<code data-url="{feed.filename}">{feed.filename}</code></section>'
    )


def render_index(matches: list[Match], now: datetime) -> str:
    feeds = "\n".join(_feed_card(feed) for feed in FEEDS)
    coming = upcoming(matches, now)
    items = "\n".join(_match_item(m) for m in coming) or "<li>Yaklaşan maç bulunamadı.</li>"
    return f"""<!doctype html>
<html lang="tr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="color-scheme" content="light dark">
<title>Beşiktaş Maç Takvimi</title>
<meta name="description" content="Beşiktaş erkek futbol ve basketbol maçları için her gün otomatik güncellenen takvim aboneliği.">
<style>{CSS}</style>
</head>
<body>
<main>
<h1>Beşiktaş Maç Takvimi</h1>
<p>Erkek A takım futbol ve basketbol maçları. Takvim her gün otomatik güncellenir; bir kez abone olmanız yeterli.</p>
<h2>Takvime abone ol</h2>
<p class="muted">Apple Takvim için düğmeyi kullanın. Google Takvim ve Outlook'ta "URL ile takvim ekle" seçeneğine aşağıdaki bağlantıyı yapıştırın.</p>
{feeds}
<h2>Sıradaki maçlar</h2>
<ul class="matches">
{items}
</ul>
<p class="muted">Saati henüz açıklanmamış maçlar, yanlış bir gece yarısı saati yazılmasın diye tüm gün etkinliği olarak gösterilir; saat kesinleşince aynı etkinlik güncellenir.</p>
<p class="muted">Son kontrol: <span id="checked">yükleniyor…</span></p>
<p class="muted">Kaynaklar: TFF, UEFA, EuroLeague Basketball ve TBF. <a id="repo" hidden>Kaynak kod (GitHub)</a></p>
</main>
<script>{SCRIPT}</script>
</body>
</html>
"""
