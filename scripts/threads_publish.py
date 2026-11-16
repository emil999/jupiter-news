"""Публикует посты из плана threads_queue.json в Threads через Threads API.

Запускается GitHub Action'ом .github/workflows/threads.yml каждый час с 9 до 22 по Москве.
Публикуется пост, у которого наступило время publish_at (МСК) и который еще не вышел.
Посты, опоздавшие больше чем на MAX_LATE, пропускаются: GitHub иногда задерживает
запуски, и старый пост не должен выйти посреди ночи или пачкой.
Опубликованные id записываются в threads_posted.json.

Формат записи плана:
  {"id": "2026-11-18-vopros-ploshchadki",
   "publish_at": "2026-11-18 10:00",
   "text": "Текст до 500 символов",
   "image": "threads/img/keys-odezhda.jpg",   # по желанию, файл в этом репозитории
   "replies": ["Продолжение ветки", "..."]}    # по желанию, ответы под постом

Секрет репозитория: THREADS_ACCESS_TOKEN. THREADS_USER_ID по желанию
(без него id берется из /me). Ключи никогда не печатаются в лог.
"""
import json, os, sys, time, urllib.error, urllib.parse, urllib.request
from datetime import datetime, timedelta, timezone

PLAN = "threads_queue.json"
POSTED = "threads_posted.json"
MSK = timezone(timedelta(hours=3))
MAX_LATE = timedelta(hours=6)
MAX_PER_RUN = 2
LIMIT = 500
RAW_URL = "https://raw.githubusercontent.com/{repo}/main/{path}"


def base():
    host = os.environ.get("THREADS_API_HOST", "").strip() or "graph.threads.net"
    return f"https://{host}/v1.0/"


def http(method, url, data=None, timeout=60):
    body = urllib.parse.urlencode(data).encode() if data is not None else None
    req = urllib.request.Request(url, data=body, method=method, headers={"User-Agent": "JupiterThreadsPublisher/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read() or b"{}")
        except Exception:
            return e.code, {}
    except Exception as e:
        return 0, {"error": {"message": type(e).__name__}}


def err(d):
    return (d.get("error") or {}).get("message", "нет описания")


def load(path, default):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return default


def check_text(t, where):
    n = len(t.encode("utf-16-le")) // 2
    if n > LIMIT:
        raise SystemExit(f"{where}: {n} символов, лимит Threads {LIMIT}")


def create_and_publish(uid, token, text, image_url=None, reply_to=None):
    data = {"text": text, "access_token": token}
    if image_url:
        data.update(media_type="IMAGE", image_url=image_url)
    else:
        data["media_type"] = "TEXT"
    if reply_to:
        data["reply_to_id"] = reply_to
    code, d = http("POST", base() + f"{uid}/threads", data)
    if code != 200 or "id" not in d:
        raise RuntimeError("контейнер не создан: " + err(d))
    cid = d["id"]
    # Meta просит подождать около 30 секунд, пока контейнер обработается
    for _ in range(12):
        time.sleep(10 if image_url else 5)
        code, s = http("GET", base() + f"{cid}?" + urllib.parse.urlencode({"fields": "status,error_message", "access_token": token}))
        st = s.get("status")
        if st == "FINISHED" or (code == 200 and st is None):
            break
        if st in ("ERROR", "EXPIRED"):
            raise RuntimeError("контейнер не обработан: " + str(s.get("error_message", st)))
    code, d = http("POST", base() + f"{uid}/threads_publish", {"creation_id": cid, "access_token": token})
    if code != 200 or "id" not in d:
        raise RuntimeError("публикация не прошла: " + err(d))
    return d["id"]


def main():
    plan = load(PLAN, [])
    for p in plan:  # проверка всего плана: ошибка в тексте видна сразу, а не в день публикации
        check_text(p["text"], p["id"])
        for i, r in enumerate(p.get("replies", []), 1):
            check_text(r, f'{p["id"]}, ответ {i}')
        datetime.strptime(p["publish_at"], "%Y-%m-%d %H:%M")
        if p.get("image") and not os.path.isfile(p["image"]):
            raise SystemExit(f'{p["id"]}: нет файла {p["image"]}')
    if os.environ.get("CHECK_ONLY"):
        print(f"План в порядке: {len(plan)} постов."); return

    token = os.environ.get("THREADS_ACCESS_TOKEN", "").strip()
    if not token:
        print("Нет секрета THREADS_ACCESS_TOKEN, пропускаю."); return
    uid = os.environ.get("THREADS_USER_ID", "").strip()
    if not uid:
        code, d = http("GET", base() + "me?" + urllib.parse.urlencode({"fields": "id", "access_token": token}))
        if code != 200 or "id" not in d:
            raise SystemExit("Threads не принял ключ: " + err(d))
        uid = d["id"]

    now = datetime.now(MSK)
    repo = os.environ.get("GITHUB_REPOSITORY", "emil999/jupiter-news")
    done = 0
    for p in sorted(plan, key=lambda x: x["publish_at"]):
        if done >= MAX_PER_RUN:
            break
        posted = load(POSTED, [])  # перечитываем перед каждым постом: защита от дублей
        if p["id"] in posted:
            continue
        at = datetime.strptime(p["publish_at"], "%Y-%m-%d %H:%M").replace(tzinfo=MSK)
        if at > now:
            continue
        if now - at > MAX_LATE:
            print(f'Пропускаю {p["id"]}: опоздал на {int((now - at).total_seconds() // 3600)} ч.')
            posted.append(p["id"]); json.dump(posted[-500:], open(POSTED, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
            continue
        img = RAW_URL.format(repo=repo, path=p["image"]) if p.get("image") else None
        try:
            pid = create_and_publish(uid, token, p["text"], img)
            print(f'Опубликован {p["id"]}')
            for r in p.get("replies", []):
                time.sleep(5)
                pid = create_and_publish(uid, token, r, reply_to=pid)
            if p.get("replies"):
                print(f'  и {len(p["replies"])} ответ(а) под ним')
        except RuntimeError as e:
            print(f'Ошибка {p["id"]}: {e}'); sys.exit(1)
        posted.append(p["id"])
        json.dump(posted[-500:], open(POSTED, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        done += 1
    if not done:
        print("Нет постов, время которых наступило.")


if __name__ == "__main__":
    main()
