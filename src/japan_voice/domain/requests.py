"""Validated user search input shared by collectors."""

from __future__ import annotations

from datetime import date
import re
from typing import List
import unicodedata

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .enums import Source


_WHITESPACE = re.compile(r"\s+")


def _normalize_keyword(value: str) -> str:
    return _WHITESPACE.sub(" ", unicodedata.normalize("NFKC", value)).strip()


class SearchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    keyword: str = Field(min_length=1, max_length=200)
    start_date: date
    end_date: date
    selected_sources: List[Source] = Field(min_length=1)
    max_results: int = Field(default=100, ge=1, le=1000)

    @field_validator("keyword", mode="before")
    @classmethod
    def normalize_keyword(cls, value: object) -> str:
        if not isinstance(value, str):
            raise TypeError("keyword must be a string")
        normalized = _normalize_keyword(value)
        if not normalized:
            raise ValueError("keyword must not be blank")
        return normalized

    @field_validator("selected_sources")
    @classmethod
    def unique_sources(cls, sources: List[Source]) -> List[Source]:
        # Preserve UI order while preventing duplicate collector execution.
        return list(dict.fromkeys(sources))

    @model_validator(mode="after")
    def valid_date_range(self) -> "SearchRequest":
        if self.end_date < self.start_date:
            raise ValueError("end_date must not be before start_date")
        return self
