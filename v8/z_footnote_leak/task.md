`docrender/` renders our markdown-ish handbook pages to HTML (`python3 -m docrender render FILE`, `python3 -m docrender batch FILE... -o DIR`; syntax and exact output in docs/SYNTAX.md). The unit tests pass, and rendering any single file with `render` gives the right HTML. But when the handbook is built with `batch` (e.g. `python3 -m docrender batch examples/*.txt -o out/`), every page after the first one comes out wrong. Users have reported things like section numbers and footnote numbers not starting at 1, odd heading ids, and links pointing at another page's URL. The same thing happens when an application imports `docrender.render` and calls it more than once in a process.

Find the cause(s) and fix them.

- After the fix, rendering a document must give exactly the same output no matter which other documents were rendered before it in the same process, or in which order a batch lists the files, and that output must follow docs/SYNTAX.md.
- Don't change the output format, the command line, or the `render(text)` API.
- Don't modify tests/, docs/ or examples/ (adding new test files is fine). `python3 -m unittest discover -s tests` must pass.
- It will be graded with other documents than the ones in examples/.
