"""Generate bounded, source-aware Japan-market search variants."""

from __future__ import annotations

from typing import Dict, List, Sequence

from japan_voice.domain.enums import Source
from japan_voice.processing.normalize import normalize_for_match, normalize_text


_SOURCE_SUFFIXES: Dict[Source, Sequence[str]] = {
    Source.YOUTUBE: ("日本", "日本発売", "日本仕様", "日本 試乗"),
    Source.NEWS: ("日本", "日本市場", "日本発売", "日本販売", "日本価格"),
    Source.YAHOO: ("日本", "日本市場", "日本発売", "日本販売", "日本価格"),
    Source.YAHOO_JAPAN: ("日本", "日本市場", "日本発売", "日本販売", "日本価格"),
    Source.X: ("日本", "日本発売", "日本価格"),
    Source.MINKARA: ("日本", "車中泊", "試乗", "商用車"),
    Source.WEB: ("日本", "日本市場", "日本発売", "日本価格"),
}


def _candidate_queries(keyword: str, source: Source) -> List[str]:
    folded = normalize_for_match(keyword)
    suffixes = _SOURCE_SUFFIXES[source]

    if folded in {"kia", "キア"}:
        localized = "キア"
        candidates = [f"{keyword} {suffix}" for suffix in suffixes]
        candidates.extend([localized, f"{localized} 日本", f"{localized} 日本市場"])
        return candidates

    if folded == "pv5":
        preferred = [
            "PV5 日本", "PV5 日本市場", "PV5 日本発売", "PV5 日本販売",
            "PV5 キア", "キア PV5", "KIA PV5 日本",
        ]
        return preferred if source not in {Source.X, Source.MINKARA} else [
            "PV5 日本", "キア PV5", "PV5 日本発売", "PV5 日本価格", "PV5 車中泊",
        ]

    if folded in {"ev3", "ev4", "ev5", "ev6", "ev9"}:
        model = keyword.upper()
        return [
            f"{model} 日本", f"KIA {model} 日本", f"キア {model}",
            f"{model} 日本発売", f"{model} 日本価格",
        ]

    return [f"{keyword} {suffix}" for suffix in suffixes]


def expand_japan_queries(keyword: str, source: Source, *, max_queries: int = 5) -> List[str]:
    """Return normalized, ordered and deduplicated Japan-focused queries."""
    if max_queries <= 0:
        raise ValueError("max_queries must be positive")
    normalized_keyword = normalize_text(keyword)
    if not normalized_keyword:
        raise ValueError("keyword must not be blank")

    output: List[str] = []
    seen = set()
    for candidate in _candidate_queries(normalized_keyword, source):
        query = normalize_text(candidate)
        key = normalize_for_match(query)
        if key not in seen:
            seen.add(key)
            output.append(query)
        if len(output) == max_queries:
            break
    return output
