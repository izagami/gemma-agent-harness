`ssg/` is a small static site generator (`python3 -m ssg build SRC OUT`; read README.md and the docstrings in `ssg/`). Add **tag pages**. Requirements:

1. **Slug of a tag.** From the tag string `t` (as listed in the front matter): apply Unicode NFKC normalization, then `.lower()`, then strip surrounding whitespace; replace every run of whitespace with a single `-`; then delete every character that is not alphanumeric (`str.isalnum()`), `-` or `_`; finally collapse runs of `-` into one `-` and remove leading/trailing `-`. Examples: `Type Hints` -> `type-hints`, `Ｐｙｔｈｏｎ` -> `python`, `node.js` -> `nodejs`, `C++` -> `c`, `日記` -> `日記`. A tag whose slug is empty is ignored everywhere.
2. **Identity.** Tags with the same slug are the same tag, across posts and inside one post (a post that lists `Go, go` has the tag once).
3. **Display name** of a tag: every non-draft post that has the tag votes once, for the first spelling it uses for it (the tag string with surrounding whitespace stripped; for `Go, go` that is `Go`). The spelling with the most votes wins; on a tie, the smallest spelling in plain Python string order (`"Python" < "python"`).
4. **Tag page** `OUT/tags/<slug>/index.html` for every tag used by at least one non-draft post. It is rendered through `ssg/templates/base.html` exactly like the existing pages (`site.page()`), with page title `Tag: <display name>`, root `../../`, and this content (items joined with `\n`):
   ```
   <h1>Tag: {display}</h1>
   <ul class="tag-posts">
   <li><a href="../../posts/{post slug}.html">{post title}</a> <time>{YYYY-MM-DD}</time></li>
   </ul>
   ```
   (A single trailing newline after `</ul>` is allowed here and in 5.) Posts are in the same order as on `index.html` (newest date first; same date: by title).
5. **Tag index** `OUT/tags/index.html`: page title `Tags`, root `../`, content
   ```
   <h1>Tags</h1>
   <ul class="tags">
   <li><a href="{slug}/index.html">{display}</a> <span class="count">{number of non-draft posts}</span></li>
   </ul>
   ```
   ordered by count (descending), then slug (ascending, plain string order). It is always written; with no tags the item part is empty (`<ul class="tags">\n\n</ul>`).
6. **Post pages.** The `{tags}` slot of `post.html` becomes `" · "` followed by links joined with `", "`: one `<a class="tag" href="../tags/{slug}/index.html">{display}</a>` per distinct tag of the post (order of first occurrence in the post's front matter; `{display}` is the site-wide display name). If the post has no (non-ignored) tags the slot is empty.
7. **Escaping.** Display names and titles are escaped with `html.escape()` (default arguments) wherever they appear in HTML, including `<title>` (as `site.page()` already does). Slugs are written into links as they are (not percent-encoded).
8. **Drafts** (`draft: true`) are invisible to tags: they are not listed, not counted, and do not affect display names. A tag used only by drafts has no page.
9. **Stale pages.** After a build, every subdirectory of `OUT/tags/` that is not the slug of a current tag is deleted (with its contents). Nothing else in `OUT` that the build did not generate is deleted or changed (files directly inside `OUT/tags/` other than `index.html`, `OUT/CNAME`, old files in `OUT/posts/`, ...).
10. **Idempotency.** Like the existing pages, a file whose content would not change is not rewritten (its mtime stays). Building twice in a row prints `wrote 0 file(s)` the second time; the count includes tag pages.
11. **Dates.** Every post (drafts included) must have `date:` in the exact form `YYYY-MM-DD` (4, 2 and 2 digits) and a valid calendar date. Otherwise the build prints `error: posts/<file name>: invalid date '<value as written>'` (empty value `''` when `date` is missing) to stderr, exits with status 1, and writes nothing (OUT is not created or changed).
12. Do not modify the existing files in `ssg/templates/` (you may add new files) or in `tests/`. `python3 -m unittest discover -s tests` must pass; existing behaviour (index page, post pages apart from the `{tags}` slot, static files, front matter errors) stays the same.
