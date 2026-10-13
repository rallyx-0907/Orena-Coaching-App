"""Main-article extraction for a fetched web page: structure and density, no AI.

A Direct URL used to be converted to text wholesale, so everything a page
wraps around its article (comments, share bars, related links, media fallback
text, captions, a site "about" footer) was analysed as if the learner were
meant to read it. This stage runs between fetch and cleaning and keeps only
the article:

1. Parse the page into a tolerant tree (stdlib `HTMLParser`).
2. Prune boilerplate by *semantics*, not by wording: element type (`nav`,
   `aside`, `video`, `figcaption`...), ARIA role / hidden state, and the class,
   id and aria-label *tokens* a page uses to say what a block is ("comments",
   "related", "share", "newsletter", "sidebar"...). A wrapper that holds most
   of the page's prose is never pruned by its class name alone.
3. Choose the dominant container: the deepest element that holds most of the
   page's prose, where prose is sentence-shaped text weighed down by link
   density.
4. Emit its blocks in order, dropping link-heavy fragments, UI-sized scraps,
   the repeated title, byline/attribution lines at the edges, orphan headings,
   and a glossary-shaped section (kept as metadata, not as passage).
5. Report a deterministic confidence - high | medium | low - with its reasons.

Nothing here knows a site. Language handling is by units (words, or CJK
characters), so a Chinese page is measured the same way as an English one.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from html.parser import HTMLParser
from typing import Any

_VOID = frozenset(
    {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"}
)
_MAX_DEPTH = 150

# Never page prose, whatever they contain.
_DROP_TAGS = frozenset(
    {
        "script", "style", "noscript", "template", "svg", "head", "title", "nav", "footer", "aside",
        "form", "video", "audio", "iframe", "object", "embed", "canvas", "button", "select",
        "input", "textarea", "dialog", "menu", "map", "figcaption", "header", "address", "picture",
    }
)
_DROP_ROLES = frozenset(
    {
        "navigation", "banner", "contentinfo", "complementary", "search", "dialog", "alertdialog",
        "form", "menu", "menubar", "toolbar", "tablist", "doc-footnotes", "doc-endnotes",
        "doc-pagelist", "doc-toc", "doc-credit", "doc-credits", "doc-biblioentry",
    }
)
# Class / id / aria-label tokens that say "this block is not the article".
_BOILERPLATE_TOKENS = frozenset(
    """
    comment comments discussion disqus share sharing social follow related recommended
    recommendation recommendations more-stories newsletter subscribe subscription signup login
    signin register promo promos promotion sponsored advert advertisement ad ads sidebar footer
    nav navbar navigation menu breadcrumb breadcrumbs cookie cookies consent banner popup modal
    toolbar widget trending popular pagination pager masthead skip player controls caption
    captions credit credits copyright teaser print utility toolbox tags topics donate
    """.split()
)
# Byline / date furniture: removed from the passage, kept as metadata.
_META_TOKENS = frozenset({"byline", "author", "authors", "dateline", "postmeta", "published", "timestamp"})
_GLOSSARY_TOKENS = frozenset({"glossary", "vocab", "vocabulary", "definitions", "wordlist"})

_INLINE = frozenset(
    """
    a abbr acronym b bdi bdo big cite code data del dfn em font i ins kbd label mark q s samp
    small span strike strong sub sup time tt u var wbr
    """.split()
)
_HEADINGS = frozenset({"h1", "h2", "h3", "h4", "h5", "h6"})
# "By" + capitalised names only: "By morning the fields were green" is a sentence.
_NAME = r"[A-Z][\w.'’-]*"
_BYLINE_RE = re.compile(
    r"^(?i:by|written by|reported by|story by|text by|edited by|photos? by|hosted by)"
    rf"\s+{_NAME}(?:(?:\s+|\s*,\s*|\s+(?i:and)\s+|\s*&\s*){_NAME}){{0,5}}\.?$"
)
_INTRO_NAME_RE = re.compile(r"^(?i:i['’]m|i am|my name is)\s+[A-Z][\w.'’-]*(?:\s+[A-Z][\w.'’-]*){0,3}\.?$")
_WROTE_RE = re.compile(
    r"\b(?:wrote|written|reported|adapted|edited|contributed|compiled)\b.*\b(?:story|article|report|reporting)\b",
    re.IGNORECASE,
)
_SEPARATOR_RE = re.compile(r"^\s*[-–—:]")
_CJK_RE = re.compile(r"[㐀-䶿一-鿿豈-﫿]")
_WORD_RE = re.compile(r"[^\W_]+(?:['’-][^\W_]+)*", re.UNICODE)
_SENTENCE_END_RE = re.compile(r"[.!?。！？…][\"'”’)\]」』）]*$")
_HIDDEN_STYLE_RE = re.compile(r"display\s*:\s*none|visibility\s*:\s*hidden", re.IGNORECASE)

MIN_PROSE_UNITS = 120


def units(text: str) -> int:
    """Words, with every CJK character counting as one: language-neutral size."""
    cjk = len(_CJK_RE.findall(text))
    return cjk + len(_WORD_RE.findall(_CJK_RE.sub(" ", text)))


class _Node:
    __slots__ = ("tag", "attrs", "children", "parent", "_text", "_link", "_prose")

    def __init__(self, tag: str, attrs: dict[str, str], parent: _Node | None) -> None:
        self.tag = tag
        self.attrs = attrs
        self.children: list[_Node | str] = []
        self.parent = parent
        self._text: str | None = None
        self._link: int | None = None
        self._prose: float | None = None


class _TreeBuilder(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.root = _Node("#root", {}, None)
        self._stack: list[_Node] = [self.root]

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"p", "li", "dt", "dd"}:  # an unclosed sibling ends where the next one begins
            for open_node in reversed(self._stack):
                if open_node.tag == tag:
                    while self._stack[-1] is not open_node:
                        self._stack.pop()
                    self._stack.pop()
                    break
                if open_node.tag in {"ul", "ol", "dl", "div", "section", "article", "table", "body"}:
                    break
        node = _Node(tag, {key.lower(): (value or "") for key, value in attrs}, self._stack[-1])
        self._stack[-1].children.append(node)
        if tag not in _VOID and len(self._stack) < _MAX_DEPTH:
            self._stack.append(node)

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        node = _Node(tag, {key.lower(): (value or "") for key, value in attrs}, self._stack[-1])
        self._stack[-1].children.append(node)

    def handle_endtag(self, tag: str) -> None:
        for index in range(len(self._stack) - 1, 0, -1):
            if self._stack[index].tag == tag:
                del self._stack[index:]
                return

    def handle_data(self, data: str) -> None:
        self._stack[-1].children.append(data)


def _text(node: _Node) -> str:
    if node._text is None:
        parts: list[str] = []
        for child in node.children:
            if isinstance(child, str):
                parts.append(child)
            elif child.tag == "br":
                parts.append(" ")
            else:
                parts.append(" " + _text(child) + " " if child.tag not in _INLINE else _text(child))
        node._text = re.sub(r"\s+", " ", "".join(parts)).strip()
    return node._text


def _link_chars(node: _Node) -> int:
    if node._link is None:
        total = 0
        for child in node.children:
            if isinstance(child, _Node):
                total += len(_text(child)) if child.tag == "a" else _link_chars(child)
        node._link = total
    return node._link


def _link_density(node: _Node) -> float:
    size = len(_text(node))
    return min(1.0, _link_chars(node) / size) if size else 0.0


def _tokens(node: _Node) -> set[str]:
    raw = " ".join(node.attrs.get(name, "") for name in ("class", "id", "aria-label"))
    spaced = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", raw).lower()
    parts = [part for part in re.split(r"[^a-z0-9]+", spaced) if part]
    found = set(parts)
    found.update("-".join(pair) for pair in zip(parts, parts[1:], strict=False))
    return found


def _is_block(node: _Node) -> bool:
    return node.tag not in _INLINE and node.tag not in _VOID


def _has_block_child(node: _Node) -> bool:
    return any(isinstance(child, _Node) and _is_block(child) for child in node.children)


def _walk(node: _Node):
    for child in node.children:
        if isinstance(child, _Node):
            yield child
            yield from _walk(child)


def _is_prose(text: str, link_density: float) -> bool:
    size = units(text)
    return link_density < 0.5 and (size >= 12 or (size >= 6 and bool(_SENTENCE_END_RE.search(text))))


def _prose_score(node: _Node) -> float:
    if node._prose is None:
        if _is_block(node) and not _has_block_child(node):
            text = _text(node)
            density = _link_density(node)
            node._prose = len(text) * (1.0 - density) if _is_prose(text, density) else 0.0
        else:
            node._prose = sum(_prose_score(c) for c in node.children if isinstance(c, _Node))
    return node._prose


@dataclass
class _Block:
    text: str
    tag: str
    link_density: float
    term: str = ""
    definition: str = ""
    in_glossary: bool = False

    @property
    def heading(self) -> bool:
        return self.tag in _HEADINGS


@dataclass
class ExtractedArticle:
    """What the page's main article is, and how sure the extractor is."""

    body: str = ""
    title: str = ""
    author: str = ""
    published: str = ""
    canonical_url: str = ""
    glossary: list[dict[str, str]] = field(default_factory=list)
    attribution: list[str] = field(default_factory=list)
    confidence: str = "low"
    reasons: list[str] = field(default_factory=list)
    method: str = ""
    units: int = 0
    prose_paragraphs: int = 0
    coverage: float = 0.0

    def metadata(self) -> dict[str, Any]:
        """The evidence an admin sees next to the candidate."""
        info: dict[str, Any] = {
            "method": self.method,
            "confidence": self.confidence,
            "reasons": list(self.reasons),
            "body_units": self.units,
            "prose_paragraphs": self.prose_paragraphs,
            "page_coverage": self.coverage,
        }
        if self.attribution:
            info["attribution_lines"] = list(self.attribution)
        return {
            "extraction": info,
            "extraction_confidence": self.confidence,
            "page_canonical_url": self.canonical_url,
            "glossary": list(self.glossary),
        }


# ---- page-level metadata ---------------------------------------------------


def _json_ld(root: _Node) -> dict[str, str]:
    found = {"headline": "", "author": "", "published": "", "url": ""}
    for node in _walk(root):
        if node.tag != "script" or "ld+json" not in node.attrs.get("type", "").lower():
            continue
        try:
            data = json.loads("".join(c for c in node.children if isinstance(c, str)))
        except ValueError:
            continue
        stack = data if isinstance(data, list) else [data]
        while stack:
            item = stack.pop(0)
            if not isinstance(item, dict):
                continue
            stack.extend(item.get("@graph") or [])
            kind = item.get("@type")
            kinds = " ".join(kind) if isinstance(kind, list) else str(kind or "")
            if not re.search(r"article|posting|report|news", kinds, re.IGNORECASE):
                continue
            found["headline"] = found["headline"] or str(item.get("headline") or "")
            found["published"] = found["published"] or str(item.get("datePublished") or "")
            found["url"] = found["url"] or str(item.get("url") or "")
            author = item.get("author")
            author = author[0] if isinstance(author, list) and author else author
            if isinstance(author, dict):
                author = author.get("name")
            found["author"] = found["author"] or (str(author) if isinstance(author, str) else "")
    return found


def _page_metadata(root: _Node) -> dict[str, str]:
    meta = {"og_title": "", "canonical": "", "author": "", "published": "", "h1": "", "title": ""}
    for node in _walk(root):
        if node.tag == "meta":
            name = (node.attrs.get("property") or node.attrs.get("name") or "").lower()
            content = node.attrs.get("content", "").strip()
            if name == "og:title":
                meta["og_title"] = meta["og_title"] or content
            elif name == "og:url":
                meta["canonical"] = meta["canonical"] or content
        elif node.tag == "link" and "canonical" in node.attrs.get("rel", "").lower():
            meta["canonical"] = node.attrs.get("href", "").strip() or meta["canonical"]
        elif node.tag == "h1" and not meta["h1"]:
            meta["h1"] = _text(node)
        elif node.tag == "title" and not meta["title"]:
            meta["title"] = _text(node)
        elif node.tag == "time" and node.attrs.get("datetime") and not meta["published"]:
            meta["published"] = node.attrs["datetime"].strip()
        elif not meta["author"] and (
            "author" in node.attrs.get("rel", "").lower()
            or node.attrs.get("itemprop", "").lower() == "author"
            or "byline" in _tokens(node)
        ) and node.tag not in {"meta", "link"}:
            meta["author"] = re.sub(r"^(?:by|written by)\s+", "", _text(node), flags=re.IGNORECASE)[:120]
    return meta


def _norm(text: str) -> str:
    return re.sub(r"[\W_]+", " ", text.casefold()).strip()


# ---- pruning ---------------------------------------------------------------


def _prune(root: _Node, glossary_nodes: list[_Node]) -> None:
    page_size = max(1, len(_visible_text(root)))

    def removable(node: _Node) -> bool:
        if node.tag in _DROP_TAGS and node.tag != "head":
            return True
        attrs = node.attrs
        if "hidden" in attrs or attrs.get("aria-hidden", "").lower() == "true":
            return True
        if _HIDDEN_STYLE_RE.search(attrs.get("style", "")):
            return True
        if attrs.get("role", "").lower() in _DROP_ROLES:
            return True
        if node.tag in {"html", "body", "main", "article"}:
            return False
        tokens = _tokens(node)
        if not tokens & (_BOILERPLATE_TOKENS | _META_TOKENS):
            return False
        # A wrapper that holds most of the page is a layout, not boilerplate.
        return len(_text(node)) < 0.6 * page_size

    def visit(node: _Node) -> None:
        kept: list[_Node | str] = []
        for child in node.children:
            if isinstance(child, str):
                kept.append(child)
                continue
            if child.tag in {"head", "script", "style", "noscript", "template", "svg"}:
                continue
            if (
                child.attrs.get("role", "").lower() == "doc-glossary"
                or (_tokens(child) & _GLOSSARY_TOKENS and len(_text(child)) < 0.6 * page_size)
            ):
                glossary_nodes.append(child)
                continue
            if removable(child):
                continue
            visit(child)
            kept.append(child)
        node.children = kept
        node._text = node._link = node._prose = None

    visit(root)


# ---- blocks ----------------------------------------------------------------


def _leading_term(node: _Node) -> tuple[str, str]:
    """`<b>term</b> - definition` or `<dt>`-shaped: (term, definition) or ("", "")."""
    first = next((c for c in node.children if not (isinstance(c, str) and not c.strip())), None)
    if isinstance(first, _Node) and first.tag in {"b", "strong", "dfn", "em", "i"}:
        term = _text(first)
        rest = _text(node)[len(term):] if _text(node).startswith(term) else ""
        if 0 < len(term) <= 40 and _SEPARATOR_RE.match(rest):
            return term, rest.lstrip(" -–—:").strip()
    return "", ""


def _collect(node: _Node, out: list[_Block]) -> None:
    run: list[str] = []

    def flush() -> None:
        text = re.sub(r"\s+", " ", " ".join(run)).strip()
        run.clear()
        if text:
            out.append(_Block(text, "p", 0.0))

    for child in node.children:
        if isinstance(child, str):
            run.append(child)
        elif not _is_block(child):
            run.append(_text(child))
        elif _has_block_child(child) and child.tag not in {"li", "dd", "p", "blockquote"}:
            flush()
            _collect(child, out)
        else:
            flush()
            text = _text(child)
            if text:
                term, definition = _leading_term(child)
                if child.tag == "dt":
                    term = text
                out.append(_Block(text, child.tag, _link_density(child), term, definition))
    flush()


def _glossary_entries(node: _Node) -> list[dict[str, str]]:
    blocks: list[_Block] = []
    _collect(node, blocks)
    entries: list[dict[str, str]] = []
    pending = ""
    for block in blocks:
        if block.tag == "dt":
            pending = block.text
        elif block.tag == "dd" and pending:
            entries.append({"term": pending, "definition": block.text})
            pending = ""
        elif block.term:
            entries.append({"term": block.term, "definition": block.definition})
    return entries


def _split_glossary(blocks: list[_Block]) -> list[dict[str, str]]:
    """A heading followed by term/definition blocks is supplementary, not body."""
    entries: list[dict[str, str]] = []
    index = 0
    while index < len(blocks):
        if not blocks[index].heading:
            index += 1
            continue
        end, pending, found = index + 1, "", []
        while end < len(blocks) and not blocks[end].heading:
            block = blocks[end]
            if block.tag == "dt":
                pending = block.text
            elif block.tag == "dd" and pending:
                found.append({"term": pending, "definition": block.text})
                pending = ""
            elif block.term and units(block.text) <= 40:
                found.append({"term": block.term, "definition": block.definition})
            else:
                break
            end += 1
        if len(found) >= 2:
            entries.extend(found)
            del blocks[index:end]
        else:
            index += 1
    return entries


def _edge_attribution(blocks: list[_Block], attribution: list[str]) -> None:
    def is_byline(block: _Block) -> bool:
        size = units(block.text)
        if block.heading or size > 25:
            return False
        if size <= 8 and (_BYLINE_RE.match(block.text) or _INTRO_NAME_RE.match(block.text)):
            return True
        return bool(_WROTE_RE.search(block.text))

    for position in (0, -1):
        while blocks and is_byline(blocks[position]):
            attribution.append(blocks.pop(position).text)


def _clean_blocks(blocks: list[_Block], titles: set[str], attribution: list[str]) -> tuple[list[_Block], list[dict[str, str]]]:
    kept = []
    for block in blocks:
        size = units(block.text)
        if block.link_density > 0.5 and size < 30:
            continue
        if not block.heading and size <= 3 and not _SENTENCE_END_RE.search(block.text):
            continue
        if block.tag == "h1":
            continue
        kept.append(block)
    for block in list(kept[:3]):
        if _norm(block.text) in titles:
            kept.remove(block)
    glossary = _split_glossary(kept)
    for _ in range(2):  # a trailing heading hides the closing byline, and vice versa
        while kept and kept[-1].heading:  # a heading with nothing under it
            kept.pop()
        _edge_attribution(kept, attribution)
    result: list[_Block] = []
    for index, block in enumerate(kept):
        if block.heading and (index + 1 == len(kept) or kept[index + 1].heading):
            continue
        result.append(block)
    return result, glossary


def _dominant_container(body: _Node) -> _Node:
    total = _prose_score(body)
    node = body
    while total > 0:
        heavier = [c for c in node.children if isinstance(c, _Node) and _prose_score(c) >= 0.8 * total]
        if not heavier:
            break
        node = heavier[0]
    if _is_block(node) and not _has_block_child(node) and node.parent is not None:
        node = node.parent
    return node


def _semantic(node: _Node) -> bool:
    current: _Node | None = node
    while current is not None:
        if current.tag in {"article", "main"} or current.attrs.get("role", "").lower() == "main":
            return True
        current = current.parent
    return False


def extract_article(html: str) -> ExtractedArticle:
    """The main article of `html`, or a low-confidence best effort."""
    builder = _TreeBuilder()
    builder.feed(html or "")
    builder.close()
    root = builder.root

    info = _page_metadata(root)
    ld = _json_ld(root)
    page_units = units(_visible_text(root))
    titles = {_norm(t) for t in (ld["headline"], info["og_title"], info["h1"], info["title"]) if t}

    glossary_nodes: list[_Node] = []
    _prune(root, glossary_nodes)
    body_node = next((n for n in _walk(root) if n.tag == "body"), root)

    container = _dominant_container(body_node)
    reasons: list[str] = []
    method = "dominant_container"
    page_title = ld["headline"] or info["og_title"] or info["h1"] or info["title"]

    # Whole-page pass: supplementary sections (glossary, attribution) and a
    # visible title sit beside the article as often as inside it.
    page_raw: list[_Block] = []
    _collect(body_node, page_raw)
    if not (ld["headline"] or info["og_title"] or info["h1"]):
        lead = next(
            (b for b in page_raw[:4] if b.heading and units(b.text) >= 2
             and _norm(info["title"]).startswith(_norm(b.text))),
            None,
        )
        if lead:
            page_title = lead.text
            titles.add(_norm(lead.text))
    page_attribution: list[str] = []
    _, glossary = _clean_blocks(page_raw, titles, page_attribution)

    attribution: list[str] = []
    blocks = _clean_blocks_for(container, titles, attribution)
    if sum(units(b.text) for b in blocks) < 60 and container is not body_node:
        wide = _clean_blocks_for(body_node, titles, [])
        if sum(units(b.text) for b in wide) > 2 * sum(units(b.text) for b in blocks):
            blocks, method, container = wide, "page_fallback", body_node
            reasons.append("fallback_to_whole_page")
    attribution = list(dict.fromkeys(attribution + page_attribution))

    for node in glossary_nodes:
        glossary.extend(_glossary_entries(node))

    body = "\n\n".join(b.text for b in blocks)
    size = units(body)
    paragraphs = sum(1 for b in blocks if not b.heading and _is_prose(b.text, b.link_density))
    coverage = round(size / page_units, 3) if page_units else 0.0

    cards = [n for n in _walk(container) if n.tag == "article" and _prose_score(n) >= 0.15 * max(_prose_score(container), 1)]
    semantic = _semantic(container)
    if len(cards) >= 2:
        reasons.append("multiple_article_candidates")
    if paragraphs < 2:
        reasons.append("few_prose_paragraphs")
    if size < 60:
        reasons.append("very_short_body")
    if method == "dominant_container" and not semantic:
        reasons.append("no_article_or_main_element")
    if coverage < 0.15:
        reasons.append("small_share_of_page")
    if size < MIN_PROSE_UNITS and "very_short_body" not in reasons:
        reasons.append("short_body")

    hard = {"multiple_article_candidates", "few_prose_paragraphs", "very_short_body", "fallback_to_whole_page"}
    if hard & set(reasons):
        confidence = "low"
    elif reasons:
        confidence = "medium"
    else:
        confidence = "high"

    return ExtractedArticle(
        body=body,
        title=" ".join(page_title.split()),
        author=ld["author"] or info["author"],
        published=ld["published"] or info["published"],
        canonical_url=ld["url"] or info["canonical"],
        glossary=glossary,
        attribution=attribution,
        confidence=confidence,
        reasons=reasons,
        method=method,
        units=size,
        prose_paragraphs=paragraphs,
        coverage=coverage,
    )


def _clean_blocks_for(container: _Node, titles: set[str], attribution: list[str]) -> list[_Block]:
    raw: list[_Block] = []
    _collect(container, raw)
    return _clean_blocks(raw, titles, attribution)[0]


def _visible_text(root: _Node) -> str:
    parts: list[str] = []

    def visit(node: _Node) -> None:
        for child in node.children:
            if isinstance(child, str):
                parts.append(child)
            elif child.tag not in {"script", "style", "head", "template", "noscript", "svg"}:
                visit(child)

    visit(root)
    return " ".join(parts)
