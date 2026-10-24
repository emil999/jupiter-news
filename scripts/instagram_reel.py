"""Раз в неделю публикует в Instagram следующий Reels из reels/scripts.json.

Видео рендерится здесь же (reels/render.py), кладётся в ig/reels/ и отдаётся
Instagram по ссылке raw.githubusercontent.com. Опубликованные id — в reels_posted.json.
Когда все сценарии опубликованы, ничего не делает: нужно добавить новые в reels/scripts.json.
Ключи в лог не выводятся.
"""
import json, os, shutil, subprocess, sys, time, traceback, urllib.parse, urllib.request
sys.path.insert(0, os.path.dirname(__file__))
from instagram_publish import http, graph_base, graph_error, BOT_CTA, UA, RAW_URL, git

POSTED = "reels_posted.json"
TAGS = "#маркетплейсы #wildberries #ozon #селлеры #jupiteragency"


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
    # видео кладём в репозиторий и отдаём Instagram по ссылке raw.githubusercontent.com
    os.makedirs("ig/reels", exist_ok=True)
    name = nxt["id"] + ".mp4"
    shutil.move(out, os.path.join("ig/reels", name))
    for old in sorted(os.listdir("ig/reels")):
        if old != name and old.endswith(".mp4"):
            os.remove(os.path.join("ig/reels", old))
    git("config", "user.name", "github-actions[bot]")
    git("config", "user.email", "41898333+github-actions[bot]@users.noreply.github.com")
    git("add", "-A", "ig/reels")
    git("commit", "-m", f"Reels: видео {nxt['id']}")
    for _ in range(3):
        if subprocess.run(["git", "pull", "--rebase", "origin", "main"]).returncode == 0 and \
           subprocess.run(["git", "push", "origin", "main"]).returncode == 0:
            break
        time.sleep(5)
    video_url = RAW_URL.format(repo=os.environ.get("GITHUB_REPOSITORY", "emil999/jupiter-news"), name="reels/" + name)
    for _ in range(12):
        if http("HEAD", video_url, timeout=30)[0] == 200:
            break
        time.sleep(5)
    caption = f"{nxt['caption']}\n\n{BOT_CTA}\n\nНовости для селлеров каждый день — в Telegram-канале @jupiteragency\n\n{TAGS}"
    st, body = http("POST", f"{base}{ig_user}/media", {"media_type": "REELS", "video_url": video_url,
                    "caption": caption[:2200], "share_to_feed": "true",
                    # обложка — кадр на 2,8 с, когда заголовок уже полностью на экране
                    "thumb_offset": "2800", "access_token": token})
    if st != 200:
        print("::error::Не удалось создать Reels: " + graph_error(body)); return 1
    cid = json.loads(body)["id"]
    for _ in range(30):  # обработка видео — до 10 минут
        time.sleep(20)
        st, body = http("GET", f"{base}{cid}?" + urllib.parse.urlencode({"fields": "status_code,status", "access_token": token}))
        code = json.loads(body).get("status_code") if st == 200 else None
        if code == "FINISHED":
            break
        if code in ("ERROR", "EXPIRED"):
            print("::error::Instagram не обработал видео: " + str(code) + " " + str(json.loads(body).get("status"))); return 1
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
    try:
        sys.exit(main())
    except Exception as e:  # покажем причину в аннотации запуска (без ключей)
        print("::error::" + type(e).__name__ + ": " + str(e)[:300])
        traceback.print_exc()
        sys.exit(1)
