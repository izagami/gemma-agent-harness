# feed

`python3 -m feed POSTS.jsonl [--author NAME] [--limit N] [--cursor C]` prints one page of posts, one per
line (`id<TAB>created_at<TAB>author<TAB>title`), then `next: <cursor>` or `next: -`.
The same is available as `feed.paginate.page(posts, limit=20, cursor=None, author=None)` →
`{"items": [post, ...], "next": str | None}`.

## Rules

* Order: `created_at` descending (ISO-8601 strings, compared as strings); posts with the same
  `created_at`: larger `id` first. `id` is a unique integer.
* Posts with `"deleted": true` never appear. With `--author`, only that author's posts appear.
* `limit` is 1..100 (default 20); otherwise `error: limit must be 1..100`, exit 1.
* A page holds the first `limit` matching posts after the cursor position (from the start without a
  cursor). It is shorter than `limit` only when there are no more matching posts.
* `next` is a cursor for the following page if — and only if — more matching posts come after this page;
  on the last page it is `None` (`next: -`). The cursor is opaque (it marks the position of the last post
  of the page); the page for a cursor holds the matching posts strictly after that position.
* Following `next` from the first page therefore lists every matching post exactly once, in order.
* A cursor that cannot be decoded: `error: bad cursor`, exit 1.
