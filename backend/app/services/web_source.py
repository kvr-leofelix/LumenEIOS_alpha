"""Fetch a learning-resource link (Wikipedia, BYJU'S, ...) and extract its readable text.

Used by AI Question Studio as a retrieval source next to (or instead of) a chapter PDF.

Safety, because the server fetches a URL a user typed:
- only http/https on ports 80/443, no credentials in the URL
- every hostname is resolved and rejected if any address is private, loopback, link-local,
  multicast or reserved (blocks requests into the server's own network); redirects are
  followed by hand so each hop is checked again
- 15 s timeout, 3 MB download cap, HTML or plain text only
The page text is treated as untrusted source material by the prompt, never as instructions.
"""
import asyncio
import ipaddress
import re
import socket
from dataclasses import dataclass
from html import unescape
from html.parser import HTMLParser
from typing import List, Optional
from urllib.parse import urljoin, urlsplit

import httpx

MAX_LINKS = 3
MAX_BYTES = 3 * 1024 * 1024
MAX_REDIRECTS = 4
TIMEOUT_SECONDS = 15.0
MIN_TEXT_CHARS = 200
# Wikimedia rejects (403) clients whose User-Agent carries no contact point.
USER_AGENT = "LumenEIOS-QuestionStudio/1.0 (+https://github.com/kvr-leofelix/arena; educational question generation)"

# Content that is never lesson text.
_SKIP_TAGS = {"script", "style", "noscript", "template", "svg", "nav", "footer", "header", "aside", "form", "button", "iframe"}
_BLOCK_TAGS = {"p", "div", "section", "article", "main", "li", "ul", "ol", "table", "tr", "br", "h1", "h2", "h3", "h4", "h5", "h6", "blockquote", "pre", "dd", "dt", "figcaption"}
_VOID_TAGS = {"br", "img", "hr", "meta", "link", "input", "source", "wbr", "area", "base", "col", "embed", "param", "track"}
# Wikipedia/MediaWiki boilerplate inside the article body.
_SKIP_CLASSES = {"reflist", "references", "navbox", "mw-editsection", "infobox", "sidebar", "hatnote", "toc", "metadata", "noprint", "catlinks", "mw-references-wrap", "printfooter"}


class WebSourceError(ValueError):
    """The link can't be used; the message is safe to show the teacher."""


@dataclass
class WebSource:
    url: str
    title: str
    text: str


class _ReadableTextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.title = ""
        self._in_title = False
        self.og_title = ""
        self.h1 = ""
        self._in_h1 = False
        self._skip_depth = 0
        self._main_depth = 0
        self._stack: List[tuple[str, bool, bool]] = []  # (tag, skipping, main)
        self.body: List[str] = []
        self.main: List[str] = []

    def handle_starttag(self, tag, attrs):
        attr = dict(attrs)
        if tag in _VOID_TAGS:
            if tag == "br":
                self._emit("\n")
            elif tag == "meta" and attr.get("property") == "og:title":
                self.og_title = attr.get("content") or ""
            return
        # Whole class names only: Wikipedia's <html> class contains "...-toc-..." substrings.
        classes = set((attr.get("class") or "").lower().split())
        skipping = tag in _SKIP_TAGS or bool(classes & _SKIP_CLASSES) or attr.get("role") == "navigation"
        is_main = tag in {"main", "article"} or attr.get("id") in {"mw-content-text", "content", "main-content"} or attr.get("role") == "main"
        self._stack.append((tag, skipping, is_main))
        self._skip_depth += skipping
        self._main_depth += is_main
        if tag == "title":
            self._in_title = True
        if tag == "h1" and not self.h1:
            self._in_h1 = True
        if tag in _BLOCK_TAGS:
            self._emit("\n")

    def handle_endtag(self, tag):
        if tag == "h1":
            self._in_h1 = False
        if tag in _VOID_TAGS:
            return
        # Pop up to the matching tag; tolerates the unclosed tags real pages have.
        for index in range(len(self._stack) - 1, -1, -1):
            if self._stack[index][0] == tag:
                for _, skipping, is_main in self._stack[index:]:
                    self._skip_depth -= skipping
                    self._main_depth -= is_main
                del self._stack[index:]
                break
        if tag == "title":
            self._in_title = False
        if tag in _BLOCK_TAGS:
            self._emit("\n")

    def handle_data(self, data):
        if self._in_title:
            self.title += data
            return
        if self._in_h1:
            self.h1 += data
        self._emit(data)

    def _emit(self, text: str) -> None:
        if self._skip_depth:
            return
        self.body.append(text)
        if self._main_depth:
            self.main.append(text)


def _clean(text: str) -> str:
    text = unescape(text).replace("\xa0", " ")
    text = re.sub(r"\[\s*(\d+|edit|citation needed)\s*\]", "", text)  # [1], [edit] markers
    lines = [re.sub(r"[ \t\r\f\v]+", " ", line).strip() for line in text.split("\n")]
    out, blank = [], False
    for line in lines:
        if line:
            out.append(line)
            blank = False
        elif not blank:
            out.append("")
            blank = True
    return "\n".join(out).strip()


def extract_readable_text(html: str) -> tuple[str, str]:
    """Return (title, text), preferring the page's main/article region when it has real content."""
    parser = _ReadableTextParser()
    parser.feed(html)
    parser.close()
    main, body = _clean("".join(parser.main)), _clean("".join(parser.body))
    text = main if len(main) >= MIN_TEXT_CHARS else body
    # Some sites (e.g. BYJU'S) ship no <title>; fall back to og:title, then the first heading.
    title = next((t for t in (_clean(parser.title), _clean(parser.og_title), _clean(parser.h1)) if t), "")
    return title, text


def normalize_urls(urls: List[str]) -> List[str]:
    cleaned = list(dict.fromkeys(u.strip() for u in urls if u and u.strip()))
    if len(cleaned) > MAX_LINKS:
        raise WebSourceError(f"Add at most {MAX_LINKS} links.")
    for url in cleaned:
        _check_url_shape(url)
    return cleaned


def _check_url_shape(url: str) -> None:
    parts = urlsplit(url)
    if parts.scheme not in {"http", "https"} or not parts.hostname:
        raise WebSourceError(f"'{url}' is not a web link. Use a full http(s):// address.")
    if parts.username or parts.password:
        raise WebSourceError("Links with a username or password are not allowed.")
    if parts.port not in (None, 80, 443):
        raise WebSourceError("Only standard web ports (80 and 443) are allowed.")


async def _check_public_host(host: str) -> None:
    try:
        infos = await asyncio.get_running_loop().getaddrinfo(host, None, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise WebSourceError(f"Couldn't find the website '{host}'.") from exc
    for info in infos:
        address = ipaddress.ip_address(info[4][0].split("%")[0])
        if not address.is_global or address.is_multicast:
            raise WebSourceError(f"'{host}' points to a private or internal address, which isn't allowed.")


async def fetch_web_source(url: str, client: Optional[httpx.AsyncClient] = None) -> WebSource:
    own_client = client is None
    client = client or httpx.AsyncClient(
        timeout=TIMEOUT_SECONDS, follow_redirects=False, headers={"User-Agent": USER_AGENT, "Accept": "text/html,text/plain"}
    )
    try:
        current = url
        for _ in range(MAX_REDIRECTS + 1):
            _check_url_shape(current)
            await _check_public_host(urlsplit(current).hostname)
            try:
                async with client.stream("GET", current) as response:
                    if response.is_redirect:
                        current = urljoin(current, response.headers.get("location", ""))
                        continue
                    if response.status_code >= 400:
                        raise WebSourceError(f"The page returned an error ({response.status_code}): {url}")
                    content_type = response.headers.get("content-type", "").lower()
                    if not any(kind in content_type for kind in ("text/html", "application/xhtml", "text/plain")):
                        raise WebSourceError(f"Only web pages can be used as links (got '{content_type or 'unknown'}'). Upload PDFs with the PDF option.")
                    body = bytearray()
                    async for chunk in response.aiter_bytes():
                        body.extend(chunk)
                        if len(body) > MAX_BYTES:
                            raise WebSourceError("The page is too large (over 3 MB).")
                    raw = _decode(bytes(body), response.headers.get("content-type", ""))
                    break
            except httpx.TimeoutException as exc:
                raise WebSourceError(f"The page took too long to load: {url}") from exc
            except httpx.HTTPError as exc:
                raise WebSourceError(f"Couldn't load the page: {url}") from exc
        else:
            raise WebSourceError(f"Too many redirects: {url}")
    finally:
        if own_client:
            await client.aclose()

    if "text/plain" in content_type:
        title, text = urlsplit(current).path.rsplit("/", 1)[-1] or current, _clean(raw)
    else:
        title, text = extract_readable_text(raw)
    if len(text) < MIN_TEXT_CHARS:
        raise WebSourceError(f"Couldn't find readable lesson text on {url}. Pages that need a login or JavaScript can't be read.")
    return WebSource(url=current, title=title or _title_from_url(current), text=text)


def _decode(body: bytes, content_type: str) -> str:
    """Header charset, then <meta charset>, then UTF-8, then Windows-1252 (common on Indian ed-tech sites)."""
    declared = re.search(r"charset=([\w-]+)", content_type, re.I) or re.search(rb"<meta[^>]+charset=[\"']?([\w-]+)", body[:4096], re.I)
    candidates = [declared.group(1).decode() if isinstance(declared.group(1), bytes) else declared.group(1)] if declared else []
    for encoding in [*candidates, "utf-8", "cp1252"]:
        try:
            return body.decode(encoding)
        except (LookupError, UnicodeDecodeError):
            continue
    return body.decode("utf-8", errors="replace")


def _title_from_url(url: str) -> str:
    """'https://byjus.com/biology/photosynthesis/' -> 'Photosynthesis'."""
    slug = urlsplit(url).path.rstrip("/").rsplit("/", 1)[-1]
    words = re.sub(r"\.\w+$", "", slug).replace("-", " ").replace("_", " ").strip()
    return words[:1].upper() + words[1:] if words else urlsplit(url).hostname or url


async def fetch_web_sources(urls: List[str]) -> List[WebSource]:
    urls = normalize_urls(urls)
    async with httpx.AsyncClient(
        timeout=TIMEOUT_SECONDS, follow_redirects=False, headers={"User-Agent": USER_AGENT, "Accept": "text/html,text/plain"}
    ) as client:
        return [await fetch_web_source(url, client) for url in urls]


def chunk_text(text: str, size: int = 1500) -> List[str]:
    """Split on paragraph boundaries into passages of about `size` characters for retrieval."""
    chunks, current = [], ""
    for paragraph in (p.strip() for p in text.split("\n\n")):
        if not paragraph:
            continue
        while len(paragraph) > size:
            if current:
                chunks.append(current)
                current = ""
            cut = paragraph.rfind(" ", 0, size)
            cut = cut if cut > size // 2 else size
            chunks.append(paragraph[:cut].strip())
            paragraph = paragraph[cut:].strip()
        if len(current) + len(paragraph) + 2 > size and current:
            chunks.append(current)
            current = paragraph
        else:
            current = f"{current}\n\n{paragraph}" if current else paragraph
    if current:
        chunks.append(current)
    return chunks
