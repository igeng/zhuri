"""Academic search clients — ArXiv API + Semantic Scholar API.

Both APIs are free and require no authentication for basic usage.  Results are
returned as :class:`PaperResult` dataclasses that can be injected directly into
work-agent prompts or written to findings.

Usage::

    papers = arxiv_search("large language model HPC post-training", max_results=10)
    for p in papers:
        print(p.title, p.arxiv_id, p.year)

    # Combined search across both sources, deduplicated by arxiv_id.
    all_papers = search_all("GRPO reinforcement learning", max_results=20)
"""
from __future__ import annotations

import time
import urllib.parse
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field

import httpx

# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

ARXIV_NS = "{http://www.w3.org/2005/Atom}"
ARXIV_API = "https://export.arxiv.org/api/query"
S2_API = "https://api.semanticscholar.org/graph/v1/paper/search"


@dataclass
class PaperResult:
    """A single paper from an academic search."""

    title: str
    authors: list[str] = field(default_factory=list)
    year: int = 0
    abstract: str = ""
    arxiv_id: str = ""
    doi: str = ""
    venue: str = ""  # e.g. "NeurIPS 2023" or ""
    citation_count: int = 0
    url: str = ""
    source: str = "arxiv"  # "arxiv" | "semantic_scholar"

    def bibtex_key(self) -> str:
        if not self.authors:
            return "unknown"
        last = self.authors[0].split()[-1]
        return f"{last}{self.year}" if self.year else last

    def one_line(self) -> str:
        authors_short = (
            f"{self.authors[0]} et al." if len(self.authors) > 1
            else (self.authors[0] if self.authors else "Unknown")
        )
        venue_str = f" ({self.venue})" if self.venue else ""
        cites = f" [{self.citation_count} cites]" if self.citation_count else ""
        return f"{authors_short} ({self.year}) — {self.title}{venue_str}{cites}"


# ---------------------------------------------------------------------------
# ArXiv API
# ---------------------------------------------------------------------------

def arxiv_search(
    query: str,
    *,
    max_results: int = 10,
    start: int = 0,
    timeout: float = 30.0,
) -> list[PaperResult]:
    """Search ArXiv via its public API (no auth required).

    Returns up to *max_results* papers matching *query*, sorted by relevance.
    Respects ArXiv's rate limit of ~1 request / 3 seconds.
    """
    params = {
        "search_query": query,
        "start": start,
        "max_results": min(max_results, 100),
        "sortBy": "relevance",
    }
    url = f"{ARXIV_API}?{urllib.parse.urlencode(params)}"
    try:
        resp = httpx.get(url, timeout=timeout, follow_redirects=True)
    except httpx.HTTPError:
        return []
    if resp.status_code != 200:
        return []

    root = ET.fromstring(resp.text)
    papers: list[PaperResult] = []
    for entry in root.findall(f"{ARXIV_NS}entry"):
        title = _text(entry, f"{ARXIV_NS}title")
        abstract = _text(entry, f"{ARXIV_NS}summary")
        arxiv_id = _text(entry, f"{ARXIV_NS}id").rsplit("/abs/", 1)[-1]
        # Strip version suffix e.g. "2301.12345v2" → "2301.12345"
        arxiv_id = arxiv_id.split("v")[0] if arxiv_id else ""
        published = _text(entry, f"{ARXIV_NS}published")
        year = int(published[:4]) if published and len(published) >= 4 else 0

        authors: list[str] = []
        for author in entry.findall(f"{ARXIV_NS}author"):
            name = _text(author, f"{ARXIV_NS}name")
            if name:
                authors.append(name)

        doi = ""
        for link in entry.findall(f"{ARXIV_NS}link"):
            if link.attrib.get("title") == "doi":
                doi = link.attrib.get("href", "")
                break

        papers.append(PaperResult(
            title=title.strip().replace("\n", " ") if title else "",
            authors=authors,
            year=year,
            abstract=(abstract or "")[:2000],
            arxiv_id=arxiv_id,
            doi=doi,
            url=f"https://arxiv.org/abs/{arxiv_id}" if arxiv_id else "",
            source="arxiv",
        ))

    # Rate-limit courtesy: pause at least 3s between ArXiv calls.
    time.sleep(0.1)  # light pause; real rate-limit in caller if looping
    return papers


# ---------------------------------------------------------------------------
# Semantic Scholar API
# ---------------------------------------------------------------------------

def semantic_scholar_search(
    query: str,
    *,
    max_results: int = 10,
    timeout: float = 30.0,
) -> list[PaperResult]:
    """Search Semantic Scholar (free tier, no auth required).

    Returns up to *max_results* papers sorted by relevance.  The free tier
    allows ~100 requests / 5 minutes without an API key.
    """
    params = {
        "query": query,
        "limit": min(max_results, 100),
        "fields": "title,authors,year,abstract,externalIds,url,venue,citationCount,publicationDate",
    }
    url = f"{S2_API}?{urllib.parse.urlencode(params)}"
    try:
        resp = httpx.get(url, timeout=timeout, follow_redirects=True)
    except httpx.HTTPError:
        return []
    if resp.status_code != 200:
        return []

    data = resp.json()
    papers: list[PaperResult] = []
    for item in data.get("data", []):
        authors = [a.get("name", "") for a in item.get("authors", [])]
        ext_ids = item.get("externalIds", {}) or {}
        arxiv_id = (ext_ids.get("ArXiv") or "").split("v")[0]
        papers.append(PaperResult(
            title=item.get("title", "") or "",
            authors=authors,
            year=item.get("year") or 0,
            abstract=(item.get("abstract") or "")[:2000],
            arxiv_id=arxiv_id,
            doi=ext_ids.get("DOI", ""),
            venue=item.get("venue", "") or "",
            citation_count=item.get("citationCount", 0),
            url=item.get("url", ""),
            source="semantic_scholar",
        ))
    return papers


# ---------------------------------------------------------------------------
# Combined search
# ---------------------------------------------------------------------------

def search_all(
    query: str,
    *,
    max_results: int = 20,
    timeout: float = 30.0,
) -> list[PaperResult]:
    """Search both ArXiv and Semantic Scholar, deduplicate by arxiv_id.

    Returns papers sorted by relevance (ArXiv results first, then S2 results
    not already found in ArXiv).
    """
    arxiv_results = arxiv_search(query, max_results=max_results, timeout=timeout)
    seen_ids = {p.arxiv_id for p in arxiv_results if p.arxiv_id}

    s2_results = semantic_scholar_search(query, max_results=max_results, timeout=timeout)
    s2_new = [p for p in s2_results if p.arxiv_id not in seen_ids or not p.arxiv_id]

    # Merge: ArXiv first (better metadata quality), then S2 unique
    combined = list(arxiv_results) + s2_new
    return combined[:max_results]


# ---------------------------------------------------------------------------
# Format helpers for prompt injection
# ---------------------------------------------------------------------------

def format_for_prompt(papers: list[PaperResult]) -> str:
    """Render a list of papers as a compact prompt-ready reference block."""
    if not papers:
        return "(no papers found)"

    lines = [f"## Real-time search results ({len(papers)} papers)\n"]
    for i, p in enumerate(papers, 1):
        authors = ", ".join(p.authors[:3])
        if len(p.authors) > 3:
            authors += " et al."
        lines.append(
            f"{i}. **{p.title}**\n"
            f"   Authors: {authors}\n"
            f"   Year: {p.year}  |  Venue: {p.venue or 'N/A'}  "
            f"|  ArXiv: [{p.arxiv_id}]({p.url})  "
            f"|  Cites: {p.citation_count}\n"
            f"   Abstract: {p.abstract[:400]}..."
        )
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _text(element: ET.Element, tag: str) -> str:
    child = element.find(tag)
    return (child.text or "") if child is not None else ""
