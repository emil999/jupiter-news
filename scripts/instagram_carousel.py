"""Разовая публикация карусели в Instagram из картинок ig/zakrep/*.jpg.

Запускается workflow .github/workflows/instagram-carousel.yml при изменении
файла .github/instagram-carousel. Подпись берётся из ig/zakrep/caption.txt.
Ключи в лог не выводятся.
"""
import glob, json, os, sys, time, urllib.parse
sys.path.insert(0, os.path.dirname(__file__))
from instagram_publish import http, graph_base, graph_error, RAW_URL

def main():
    ig_user = os.environ.get("IG_USER_ID", "").strip()
    token = os.environ.get("IG_ACCESS_TOKEN", "").strip()
    if not ig_user or not token:
        print("::error::Нет секретов IG_USER_ID / IG_ACCESS_TOKEN"); return 1
    repo = os.environ.get("GITHUB_REPOSITORY", "emil999/jupiter-news")
    files = sorted(glob.glob("ig/zakrep/*.jpg"))
    caption = open("ig/zakrep/caption.txt", encoding="utf-8").read().strip()
    base = graph_base()
    children = []
    for f in files:
        url = RAW_URL.format(repo=repo, name="zakrep/" + os.path.basename(f))
        st, body = http("POST", f"{base}{ig_user}/media",
                        {"image_url": url, "is_carousel_item": "true", "access_token": token})
        if st != 200:
            print("::error::Слайд " + os.path.basename(f) + ": " + graph_error(body)); return 1
        children.append(json.loads(body)["id"])
    st, body = http("POST", f"{base}{ig_user}/media",
                    {"media_type": "CAROUSEL", "children": ",".join(children), "caption": caption, "access_token": token})
    if st != 200:
        print("::error::Карусель: " + graph_error(body)); return 1
    cid = json.loads(body)["id"]
    for attempt in range(6):
        time.sleep(10 if attempt == 0 else 60)
        st, body = http("GET", f"{base}{cid}?" + urllib.parse.urlencode({"fields": "status_code", "access_token": token}))
        code = json.loads(body).get("status_code") if st == 200 else None
        if code == "FINISHED":
            break
        if code in ("ERROR", "EXPIRED"):
            print("::error::Instagram не принял карусель: " + str(code)); return 1
    st, body = http("POST", f"{base}{ig_user}/media_publish", {"creation_id": cid, "access_token": token})
    if st != 200:
        print("::error::Публикация: " + graph_error(body)); return 1
    print("::notice::Карусель опубликована")
    return 0

if __name__ == "__main__":
    sys.exit(main())
