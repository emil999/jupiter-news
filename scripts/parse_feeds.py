"""Собирает последние записи RSS-лент в feeds/latest.json."""
import html, json, re, sys, xml.etree.ElementTree as ET
from datetime import datetime, timezone

FEEDS = {"Oborot.ru": "feeds/oborot.xml", "Retail.ru": "feeds/retail.xml"}
out = {"updated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "feeds": {}}

def clean(s):
    s = re.sub(r"<[^>]+>", " ", s or "")
    return re.sub(r"\s+", " ", html.unescape(s)).strip()

for name, path in FEEDS.items():
    try:
        root = ET.parse(path).getroot()
        items = []
        for it in root.iter("item"):
            full = it.findtext("{http://purl.org/rss/1.0/modules/content/}encoded") or it.findtext("{http://www.yandex.ru}full-text")
            items.append({
                "title": clean(it.findtext("title")),
                "link": (it.findtext("link") or "").strip(),
                "date": (it.findtext("pubDate") or "").strip(),
                "description": clean(it.findtext("description"))[:1500],
                "full_text": clean(full)[:6000] if full else "",
            })
            if len(items) >= 20:
                break
        out["feeds"][name] = {"ok": True, "items": items}
    except Exception as e:
        out["feeds"][name] = {"ok": False, "error": str(e), "items": []}
        print(f"{name}: {e}", file=sys.stderr)

json.dump(out, open("feeds/latest.json", "w"), ensure_ascii=False, indent=2)
