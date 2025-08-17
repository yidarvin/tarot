#!/usr/bin/env python3
import json
import os
import time
from datetime import datetime, timezone
from urllib.parse import urlencode
from urllib.request import urlopen, Request
from urllib.error import HTTPError, URLError

API_URL = "https://commons.wikimedia.org/w/api.php"
CATEGORY = "Category:Rider-Waite tarot deck"
USER_AGENT = "TarotCardsDownloader/1.0 (+local)"


def request_json(params):
    query = urlencode(params)
    req = Request(API_URL + "?" + query, headers={"User-Agent": USER_AGENT})
    for attempt in range(5):
        try:
            with urlopen(req) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except (HTTPError, URLError):
            if attempt == 4:
                raise
            time.sleep(1.0 + attempt * 0.5)


def fetch_category_file_titles():
    titles = []
    cont = {}
    while True:
        params = {
            "action": "query",
            "format": "json",
            "list": "categorymembers",
            "cmtitle": CATEGORY,
            "cmtype": "file",
            "cmlimit": "500",
        }
        params.update(cont)
        data = request_json(params)
        cms = data.get("query", {}).get("categorymembers", [])
        for item in cms:
            title = item.get("title")
            if title:
                titles.append(title)
        if "continue" in data:
            cont = data["continue"]
        else:
            break
    return titles


def chunked(iterable, size):
    for i in range(0, len(iterable), size):
        yield iterable[i : i + size]


def fetch_image_infos(titles):
    image_infos = []
    for group in chunked(titles, 50):
        params = {
            "action": "query",
            "format": "json",
            "prop": "imageinfo",
            "iiprop": "url|mime",
            "titles": "|".join(group),
        }
        data = request_json(params)
        pages = data.get("query", {}).get("pages", {})
        for page in pages.values():
            title = page.get("title")
            info_list = page.get("imageinfo", [])
            if not info_list:
                continue
            info = info_list[0]
            url = info.get("url")
            mime = info.get("mime")
            if mime != "image/jpeg":
                continue
            image_infos.append({"title": title, "url": url, "mime": mime})
        time.sleep(0.1)
    return image_infos


def download_file(url, out_path):
    req = Request(url, headers={"User-Agent": USER_AGENT})
    for attempt in range(5):
        try:
            with urlopen(req) as resp, open(out_path, "wb") as f:
                f.write(resp.read())
            return
        except (HTTPError, URLError):
            if attempt == 4:
                raise
            time.sleep(1.0 + attempt * 0.5)


def main():
    out_dir = os.path.join(os.path.dirname(__file__), "images")
    os.makedirs(out_dir, exist_ok=True)

    titles = fetch_category_file_titles()
    if not titles:
        raise SystemExit("No files found in category")

    infos = fetch_image_infos(titles)

    cards = []
    for info in sorted(infos, key=lambda x: x["title"]):
        url = info["url"]
        filename = os.path.basename(url.split("?")[0])
        out_path = os.path.join(out_dir, filename)
        if not os.path.exists(out_path):
            print("Downloading", filename)
            download_file(url, out_path)
            time.sleep(0.05)
        else:
            print("Exists", filename)
        cards.append(
            {
                "title": info["title"],
                "url": url,
                "filename": "images/" + filename,
                "mime": info["mime"],
            }
        )

    manifest = {
        "source_category": "https://commons.wikimedia.org/wiki/Category:Rider-Waite_tarot_deck",
        "downloaded_at": datetime.now(timezone.utc).isoformat(),
        "count": len(cards),
        "cards": cards,
    }
    with open(os.path.join(os.path.dirname(__file__), "manifest.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)

    print("Done. JPEGs downloaded:", len(cards))


if __name__ == "__main__":
    main()
