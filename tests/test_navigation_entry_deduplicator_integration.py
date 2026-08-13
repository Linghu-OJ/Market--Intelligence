"""Frozen-snapshot integration audit for ExactEntryDeduplicator."""

from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime
from html import escape
import json
from pathlib import Path
from typing import Any

from pipeline.navigation_orchestrator import NavigationOrchestrator
from processor.navigation_entry_deduplicator import ExactEntryDeduplicator


_SNAPSHOT_PATH = (
    Path(__file__).resolve().parent
    / "fixtures"
    / "amazon_department_collector_snapshot.json"
)
_SNAPSHOT_VERSION = 1


def main() -> None:
    """Audit exact deduplication from the frozen collector contract only."""
    before: dict[str, Any] | None = None
    result: dict[str, Any] | None = None
    error: str | None = None
    snapshot_version: int | None = None
    try:
        collector_output, snapshot_version = _load_collector_snapshot()
        before = NavigationOrchestrator().run(collector_output)
        result = ExactEntryDeduplicator().deduplicate(before)
    except Exception as exception:
        error = f"{type(exception).__name__}: {exception}"

    evaluation = _evaluate(before, result, error)
    report_path = Path("reports") / "navigation_entry_deduplicator_integration.html"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        _report(evaluation, error, snapshot_version), encoding="utf-8"
    )
    _print_summary(evaluation, error, report_path)
    assert all(evaluation["checks"].values()), "; ".join(
        name for name, passed in evaluation["checks"].items() if not passed
    )


def _load_collector_snapshot() -> tuple[dict[str, Any], int]:
    """Load the approved fixture; never fall back to live Amazon collection."""
    if not _SNAPSHOT_PATH.is_file():
        raise FileNotFoundError(
            "Collector snapshot is missing. Run the collector integration test to "
            "regenerate tests/fixtures/amazon_department_collector_snapshot.json."
        )
    try:
        with _SNAPSHOT_PATH.open(encoding="utf-8") as stream:
            snapshot = json.load(stream)
    except json.JSONDecodeError as exception:
        raise ValueError(f"Collector snapshot contains invalid JSON: {exception}") from exception
    if not isinstance(snapshot, dict):
        raise ValueError("Collector snapshot must be a JSON object.")
    version = snapshot.get("snapshot_version")
    if version != _SNAPSHOT_VERSION:
        raise ValueError(f"Unsupported collector snapshot version: {version}")
    if snapshot.get("source") != "amazon_department_collector":
        raise ValueError("Collector snapshot has an unsupported source.")
    collector_output = snapshot.get("collector_output")
    if not isinstance(collector_output, dict) or not isinstance(
        collector_output.get("categories"), list
    ):
        raise ValueError("Collector snapshot requires collector_output.categories.")
    return collector_output, version


def _evaluate(
    before: dict[str, Any] | None,
    result: dict[str, Any] | None,
    error: str | None,
) -> dict[str, Any]:
    before_data = before.get("data", {}) if isinstance(before, dict) else {}
    result_data = result.get("data", {}) if isinstance(result, dict) else {}
    input_entries = before_data.get("entries", []) if isinstance(before_data.get("entries"), list) else []
    failed_entries = before_data.get("failed_entries", []) if isinstance(before_data.get("failed_entries"), list) else []
    retained_entries = result_data.get("entries", []) if isinstance(result_data.get("entries"), list) else []
    duplicates = result_data.get("duplicate_entries", []) if isinstance(result_data.get("duplicate_entries"), list) else []
    summary = result.get("summary", {}) if isinstance(result, dict) else {}
    expected_retained, expected_duplicates = _expected_classification(input_entries)
    edge_checks = _edge_case_checks()
    category_rows = _category_rows(input_entries, retained_entries, duplicates)
    checks = {
        "all_input_entries_accounted_for": len(input_entries) == len(retained_entries) + len(duplicates),
        "first_duplicate_entry_retained": retained_entries == expected_retained,
        "duplicates_removed_only_after_exact_level_3_match": duplicates == expected_duplicates,
        "exact_duplicate_verified": edge_checks["exact_duplicate"],
        "no_cross_category_deduplication": edge_checks["different_category"],
        "empty_direct_top_nav_entries_not_deduplicated": edge_checks["empty_navigation"],
        "order_sensitive_signature_verified": edge_checks["different_order"],
        "one_url_difference_not_deduplicated": edge_checks["different_url"],
        "level_4_excluded_from_signature": edge_checks["level_4_differs"],
        "retained_entry_data_unchanged": all(
            actual == expected for actual, expected in zip(retained_entries, expected_retained)
        ) and len(retained_entries) == len(expected_retained),
        "failed_entries_preserved": result_data.get("failed_entries") == failed_entries,
        "direct_top_nav_accounting_consistent": summary.get("input_direct_top_nav_nodes") == _count(input_entries, "direct_top_nav") == summary.get("retained_direct_top_nav_nodes", 0) + summary.get("removed_duplicate_entry_direct_top_nav_nodes", 0),
        "level_4_accounting_consistent": summary.get("input_level_4_nodes") == _count(input_entries, "level_4_nodes") == summary.get("retained_level_4_nodes", 0) + summary.get("removed_duplicate_entry_level_4_nodes", 0),
        "summary_counts_consistent": summary == _expected_summary(input_entries, retained_entries, duplicates, failed_entries),
        "no_deduplicator_error": error is None,
    }
    return {
        "input_entries": input_entries,
        "retained_entries": retained_entries,
        "duplicates": duplicates,
        "failed_entries": failed_entries,
        "summary": summary,
        "category_rows": category_rows,
        "checks": checks,
    }


def _expected_classification(
    entries: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    retained, duplicates, first = [], [], {}
    for entry in entries:
        signature = _signature(entry)
        if signature is None or signature not in first:
            if signature is not None:
                first[signature] = entry
            retained.append(entry)
            continue
        original = first[signature]
        duplicates.append({
            "category": entry.get("category"), "topic": entry.get("topic"),
            "topic_url": entry.get("topic_url"),
            "duplicate_of_topic": original.get("topic"),
            "duplicate_of_topic_url": original.get("topic_url"),
            "direct_top_nav_count": len(entry["direct_top_nav"]),
            "level_4_node_count": len(entry["level_4_nodes"]),
            "removed_entry": entry,
        })
    return retained, duplicates


def _signature(entry: dict[str, Any]) -> tuple[Any, ...] | None:
    direct_top_nav = entry["direct_top_nav"]
    if not direct_top_nav:
        return None
    return entry["category"], tuple(
        (node.get("name"), node.get("url")) for node in direct_top_nav
    )


def _expected_summary(
    input_entries: list[dict[str, Any]],
    retained_entries: list[dict[str, Any]],
    duplicates: list[dict[str, Any]],
    failed_entries: list[dict[str, Any]],
) -> dict[str, int]:
    input_direct, retained_direct = _count(input_entries, "direct_top_nav"), _count(retained_entries, "direct_top_nav")
    input_level_4, retained_level_4 = _count(input_entries, "level_4_nodes"), _count(retained_entries, "level_4_nodes")
    return {
        "input_entries": len(input_entries), "retained_entries": len(retained_entries),
        "duplicate_entries": len(duplicates), "failed_entries": len(failed_entries),
        "input_direct_top_nav_nodes": input_direct, "retained_direct_top_nav_nodes": retained_direct,
        "removed_duplicate_entry_direct_top_nav_nodes": input_direct - retained_direct,
        "input_level_4_nodes": input_level_4, "retained_level_4_nodes": retained_level_4,
        "removed_duplicate_entry_level_4_nodes": input_level_4 - retained_level_4,
    }


def _count(entries: list[dict[str, Any]], field: str) -> int:
    return sum(len(entry.get(field, [])) for entry in entries)


def _category_rows(
    before: list[dict[str, Any]],
    after: list[dict[str, Any]],
    duplicates: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    categories = []
    for entry in before:
        if entry["category"] not in categories:
            categories.append(entry["category"])
    return [{
        "category": category,
        "before_topics": sum(entry["category"] == category for entry in before),
        "after_topics": sum(entry["category"] == category for entry in after),
        "duplicates": sum(item.get("category") == category for item in duplicates),
        "before_direct": _count([entry for entry in before if entry["category"] == category], "direct_top_nav"),
        "after_direct": _count([entry for entry in after if entry["category"] == category], "direct_top_nav"),
        "before_level_4": _count([entry for entry in before if entry["category"] == category], "level_4_nodes"),
        "after_level_4": _count([entry for entry in after if entry["category"] == category], "level_4_nodes"),
    } for category in categories]


def _edge_case_checks() -> dict[str, bool]:
    def entry(category: str, topic: str, nav: list[tuple[str, str]], level_4: str = "x") -> dict[str, Any]:
        return {"category": category, "topic": topic, "topic_url": topic, "collector_status": "TOPIC_PAGE_OPENED", "top_nav_status": "TOP_NAV_COLLECTED", "direct_top_nav": [{"name": name, "url": url} for name, url in nav], "level_4_nodes": [{"name": level_4}], "errors": []}
    exact = [entry("A", "one", [("A", "/a")]), entry("A", "two", [("A", "/a")])]
    exact_result = ExactEntryDeduplicator().deduplicate({"data": {"entries": exact, "failed_entries": []}})
    different_category = ExactEntryDeduplicator().deduplicate({"data": {"entries": [entry("A", "one", [("A", "/a")]), entry("B", "two", [("A", "/a")])], "failed_entries": []}})
    different_order = ExactEntryDeduplicator().deduplicate({"data": {"entries": [entry("A", "one", [("A", "/a"), ("B", "/b")]), entry("A", "two", [("B", "/b"), ("A", "/a")])], "failed_entries": []}})
    different_url = ExactEntryDeduplicator().deduplicate({"data": {"entries": [entry("A", "one", [("A", "/a")]), entry("A", "two", [("A", "/b")])], "failed_entries": []}})
    empty = ExactEntryDeduplicator().deduplicate({"data": {"entries": [entry("A", "one", []), entry("A", "two", [])], "failed_entries": []}})
    level_4 = ExactEntryDeduplicator().deduplicate({"data": {"entries": [entry("A", "one", [("A", "/a")], "first"), entry("A", "two", [("A", "/a")], "second")], "failed_entries": []}})
    return {"exact_duplicate": len(exact_result["data"]["entries"]) == 1 and len(exact_result["data"]["duplicate_entries"]) == 1, "different_category": len(different_category["data"]["entries"]) == 2, "different_order": len(different_order["data"]["entries"]) == 2, "different_url": len(different_url["data"]["entries"]) == 2, "empty_navigation": len(empty["data"]["entries"]) == 2, "level_4_differs": len(level_4["data"]["entries"]) == 1}


def _report(evaluation: dict[str, Any], error: str | None, snapshot_version: int | None) -> str:
    checks, summary = evaluation["checks"], evaluation["summary"]
    retained_ids = {id(entry) for entry in evaluation["retained_entries"]}
    duplicate_by_id = {id(item["removed_entry"]): item for item in evaluation["duplicates"]}
    before_rows = "".join(_before_row(index, entry, retained_ids, duplicate_by_id) for index, entry in enumerate(evaluation["input_entries"], 1))
    retained_rows = "".join(_retained_row(index, entry) for index, entry in enumerate(evaluation["retained_entries"], 1))
    duplicate_rows = "".join(_duplicate_row(item, evaluation["retained_entries"]) for item in evaluation["duplicates"])
    category_rows = "".join(f"<tr><td>{_v(row['category'])}</td><td>{row['before_topics']}</td><td>{row['after_topics']}</td><td>{row['duplicates']}</td><td>{row['before_direct']}</td><td>{row['after_direct']}</td><td>{row['before_level_4']}</td><td>{row['after_level_4']}</td></tr>" for row in evaluation["category_rows"])
    check_rows = "".join(f"<tr><th>{escape(name)}</th><td>{'PASS' if value else 'FAIL'}</td></tr>" for name, value in checks.items())
    passed = all(checks.values())
    style = "body{font:15px system-ui;margin:28px;color:#172033}table{border-collapse:collapse;width:100%;margin:12px 0 28px}th,td{border:1px solid #cbd5e1;padding:8px;vertical-align:top;text-align:left}th{background:#17345d;color:#fff}.wrap{overflow:auto}details{min-width:420px}pre{white-space:pre-wrap}.result{padding:16px;font-size:24px;font-weight:700;background:" + ("#dcfce7" if passed else "#fee2e2") + "}"
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><title>Navigation Entry Deduplicator Integration</title><style>{style}</style></head><body><h1>Navigation Entry Deduplicator Integration</h1><div class="result">{'PASS' if passed else 'FAIL'}</div><p>Generated: {escape(datetime.now(UTC).isoformat())}</p><p><strong>Input source:</strong> Frozen Collector Snapshot → Navigation Orchestrator → ExactEntryDeduplicator<br><strong>Snapshot path:</strong> tests/fixtures/amazon_department_collector_snapshot.json<br><strong>Snapshot version:</strong> {_v(snapshot_version)}</p><h2>Before / After / Removed</h2><table><thead><tr><th></th><th>Topic entries</th><th>Direct Top Nav nodes</th><th>Level-4 nodes</th></tr></thead><tbody><tr><th>BEFORE</th><td>{summary.get('input_entries', 0)}</td><td>{summary.get('input_direct_top_nav_nodes', 0)}</td><td>{summary.get('input_level_4_nodes', 0)}</td></tr><tr><th>AFTER</th><td>{summary.get('retained_entries', 0)}</td><td>{summary.get('retained_direct_top_nav_nodes', 0)}</td><td>{summary.get('retained_level_4_nodes', 0)}</td></tr><tr><th>REMOVED</th><td>{summary.get('duplicate_entries', 0)}</td><td>{summary.get('removed_duplicate_entry_direct_top_nav_nodes', 0)}</td><td>{summary.get('removed_duplicate_entry_level_4_nodes', 0)}</td></tr></tbody></table><h2>Contract checks</h2><table>{check_rows}</table><h2>Before deduplication</h2><div class="wrap"><table><thead><tr><th>Index</th><th>Category</th><th>Topic</th><th>Collector Status</th><th>Topic URL</th><th>Direct Top Nav Count</th><th>Level-4 Count</th><th>Dedup Result</th><th>Direct Top Nav inspection</th></tr></thead><tbody>{before_rows}</tbody></table></div><h2>Duplicates removed</h2><div class="wrap"><table><thead><tr><th>Category</th><th>Removed Topic</th><th>Removed Topic URL</th><th>Duplicate Of Topic</th><th>Duplicate Of Topic URL</th><th>Direct Top Nav Count</th><th>Level-4 Count Removed</th><th>Direct Top Nav Match</th></tr></thead><tbody>{duplicate_rows or '<tr><td colspan="8">No exact duplicates in this snapshot.</td></tr>'}</tbody></table></div><h2>After deduplication</h2><div class="wrap"><table><thead><tr><th>Index</th><th>Category</th><th>Topic</th><th>Topic URL</th><th>Collector Status</th><th>Direct Top Nav Count</th><th>Level-4 Count</th></tr></thead><tbody>{retained_rows}</tbody></table></div><h2>Per-category reduction</h2><table><thead><tr><th>Category</th><th>Before Topics</th><th>After Topics</th><th>Duplicates Removed</th><th>Before Direct Top Nav</th><th>After Direct Top Nav</th><th>Before Level-4</th><th>After Level-4</th></tr></thead><tbody>{category_rows}</tbody></table><h2>Deduplicator error</h2><pre>{_v(error)}</pre></body></html>"""


def _before_row(index: int, entry: dict[str, Any], retained_ids: set[int], duplicates: dict[int, dict[str, Any]]) -> str:
    audit = duplicates.get(id(entry))
    decision = "RETAINED" if id(entry) in retained_ids else "REMOVED AS DUPLICATE"
    if audit:
        decision += f" → {escape(str(audit['duplicate_of_topic']))}"
    return f"<tr><td>{index}</td><td>{_v(entry.get('category'))}</td><td>{_v(entry.get('topic'))}</td><td>{_v(entry.get('collector_status'))}</td><td>{_v(entry.get('topic_url'))}</td><td>{len(entry['direct_top_nav'])}</td><td>{len(entry['level_4_nodes'])}</td><td>{decision}</td><td>{_nav_details(entry['direct_top_nav'], 'Direct Top Nav')}</td></tr>"


def _retained_row(index: int, entry: dict[str, Any]) -> str:
    return f"<tr><td>{index}</td><td>{_v(entry.get('category'))}</td><td>{_v(entry.get('topic'))}</td><td>{_v(entry.get('topic_url'))}</td><td>{_v(entry.get('collector_status'))}</td><td>{len(entry['direct_top_nav'])}</td><td>{len(entry['level_4_nodes'])}</td></tr>"


def _duplicate_row(audit: dict[str, Any], retained_entries: list[dict[str, Any]]) -> str:
    original = next((entry for entry in retained_entries if entry.get('category') == audit.get('category') and entry.get('topic') == audit.get('duplicate_of_topic') and entry.get('topic_url') == audit.get('duplicate_of_topic_url')), None)
    pair = _nav_details(audit['removed_entry']['direct_top_nav'], 'Removed Topic Direct Top Nav') + _nav_details(original.get('direct_top_nav', []) if original else [], 'Retained Topic Direct Top Nav')
    return f"<tr><td>{_v(audit.get('category'))}</td><td>{_v(audit.get('topic'))}</td><td>{_v(audit.get('topic_url'))}</td><td>{_v(audit.get('duplicate_of_topic'))}</td><td>{_v(audit.get('duplicate_of_topic_url'))}</td><td>{audit.get('direct_top_nav_count')}</td><td>{audit.get('level_4_node_count')}</td><td>EXACT MATCH{pair}</td></tr>"


def _nav_details(nodes: list[dict[str, Any]], title: str) -> str:
    rows = "".join(f"<li>{index}. {_v(node.get('name'))} — {_v(node.get('url'))}</li>" for index, node in enumerate(nodes, 1))
    return f"<details><summary>{escape(title)} ({len(nodes)})</summary><ol>{rows or '<li>None</li>'}</ol></details>"


def _print_summary(evaluation: dict[str, Any], error: str | None, report_path: Path) -> None:
    summary, duplicates = evaluation["summary"], evaluation["duplicates"]
    failures = [name for name, passed in evaluation["checks"].items() if not passed]
    print("=" * 60); print("NAVIGATION ENTRY DEDUPLICATOR INTEGRATION TEST"); print("=" * 60)
    print("\nInput source: FROZEN COLLECTOR SNAPSHOT")
    print(f"\nOverall: {'PASS' if not failures else 'FAIL'}\n\nBEFORE\nTopic entries: {summary.get('input_entries', 0)}\nDirect Top Nav nodes: {summary.get('input_direct_top_nav_nodes', 0)}\nLevel-4 nodes: {summary.get('input_level_4_nodes', 0)}\n\nAFTER\nTopic entries: {summary.get('retained_entries', 0)}\nDirect Top Nav nodes: {summary.get('retained_direct_top_nav_nodes', 0)}\nLevel-4 nodes: {summary.get('retained_level_4_nodes', 0)}\n\nREMOVED\nDuplicate Topic entries: {summary.get('duplicate_entries', 0)}\nDirect Top Nav nodes: {summary.get('removed_duplicate_entry_direct_top_nav_nodes', 0)}\nLevel-4 nodes: {summary.get('removed_duplicate_entry_level_4_nodes', 0)}\n\nDuplicate groups: {len(duplicates)}\nContract failures: {len(failures)}")
    for audit in duplicates: print(f"[DUPLICATE]\n{audit.get('category')}\n{audit.get('topic')}\n→ duplicate of {audit.get('duplicate_of_topic')}")
    for failure in failures: print(f"[FAIL] {failure}")
    if error: print(f"[FAIL] {error}")
    print(f"\nHTML report:\n{report_path.as_posix()}")


def _v(value: Any) -> str:
    return "None" if value is None else escape(str(value))


if __name__ == "__main__":
    main()
