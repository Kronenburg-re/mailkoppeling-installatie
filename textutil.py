import html, re
from html.parser import HTMLParser


class _Strip(HTMLParser):
    def __init__(self):
        super().__init__()
        self.out, self.skip = [], 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style", "head"):
            self.skip += 1
        elif tag in ("br", "p", "div", "tr", "li", "h1", "h2", "h3"):
            self.out.append("\n")

    def handle_endtag(self, tag):
        if tag in ("script", "style", "head") and self.skip:
            self.skip -= 1

    def handle_data(self, d):
        if not self.skip:
            self.out.append(d)


def html_to_text(s: str) -> str:
    p = _Strip()
    try:
        p.feed(s)
    except Exception:
        return re.sub(r"<[^>]+>", " ", s)
    t = "".join(p.out)
    t = re.sub(r"[ \t\xa0]+", " ", t)
    return re.sub(r"\n\s*\n\s*\n+", "\n\n", t).strip()


def text_to_html(s: str) -> str:
    return "<br>".join(html.escape(s).splitlines())


def clip(s: str, n: int = 20000) -> str:
    return s if len(s) <= n else s[:n] + f"\n\n[... ingekort, {len(s) - n} tekens weggelaten]"
