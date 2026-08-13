"""Frozen collector snapshot preservation contract for NavigationOrchestrator.

Regenerate the snapshot only by intentionally running the real collector
integration test after a collector contract or schema change.
"""

from __future__ import annotations

from datetime import UTC, datetime
from html import escape
import json
from pathlib import Path
from typing import Any

from pipeline.navigation_orchestrator import NavigationOrchestrator


_SNAPSHOT_PATH = (
    Path(__file__).resolve().parent
    / "fixtures"
    / "amazon_department_collector_snapshot.json"
)
_SNAPSHOT_VERSION = 1


def main() -> None:
    """Organize the frozen collector contract, report, then assert."""
    collector_result: dict[str, Any] | None = None
    output: dict[str, Any] | None = None
    error: str | None = None
    snapshot_version: int | None = None
    try:
        collector_result, snapshot_version = _load_collector_snapshot()
        output = NavigationOrchestrator().run(collector_result)
    except Exception as exception:
        error = f"{type(exception).__name__}: {exception}"

    evaluation = _evaluate(collector_result, output, error)
    report_path = Path("reports") / "navigation_orchestrator_integration.html"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        _report(evaluation, error, snapshot_version),
        encoding="utf-8",
    )
    _print_summary(evaluation, error, report_path, snapshot_version)
    assert all(evaluation["checks"].values()), "; ".join(
        name for name, passed in evaluation["checks"].items() if not passed
    )


def _load_collector_snapshot() -> tuple[dict[str, Any], int]:
    """Load the approved immutable collector fixture; never run Amazon as fallback."""
    if not _SNAPSHOT_PATH.is_file():
        raise FileNotFoundError(
            "Collector snapshot is missing. Run the collector integration test to "
            "regenerate tests/fixtures/amazon_department_collector_snapshot.json."
        )
    try:
        with _SNAPSHOT_PATH.open(encoding="utf-8") as stream:
            snapshot = json.load(stream)
    except json.JSONDecodeError as error:
        raise ValueError(f"Collector snapshot contains invalid JSON: {error}") from error
    if not isinstance(snapshot, dict):
        raise ValueError("Collector snapshot must be a JSON object.")
    version = snapshot.get("snapshot_version")
    if version != _SNAPSHOT_VERSION:
        raise ValueError(f"Unsupported collector snapshot version: {version}")
    if snapshot.get("source") != "amazon_department_collector":
        raise ValueError("Collector snapshot has an unsupported source.")
    collector_output = snapshot.get("collector_output")
    if not isinstance(collector_output, dict):
        raise ValueError("Collector snapshot requires a collector_output object.")
    if not isinstance(collector_output.get("categories"), list):
        raise ValueError("Collector snapshot collector_output requires categories as a list.")
    return collector_output, version


def _topics(collector_result: Any) -> list[tuple[dict[str, Any], dict[str, Any]]]:
    if not isinstance(collector_result, dict):
        return []
    records = []
    for category in collector_result.get("categories", []):
        if not isinstance(category, dict):
            continue
        for topic in category.get("topics", []):
            if isinstance(topic, dict):
                records.append((category, topic))
    return records


def _is_failed_topic(topic: dict[str, Any]) -> bool:
    return topic.get("navigation_status") in {
        "TOPIC_NAVIGATION_FAILED",
        "TOPIC_NAVIGATION_SKIPPED",
    } or topic.get("top_nav_status") == "TOP_NAV_COLLECTION_FAILED" or any(
        isinstance(node, dict)
        and node.get("mega_menu_status")
        in {"MEGA_MENU_NOT_FOUND", "MEGA_MENU_COLLECTION_FAILED"}
        for node in topic.get("top_nav", [])
    )


def _collector_nodes(topic: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    direct_top_nav = [
        node for node in topic.get("top_nav", [])
        if isinstance(node, dict) and node.get("level") == 3
    ]
    level_4_nodes = [
        node for top_nav in direct_top_nav for node in top_nav.get("mega_menu", [])
        if isinstance(node, dict) and node.get("level") == 4
    ]
    return direct_top_nav, level_4_nodes


def _evaluate(
    collector_result: dict[str, Any] | None,
    output: dict[str, Any] | None,
    error: str | None,
) -> dict[str, Any]:
    topic_records = _topics(collector_result)
    data = output.get("data", {}) if isinstance(output, dict) else {}
    entries = data.get("entries", []) if isinstance(data.get("entries"), list) else []
    failed_entries = data.get("failed_entries", []) if isinstance(data.get("failed_entries"), list) else []
    successful = [(category, topic) for category, topic in topic_records if not _is_failed_topic(topic)]
    failed = [(category, topic) for category, topic in topic_records if _is_failed_topic(topic)]
    expected_direct = [node for _, topic in successful for node in _collector_nodes(topic)[0]]
    expected_level_4 = [node for _, topic in successful for node in _collector_nodes(topic)[1]]
    actual_direct = [node for entry in entries for node in entry.get("direct_top_nav", [])]
    actual_level_4 = [node for entry in entries for node in entry.get("level_4_nodes", [])]
    summary = output.get("summary", {}) if isinstance(output, dict) else {}
    checks = {
        "all_collector_results_accounted_for": len(entries) + len(failed_entries) == len(topic_records),
        "all_successful_topics_preserved": len(entries) == len(successful),
        "all_collector_failures_recorded": len(failed_entries) == len(failed),
        "all_level_3_nodes_preserved": actual_direct == expected_direct,
        "all_level_4_nodes_preserved": actual_level_4 == expected_level_4,
        "no_topic_entries_merged": [
            (entry.get("category"), entry.get("topic")) for entry in entries
        ] == [(category.get("name"), topic.get("name")) for category, topic in successful],
        "no_orchestrator_deduplication": len(actual_direct) == len(expected_direct)
        and len(actual_level_4) == len(expected_level_4),
        "summary_counts_consistent": summary == {
            "collector_topic_results": len(topic_records),
            "retained_topic_entries": len(entries),
            "failed_topic_entries": len(failed_entries),
            "direct_top_nav_node_count": len(actual_direct),
            "level_4_node_count": len(actual_level_4),
            "total_preserved_node_count": len(actual_direct) + len(actual_level_4),
        },
        "no_orchestrator_error": error is None,
    }
    rows = []
    entry_index = 0
    for category, topic in topic_records:
        collector_direct, collector_level_4 = _collector_nodes(topic)
        entry = None
        if not _is_failed_topic(topic) and entry_index < len(entries):
            entry = entries[entry_index]
            entry_index += 1
        rows.append({
            "category": category.get("name"), "topic": topic.get("name"),
            "collector_status": topic.get("navigation_status"),
            "topic_url": topic.get("final_topic_url") or topic.get("topic_page_url"),
            "collector_direct_count": len(collector_direct),
            "orchestrator_direct_count": len(entry.get("direct_top_nav", [])) if entry else 0,
            "collector_level_4_count": len(collector_level_4),
            "orchestrator_level_4_count": len(entry.get("level_4_nodes", [])) if entry else 0,
            "error_count": len(entry.get("errors", [])) if entry else 0,
        })
    return {"topics": topic_records, "entries": entries, "failed_entries": failed_entries, "rows": rows, "checks": checks}


def _report(
    evaluation: dict[str, Any],
    error: str | None,
    snapshot_version: int | None,
) -> str:
    checks = evaluation["checks"]
    passed = all(checks.values())
    check_rows = "".join(f"<tr><th>{escape(name)}</th><td>{'PASS' if value else 'FAIL'}</td></tr>" for name, value in checks.items())
    topic_rows = "".join(
        f"<tr><td>{_value(row['category'])}</td><td>{_value(row['topic'])}</td><td>{_value(row['collector_status'])}</td><td>{_value(row['topic_url'])}</td><td>{row['collector_direct_count']}</td><td>{row['orchestrator_direct_count']}</td><td>{row['collector_level_4_count']}</td><td>{row['orchestrator_level_4_count']}</td><td>{row['error_count']}</td></tr>"
        for row in evaluation["rows"]
    )
    summary = {"collector_topic_results": len(evaluation["topics"]), "orchestrator_entries": len(evaluation["entries"]), "failed_entries": len(evaluation["failed_entries"]), "direct_top_nav_nodes_preserved": sum(len(entry.get("direct_top_nav", [])) for entry in evaluation["entries"]), "level_4_nodes_preserved": sum(len(entry.get("level_4_nodes", [])) for entry in evaluation["entries"])}
    style = "body{font:15px system-ui;margin:32px;color:#172033}table{border-collapse:collapse;width:100%;margin:12px 0 28px}th,td{border:1px solid #cbd5e1;padding:8px;text-align:left;vertical-align:top}th{background:#17345d;color:#fff}.wrap{overflow:auto}pre{white-space:pre-wrap;background:#111827;color:#e5e7eb;padding:16px}.result{padding:16px;font-size:24px;font-weight:700;background:" + ("#dcfce7" if passed else "#fee2e2") + "}"
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><title>Navigation Orchestrator Integration</title><style>{style}</style></head><body><h1>Navigation Orchestrator Integration</h1><div class="result">{'PASS' if passed else 'FAIL'}</div><p>Execution timestamp: {escape(datetime.now(UTC).isoformat())}</p><p><strong>Input source:</strong> Frozen collector snapshot<br><strong>Snapshot path:</strong> {escape(_snapshot_display_path())}<br><strong>Snapshot version:</strong> {_value(snapshot_version)}</p><h2>Summary</h2><pre>{escape(json.dumps(summary, indent=2))}</pre><h2>Contract checks</h2><table>{check_rows}</table><h2>Topic preservation</h2><div class="wrap"><table><thead><tr><th>Category</th><th>Topic</th><th>Collector Status</th><th>Topic URL</th><th>Collector Level-3</th><th>Orchestrator Direct Top Nav</th><th>Collector Level-4</th><th>Orchestrator Level-4</th><th>Error Count</th></tr></thead><tbody>{topic_rows}</tbody></table></div><h2>Orchestrator error</h2><pre>{escape(str(error)) if error else 'None'}</pre><h2>Failed entries</h2><pre>{escape(json.dumps(evaluation['failed_entries'], ensure_ascii=False, indent=2))}</pre></body></html>"""


def _print_summary(
    evaluation: dict[str, Any],
    error: str | None,
    report_path: Path,
    snapshot_version: int | None,
) -> None:
    entries = evaluation["entries"]
    direct = sum(len(entry.get("direct_top_nav", [])) for entry in entries)
    level_4 = sum(len(entry.get("level_4_nodes", [])) for entry in entries)
    failures = [name for name, passed in evaluation["checks"].items() if not passed]
    print("=" * 60); print("NAVIGATION ORCHESTRATOR INTEGRATION TEST"); print("=" * 60)
    print("\nInput source: FROZEN COLLECTOR SNAPSHOT")
    print(f"Snapshot path: {_snapshot_display_path()}")
    print(f"Snapshot version: {snapshot_version if snapshot_version is not None else 'unavailable'}")
    print(f"\nOverall: {'PASS' if not failures else 'FAIL'}\n\nCollector snapshot topics: {len(evaluation['topics'])}\nOrchestrator entries: {len(entries)}\nFailed entries: {len(evaluation['failed_entries'])}\n\nDirect top-nav nodes preserved: {direct}\nLevel-4 nodes preserved: {level_4}\nTotal nodes preserved: {direct + level_4}\n\nContract failures: {len(failures)}")
    for failure in failures: print(f"[FAIL] {failure}")
    if error: print(f"[FAIL] {error}")
    print(f"\nHTML report:\n{report_path.as_posix()}")


def _value(value: Any) -> str:
    return "None" if value is None else escape(str(value))


def _snapshot_display_path() -> str:
    return "tests/fixtures/amazon_department_collector_snapshot.json"


if __name__ == "__main__":
    main()
