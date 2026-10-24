# docrender syntax and output

Every document renders to `<article>` ... `</article>` followed by a newline; one HTML
line per block line as shown below.

| input | output |
|---|---|
| `# Title` | `<h1 id="title">Title</h1>` (not numbered) |
| `## Section` | `<h2 id="section">1. Section</h2>` — `##` headings are numbered 1, 2, 3 ... |
| `### Sub` | `<h3 id="sub">1.1. Sub</h3>` — numbered within the current `##`, restarting at 1 |
| paragraph lines | `<p>joined with single spaces</p>` |
| `- a` / `1. a` | `<ul>` / `<ol>`, one `<li>` per item |
| fenced code | `<pre><code class="lang-x">...</code></pre>` |
| `---` | `<hr>` |

Heading ids are slugs of the heading text; when a slug repeats *within a document*
the later ones get `-2`, `-3`, ...  Numbering and ids start afresh in every document.

Inline: `` `code` ``, `**strong**`, `*em*`, `[text](url)`, `[text][name]` / `[name][]`
with a `[name]: url` definition **in the same document** (names are case-insensitive,
the first definition wins; an undefined reference is output literally), footnote
references `[^id]` with a `[^id]: text` definition in the same document (undefined
references are output literally).

Footnotes are numbered 1, 2, 3 ... in the order of their first reference in the
document.  Every reference renders as `<sup><a href="#fn-N">N</a></sup>`; the first
reference of each footnote also carries `id="fnref-N"`.  If any footnote is
referenced, the document ends with

```
<section class="footnotes">
<ol>
<li id="fn-1">text <a href="#fnref-1">&#8617;</a></li>
</ol>
</section>
```

listing only the referenced footnotes, by number.  Rendering a document never
depends on other documents rendered before it (in a batch or in the same process).
