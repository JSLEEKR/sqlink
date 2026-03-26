"""Query timeline — track query performance over time."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class TimelineEntry:
    """A snapshot of query analysis at a point in time."""

    timestamp: str
    query_hash: str
    score: int
    finding_count: int
    findings_by_severity: dict[str, int] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "query_hash": self.query_hash,
            "score": self.score,
            "finding_count": self.finding_count,
            "findings_by_severity": self.findings_by_severity,
            "metadata": self.metadata,
        }


@dataclass
class Timeline:
    """Track query analysis results over time."""

    entries: list[TimelineEntry] = field(default_factory=list)

    def add(self, entry: TimelineEntry) -> None:
        self.entries.append(entry)

    def get_by_hash(self, query_hash: str) -> list[TimelineEntry]:
        return [e for e in self.entries if e.query_hash == query_hash]

    def latest(self, n: int = 10) -> list[TimelineEntry]:
        return self.entries[-n:]

    @property
    def score_trend(self) -> list[int]:
        return [e.score for e in self.entries]

    def score_improved(self) -> bool:
        """Check if the latest score improved over the previous."""
        if len(self.entries) < 2:
            return False
        return self.entries[-1].score > self.entries[-2].score

    def score_degraded(self) -> bool:
        """Check if the latest score degraded from the previous."""
        if len(self.entries) < 2:
            return False
        return self.entries[-1].score < self.entries[-2].score

    def average_score(self) -> float:
        if not self.entries:
            return 0.0
        return sum(e.score for e in self.entries) / len(self.entries)

    def save(self, path: str | Path) -> None:
        data = {"entries": [e.to_dict() for e in self.entries]}
        Path(path).write_text(json.dumps(data, indent=2))

    @classmethod
    def load(cls, path: str | Path) -> Timeline:
        p = Path(path)
        if not p.exists():
            return cls()
        data = json.loads(p.read_text())
        timeline = cls()
        for entry_data in data.get("entries", []):
            timeline.add(TimelineEntry(
                timestamp=entry_data["timestamp"],
                query_hash=entry_data["query_hash"],
                score=entry_data["score"],
                finding_count=entry_data["finding_count"],
                findings_by_severity=entry_data.get("findings_by_severity", {}),
                metadata=entry_data.get("metadata", {}),
            ))
        return timeline

    def to_dict(self) -> dict[str, Any]:
        return {
            "entry_count": len(self.entries),
            "average_score": round(self.average_score(), 1),
            "score_trend": self.score_trend[-20:],
            "entries": [e.to_dict() for e in self.entries],
        }
