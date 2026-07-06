"""zhuri external tools — search, file I/O, shell exec.

These are stateless utility functions available to work agents and sub-agents.
None of them require an agent framework; they are called directly.
"""
from __future__ import annotations

from .search import PaperResult, arxiv_search, semantic_scholar_search, search_all

__all__ = [
    "PaperResult",
    "arxiv_search",
    "semantic_scholar_search",
    "search_all",
]
