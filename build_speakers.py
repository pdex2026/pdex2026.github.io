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

Hiding the speaker list (e.g. while schedules are being fixed):
  python3 build_speakers.py hide   # comment out the whole Invited Speakers section
  python3 build_speakers.py show   # restore it and re-bake from speakers.csv
The hidden markup is kept in index.html inside one large HTML comment. The
BEGIN/END markers switch to [bracket] form while hidden, because HTML
comments cannot nest. Editing speakers.csv and re-running the plain bake
still works while hidden (articles update in place).

Usage:
  python3 build_speakers.py            # bake speakers.csv -> index.html
  python3 build_speakers.py --dry-run  # report count without writing
  python3 build_speakers.py hide       # temporarily comment out the section
  python3 build_speakers.py show       # restore a hidden section
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
BEGIN_HID = "[BEGIN SPEAKERS (auto-generated from speakers.csv by build_speakers.py; edit speakers.csv and re-run)]"
END_HID = "[END SPEAKERS]"
HIDE_OPEN = ("<!-- SPEAKERS SECTION HIDDEN (temporarily removed pending schedule"
             " finalization; restore with: python3 build_speakers.py show)")
HIDE_CLOSE = "-->"

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


def find_markers(text):
    for begin, end in ((BEGIN, END), (BEGIN_HID, END_HID)):
        if begin in text and end in text:
            return begin, end
    return None, None


def bake(rows, text):
    begin, end = find_markers(text)
    if begin is not None:
        bi = text.find(begin)
        ei = text.find(end)
        if ei > bi:
            head = text[:bi + len(begin)]
            tail = text[ei:]
            return head + "\n" + build_inner(rows) + "\n\t\t\t  " + tail
        sys.exit("Marker order error in index.html (END SPEAKERS before BEGIN).")
    if HIDE_OPEN in text:
        sys.exit("Speakers section is hidden but has no usable markers; "
                 'run "python3 build_speakers.py show" to restore it first.')
    # first run: wrap the existing <section class="features"> ... </section>
    m = re.search(r'(<section class="features">)(.*?)(</section>)', text, re.DOTALL)
    if not m:
        sys.exit('Could not find <section class="features"> ... </section> in index.html')
    head = text[:m.end(1)]
    tail = text[m.start(3):]
    inner = ("\n\t\t\t  " + BEGIN + "\n" + build_inner(rows) + "\n\t\t\t  " + END
             + "\n\t\t\t")
    return head + inner + tail


def section_four_span(text):
    start = text.find('<section id="four"')
    if start == -1:
        return None
    depth = 0
    for m in re.finditer(r'<section\b|</section>', text[start:]):
        depth += -1 if m.group(0).startswith("</") else 1
        if depth == 0:
            return start, start + m.end()
    return None


def hide(text):
    if HIDE_OPEN in text:
        return text, False
    span = section_four_span(text)
    if not span:
        sys.exit('Could not find <section id="four"> ... </section> in index.html')
    start, end = span
    region = text[start:end].replace(BEGIN, BEGIN_HID).replace(END, END_HID)
    if BEGIN_HID not in region or END_HID not in region:
        sys.exit('Speaker markers not found in section four; '
                 'run "python3 build_speakers.py" (plain bake) first.')
    if "--" in region:
        i = region.find("--")
        sys.exit("Refusing to hide: region contains '--' (breaks HTML comments) "
                 "near: %r" % region[max(0, i - 60):i + 60])
    hidden = HIDE_OPEN + "\n\t\t" + region + "\n\t\t" + HIDE_CLOSE
    return text[:start] + hidden + text[end:], True


def unhide(text):
    i = text.find(HIDE_OPEN)
    if i == -1:
        return text, False
    j = text.find(HIDE_CLOSE, i)
    if j == -1:
        sys.exit("Malformed hidden speakers section: no closing '-->'.")
    region = text[i + len(HIDE_OPEN):j].strip("\r\n\t ")
    region = region.replace(BEGIN_HID, BEGIN).replace(END_HID, END)
    if not region.startswith('<section id="four"') or BEGIN not in region:
        sys.exit("Malformed hidden speakers section; refusing to restore.")
    return text[:i] + region + text[j + len(HIDE_CLOSE):], True


def main():
    args = sys.argv[1:]
    dry = "--dry-run" in args
    mode = next((a for a in ("hide", "show") if a in args), "bake")
    rows = load_speakers(CSV_PATH)
    with open(HTML_PATH, "rb") as f:
        raw = f.read()
    orig = raw.decode("utf-8")
    crlf = "\r\n" in orig
    text = orig.replace("\r\n", "\n")
    if mode == "hide":
        text = bake(rows, text)
        text, did = hide(text)
        note = ", speakers section hidden" if did else ", already hidden"
    elif mode == "show":
        text, did = unhide(text)
        text = bake(rows, text)
        note = ", speakers section restored" if did else ", was not hidden"
    else:
        text = bake(rows, text)
        note = ""
    if dry:
        print("[dry-run] mode=%s, %d speaker(s)%s." % (mode, len(rows), note))
        return
    if crlf:
        text = text.replace("\n", "\r\n")
    with open(HTML_PATH, "wb") as f:
        f.write(text.encode("utf-8"))
    print("Baked %d speaker(s) into index.html (%s%s)."
          % (len(rows), "updated" if text != orig else "unchanged", note))


if __name__ == "__main__":
    main()
