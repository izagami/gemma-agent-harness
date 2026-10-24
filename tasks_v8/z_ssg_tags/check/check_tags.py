"""Hidden check for z_ssg_tags: builds a fresh site and compares against an independent implementation of the spec."""
import html, os, re, shutil, subprocess, sys, unicodedata
from datetime import date

SRC, OUT = "/tmp/tsrc", "/tmp/tout"
BASE = open("/check/orig_tpl_base.html", encoding="utf-8").read()
POST_TPL = open("/check/orig_tpl_post.html", encoding="utf-8").read()
SITE = "Dev & Travel <Notes>"
ENV = dict(os.environ, PYTHONPATH="/work", PYTHONDONTWRITEBYTECODE="1")

POSTS = {
    "a.md": ("Go の並行処理", "2026-04-01", "Go, go, 並行処理", False),
    "b.md": ("Rust & Go 比較", "2026-04-01", "rust, Go, <script>", False),
    "c.md": ("Python 3.13 の新機能", "2026-03-15", "Python, Type  Hints", False),
    "d.md": ("Notes on node.js", "2026-02-20", "node.js, NodeJS, !!!, c++", False),
    "e.md": ("type hints deep dive", "2026-02-20", "type hints, python, NodeJS", False),
    "f.md": ("Zig first look", "2026-02-20", "Rust, zig", False),
    "g.md": ("secret plans", "2026-05-01", "secret, PYTHON, python, Zig", True),
    "h.md": ("About", "2026-01-01", "", False),
    "i.md": ("C tips", "2026-01-10", " C , C++", False),
    "j.md": ("Async <await>", "2026-01-10", "[Python, 機械 学習]", False),
    "k.md": ("全角テスト", "2025-12-31", "Ｐｙｔｈｏｎ, 機械学習", False),
}


def write_src(posts):
    shutil.rmtree(SRC, ignore_errors=True)
    os.makedirs(SRC + "/posts"); os.makedirs(SRC + "/static")
    open(SRC + "/config.ini", "w", encoding="utf-8").write(f"[site]\nname = {SITE}\n")
    open(SRC + "/static/style.css", "w").write("body{}\n")
    for name, (title, d, tags, draft) in posts.items():
        fm = f"---\ntitle: {title}\n" + (f"date: {d}\n" if d is not None else "") + (f"tags: {tags}\n" if tags else "")
        fm += "draft: true\n" if draft else ""
        open(f"{SRC}/posts/{name}", "w", encoding="utf-8").write(fm + "---\nbody of " + name + "\n")


def slugify(t):
    s = unicodedata.normalize("NFKC", t).lower().strip()
    s = re.sub(r"\s+", "-", s)
    s = "".join(c for c in s if c.isalnum() or c in "-_")
    return re.sub(r"-+", "-", s).strip("-")


def tag_list(v):
    if v.startswith("[") and v.endswith("]"):
        v = v[1:-1]
    return [t.strip() for t in v.split(",") if t.strip()]


def model(posts):
    live = [(n[:-3], t, date.fromisoformat(d), tag_list(tags)) for n, (t, d, tags, dr) in posts.items() if not dr]
    live.sort(key=lambda p: p[1]); live.sort(key=lambda p: p[2], reverse=True)
    per_post, votes, members = {}, {}, {}
    for slug, title, d, tags in live:
        seen = {}
        for t in tags:
            s = slugify(t)
            if s and s not in seen:
                seen[s] = t
        per_post[slug] = list(seen)
        for s, t in seen.items():
            votes.setdefault(s, {}).setdefault(t, 0); votes[s][t] += 1
            members.setdefault(s, []).append((slug, title, d))
    display = {s: min(v, key=lambda t: (-v[t], t)) for s, v in votes.items()}
    return live, per_post, display, members


def page(title, root, content):
    return BASE.format(site=html.escape(SITE), title=html.escape(title), root=root, content=content)


def same(got, title, root, content):
    """content may or may not end with one newline (a template file usually does)."""
    return got in (page(title, root, content), page(title, root, content + "\n"))


def build(src=SRC, out=OUT):
    return subprocess.run([sys.executable, "-m", "ssg", "build", src, out], cwd="/tmp", env=ENV,
                          capture_output=True, text=True, timeout=60)


def read(rel):
    with open(os.path.join(OUT, rel), encoding="utf-8") as f:
        return f.read()


def verify(posts):
    live, per_post, display, members = model(posts)
    # tag pages
    for s, ms in members.items():
        items = "\n".join(f'<li><a href="../../posts/{sl}.html">{html.escape(t)}</a> <time>{d.isoformat()}</time></li>' for sl, t, d in ms)
        content = f'<h1>Tag: {html.escape(display[s])}</h1>\n<ul class="tag-posts">\n{items}\n</ul>'
        got = read(f"tags/{s}/index.html")
        assert same(got, "Tag: " + display[s], "../../", content), (f"tags/{s}/index.html", got, content)
    order = sorted(members, key=lambda s: (-len(members[s]), s))
    items = "\n".join(f'<li><a href="{s}/index.html">{html.escape(display[s])}</a> <span class="count">{len(members[s])}</span></li>' for s in order)
    content = f'<h1>Tags</h1>\n<ul class="tags">\n{items}\n</ul>'
    got = read("tags/index.html")
    assert same(got, "Tags", "../", content), ("tags/index.html", got, content)
    dirs = sorted(x for x in os.listdir(OUT + "/tags") if os.path.isdir(f"{OUT}/tags/{x}"))
    assert dirs == sorted(members), ("tag directories", dirs, sorted(members))
    # post pages: only the {tags} slot changes
    for slug, title, d, tags in live:
        links = [f'<a class="tag" href="../tags/{s}/index.html">{html.escape(display[s])}</a>' for s in per_post[slug]]
        slot = (" · " + ", ".join(links)) if links else ""
        want = page(title, "../", POST_TPL.format(title=html.escape(title), date=d.isoformat(), tags=slot,
                                                   body=f"<p>body of {slug}.md</p>"))
        got = read(f"posts/{slug}.html")
        assert got == want, (f"posts/{slug}.html", got, want)
    # index page unchanged in format
    items = "\n".join(f'<li><a href="posts/{sl}.html">{html.escape(t)}</a> <time>{d.isoformat()}</time></li>' for sl, t, d, _ in live)
    want = page("Home", "", f"<h1>{html.escape(SITE)}</h1>\n<ul class=\"posts\">\n{items}\n</ul>\n")
    assert read("index.html") == want, ("index.html", read("index.html"), want)


def foreign():
    return {p: open(os.path.join(OUT, p), "rb").read() for p in ["CNAME", "tags/README.txt", "posts/legacy.html"]}


# --- 1. first build into an OUT that already has deploy files and a stale tag dir
shutil.rmtree(OUT, ignore_errors=True)
for p, c in [("CNAME", "blog.example.jp\n"), ("tags/README.txt", "generated\n"), ("tags/old-tag/index.html", "old"),
             ("tags/old-tag/x.png", "png"), ("posts/legacy.html", "<p>legacy</p>")]:
    os.makedirs(os.path.dirname(os.path.join(OUT, p)), exist_ok=True)
    open(os.path.join(OUT, p), "w").write(c)
before = foreign()
write_src(POSTS)
r = build()
assert r.returncode == 0, r.stderr[-1500:]
verify(POSTS)
assert foreign() == before, "files the build does not own were changed"
assert not os.path.exists(OUT + "/tags/old-tag"), "stale tag directory not removed"
assert not os.path.exists(OUT + "/tags/secret"), "draft-only tag got a page"

# --- 2. idempotent rebuild: nothing rewritten
stamp = 1_000_000_000
for root, _, files in os.walk(OUT):
    for f in files:
        os.utime(os.path.join(root, f), (stamp, stamp))
r = build()
assert r.returncode == 0 and r.stdout.strip() == "wrote 0 file(s)", (r.stdout, r.stderr[-500:])
changed = [os.path.join(root, f) for root, _, files in os.walk(OUT) for f in files if os.stat(os.path.join(root, f)).st_mtime != stamp]
assert not changed, ("rewritten on an unchanged rebuild", changed)

# --- 3. source changes: a tag disappears, a post becomes a draft, display names change
P2 = dict(POSTS)
del P2["j.md"]
P2["f.md"] = P2["f.md"][:3] + (True,)
P2["e.md"] = ("type hints deep dive", "2026-02-20", "type hints, PYTHON, nodejs", False)
write_src(P2)
r = build()
assert r.returncode == 0, r.stderr[-1500:]
verify(P2)
assert not os.path.exists(OUT + "/tags/zig")
assert foreign() == before

# --- 4. invalid dates: error message, exit 1, nothing written
for bad in ["2026-02-30", "20260131", "2026-1-05", "2026-02-1x", None]:
    P3 = dict(POSTS)
    P3["e.md"] = ("type hints deep dive", bad, "x", True)   # drafts are validated too
    write_src(P3)
    out2 = "/tmp/tout_bad"
    shutil.rmtree(out2, ignore_errors=True)
    r = build(SRC, out2)
    shown = "" if bad is None else bad
    assert r.returncode == 1, (bad, r.returncode, r.stdout, r.stderr[-500:])
    assert r.stderr.strip() == f"error: posts/e.md: invalid date '{shown}'", (bad, r.stderr[-500:])
    assert not os.path.exists(out2), (bad, "output written despite the error")
    snap = {os.path.join(rt, f): os.stat(os.path.join(rt, f)).st_mtime_ns for rt, _, fs in os.walk(OUT) for f in fs}
    r = build()
    assert r.returncode == 1
    snap2 = {os.path.join(rt, f): os.stat(os.path.join(rt, f)).st_mtime_ns for rt, _, fs in os.walk(OUT) for f in fs}
    assert snap == snap2, (bad, "existing output changed despite the error")

# --- 5. a site without tags still gets an (empty) tag index
write_src({"only.md": ("Only", "2026-01-01", "", False), "dr.md": ("D", "2026-01-02", "x", True)})
shutil.rmtree(OUT)
r = build()
assert r.returncode == 0, r.stderr[-800:]
assert same(read("tags/index.html"), "Tags", "../", '<h1>Tags</h1>\n<ul class="tags">\n\n</ul>'), read("tags/index.html")
assert sorted(os.listdir(OUT + "/tags")) == ["index.html"]
print("ok")
