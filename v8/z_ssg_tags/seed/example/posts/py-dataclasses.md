---
title: dataclasses の小技
date: 2026-02-11
tags: Python, tips
---
# field(default_factory=list)

`list` をデフォルト値にするときは *必ず* default_factory を使う。

- 可変なデフォルト値は共有される
- [公式ドキュメント](https://docs.python.org/3/library/dataclasses.html)
