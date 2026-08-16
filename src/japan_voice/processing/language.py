"""Conservative Japanese-language classification optimized for short VOC."""

from __future__ import annotations

import re

from japan_voice.domain.enums import Language
from .normalize import normalize_text


_KANA = re.compile(r"[\u3040-\u30ff]")
_CJK = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff]")
_LATIN_WORD = re.compile(r"[A-Za-z]{2,}")
_SHORT_JAPANESE = {
    "欲しい", "高い", "安い", "買いたい", "かっこいい", "かわいい",
    "デザイン好き", "気になる", "乗りたい", "大きい", "小さい",
}


def detect_japanese(value: str) -> Language:
    text = normalize_text(value)
    if not text:
        return Language.UNKNOWN
    if text in _SHORT_JAPANESE or _KANA.search(text):
        return Language.JA
    cjk_count = len(_CJK.findall(text))
    latin_count = sum(len(word) for word in _LATIN_WORD.findall(text))
    if cjk_count >= 2 and latin_count == 0:
        return Language.JA
    if latin_count >= 2 and cjk_count == 0:
        return Language.NON_JA
    return Language.UNKNOWN

