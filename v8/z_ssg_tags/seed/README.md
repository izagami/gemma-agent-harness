# ssg

A very small static site generator.

    python3 -m ssg build example /tmp/site

Source layout and output layout: see `ssg/site.py`.  Front matter: `ssg/frontmatter.py`.
Markdown subset: `ssg/markdown.py`.  Page templates (`str.format`): `ssg/templates/`.

The output directory is deployed with rsync, so a rebuild must not touch files whose content
did not change (`ssg/writer.py`).  The deploy also puts a few files of its own into the output
directory (e.g. `CNAME`, `robots.txt`); the build never deletes files it does not own.
