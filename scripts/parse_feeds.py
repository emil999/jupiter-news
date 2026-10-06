"""Собирает последние записи RSS-лент в feeds/latest.json."""
import html, json, re, sys, xml.etree.ElementTree as ET
from datetime import datetime, timezone

FEEDS = {"Oborot.ru": "feeds/oborot.xml", "Retail.ru": "feeds/retail.xml"}
out = {"updated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "feeds": {}}

def local(tag):
    return tag.rsplit("}", 1)[-1]

def clean(s):
    s = re.sub(r"<[^>]+>", " ", s or "")
    return re.sub(r"\s+", " ", html.unescape(s)).strip()

for name, path in FEEDS.items():
    try:
        root = ET.parse(path).getroot()
        items = []
        for it in (e for e in root.iter() if local(e.tag) == "item"):
            f = {}
            for c in it:
                f.setdefault(local(c.tag), c.text or "")
            full = f.get("encoded") or f.get("full-text")
            items.append({
                "title": clean(f.get("title")),
                "link": (f.get("link") or "").strip(),
                "date": (f.get("pubDate") or "").strip(),
                "description": clean(f.get("description"))[:1500],
                "full_text": clean(full)[:6000] if full else "",
            })
            if len(items) >= 20:
                break
        out["feeds"][name] = {"ok": True, "items": items}
    except Exception as e:
        out["feeds"][name] = {"ok": False, "error": str(e), "items": []}
        print(f"{name}: {e}", file=sys.stderr)

json.dump(out, open("feeds/latest.json", "w"), ensure_ascii=False, indent=2)
