"""Раз в неделю публикует в Instagram следующий Reels из reels/scripts.json.

Видео рендерится здесь же (reels/render.py) и загружается напрямую в Instagram
(resumable upload), без промежуточного хостинга. Опубликованные id — в reels_posted.json.
Когда все сценарии опубликованы, ничего не делает: нужно добавить новые в reels/scripts.json.
Ключи в лог не выводятся.
"""
import json, os, subprocess, sys, time, urllib.parse, urllib.request
sys.path.insert(0, os.path.dirname(__file__))
from instagram_publish import http, graph_base, graph_error, BOT_CTA, UA

POSTED = "reels_posted.json"
TAGS = "#маркетплейсы #wildberries #ozon #селлеры #jupiteragency"


def upload(uri_base, cid, path, token):
    data = open(path, "rb").read()
    req = urllib.request.Request(f"{uri_base}{cid}", data=data, method="POST", headers={
        "Authorization": f"OAuth {token}", "offset": "0", "file_size": str(len(data)), "User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=300) as r:
            return r.status, r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")


def main():
    ig_user = os.environ.get("IG_USER_ID", "").strip()
    token = os.environ.get("IG_ACCESS_TOKEN", "").strip()
    if not ig_user or not token:
        print("Секреты IG_USER_ID / IG_ACCESS_TOKEN не заданы — пропускаю."); return 0
    scripts = json.load(open("reels/scripts.json", encoding="utf-8"))
    posted = json.load(open(POSTED, encoding="utf-8")) if os.path.exists(POSTED) else []
    nxt = next((s for s in scripts if s["id"] not in posted), None)
    if not nxt:
        print("::warning::Все сценарии Reels уже опубликованы — добавьте новые в reels/scripts.json"); return 0
    print("Рендерю:", nxt["id"])
    out = f"/tmp/{nxt['id']}.mp4"
    subprocess.run([sys.executable, "reels/render.py", nxt["id"], out], check=True)

    base = graph_base()
    v = base.rstrip("/").rsplit("/", 1)[-1]
    caption = f"{nxt['caption']}\n\n{BOT_CTA}\n\nНовости для селлеров каждый день — в Telegram-канале @jupiteragency\n\n{TAGS}"
    st, body = http("POST", f"{base}{ig_user}/media", {"media_type": "REELS", "upload_type": "resumable",
                    "caption": caption[:2200], "share_to_feed": "true", "access_token": token})
    if st != 200:
        print("::error::Не удалось создать Reels: " + graph_error(body)); return 1
    cid = json.loads(body)["id"]
    st, body = upload(f"https://rupload.facebook.com/ig-api-upload/{v}/", cid, out, token)
    if st != 200:
        print("::error::Не удалось загрузить видео: " + graph_error(body)); return 1
    for _ in range(30):  # обработка видео — до 10 минут
        time.sleep(20)
        st, body = http("GET", f"{base}{cid}?" + urllib.parse.urlencode({"fields": "status_code", "access_token": token}))
        code = json.loads(body).get("status_code") if st == 200 else None
        if code == "FINISHED":
            break
        if code in ("ERROR", "EXPIRED"):
            print("::error::Instagram не обработал видео: " + str(code)); return 1
    else:
        print("::error::Instagram слишком долго обрабатывает видео"); return 1
    st, body = http("POST", f"{base}{ig_user}/media_publish", {"creation_id": cid, "access_token": token})
    if st != 200:
        print("::error::Не удалось опубликовать Reels: " + graph_error(body)); return 1
    posted.append(nxt["id"])
    with open(POSTED, "w", encoding="utf-8") as f:
        json.dump(posted, f, ensure_ascii=False, indent=2); f.write("\n")
    print("::notice::Reels опубликован: " + nxt["id"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
