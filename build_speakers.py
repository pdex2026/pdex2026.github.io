#!/usr/bin/env python3
"""Bake speakers.csv into index.html (invited-speaker cards).

Regenerates the <article> blocks inside <section class="features"> in
index.html from speakers.csv. Idempotent; safe to re-run. Preserves the
file's CRLF line endings. Python stdlib only (no dependencies).

Workflow:
  1. edit speakers.csv (one row per speaker)
  2. run: python3 build_speakers.py
  3. open index.html to verify, then commit site/

CSV columns: name, affiliation, title, online, photo
  - affiliation may contain commas (it must be quoted, e.g. "Prof, Inst, City")
  - online: yes / no   (yes -> appends "(online participation)")
  - photo: optional image path (e.g. images/foo.jpg); blank = no photo card
  - title: rendered as "Title: X"; blank or "TBD" is omitted entirely
    (so TBD titles stay hidden until a real title is filled in)
  - any extra columns (e.g. "Faculty?") are ignored

Usage:
  python3 build_speakers.py            # bake speakers.csv -> index.html
  python3 build_speakers.py --dry-run  # report count without writing
"""
import csv
import html
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
CSV_PATH = os.path.join(HERE, "speakers.csv")
HTML_PATH = os.path.join(HERE, "index.html")

BEGIN = "<!-- BEGIN SPEAKERS (auto-generated from speakers.csv by build_speakers.py; edit speakers.csv and re-run) -->"
END = "<!-- END SPEAKERS -->"

REQUIRED_COLS = ["name", "affiliation", "title", "online", "photo"]


def load_speakers(path):
    with open(path, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    if rows:
        missing = [c for c in REQUIRED_COLS if c not in rows[0]]
        if missing:
            sys.exit("speakers.csv: missing required columns %s; header was %s"
                     % (missing, list(rows[0].keys())))
    return rows


def _esc(s):
    return html.escape(s.strip(), quote=False)


def render_article(row):
    name = _esc(row["name"])
    affil = _esc(row["affiliation"])
    title = _esc(row["title"])
    if title.lower() == "tbd":
        title = ""
    online = row["online"].strip().lower() in ("yes", "y", "true", "1")
    photo = row["photo"].strip()
    lines = ["\t\t\t  <article>"]
    if photo:
        lines.append('\t\t\t\t<a href="#" class="image"><img src="'
                     + html.escape(photo, quote=True) + '" alt="" /></a>')
    lines.append('\t\t\t\t<h3 class="major">' + name + '</h3>')
    body = affil + (" (online participation)" if online else "")
    if title:
        body = body + " <br> Title: " + title
    lines.append("\t\t\t\t<p>" + body + "</p>")
    lines.append("\t\t\t  </article>")
    return "\n".join(lines)


def build_inner(rows):
    return "\n\n".join(render_article(r) for r in rows)


def bake(rows, text):
    bi = text.find(BEGIN)
    ei = text.find(END)
    if bi != -1 and ei != -1 and ei > bi:
        head = text[:bi + len(BEGIN)]
        tail = text[ei:]
        return head + "\n" + build_inner(rows) + "\n\t\t\t  " + tail
    # first run: wrap the existing <section class="features"> ... </section>
    m = re.search(r'(<section class="features">)(.*?)(</section>)', text, re.DOTALL)
    if not m:
        sys.exit('Could not find <section class="features"> ... </section> in index.html')
    head = text[:m.end(1)]
    tail = text[m.start(3):]
    inner = ("\n\t\t\t  " + BEGIN + "\n" + build_inner(rows) + "\n\t\t\t  " + END
             + "\n\t\t\t")
    return head + inner + tail


def main():
    dry = "--dry-run" in sys.argv
    rows = load_speakers(CSV_PATH)
    with open(HTML_PATH, "rb") as f:
        raw = f.read()
    crlf = b"\r\n" in raw
    text = raw.decode("utf-8")
    new_text = bake(rows, text)
    # normalize line endings to match the file's existing style
    new_text = new_text.replace("\r\n", "\n")
    if crlf:
        new_text = new_text.replace("\n", "\r\n")
    if dry:
        print("[dry-run] would bake %d speaker(s) into index.html." % len(rows))
        return
    changed = new_text != text
    with open(HTML_PATH, "wb") as f:
        f.write(new_text.encode("utf-8"))
    print("Baked %d speaker(s) into index.html (%s)."
          % (len(rows), "updated" if changed else "unchanged"))


if __name__ == "__main__":
    main()
