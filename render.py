#!/usr/bin/env python3
"""Render an EPUB into Lector's narrated-book format.

  python render.py --epub book.epub --slug poggio --voice bm_george --out site
  python render.py --index --out site          # (re)build site/library.json

Output per book:
  site/books/<slug>/book.json            chapters (title, sentences, paragraph starts)
  site/books/<slug>/<voice>/chNN.m4a     one AAC file per chapter
  site/books/<slug>/<voice>/chNN.json    {"starts": [sec per sentence], "dur": sec}
"""
import argparse, json, os, re, subprocess, sys, tempfile, zipfile, posixpath
from urllib.parse import unquote

# ---------------------------------------------------------------- voices
VOICES = {
    "bm_george":  {"name": "George",  "sub": "Male, British. Measured and clear.", "lang": "en-gb"},
    "am_michael": {"name": "Michael", "sub": "Male, American. Warm.",             "lang": "en-us"},
    "am_fenrir":  {"name": "Fenrir",  "sub": "Male, American. Deeper.",           "lang": "en-us"},
    "af_heart":   {"name": "Heart",   "sub": "Female, American. Natural.",        "lang": "en-us"},
    "bf_emma":    {"name": "Emma",    "sub": "Female, British. Soft.",            "lang": "en-gb"},
}

# Italian, Latin and French names espeak gets wrong, as IPA (US variant, GB variant).
NAMES = {
    "Poggio":       ("pˈɔdʒoʊ",        "pˈɒdʒəʊ"),
    "Bracciolini":  ("bɹɑːtʃoʊlˈiːni", "bɹɑːtʃəʊlˈiːni"),
    "Niccoli":      ("nˈɪkoʊli",       "nˈɪkəʊli"),
    "Niccolo":      ("nɪkolˈɔ",        "nɪkolˈɒ"),
    "Niccolò":      ("nɪkolˈɔ",        "nɪkolˈɒ"),
    "Bruni":        ("bɹˈuːni",        "bɹˈuːni"),
    "Medici":       ("mˈɛdɪtʃi",       "mˈɛdɪtʃi"),
    "Guarino":      ("ɡwɑːɹˈiːnoʊ",    "ɡwɑːɹˈiːnəʊ"),
    "Terranuova":   ("tɛɹɑːnwˈɔːvɑː",  "tɛɹɑːnwˈɔːvɑː"),
    "Cosimo":       ("kˈɔzɪmoʊ",       "kˈɒzɪməʊ"),
    "Cosmo":        ("kˈɔzmoʊ",        "kˈɒzməʊ"),
    "Salutati":     ("sɑːluːtˈɑːti",   "sɑːluːtˈɑːti"),
    "Traversari":   ("tɹɑːvɛɹsˈɑːɹi",  "tɹɑːvɛsˈɑːɹi"),
    "Filelfo":      ("fɪlˈɛlfoʊ",      "fɪlˈɛlfəʊ"),
    "Valla":        ("vˈɑːlɑː",        "vˈɑːlɑː"),
    "Beccadelli":   ("bɛkɑːdˈɛli",     "bɛkɑːdˈɛli"),
    "Aurispa":      ("aʊɹˈiːspɑː",     "aʊɹˈiːspɑː"),
    "Aretino":      ("ɑːɹɛtˈiːnoʊ",    "ɑːɹɛtˈiːnəʊ"),
    "Ambrogio":     ("ɑːmbɹˈɔːdʒoʊ",   "ɑːmbɹˈɔːdʒəʊ"),
    "Chrysoloras":  ("kɹɪsolˈɔːɹɑːs",  "kɹɪsolˈɔːɹɑːs"),
    "Scarperia":    ("skɑːɹpɛɹˈiːɑː",  "skɑːpɛɹˈiːɑː"),
    "Guarini":      ("ɡwɑːɹˈiːni",     "ɡwɑːɹˈiːni"),
    "Vespasiano":   ("vɛspɑːziˈɑːnoʊ", "vɛspɑːziˈɑːnəʊ"),
    "Bisticci":     ("bɪstˈiːtʃi",     "bɪstˈiːtʃi"),
    "Tortelli":     ("tɔɹtˈɛli",       "tɔːtˈɛli"),
    "Marsuppini":   ("mɑːɹsupˈiːni",   "mɑːsupˈiːni"),
    "Strozzi":      ("stɹˈɔtsi",       "stɹˈɒtsi"),
    "Albizzi":      ("ɑːlbˈiːtsi",     "ɑːlbˈiːtsi"),
    "Uzzano":       ("uːtsˈɑːnoʊ",     "uːtsˈɑːnəʊ"),
    "Lucretius":    ("luːkɹˈiːʃəs",    "luːkɹˈiːʃəs"),
    "Quintilian":   ("kwɪntˈɪliən",    "kwɪntˈɪliən"),
    "Petrarch":     ("pˈɛtɹɑːɹk",      "pˈɛtɹɑːk"),
    "Boccaccio":    ("boʊkˈɑːtʃoʊ",    "bəʊkˈɑːtʃəʊ"),
    "Guicciardini": ("ɡwɪtʃɑːɹdˈiːni", "ɡwɪtʃɑːdˈiːni"),
    "Huss":         ("hˈʊs",           "hˈʊs"),
    "Hus":          ("hˈʊs",           "hˈʊs"),
    "Tonelli":      ("toʊnˈɛli",       "təʊnˈɛli"),
    "Recanati":     ("ɹɛkɑːnˈɑːti",    "ɹɛkɑːnˈɑːti"),
    "Lenfant":      ("lɑ̃fˈɑ̃",          "lɑ̃fˈɑ̃"),
    "Francesco":    ("fɹɑːntʃˈɛskoʊ",  "fɹɑːntʃˈɛskəʊ"),
    "Lapo":         ("lˈɑːpoʊ",        "lˈɑːpəʊ"),
    "Cencio":       ("tʃˈɛntʃoʊ",      "tʃˈɛntʃəʊ"),
    "Rustici":      ("ɹˈuːstɪtʃi",     "ɹˈuːstɪtʃi"),
    "Bartolomeo":   ("bɑːɹtoʊlomˈɛːoʊ", "bɑːtəʊlomˈɛːəʊ"),
    "Zabarella":    ("dzɑːbɑːɹˈɛlɑː",  "dzɑːbɑːɹˈɛlɑː"),
    "Panormita":    ("pɑːnɔɹmˈiːtɑː",  "pɑːnɔːmˈiːtɑː"),
    "Facetiae":     ("fəsˈiːʃiiː",     "fəsˈiːʃiiː"),
}

# ---------------------------------------------------------------- text utilities (mirror of lector.html)
NBSP = re.compile(r"[\u00A0\u2007\u202F]")
def normalize(t):
    return re.sub(r"\s+", " ", NBSP.sub(" ", t or "")).strip()

ABBR = re.compile(r"(?:^|[\s(\[“\"'])(?:Mr|Mrs|Ms|Messrs|Dr|St|Prof|Sr|Jr|vs|etc|viz|cf|ed|eds|vol|vols|p|pp|No|Nos|ch|chap|Rev|Hon|Capt|Gen|Col|Lib|Cap|Ep|Epist|fol|ibid|id|op|cit|Fr|M|MM|Mme|Mlle|Mons|Sig|Card|Abp|Bp|Esq|Lieut|Serg|Maj|Co|Inc|Ltd|Bros|Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sept|Sep|Oct|Nov|Dec)\.$", re.I)
INITIAL = re.compile(r"(?:^|\s)[A-Za-z]\.$")
ROMAN = re.compile(r"(?:^|\s)[ivxlc]{1,5}\.$")
MAX = 240
PIECE = re.compile(r"[^.!?…]+(?:[.!?…]+[\"'”’)\]]*|$)")

def split_long(s):
    if len(s) <= MAX:
        return [s]
    parts, rest = [], s
    while len(rest) > MAX:
        cut = -1
        for pat in (r"[;:]\s", r",\s", r"\s"):
            last = -1
            for m in re.finditer(pat, rest):
                if m.start() >= MAX:
                    break
                last = m.end()
            if last > MAX * 0.35:
                cut = last
                break
        if cut < 0:
            cut = MAX
        parts.append(rest[:cut].strip())
        rest = rest[cut:]
    if rest.strip():
        parts.append(rest.strip())
    return parts

def split_sentences(text):
    text = re.sub(r"(\d)\.(\d)", "\\1\x00\\2", text)
    out, buf = [], ""
    for m in PIECE.finditer(text):
        piece = m.group(0)
        if not piece.strip():
            continue
        buf += piece
        tr = buf.rstrip()
        if ABBR.search(tr) or INITIAL.search(tr) or ROMAN.search(tr):
            continue
        out.append(buf.strip())
        buf = ""
    if buf.strip():
        out.append(buf.strip())
    res = []
    for s in out:
        res.extend(split_long(s.replace("\x00", ".")))
    return [s.strip() for s in res if s.strip()]

def clean_title(t):
    t = normalize(t)
    if len(t) > 90:
        t = t[:87].rstrip() + "…"
    return t or "Untitled"

def blocks_to_chapter(title, blocks):
    s, p, w = [], [], 0
    for b in blocks:
        sents = split_sentences(b["t"])
        if not sents:
            continue
        p.append(len(s))
        for x in sents:
            s.append(x)
            w += len(x.split())
    return {"title": clean_title(title), "s": s, "p": p, "w": w}

def merge_tiny(chapters):
    out = []
    for i, c in enumerate(chapters):
        if len(c["s"]) < 3 and i + 1 < len(chapters):
            n = chapters[i + 1]
            shift = len(c["s"])
            n["s"] = c["s"] + n["s"]
            n["p"] = c["p"] + [x + shift for x in n["p"]]
            n["w"] += c["w"]
            if not re.match(r"^(cover|contents|title|front matter)", c["title"], re.I) and c["title"] != "Untitled":
                n["title"] = clean_title(c["title"] + ". " + n["title"])
            continue
        if c["s"]:
            out.append(c)
    return out

# ---------------------------------------------------------------- EPUB
from lxml import etree, html as lhtml

BLOCK = {"p","h1","h2","h3","h4","h5","h6","li","blockquote","pre","dt","dd","td","th","figcaption","caption","div","section","article","aside","header","footer","nav","table","tr","ul","ol","dl","hr","figure","body","main","address","center","details","summary"}
SKIP = {"script","style","head","title","svg","img","noscript","template","video","audio","object","iframe","math"}
PAGENUM = re.compile(r"pagenum|pageno|page-number|pagebreak|noteref|footnote-?ref|fnanchor", re.I)
FNMARK = re.compile(r"^\s*\[?\s*\d{1,3}\s*\]?\s*$")

def local(tag):
    return tag.split("}")[-1].lower() if isinstance(tag, str) else ""

def parse_doc(data):
    try:
        root = etree.fromstring(data, etree.XMLParser(recover=True, huge_tree=True))
        if root is None or not list(root.iter()):
            raise ValueError
        return root
    except Exception:
        return lhtml.fromstring(data)

def body_of(root):
    for el in root.iter():
        if local(el.tag) == "body":
            return el
    return root

def dir_of(p):
    i = p.rfind("/")
    return p[:i + 1] if i >= 0 else ""

def resolve(base, href):
    try:
        href = unquote(href)
    except Exception:
        pass
    if href.startswith("/"):
        return href[1:]
    return posixpath.normpath(base + href) if href else base

class ZipReader:
    def __init__(self, path):
        self.z = zipfile.ZipFile(path)
        self.names = {n.lower(): n for n in self.z.namelist()}
    def read(self, p):
        n = self.names.get(p.lower())
        return self.z.read(n) if n else None

def extract_blocks(root, path, blocks, anchors):
    run = []
    def flush(is_h=False):
        t = normalize("".join(run))
        run.clear()
        if t:
            blocks.append({"t": t, "h": is_h})
    def visit(node):
        if not isinstance(node.tag, str):   # comments, PIs
            if node.tail: run.append(node.tail)
            return
        tag = local(node.tag)
        if tag in SKIP or node.get("hidden") is not None:
            if node.tail: run.append(node.tail)
            return
        is_block = tag in BLOCK
        if is_block:
            flush()
        nid = node.get("id") or (node.get("name") if tag == "a" else None)
        if nid:
            anchors[path + "#" + nid] = len(blocks)
        cls = (node.get("class") or "") + " " + (node.get("{http://www.idpf.org/2007/ops}type") or node.get("epub:type") or "")
        if PAGENUM.search(cls):
            if node.tail: run.append(node.tail)
            return
        txt = "".join(node.itertext())
        if tag in ("a", "sup") and FNMARK.match(txt) and len(txt.strip()) <= 5:
            if node.tail: run.append(node.tail)
            return
        is_h = bool(re.match(r"^h[1-6]$", tag))
        if node.text: run.append(node.text)
        for c in node:
            visit(c)
        if is_block:
            flush(is_h)
        elif tag == "br":
            run.append(" ")
        if node.tail: run.append(node.tail)
    b = body_of(root)
    if b.text: run.append(b.text)
    for c in b:
        visit(c)
    flush()

def parse_epub(path, fallback_title):
    z = ZipReader(path)
    cx = z.read("META-INF/container.xml")
    if not cx:
        raise SystemExit("Not an EPUB (no container.xml)")
    croot = etree.fromstring(cx)
    rf = [e for e in croot.iter() if local(e.tag) == "rootfile"]
    opf_path = rf[0].get("full-path")
    opf = etree.fromstring(z.read(opf_path))
    base = dir_of(opf_path)
    DC = "{http://purl.org/dc/elements/1.1/}"
    def dc(n):
        for e in opf.iter(DC + n):
            return normalize("".join(e.itertext()))
        return ""
    title = dc("title") or fallback_title
    author = dc("creator")
    items = {}
    for it in opf.iter():
        if local(it.tag) == "item" and it.get("id") and it.get("href"):
            items[it.get("id")] = {"href": resolve(base, it.get("href")), "type": it.get("media-type") or "", "props": it.get("properties") or ""}
    spine_el = next((e for e in opf.iter() if local(e.tag) == "spine"), None)
    spine = []
    if spine_el is not None:
        for r in spine_el.iter():
            if local(r.tag) == "itemref":
                it = items.get(r.get("idref"))
                if it and re.search(r"html|xml", it["type"], re.I) and r.get("linear") != "no":
                    spine.append(it)
    if not spine:
        raise SystemExit("EPUB has no readable sections")

    toc = []
    nav_item = next((i for i in items.values() if "nav" in i["props"].split()), None)
    if nav_item:
        data = z.read(nav_item["href"])
        if data:
            nd = parse_doc(data)
            navs = [e for e in nd.iter() if local(e.tag) == "nav"]
            nav = next((n for n in navs if re.search(r"toc", (n.get("{http://www.idpf.org/2007/ops}type") or n.get("epub:type") or ""), re.I)), navs[0] if navs else None)
            if nav is not None:
                for a in nav.iter():
                    if local(a.tag) == "a" and a.get("href"):
                        toc.append({"label": normalize("".join(a.itertext())), "href": a.get("href"), "from": dir_of(nav_item["href"])})
    if not toc:
        ncx_id = spine_el.get("toc") if spine_el is not None else None
        ncx = items.get(ncx_id) or next((i for i in items.values() if re.search(r"dtbncx", i["type"], re.I)), None)
        if ncx:
            data = z.read(ncx["href"])
            if data:
                xd = etree.fromstring(data, etree.XMLParser(recover=True))
                for np_ in xd.iter():
                    if local(np_.tag) == "navPoint":
                        lab = next((e for e in np_.iter() if local(e.tag) == "text"), None)
                        con = next((e for e in np_.iter() if local(e.tag) == "content"), None)
                        if lab is not None and con is not None and con.get("src"):
                            toc.append({"label": normalize("".join(lab.itertext())), "href": con.get("src"), "from": dir_of(ncx["href"])})

    blocks, anchors, file_starts = [], {}, []
    for it in spine:
        anchors[it["href"]] = len(blocks)
        file_starts.append({"i": len(blocks), "href": it["href"]})
        data = z.read(it["href"])
        if data:
            extract_blocks(parse_doc(data), it["href"], blocks, anchors)

    marks = []
    for e in toc:
        p, _, frag = e["href"].partition("#")
        path = resolve(e["from"], p) if p else None
        idx = None
        if path and frag:
            idx = anchors.get(path + "#" + frag)
        if idx is None and path:
            idx = anchors.get(path)
        if idx is None:
            continue
        marks.append({"i": idx, "title": e["label"]})
    marks.sort(key=lambda m: m["i"])
    uniq = []
    for m in marks:
        if not uniq or uniq[-1]["i"] != m["i"]:
            uniq.append(m)
    ranges = uniq if len(uniq) >= 2 else [{"i": f["i"], "title": ""} for f in file_starts]
    if ranges and ranges[0]["i"] > 0:
        ranges.insert(0, {"i": 0, "title": "Front matter"})
    chapters = []
    for k, r in enumerate(ranges):
        to = ranges[k + 1]["i"] if k + 1 < len(ranges) else len(blocks)
        sl = blocks[r["i"]:to]
        t = r["title"]
        if not t:
            h = next((b for b in sl if b["h"]), None)
            t = h["t"] if h else "Section %d" % (k + 1)
        chapters.append(blocks_to_chapter(t, sl))
    chapters = merge_tiny(chapters)
    if not chapters:
        raise SystemExit("No readable text found")
    return {"title": title, "author": author, "chapters": chapters}

# ---------------------------------------------------------------- narration
def phonemize_fixed(tok, text, lang):
    gb = lang.startswith("en-gb")
    ph = tok.phonemize(text, lang=lang)
    low = text.lower()
    for name, (us, uk) in NAMES.items():
        if name.lower() not in low:
            continue
        bad = tok.phonemize(name, lang=lang).strip()
        if bad and bad in ph:
            ph = ph.replace(bad, uk if gb else us)
    return ph

def render_voice(book, slug, voice, out, model_dir, chapters_range=None):
    import numpy as np, soundfile as sf
    from kokoro_onnx import Kokoro
    vinfo = VOICES[voice]
    lang = vinfo["lang"]
    k = Kokoro(os.path.join(model_dir, "kokoro-v1.0.onnx"), os.path.join(model_dir, "voices-v1.0.bin"))
    sr = 24000
    vdir = os.path.join(out, "books", slug, voice)
    os.makedirs(vdir, exist_ok=True)
    gap_s, gap_p, gap_h = 0.32, 0.7, 0.9
    for ci, ch in enumerate(book["chapters"]):
        if chapters_range and not (chapters_range[0] <= ci <= chapters_range[1]):
            continue
        m4a = os.path.join(vdir, "ch%02d.m4a" % ci)
        tj = os.path.join(vdir, "ch%02d.json" % ci)
        if os.path.exists(m4a) and os.path.exists(tj):
            print("skip", voice, ci, flush=True)
            continue
        pstart = set(ch["p"])
        pieces, starts, t = [], [], 0.0
        for si, sent in enumerate(ch["s"]):
            starts.append(round(t, 2))
            try:
                ph = phonemize_fixed(k.tokenizer, sent, lang)
                audio, _sr = k.create(ph, voice=voice, speed=1.0, lang=lang, is_phonemes=True)
                audio = np.asarray(audio, dtype=np.float32)
                if not np.all(np.isfinite(audio)):
                    audio = np.zeros(int(sr * 0.4), dtype=np.float32)
            except Exception as e:
                print("sentence failed", ci, si, repr(e), file=sys.stderr, flush=True)
                audio = np.zeros(int(sr * 0.4), dtype=np.float32)
            gap = gap_h if si == 0 else (gap_p if si in pstart else gap_s)
            audio = np.concatenate([audio, np.zeros(int(sr * gap), dtype=np.float32)])
            pieces.append(audio)
            t += len(audio) / sr
            if si % 50 == 0:
                print("%s ch%02d %d/%d  %.1f min" % (voice, ci, si, len(ch["s"]), t / 60), flush=True)
        wav = np.concatenate(pieces) if pieces else np.zeros(sr, dtype=np.float32)
        peak = float(np.max(np.abs(wav))) if len(wav) else 1.0
        if peak > 0:
            wav = wav / peak * 0.89
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            sf.write(tmp.name, wav, sr)
            tmpname = tmp.name
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", tmpname, "-c:a", "aac", "-b:a", "40k", "-ac", "1", "-ar", "24000", "-movflags", "+faststart", m4a], check=True)
        os.unlink(tmpname)
        with open(tj, "w") as f:
            json.dump({"starts": starts, "dur": round(t, 2)}, f)
        print("done", voice, "ch%02d" % ci, "%.1f min" % (t / 60), flush=True)

def write_book_json(book, slug, out, voices):
    bdir = os.path.join(out, "books", slug)
    os.makedirs(bdir, exist_ok=True)
    data = {"slug": slug, "title": book["title"], "author": book["author"], "chapters": book["chapters"],
            "voices": [{"id": v, **VOICES[v]} for v in voices]}
    with open(os.path.join(bdir, "book.json"), "w") as f:
        json.dump(data, f, ensure_ascii=False)

def build_index(out):
    books = []
    root = os.path.join(out, "books")
    if os.path.isdir(root):
        for slug in sorted(os.listdir(root)):
            bj = os.path.join(root, slug, "book.json")
            if not os.path.exists(bj):
                continue
            with open(bj) as f:
                b = json.load(f)
            voices = []
            for v in VOICES:
                vd = os.path.join(root, slug, v)
                n = len(b["chapters"])
                if os.path.isdir(vd) and all(os.path.exists(os.path.join(vd, "ch%02d.m4a" % i)) for i in range(n)):
                    voices.append({"id": v, **VOICES[v]})
            b["voices"] = voices
            with open(bj, "w") as f:
                json.dump(b, f, ensure_ascii=False)
            books.append({"slug": slug, "title": b["title"], "author": b["author"], "nch": len(b["chapters"]),
                          "words": sum(c["w"] for c in b["chapters"]), "voices": voices})
    with open(os.path.join(out, "library.json"), "w") as f:
        json.dump({"books": books}, f, ensure_ascii=False)
    print("library.json:", [(b["slug"], len(b["voices"])) for b in books])

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--epub")
    ap.add_argument("--slug")
    ap.add_argument("--voice", help="one voice id, or 'none' to only write book.json")
    ap.add_argument("--out", default="site")
    ap.add_argument("--models", default="models")
    ap.add_argument("--index", action="store_true")
    ap.add_argument("--limit", type=int, default=0, help="render only the first N chapters (testing)")
    ap.add_argument("--chapters", default="", help="render only chapters a-b (zero-based, inclusive), e.g. 0-6")
    a = ap.parse_args()
    if a.index:
        build_index(a.out)
        return
    book = parse_epub(a.epub, os.path.splitext(os.path.basename(a.epub))[0])
    if a.limit:
        book["chapters"] = book["chapters"][:a.limit]
    print("%s by %s: %d chapters, %d words" % (book["title"], book["author"], len(book["chapters"]), sum(c["w"] for c in book["chapters"])), flush=True)
    write_book_json(book, a.slug, a.out, list(VOICES))
    rng = None
    if a.chapters:
        lo, _, hi = a.chapters.partition("-")
        rng = (int(lo), int(hi or 999))
    if a.voice and a.voice != "none":
        render_voice(book, a.slug, a.voice, a.out, a.models, rng)

if __name__ == "__main__":
    main()
