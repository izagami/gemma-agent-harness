"""Load a site source directory and render it.

Source layout:
    SRC/config.ini        [site] name = ...
    SRC/posts/*.md        posts with front matter (see frontmatter.py)
    SRC/static/           copied as-is to OUT/

Output:
    OUT/index.html        all non-draft posts, newest first
    OUT/posts/<slug>.html one page per non-draft post
    OUT/<static files>
"""
import configparser
import html
import os
from dataclasses import dataclass, field
from datetime import date

from ssg import frontmatter, markdown, writer

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
            date=date.fromisoformat(meta["date"]),
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


def render_post(site, p):
    tags = ""
    if p.tags:
        tags = " · " + ", ".join(html.escape(t) for t in p.tags)
    content = template("post.html").format(title=html.escape(p.title), date=p.date.isoformat(),
                                           tags=tags, body=p.body_html)
    return page(site, p.title, "../", content)


def render_index(site, posts):
    items = "\n".join(f'<li><a href="posts/{p.slug}.html">{html.escape(p.title)}</a> <time>{p.date.isoformat()}</time></li>'
                      for p in posts)
    return page(site, "Home", "", template("index.html").format(site=html.escape(site), items=items))


def ordered(posts):
    """Newest first; same day: by title."""
    return sorted(sorted(posts, key=lambda p: p.title), key=lambda p: p.date, reverse=True)


def build(src, out):
    """Build the site; returns the number of files written."""
    site = site_name(src)
    posts = [p for p in load_posts(src) if not p.draft]
    n = 0
    for p in posts:
        n += writer.write_if_changed(os.path.join(out, "posts", p.slug + ".html"), render_post(site, p))
    n += writer.write_if_changed(os.path.join(out, "index.html"), render_index(site, ordered(posts)))
    n += writer.copy_static(os.path.join(src, "static"), out)
    return n
