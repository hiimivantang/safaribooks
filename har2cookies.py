#!/usr/bin/env python3
# coding: utf-8
"""
Extract learning.oreilly.com session cookies from a browser HAR export
into `cookies.json` for use by `oreilly_dl.py`.

Usage:
    python3 har2cookies.py <path-to-har-file>

To re-export: open learning.oreilly.com in your browser, open the DevTools
Network tab, log in / browse, right-click a request -> "Save all as HAR
with content", then run this script on the downloaded .har file.
"""
import json
import os
import sys

PATH = os.path.dirname(os.path.realpath(__file__))
COOKIES_FILE = os.path.join(PATH, "cookies.json")

# Authentication cookies; the rest (analytics, bot-detection) are skipped —
# the bot-detection cookies are bound to the browser and cause blocks.
KEEP = ["orm-jwt", "orm-rt", "orm-rt-refresh", "csrftoken", "groot_sessionid"]


def main():
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    with open(sys.argv[1], encoding="utf-8") as f:
        har = json.load(f)

    cookies = {}
    for entry in har.get("log", {}).get("entries", []):
        request = entry.get("request", {})
        if "learning.oreilly.com" not in request.get("url", ""):
            continue
        for header in request.get("headers", []):
            if header.get("name", "").lower() == "cookie":
                for part in header.get("value", "").split(";"):
                    if "=" in part:
                        name, value = part.strip().split("=", 1)
                        cookies[name] = value

    out = {k: v for k, v in cookies.items() if k in KEEP}
    missing = [k for k in ("orm-jwt", "orm-rt") if k not in out]
    if missing:
        sys.exit("HAR is missing auth cookies: %s\n"
                 "    Make sure you were logged in to learning.oreilly.com\n"
                 "    when you exported it." % missing)

    with open(COOKIES_FILE, "w") as f:
        json.dump(out, f)
    print("Wrote %d cookies to %s" % (len(out), COOKIES_FILE))


if __name__ == "__main__":
    main()
