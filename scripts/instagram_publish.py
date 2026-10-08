"""Публикует следующий пост из queue.json в Instagram через Instagram Graph API.

Запускается GitHub Action'ом .github/workflows/instagram.yml.
Картинка — квадратная JPEG-обложка, которую скрипт на хостинге кладёт на сайт
после публикации поста в Telegram:
    https://jupiteragency.ru/covers/<id>-square.jpg
Пост публикуется только когда эта обложка уже есть, то есть после Telegram.
Серверы Meta могут не достучаться до российского хостинга, поэтому обложка
скачивается сюда, коммитится в ig/ и отдаётся Instagram по ссылке GitHub.
Опубликованные id записываются в instagram_posted.json.

Секреты репозитория: IG_USER_ID, IG_ACCESS_TOKEN (ключ страницы Facebook,
к которой привязан Instagram). Переменные GRAPH_API_VERSION (по умолчанию
v25.0) и IG_API_HOST — по желанию.
Ключи никогда не печатаются в лог: логи публичного репозитория видны всем.
"""
import json, os, re, subprocess, sys, time, urllib.error, urllib.parse, urllib.request
from datetime import datetime, timedelta, timezone

QUEUE = "queue.json"
POSTED = "instagram_posted.json"
COVER_URL = "https://jupiteragency.ru/covers/{id}-square.jpg"
RAW_URL = "https://raw.githubusercontent.com/{repo}/main/ig/{name}"
KEEP_IMAGES = 20
MAX_AGE = timedelta(hours=48)
UA = "JupiterInstagramPublisher/1.0 (+https://jupiteragency.ru)"


def graph_base():
    # Facebook Login (ключ страницы) — graph.facebook.com.
    # Для Instagram Login можно задать переменную IG_API_HOST=graph.instagram.com.
    host = os.environ.get("IG_API_HOST", "").strip() or "graph.facebook.com"
    v = os.environ.get("GRAPH_API_VERSION", "").strip() or "v25.0"
    return f"https://{host}/{v}/"


def http(method, url, data=None, timeout=60, raw=False):
    body = urllib.parse.urlencode(data).encode() if data is not None else None
    req = urllib.request.Request(url, data=body, method=method, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            content = r.read()
            return r.status, content if raw else content.decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")
    except Exception as e:  # сеть, таймаут
        return 0, str(e)


def safe_id(post_id):
    # как в cover_lib.php: всё, кроме [A-Za-z0-9_-], заменяется на _
    return re.sub(r"[^A-Za-z0-9_-]", "_", post_id)


def caption(post):
    paragraphs = []
    for para in re.split(r"\n\s*\n", post["text"].strip()):
        sentences = [s for s in re.split(r"(?<=[.!?])\s+", para.strip())
                     if s and not re.search(r"(бот|t\.me)", s, re.I)]
        if sentences:
            paragraphs.append(" ".join(sentences))
    text = "\n\n".join(paragraphs)
    src = post.get("source")
    if src and src != "Jupiter Agency":
        text += "\n\nИсточник: " + src
    text += "\n\nНовости для селлеров каждый день — в Telegram-канале @jupiteragency"
    tags = []
    for t in (post.get("hashtags", "") + " #селлеры #маркетплейсы #jupiteragency").split():
        if t not in tags:
            tags.append(t)
    return (text + "\n\n" + " ".join(tags))[:2200]


def git(*args):
    subprocess.run(["git", *args], check=True)


def host_image(post_id, content):
    """Сохранить обложку в ig/, запушить и вернуть ссылку raw.githubusercontent.com."""
    os.makedirs("ig", exist_ok=True)
    name = safe_id(post_id) + ".jpg"
    with open(os.path.join("ig", name), "wb") as f:
        f.write(content)
    # храним только последние KEEP_IMAGES картинок (имена начинаются с даты)
    files = sorted(os.path.join("ig", n) for n in os.listdir("ig") if n.endswith(".jpg"))
    for old in files[:-KEEP_IMAGES]:
        os.remove(old)
    git("config", "user.name", "github-actions[bot]")
    git("config", "user.email", "41898333+github-actions[bot]@users.noreply.github.com")
    git("add", "-A", "ig")
    if subprocess.run(["git", "diff", "--cached", "--quiet"]).returncode == 0:
        pushed = True  # такая обложка уже в репозитории (повторная попытка)
    else:
        git("commit", "-m", f"Instagram: обложка {post_id}")
        pushed = False
    for _ in range(0 if pushed else 3):
        if subprocess.run(["git", "pull", "--rebase", "origin", "main"]).returncode == 0 and \
           subprocess.run(["git", "push", "origin", "main"]).returncode == 0:
            break
        time.sleep(5)
    else:
        if not pushed:
            raise RuntimeError("не удалось запушить обложку")
    url = RAW_URL.format(repo=os.environ.get("GITHUB_REPOSITORY", "emil999/jupiter-news"), name=name)
    for _ in range(12):  # ждём, пока raw-ссылка начнёт отдавать файл
        if http("HEAD", url, timeout=30)[0] == 200:
            return url
        time.sleep(5)
    return url


def graph_error(body):
    try:
        e = json.loads(body).get("error", {})
        return f"{e.get('type')} {e.get('code')}: {e.get('message')}"
    except Exception:
        return body[:300]


def main():
    ig_user = os.environ.get("IG_USER_ID", "").strip()
    token = os.environ.get("IG_ACCESS_TOKEN", "").strip()
    if not ig_user or not token:
        print("Секреты IG_USER_ID / IG_ACCESS_TOKEN не заданы — пропускаю.")
        return 0

    queue = json.load(open(QUEUE, encoding="utf-8"))
    posted = json.load(open(POSTED, encoding="utf-8")) if os.path.exists(POSTED) else []
    now = datetime.now(timezone.utc)

    post = None
    for p in queue:
        if not p.get("id") or not p.get("text") or p["id"] in posted:
            continue
        try:
            created = datetime.fromisoformat(p["created_at"])
        except Exception:
            continue
        if now - created > MAX_AGE:
            continue
        url = COVER_URL.format(id=safe_id(p["id"]))
        status, content = http("GET", url, timeout=60, raw=True)
        if status != 200 or not content[:3] == b"\xff\xd8\xff":
            print(f"{p['id']}: обложки ещё нет ({status}) — значит, в Telegram он ещё не вышел.")
            continue
        post, image = p, content
        break

    if not post:
        print("Нечего публиковать.")
        return 0

    print("Публикую:", post["id"])
    image_url = host_image(post["id"], image)
    base = graph_base()
    status, body = http("POST", f"{base}{ig_user}/media",
                        {"image_url": image_url, "caption": caption(post), "access_token": token})
    if status != 200:
        print("Не удалось создать публикацию:", graph_error(body))
        return 1
    creation_id = json.loads(body)["id"]

    # Instagram скачивает картинку не мгновенно — ждём готовности
    # (документация Meta советует опрашивать не чаще раза в минуту и не дольше 5 минут)
    for attempt in range(6):
        time.sleep(10 if attempt == 0 else 60)
        status, body = http("GET", f"{base}{creation_id}?" + urllib.parse.urlencode(
            {"fields": "status_code", "access_token": token}))
        code = json.loads(body).get("status_code") if status == 200 else None
        if code == "FINISHED":
            break
        if code in ("ERROR", "EXPIRED"):
            print("Instagram не принял картинку:", code)
            return 1

    status, body = http("POST", f"{base}{ig_user}/media_publish",
                        {"creation_id": creation_id, "access_token": token})
    if status != 200:
        print("Не удалось опубликовать:", graph_error(body))
        return 1

    posted.append(post["id"])
    posted = posted[-500:]
    with open(POSTED, "w", encoding="utf-8") as f:
        json.dump(posted, f, ensure_ascii=False, indent=2)
        f.write("\n")
    print("Опубликовано в Instagram:", post["id"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
