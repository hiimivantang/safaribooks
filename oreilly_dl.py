#!/usr/bin/env python3
# coding: utf-8
"""
Download books from learning.oreilly.com as original EPUB files,
using the session cookies saved in `cookies.json`.

O'Reilly's current API exposes every file of a book under
    /api/v2/epubs/urn:orm:book:<id>/files/<path>
so we fetch the file listing plus the OPF/NCX and rebuild the
publisher's EPUB as-is.

Usage:
    python3 oreilly_dl.py <book_id> [book_id ...]

The <book_id> is the number in the book URL, e.g.
    https://learning.oreilly.com/library/view/<name>/9781491958698/
                                                             ^^^^^^^^^^^^^
"""
import json
import os
import re
import sys
import zipfile

from curl_cffi import requests

PATH = os.path.dirname(os.path.realpath(__file__))
COOKIES_FILE = os.path.join(PATH, "cookies.json")
BOOKS_DIR = os.path.join(PATH, "Books")

BASE_URL = "https://learning.oreilly.com"

CONTAINER_XML = """<?xml version="1.0" encoding="UTF-8"?>
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
  <rootfiles>
    <rootfile full-path="{opf_path}" media-type="application/oebps-package+xml"/>
  </rootfiles>
</container>
"""


def load_session():
    if not os.path.isfile(COOKIES_FILE):
        sys.exit("Login: unable to find `cookies.json` file.")
    with open(COOKIES_FILE) as f:
        cookies = json.load(f)
    # curl_cffi impersonates Chrome's TLS fingerprint; the plain
    # `requests` fingerprint is blocked by Akamai with 403.
    session = requests.Session(impersonate="chrome")
    session.cookies.update(cookies)
    return session


def check_login(session):
    response = session.get(BASE_URL + "/profile/", allow_redirects=False, timeout=30)
    if response.status_code != 200:
        sys.exit("Authentication issue: unable to access profile page.\n"
                 "    Your session may have expired: re-export cookies from your\n"
                 "    browser and save them to `cookies.json`.")
    if '"user_type":"Expired"' in response.text:
        sys.exit("Authentication issue: account subscription expired.")


def get_json(session, url):
    response = session.get(url, timeout=60)
    response.raise_for_status()
    return response.json()


def list_book_files(session, book_id):
    """Return {full_path: download_url} for every file of the book."""
    base = "%s/api/v2/epubs/urn:orm:book:%s/files" % (BASE_URL, book_id)
    files = {}
    url = base + "/?limit=1000"
    while url:
        page = get_json(session, url)
        for item in page.get("results", []):
            files[item["full_path"]] = item["url"]
        url = page.get("next")
    # The OPF/NCX are not always part of the listing but are fetchable.
    for extra in ("content.opf", "toc.ncx"):
        files.setdefault(extra, "%s/%s" % (base, extra))
    return files


def download_book(session, book_id):
    meta = get_json(session, "%s/api/v2/epubs/urn:orm:book:%s/" % (BASE_URL, book_id))
    title = meta.get("title", book_id)
    print("[%s] %s" % (book_id, title))

    files = list_book_files(session, book_id)
    opf_path = next((p for p in files if p.endswith(".opf")), "content.opf")
    print("    %d files, OPF: %s" % (len(files), opf_path))

    safe_title = re.sub(r"[^\w\s.,'-]", "", title).strip().replace(":", " -")
    out_dir = os.path.join(BOOKS_DIR, "%s (%s)" % (safe_title, book_id))
    os.makedirs(out_dir, exist_ok=True)
    epub_path = os.path.join(out_dir, book_id + ".epub")

    done = 0
    with zipfile.ZipFile(epub_path, "w", zipfile.ZIP_DEFLATED) as epub:
        # The "mimetype" entry must be first and stored uncompressed.
        mimetype = zipfile.ZipInfo("mimetype")
        mimetype.compress_type = zipfile.ZIP_STORED
        epub.writestr(mimetype, "application/epub+zip")
        epub.writestr("META-INF/container.xml", CONTAINER_XML.format(opf_path=opf_path))

        for path, url in sorted(files.items()):
            response = session.get(url, timeout=120)
            response.raise_for_status()
            epub.writestr(path, response.content)
            done += 1
            if done % 20 == 0:
                print("    %d/%d files..." % (done, len(files)))

    print("    saved: %s" % epub_path)
    return epub_path


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    book_ids = sys.argv[1:]

    session = load_session()
    check_login(session)

    for book_id in book_ids:
        download_book(session, book_id)

    # Persist any refreshed cookies for the next run.
    with open(COOKIES_FILE, "w") as f:
        json.dump(session.cookies.get_dict(), f)


if __name__ == "__main__":
    main()
