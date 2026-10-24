"""docrender: a tiny markdown-ish to HTML renderer used for the internal handbook.

    from docrender import render
    html = render(text)

See docs/SYNTAX.md for the supported syntax and the exact output.
"""
from docrender.renderer import render

__all__ = ["render"]
