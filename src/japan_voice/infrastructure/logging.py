"""Allowlist-based structured application logging."""

from __future__ import annotations

from datetime import datetime, timezone
import json
import logging
from typing import Any, Dict, Optional

from japan_voice.domain.enums import Source


class StructuredLogger:
    """Emit only approved operational fields; never arbitrary payloads/headers."""

    def __init__(self, logger: Optional[logging.Logger] = None) -> None:
        self._logger = logger or logging.getLogger("japan_voice")

    def event(
        self,
        *,
        run_id: str,
        source: Source,
        event: str,
        duration_ms: Optional[int] = None,
        records_collected: Optional[int] = None,
        error_type: Optional[str] = None,
        **safe_metrics: Any,
    ) -> Dict[str, Any]:
        entry: Dict[str, Any] = {
            "run_id": run_id,
            "source": source.value,
            "event": event,
            "duration_ms": duration_ms,
            "records_collected": records_collected,
            "error_type": error_type,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        # Only numeric/boolean operational counters explicitly prefixed metric_.
        for key, value in safe_metrics.items():
            if key.startswith("metric_") and isinstance(value, (int, float, bool)):
                entry[key] = value
        self._logger.info(json.dumps(entry, ensure_ascii=False, separators=(",", ":")))
        return entry

