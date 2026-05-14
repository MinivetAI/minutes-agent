import json
import os
import re
from typing import Optional


class _KeywordContext:
    def __init__(self, path: str):
        self.path = path
        self._mtime = None
        self.entries = {}
        self.keyword_index = {}
        self._reload_if_needed(force=True)

    def _reload_if_needed(self, force: bool = False):
        try:
            mtime = os.path.getmtime(self.path)
        except FileNotFoundError:
            return

        if not force and self._mtime == mtime:
            return

        with open(self.path) as handle:
            self.entries = json.load(handle)

        self.keyword_index = {}
        for key, entry in self.entries.items():
            for keyword in entry.get("keywords", [key]):
                self.keyword_index[keyword.lower()] = entry

        self._mtime = mtime

    @staticmethod
    def _matches_keyword(query_lower: str, keyword: str) -> bool:
        parts = [part.strip().lower() for part in keyword.split("^") if part.strip()]
        if not parts:
            return False

        for part in parts:
            pattern = r"\b" + re.escape(part) + r"\b"
            if not re.search(pattern, query_lower):
                return False
        return True

    def retrieve(self, query: str) -> Optional[str]:
        self._reload_if_needed()
        query_lower = query.lower()
        matched = []
        seen = set()
        for keyword, entry in self.keyword_index.items():
            if not self._matches_keyword(query_lower, keyword):
                continue

            payload = entry.get("context", "")
            if payload and payload not in seen:
                matched.append(f"- {keyword.upper()}: {payload}")
                seen.add(payload)
        return "\n".join(matched) if matched else None


class IndianContext(_KeywordContext):
    pass


class BrandContext(_KeywordContext):
    pass
