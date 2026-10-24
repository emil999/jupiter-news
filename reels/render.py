"""Рендер 30-секундного вертикального видео (1080×1920) для Reels из reels/scripts.json.

    python3 reels/render.py <id> <out.mp4>

Нужны: playwright (chromium) и ffmpeg. Видео без звука — музыку можно добавить в Instagram.
"""
import asyncio, base64, html, json, os, shutil, subprocess, sys, tempfile
from playwright.async_api import async_playwright

HERE = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.path.join(HERE, "assets")
FPS, TOTAL = 30, 30.0
BOT = "@jupiteragency_bot"
e = lambda s: html.escape(str(s))


def layout(scenes):
    """Раскладывает сцены по времени: CTA и концовка фиксированы, остальное делится между сценами."""
    fixed = {"hook": 3.6, "bars": 5.6, "cta": 4.6}
    outro = 3.6
    flex = [s for s in scenes if s["type"] == "list"]
    used = sum(fixed.get(s["type"], 0) for s in scenes) + outro
    rest = max(0.0, TOTAL - used)
    out, t = [], 0.0
    for s in scenes:
        d = fixed.get(s["type"], rest / max(1, len(flex)))
        out.append((s, t, t + d)); t += d
    return out, t


def scene_html(s, t0, t1):
    a = lambda d, extra="", cls="": f'class="a {cls}" data-in="{t0 + d:.2f}" data-out="{t1 - 0.35:.2f}" {extra}'
    ty = s["type"]
    if ty == "hook":
        lines = "".join(f'<div {a(0.3 + 0.35 * i, "", "h")}>{e(l)}</div>' for i, l in enumerate(s["lines"]))
        n = len(s["lines"])
        return f'''<div class="sc"><div {a(0.1, "", "k")}>{e(s["kicker"])}</div><div style="height:40px"></div>{lines}
<div {a(0.3 + 0.35 * n, "", "h")}><em>{e(s["accent"])}</em></div>
<div {a(1.0 + 0.35 * n, 'style="margin-top:50px"', "sub")}>{e(s.get("sub", ""))}</div></div>'''
    if ty == "bars":
        return f'''<div class="sc"><div {a(0.1, "", "m")}>{e(s["title"])}<em>{e(s["accent"])}</em></div>
<div {a(0.3, "", "bars")}><div class="bar x"><b>{e(s["from"])} {e(s["unit"])}</b><i style="height:12%"></i><small>{e(s["label_from"])}</small></div>
<div class="bar y"><b class="cnt" data-from="{s["from"]}" data-to="{s["to"]}" data-unit="{e(s["unit"])}" data-t0="{t0 + 0.9:.2f}">{e(s["from"])} {e(s["unit"])}</b><i class="grow" data-t0="{t0 + 0.9:.2f}" style="height:12%"></i><small>{e(s["label_to"])}</small></div></div></div>'''
    if ty == "list":
        n = len(s["items"]); step = min(2.4, (t1 - t0 - 2.2) / n)
        items = "".join(f'<div {a(0.7 + i * step, "", "it")}><b>{i + 1:02d}</b><span>{e(x)}</span></div>' for i, x in enumerate(s["items"]))
        mb = 'style="margin-bottom:24px"'
        return f'<div class="sc" style="justify-content:flex-start;top:330px"><div {a(0.1, mb, "m")}>{e(s["title"])}<em>{e(s["accent"])}</em></div>{items}</div>'
    if ty == "cta":
        return f'''<div class="sc"><div {a(0.1, "", "k")}>Бесплатно</div><div style="height:30px"></div>
<div {a(0.3, "", "m")}>Чек-лист <em>«20 причин, почему карточка не продаёт»</em></div>
<div {a(0.9, 'style="margin-top:40px"', "sub")}>Заберите в нашем Telegram-боте</div>
<div {a(1.4, "", "cta")}>{BOT}</div></div>'''
    raise ValueError(ty)


def build_html(script):
    timed, t_end = layout(script["scenes"])
    logo = "data:image/png;base64," + base64.b64encode(open(os.path.join(ASSETS, "cover-logo.png"), "rb").read()).decode()
    body = "".join(scene_html(s, t0, t1) for s, t0, t1 in timed)
    body += f'''<div class="sc" style="align-items:flex-start"><img class="a logo" data-in="{t_end + 0.1:.2f}" data-out="99" src="{logo}">
<div class="a m" data-in="{t_end + 0.3:.2f}" data-out="99" style="margin-top:50px;font-size:84px">Jupiter Agency</div>
<div class="a sub" data-in="{t_end + 0.5:.2f}" data-out="99" style="margin-top:12px">агентство продвижения на маркетплейсах</div>
<div class="a ct" data-in="{t_end + 0.8:.2f}" data-out="99" style="margin-top:60px">Telegram <span>@jupitermp</span><br>jupiteragency.ru</div></div>'''
    css = open(os.path.join(HERE, "style.css"), encoding="utf-8").read().replace("ASSETS", "file://" + ASSETS)
    js = open(os.path.join(HERE, "anim.js"), encoding="utf-8").read().replace("TOTAL", str(TOTAL))
    return f'<!doctype html><html><head><meta charset="utf-8"><style>{css}</style></head><body><div id="glow"></div><div id="prog"><i></i></div>{body}<script>{js}</script></body></html>'


async def frames(page_html, d):
    src = os.path.join(d, "reel.html"); open(src, "w", encoding="utf-8").write(page_html)
    async with async_playwright() as p:
        b = await p.chromium.launch(); pg = await b.new_page(viewport={"width": 1080, "height": 1920})
        await pg.goto("file://" + src); await pg.wait_for_timeout(800)
        for n in range(int(FPS * TOTAL)):
            await pg.evaluate(f"render({n / FPS})")
            await pg.screenshot(path=os.path.join(d, f"{n:04d}.jpg"), type="jpeg", quality=90)
        await b.close()


def render(script_id, out):
    script = next(s for s in json.load(open(os.path.join(HERE, "scripts.json"), encoding="utf-8")) if s["id"] == script_id)
    d = tempfile.mkdtemp()
    try:
        asyncio.run(frames(build_html(script), d))
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-framerate", str(FPS), "-i", os.path.join(d, "%04d.jpg"),
                        "-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=44100", "-shortest",
                        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "20", "-preset", "medium",
                        "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart", out], check=True)
    finally:
        shutil.rmtree(d, ignore_errors=True)


if __name__ == "__main__":
    render(sys.argv[1], sys.argv[2])
