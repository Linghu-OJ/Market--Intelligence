"""Conservative exact deduplication of current topic-based navigation entries."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any


class ExactEntryDeduplicator:
    """Retain first category-scoped exact Level-3 navigation signatures."""

    def deduplicate(self, orchestrator_output: dict[str, Any]) -> dict[str, Any]:
        """Remove only later exact duplicates; preserve retained entry objects unchanged."""
        entries, failed_entries = self._input_data(orchestrator_output)
        retained_entries: list[dict[str, Any]] = []
        duplicate_entries: list[dict[str, Any]] = []
        first_entries: dict[tuple[Any, ...], dict[str, Any]] = {}

        for entry in entries:
            signature = self._entry_signature(entry)
            # Empty Level-3 navigation is not evidence that two Topics are equal.
            if signature is None:
                retained_entries.append(entry)
                continue
            original = first_entries.get(signature)
            if original is None:
                first_entries[signature] = entry
                retained_entries.append(entry)
                continue
            duplicate_entries.append(self._duplicate_audit(entry, original))

        return {
            "source": "navigation_entry_deduplicator",
            "timestamp": datetime.now(UTC).isoformat(),
            "data": {
                "entries": retained_entries,
                "duplicate_entries": duplicate_entries,
                "failed_entries": failed_entries,
            },
            "summary": self._summary(entries, retained_entries, duplicate_entries, failed_entries),
        }

    @staticmethod
    def _input_data(
        orchestrator_output: Any,
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        """Validate the current Orchestrator entry contract without transforming it."""
        if not isinstance(orchestrator_output, dict):
            raise ValueError("orchestrator_output must be a dictionary.")
        data = orchestrator_output.get("data")
        if not isinstance(data, dict):
            raise ValueError("orchestrator_output requires a data dictionary.")
        entries = data.get("entries")
        failed_entries = data.get("failed_entries", [])
        if not isinstance(entries, list):
            raise ValueError("orchestrator_output data.entries must be a list.")
        if not isinstance(failed_entries, list):
            raise ValueError("orchestrator_output data.failed_entries must be a list.")
        for entry in entries:
            if not isinstance(entry, dict):
                raise ValueError("Each navigation entry must be a dictionary.")
            for field in ("category", "topic"):
                if not isinstance(entry.get(field), str) or not entry[field].strip():
                    raise ValueError(f"Each navigation entry requires a non-empty {field}.")
            for field in ("direct_top_nav", "level_4_nodes", "errors"):
                if not isinstance(entry.get(field), list):
                    raise ValueError(f"Each navigation entry requires {field} as a list.")
            for node in entry["direct_top_nav"] + entry["level_4_nodes"]:
                if not isinstance(node, dict):
                    raise ValueError("Navigation nodes must be dictionaries.")
        return entries, failed_entries

    @staticmethod
    def _entry_signature(entry: dict[str, Any]) -> tuple[Any, ...] | None:
        """Return category plus ordered raw Level-3 name/URL pairs, or None if empty."""
        direct_top_nav = entry["direct_top_nav"]
        if not direct_top_nav:
            return None
        return (
            entry["category"],
            tuple((node.get("name"), node.get("url")) for node in direct_top_nav),
        )

    @staticmethod
    def _duplicate_audit(
        entry: dict[str, Any], original: dict[str, Any]
    ) -> dict[str, Any]:
        """Record the removed Topic and its retained first-occurrence counterpart."""
        return {
            "category": entry.get("category"),
            "topic": entry.get("topic"),
            "topic_url": entry.get("topic_url"),
            "duplicate_of_topic": original.get("topic"),
            "duplicate_of_topic_url": original.get("topic_url"),
            "direct_top_nav_count": len(entry["direct_top_nav"]),
            "level_4_node_count": len(entry["level_4_nodes"]),
            "removed_entry": entry,
        }

    @staticmethod
    def _summary(
        entries: list[dict[str, Any]],
        retained_entries: list[dict[str, Any]],
        duplicate_entries: list[dict[str, Any]],
        failed_entries: list[dict[str, Any]],
    ) -> dict[str, int]:
        def count(items: list[dict[str, Any]], field: str) -> int:
            return sum(len(item[field]) for item in items)

        retained_direct = count(retained_entries, "direct_top_nav")
        retained_level_4 = count(retained_entries, "level_4_nodes")
        input_direct = count(entries, "direct_top_nav")
        input_level_4 = count(entries, "level_4_nodes")
        return {
            "input_entries": len(entries),
            "retained_entries": len(retained_entries),
            "duplicate_entries": len(duplicate_entries),
            "failed_entries": len(failed_entries),
            "input_direct_top_nav_nodes": input_direct,
            "retained_direct_top_nav_nodes": retained_direct,
            "removed_duplicate_entry_direct_top_nav_nodes": input_direct - retained_direct,
            "input_level_4_nodes": input_level_4,
            "retained_level_4_nodes": retained_level_4,
            "removed_duplicate_entry_level_4_nodes": input_level_4 - retained_level_4,
        }
