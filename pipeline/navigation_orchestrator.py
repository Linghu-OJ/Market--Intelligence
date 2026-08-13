"""Losslessly organize current Amazon department collector output by Topic."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any


class NavigationOrchestrator:
    """Organize collector facts without filtering, merging, or deduplicating."""

    _FAILED_TOPIC_STATUSES = {
        "TOPIC_NAVIGATION_FAILED",
        "TOPIC_NAVIGATION_SKIPPED",
        "TOP_NAV_COLLECTION_FAILED",
    }
    _FAILED_MEGA_MENU_STATUSES = {
        "MEGA_MENU_NOT_FOUND",
        "MEGA_MENU_COLLECTION_FAILED",
    }

    def run(self, collector_result: dict[str, Any]) -> dict[str, Any]:
        """Package each collector Topic as one independent downstream entry."""
        self._validate_collector_result(collector_result)
        entries: list[dict[str, Any]] = []
        failed_entries: list[dict[str, Any]] = []

        for category in collector_result["categories"]:
            if not isinstance(category, dict):
                continue
            category_name = category.get("name")
            topics = category.get("topics")
            if isinstance(topics, list) and topics:
                for topic in topics:
                    if not isinstance(topic, dict):
                        continue
                    if self._topic_failure_reason(topic) is not None:
                        failed_entries.append(self._failed_entry(category_name, topic))
                    else:
                        entries.append(self._entry(category_name, topic))
            elif self._category_failure_reason(category) is not None:
                failed_entries.append(
                    {
                        "category": category_name,
                        "topic": None,
                        "status": category.get("status"),
                        "error": category.get("error"),
                    }
                )

        direct_top_nav_count = sum(len(entry["direct_top_nav"]) for entry in entries)
        level_4_node_count = sum(len(entry["level_4_nodes"]) for entry in entries)
        return {
            "source": "navigation_orchestrator",
            "timestamp": datetime.now(UTC).isoformat(),
            "data": {"entries": entries, "failed_entries": failed_entries},
            "summary": {
                "collector_topic_results": len(entries) + len(failed_entries),
                "retained_topic_entries": len(entries),
                "failed_topic_entries": len(failed_entries),
                "direct_top_nav_node_count": direct_top_nav_count,
                "level_4_node_count": level_4_node_count,
                "total_preserved_node_count": direct_top_nav_count + level_4_node_count,
            },
        }

    @staticmethod
    def _validate_collector_result(collector_result: Any) -> None:
        """Validate only the frozen collector's top-level result envelope."""
        if not isinstance(collector_result, dict):
            raise ValueError("collector_result must be a dictionary.")
        if not isinstance(collector_result.get("categories"), list):
            raise ValueError("collector_result requires categories as a list.")

    def _entry(self, category_name: Any, topic: dict[str, Any]) -> dict[str, Any]:
        """Preserve one non-failed Topic and its ordered Level-3/Level-4 nodes."""
        top_nav = topic.get("top_nav")
        direct_top_nav = [
            node
            for node in top_nav
            if isinstance(node, dict) and node.get("level") == 3
        ] if isinstance(top_nav, list) else []
        level_4_nodes = [
            node
            for top_nav_node in direct_top_nav
            for node in top_nav_node.get("mega_menu", [])
            if isinstance(node, dict) and node.get("level") == 4
        ]
        error = topic.get("error")
        return {
            "category": category_name,
            "topic": topic.get("name"),
            "topic_url": topic.get("final_topic_url") or topic.get("topic_page_url"),
            "collector_status": topic.get("navigation_status"),
            "top_nav_status": topic.get("top_nav_status"),
            "direct_top_nav": direct_top_nav,
            "level_4_nodes": level_4_nodes,
            "errors": [error] if error else [],
        }

    def _topic_failure_reason(self, topic: dict[str, Any]) -> str | None:
        """Keep technical collector failures separate from valid source states."""
        navigation_status = topic.get("navigation_status")
        top_nav_status = topic.get("top_nav_status")
        if navigation_status in self._FAILED_TOPIC_STATUSES:
            return str(topic.get("error") or navigation_status)
        if top_nav_status in self._FAILED_TOPIC_STATUSES:
            return str(topic.get("error") or top_nav_status)
        for node in topic.get("top_nav", []):
            if isinstance(node, dict) and node.get("mega_menu_status") in self._FAILED_MEGA_MENU_STATUSES:
                return str(node.get("mega_menu_error") or node["mega_menu_status"])
        return None

    @staticmethod
    def _category_failure_reason(category: dict[str, Any]) -> str | None:
        status = category.get("status")
        if status in {"FAILED", "TOPIC_COLLECTION_FAILED"}:
            return str(category.get("error") or status)
        return None

    def _failed_entry(self, category_name: Any, topic: dict[str, Any]) -> dict[str, Any]:
        """Preserve a genuine collector failure without repairing its facts."""
        return {
            "category": category_name,
            "topic": topic.get("name"),
            "status": topic.get("navigation_status") or topic.get("top_nav_status"),
            "error": self._topic_failure_reason(topic),
        }
