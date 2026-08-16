"""Common collector contracts. Concrete external collectors are added later."""

from .base import Collector, CollectorResult
from .minkara import MinkaraCollector
from .youtube import YouTubeCollector

__all__ = ["Collector", "CollectorResult", "YouTubeCollector"]
from .yahoo_japan import YahooJapanCollector

__all__ = ["YahooJapanCollector"]
