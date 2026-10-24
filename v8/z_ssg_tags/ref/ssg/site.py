"""Load a site source directory and render it.

Source layout:
    SRC/config.ini        [site] name = ...
    SRC/posts/*.md        posts with front matter (see frontmatter.py)
    SRC/static/           copied as-is to OUT/

Output:
    OUT/index.html        all non-draft posts, newest first
    OUT/posts/<slug>.html one page per non-draft post
    OUT/tags/index.html   all tags, most used first
    OUT/tags/<tag slug>/index.html  the posts of one tag
    OUT/<static files>
"""
import configparser
import html
import os
import re
import shutil
import unicodedata
from collections import Counter
from dataclasses import dataclass, field
from datetime import date

from ssg import frontmatter, markdown, writer

class DateError(ValueError):
    pass


_DATE = re.compile(r"\d{4}-\d{2}-\d{2}")


def parse_date(rel, value):
    try:
        if not _DATE.fullmatch(value):
            raise ValueError(value)
        return date.fromisoformat(value)
    except ValueError:
        raise DateError(f"{rel}: invalid date '{value}'") from None


def slugify(tag):
    s = unicodedata.normalize("NFKC", tag).lower().strip()
    s = re.sub(r"\s+", "-", s)
    s = "".join(c for c in s if c.isalnum() or c in "-_")
    return re.sub(r"-+", "-", s).strip("-")


TEMPLATES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "templates")


@dataclass
class Post:
    path: str            # relative to SRC, e.g. "posts/hello.md"
    slug: str
    title: str
    date: date
    tags: list = field(default_factory=list)
    draft: bool = False
    body_html: str = ""


def template(name):
    with open(os.path.join(TEMPLATES, name), encoding="utf-8") as f:
        return f.read()


def load_posts(src):
    posts = []
    pdir = os.path.join(src, "posts")
    for name in sorted(os.listdir(pdir)):
        if not name.endswith(".md"):
            continue
        rel = "posts/" + name
        with open(os.path.join(pdir, name), encoding="utf-8") as f:
            meta, body = frontmatter.parse(f.read())
        posts.append(Post(
            path=rel,
            slug=meta.get("slug") or name[:-3],
            title=meta.get("title") or name[:-3],
            date=parse_date(rel, meta.get("date", "")),
            tags=meta["tags"],
            draft=meta["draft"],
            body_html=markdown.render(body),
        ))
    return posts


def site_name(src):
    cp = configparser.ConfigParser()
    cp.read(os.path.join(src, "config.ini"), encoding="utf-8")
    return cp.get("site", "name", fallback="My Site")


def page(site, title, root, content):
    return template("base.html").format(site=html.escape(site), title=html.escape(title), root=root, content=content)


def post_slugs(p):
    """Distinct tag slugs of a post, in first-occurrence order, with the spelling used."""
    seen = {}
    for t in p.tags:
        sl = slugify(t)
        if sl and sl not in seen:
            seen[sl] = t.strip()
    return seen


def collect_tags(posts):
    """{slug: (display, [posts])}"""
    spell = {}
    members = {}
    for p in posts:
        for sl, t in post_slugs(p).items():
            spell.setdefault(sl, Counter())[t] += 1
            members.setdefault(sl, []).append(p)
    return {sl: (min(c, key=lambda t: (-c[t], t)), members[sl]) for sl, c in spell.items()}


def render_post(site, p, tags_info=None):
    tags = ""
    links = [f'<a class="tag" href="../tags/{sl}/index.html">{html.escape(tags_info[sl][0])}</a>'
             for sl in post_slugs(p)] if tags_info is not None else []
    if links:
        tags = " · " + ", ".join(links)
    content = template("post.html").format(title=html.escape(p.title), date=p.date.isoformat(),
                                           tags=tags, body=p.body_html)
    return page(site, p.title, "../", content)


def render_index(site, posts):
    items = "\n".join(f'<li><a href="posts/{p.slug}.html">{html.escape(p.title)}</a> <time>{p.date.isoformat()}</time></li>'
                      for p in posts)
    return page(site, "Home", "", template("index.html").format(site=html.escape(site), items=items))


def render_tag(site, display, posts):
    items = "\n".join(f'<li><a href="../../posts/{p.slug}.html">{html.escape(p.title)}</a> <time>{p.date.isoformat()}</time></li>'
                      for p in ordered(posts))
    content = f'<h1>Tag: {html.escape(display)}</h1>\n<ul class="tag-posts">\n{items}\n</ul>'
    return page(site, "Tag: " + display, "../../", content)


def render_tag_index(site, info):
    order = sorted(info, key=lambda sl: (-len(info[sl][1]), sl))
    items = "\n".join(f'<li><a href="{sl}/index.html">{html.escape(info[sl][0])}</a> <span class="count">{len(info[sl][1])}</span></li>'
                      for sl in order)
    return page(site, "Tags", "../", f'<h1>Tags</h1>\n<ul class="tags">\n{items}\n</ul>')


def ordered(posts):
    """Newest first; same day: by title."""
    return sorted(sorted(posts, key=lambda p: p.title), key=lambda p: p.date, reverse=True)


def build(src, out):
    """Build the site; returns the number of files written."""
    site = site_name(src)
    posts = [p for p in load_posts(src) if not p.draft]
    info = collect_tags(posts)
    n = 0
    for p in posts:
        n += writer.write_if_changed(os.path.join(out, "posts", p.slug + ".html"), render_post(site, p, info))
    tdir = os.path.join(out, "tags")
    for sl, (display, members) in info.items():
        n += writer.write_if_changed(os.path.join(tdir, sl, "index.html"), render_tag(site, display, members))
    n += writer.write_if_changed(os.path.join(tdir, "index.html"), render_tag_index(site, info))
    for name in sorted(os.listdir(tdir)):
        if os.path.isdir(os.path.join(tdir, name)) and name not in info:
            shutil.rmtree(os.path.join(tdir, name))
    n += writer.write_if_changed(os.path.join(out, "index.html"), render_index(site, ordered(posts)))
    n += writer.copy_static(os.path.join(src, "static"), out)
    return n
