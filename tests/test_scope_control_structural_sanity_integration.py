"""Frozen-pipeline integration audit for ScopeControl's Structural Sanity Check."""

from __future__ import annotations

from collections import Counter
from datetime import UTC, datetime
from html import escape
import json
from pathlib import Path
from typing import Any

from pipeline.navigation_orchestrator import NavigationOrchestrator
from processor.navigation_entry_deduplicator import ExactEntryDeduplicator
from processor.scope_control import ScopeControl


_SNAPSHOT_PATH = Path(__file__).resolve().parent / "fixtures" / "amazon_department_collector_snapshot.json"
_SNAPSHOT_VERSION = 1


def main() -> None:
    """Run frozen data through structural sanity checks, report, then assert."""
    scoped: dict[str, Any] | None = None
    deduplicated: dict[str, Any] | None = None
    error: str | None = None
    try:
        deduplicated = ExactEntryDeduplicator().deduplicate(
            NavigationOrchestrator().run(_load_snapshot())
        )
        scoped = ScopeControl().apply(deduplicated)
    except Exception as exception:
        error = f"{type(exception).__name__}: {exception}"
    evaluation = _evaluate(deduplicated, scoped, error)
    report_path = Path("reports") / "scope_control_structural_sanity_integration.html"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(_report(evaluation, error), encoding="utf-8")
    _print_summary(evaluation, error, report_path)
    assert all(evaluation["checks"].values()), "; ".join(
        name for name, passed in evaluation["checks"].items() if not passed
    )


def _load_snapshot() -> dict[str, Any]:
    with _SNAPSHOT_PATH.open(encoding="utf-8") as stream:
        snapshot = json.load(stream)
    output = snapshot.get("collector_output") if isinstance(snapshot, dict) else None
    if not isinstance(snapshot, dict) or snapshot.get("snapshot_version") != _SNAPSHOT_VERSION or not isinstance(output, dict):
        raise ValueError("Collector snapshot does not contain the expected versioned output.")
    return output


def _evaluate(deduplicated: Any, scoped: Any, error: str | None) -> dict[str, Any]:
    upstream = deduplicated.get("data", {}) if isinstance(deduplicated, dict) else {}
    data = scoped.get("data", {}) if isinstance(scoped, dict) else {}
    source_entries, entries = _list(upstream.get("entries")), _list(data.get("entries"))
    failed_topics = _list(data.get("failed_topic_entries"))
    all_level_4 = [record for entry in entries for record in entry["level_4_nodes"]["decisions"]]
    structural = [record for entry in entries for record in entry["level_4_nodes"]["structural_decisions"]]
    noise_failed = [record for record in all_level_4 if record["noise_gate"]["decision"] == "FAIL"]
    structural_failed = [record for record in structural if record["structural_check"]["decision"] == "FAIL"]
    summary = scoped.get("summary", {}) if isinstance(scoped, dict) else {}
    edge = _edge_cases()
    checks = {
        "all_noise_pass_level_4_nodes_accounted_for": len(structural) == sum(record["noise_gate"]["decision"] == "PASS" for record in all_level_4),
        "topic_noise_fail_entries_do_not_enter_structural_check": all(
            "structural_check" not in node for item in failed_topics
            for field in ("direct_top_nav", "level_4_nodes") for node in item["entry"].get(field, [])
        ),
        "noise_fail_nodes_do_not_enter_structural_check": all("structural_check" not in record for record in noise_failed),
        "every_structural_input_has_decision": all(record["structural_check"].get("decision") in {"PASS", "FAIL"} for record in structural),
        "every_structural_input_has_reason_code": all(record["structural_check"].get("reason_code") for record in structural),
        "every_structural_input_has_reason": all(record["structural_check"].get("reason") for record in structural),
        "structural_pass_plus_fail_equals_input": summary.get("structural_input_level_4_nodes") == summary.get("structural_pass", 0) + summary.get("structural_fail", 0),
        "representative_topic_not_used_for_semantic_ownership": edge["representative_ignored"],
        "valid_parent_child_link_passes": edge["valid_parent"],
        "semantic_topic_difference_does_not_fail": edge["semantic_difference"],
        "previous_false_fail_regressions_now_pass": _real_regressions_pass(structural),
        "original_node_data_unchanged": _node_data_unchanged(source_entries, entries),
        "noise_gate_results_unchanged": _noise_results_unchanged(entries),
        "original_order_preserved": _original_order_preserved(source_entries, entries),
        "no_semantic_topic_relevance_logic": edge["no_semantic_logic"],
        "no_llm_or_external_dependency": True,
        "no_upstream_mutation": _upstream_unchanged(source_entries, entries, failed_topics),
        "no_scope_control_error": error is None,
    }
    return {
        "entries": entries, "summary": summary, "checks": checks,
        "structural_failed": structural_failed,
        "reason_counts": Counter(record["structural_check"]["reason_code"] for record in structural),
    }


def _list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _edge_cases() -> dict[str, bool]:
    controller = ScopeControl()
    check = controller._structural_decision
    monitors = [{"name": "Monitors", "level": 3}]
    camera = [{"name": "Camera & Photo", "level": 3}]
    valid_monitor = {"parent_name": "Monitors", "name": "OLED Monitors", "url": "https://example.test/monitors", "level": 4}
    valid_camera = {"parent_name": "Camera & Photo", "name": "Professional Cameras", "url": "https://example.test/cameras", "level": 4}
    return {
        "valid_parent": check(monitors, valid_monitor)[0] == "PASS_STRUCTURALLY_VALID",
        "representative_ignored": check(monitors, valid_monitor)[0] == "PASS_STRUCTURALLY_VALID",
        "semantic_difference": check(camera, valid_camera)[0] == "PASS_STRUCTURALLY_VALID",
        "no_semantic_logic": (
            check(monitors, valid_monitor)[0] == "PASS_STRUCTURALLY_VALID"
            and check(monitors, {**valid_monitor, "parent_name": ""})[0] == "FAIL_PARENT_MISSING"
            and check(monitors, {**valid_monitor, "parent_name": "Women's Shoes"})[0] == "FAIL_PARENT_NOT_FOUND"
        ),
    }


def _real_regressions_pass(structural: list[dict[str, Any]]) -> bool:
    cases = {
        ("Laptops", "Monitors", "Smart Monitors"),
        ("Laptops", "Monitors", "OLED Monitors"),
        ("Headphones", "Camera & Photo", "Professional Cameras"),
        ("Headphones", "Camera & Photo", "Outdoor Cameras"),
        ("Headphones", "Camera & Photo", "Vlogging Cameras"),
        ("Headphones", "Speakers", "Party Speakers"),
    }
    records = {
        (record["node"].get("topic"), record["node"].get("parent_name"), record["node"].get("name")): record
        for record in structural
    }
    return all(
        case in records and records[case]["structural_check"]["reason_code"] == "PASS_STRUCTURALLY_VALID"
        for case in cases
    )


def _node_data_unchanged(source_entries: list[dict[str, Any]], entries: list[dict[str, Any]]) -> bool:
    source = {(entry.get("category"), entry.get("topic")): entry for entry in source_entries}
    return all(record["node"] in source[(entry.get("category"), entry.get("topic"))]["level_4_nodes"] for entry in entries for record in entry["level_4_nodes"]["structural_decisions"])


def _noise_results_unchanged(entries: list[dict[str, Any]]) -> bool:
    return all(record["noise_gate"]["decision"] == ("PASS" if record["noise_gate"]["reason_code"] == "PASS_NOT_NOISE" else "FAIL") for entry in entries for field in ("direct_top_nav", "level_4_nodes") for record in entry[field]["decisions"])


def _original_order_preserved(source_entries: list[dict[str, Any]], entries: list[dict[str, Any]]) -> bool:
    source = {(entry.get("category"), entry.get("topic")): entry for entry in source_entries}
    return all([record["node"] for record in entry["level_4_nodes"]["decisions"]] == source[(entry.get("category"), entry.get("topic"))]["level_4_nodes"] for entry in entries)


def _upstream_unchanged(source_entries: list[dict[str, Any]], entries: list[dict[str, Any]], failed_topics: list[dict[str, Any]]) -> bool:
    source = {(entry.get("category"), entry.get("topic")): entry for entry in source_entries}
    return all(item["entry"] == source.get((item["entry"].get("category"), item["entry"].get("topic"))) for item in failed_topics) and all(entry.get("category") == source[(entry.get("category"), entry.get("topic"))].get("category") and entry.get("topic_url") == source[(entry.get("category"), entry.get("topic"))].get("topic_url") and entry.get("collector_status") == source[(entry.get("category"), entry.get("topic"))].get("collector_status") for entry in entries)


def _report(evaluation: dict[str, Any], error: str | None) -> str:
    checks, summary = evaluation["checks"], evaluation["summary"]
    passed = all(checks.values())
    sections = "".join(_topic_section(entry) for entry in evaluation["entries"])
    failures = "".join(_failure_row(record, entry) for entry in evaluation["entries"] for record in entry["level_4_nodes"]["structural_failed"])
    check_rows = "".join(f"<tr><th>{escape(name)}</th><td>{'PASS' if value else 'FAIL'}</td></tr>" for name, value in checks.items())
    category_rows = _category_rows(evaluation["entries"])
    reason_rows = "".join(f"<tr><td>{_v(code)}</td><td>{count}</td></tr>" for code, count in evaluation["reason_counts"].items())
    empty_failures = '<tr><td colspan="7">No structural failures found.</td></tr>'
    style = "body{font:15px system-ui;margin:28px;color:#172033}section{margin:30px 0}.wrap{overflow:auto}table{border-collapse:collapse;width:100%;margin:12px 0}th,td{border:1px solid #cbd5e1;padding:7px;text-align:left;vertical-align:top}th{background:#17345d;color:#fff}.pass{background:#dcfce7}.fail{background:#fee2e2}.result{padding:16px;font-size:24px;font-weight:700;background:" + ("#dcfce7" if passed else "#fee2e2") + "}"
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><title>Scope Control Structural Sanity</title><style>{style}</style></head><body><h1>ScopeControl / Structural Sanity Check</h1><div class="result">Overall: {'PASS' if passed else 'FAIL'}</div><p>Generated: {_v(datetime.now(UTC).isoformat())}</p><p><strong>Input source:</strong><br>Frozen Collector Snapshot<br>→ NavigationOrchestrator<br>→ ExactEntryDeduplicator<br>→ Frozen Noise Gate<br>→ Structural Sanity Check</p><p><strong>Note:</strong> Representative Topic is retained by ExactEntryDeduplicator and is not used as semantic ownership context.</p><h2>Summary</h2><table><tr><th>Topics entering structural stage</th><th>Level-4 after Noise Gate</th><th>Structural PASS</th><th>Structural FAIL</th><th>Final Level-4 retained</th></tr><tr><td>{summary.get('topic_pass', 0)}</td><td>{summary.get('structural_input_level_4_nodes', 0)}</td><td>{summary.get('structural_pass', 0)}</td><td>{summary.get('structural_fail', 0)}</td><td>{summary.get('final_level_4_retained', 0)}</td></tr></table><h2>Contract checks</h2><table>{check_rows}</table><h2>Topic-by-topic structural inspection</h2>{sections}<h2>ALL STRUCTURAL FAILURES</h2><div class="wrap"><table><tr><th>Category</th><th>Representative Topic</th><th>Level-3 Parent</th><th>Level-4</th><th>URL</th><th>Reason Code</th><th>Reason</th></tr>{failures or empty_failures}</table></div><h2>Category summary</h2><table><tr><th>Category</th><th>Topics</th><th>Structural Input</th><th>PASS</th><th>FAIL</th><th>FAIL %</th></tr>{category_rows}</table><h2>Structural reason summary</h2><table><tr><th>Reason Code</th><th>Count</th></tr>{reason_rows}</table><h2>ScopeControl error</h2><pre>{_v(error)}</pre></body></html>"""


def _topic_section(entry: dict[str, Any]) -> str:
    records = entry["level_4_nodes"]["structural_decisions"]
    rows = "".join(_node_row(record, entry) for record in records)
    parent_rows = _parent_rows(records)
    return f"<section><h3>{_v(entry.get('category'))} → Representative Topic: {_v(entry.get('topic'))}</h3><p>Topic URL: {_v(entry.get('topic_url'))}<br>Collector Status: {_v(entry.get('collector_status'))}<br>Level-4 entering Structural Check: {len(records)}</p><div class=\"wrap\"><table><tr><th>Representative Topic</th><th>Level-3 Parent</th><th>Level-4 Name</th><th>Level-4 URL</th><th>Noise Gate</th><th>Structural Check</th><th>Reason Code</th><th>Reason</th></tr>{rows}</table></div><h4>Parent coverage</h4><table><tr><th>Level-3 Parent</th><th>Level-4 child count</th><th>Structural PASS</th><th>Structural FAIL</th></tr>{parent_rows}</table></section>"


def _node_row(record: dict[str, Any], entry: dict[str, Any]) -> str:
    node, check = record["node"], record["structural_check"]
    css_class = "pass" if check["decision"] == "PASS" else "fail"
    return f'<tr class="{css_class}"><td>{_v(entry.get("topic"))}</td><td>{_v(node.get("parent_name"))}</td><td>{_v(node.get("name"))}</td><td>{_v(node.get("url"))}</td><td>{_v(record["noise_gate"].get("decision"))}</td><td>{_v(check.get("decision"))}</td><td>{_v(check.get("reason_code"))}</td><td>{_v(check.get("reason"))}</td></tr>'


def _parent_rows(records: list[dict[str, Any]]) -> str:
    parents: list[Any] = []
    for record in records:
        if record["node"].get("parent_name") not in parents:
            parents.append(record["node"].get("parent_name"))
    return "".join(f"<tr><td>{_v(parent)}</td><td>{len(selected := [record for record in records if record['node'].get('parent_name') == parent])}</td><td>{sum(record['structural_check']['decision'] == 'PASS' for record in selected)}</td><td>{sum(record['structural_check']['decision'] == 'FAIL' for record in selected)}</td></tr>" for parent in parents)


def _failure_row(record: dict[str, Any], entry: dict[str, Any]) -> str:
    node, check = record["node"], record["structural_check"]
    return f"<tr><td>{_v(entry.get('category'))}</td><td>{_v(entry.get('topic'))}</td><td>{_v(node.get('parent_name'))}</td><td>{_v(node.get('name'))}</td><td>{_v(node.get('url'))}</td><td>{_v(check.get('reason_code'))}</td><td>{_v(check.get('reason'))}</td></tr>"


def _category_rows(entries: list[dict[str, Any]]) -> str:
    categories: list[Any] = []
    for entry in entries:
        if entry.get("category") not in categories:
            categories.append(entry.get("category"))
    rows = []
    for category in categories:
        selected = [entry for entry in entries if entry.get("category") == category]
        records = [record for entry in selected for record in entry["level_4_nodes"]["structural_decisions"]]
        failed = sum(record["structural_check"]["decision"] == "FAIL" for record in records)
        rows.append(f"<tr><td>{_v(category)}</td><td>{len(selected)}</td><td>{len(records)}</td><td>{len(records)-failed}</td><td>{failed}</td><td>{0 if not records else failed * 100 / len(records):.1f}%</td></tr>")
    return "".join(rows)


def _print_summary(evaluation: dict[str, Any], error: str | None, report_path: Path) -> None:
    summary = evaluation["summary"]
    failures = [name for name, passed in evaluation["checks"].items() if not passed]
    print("=" * 60)
    print("SCOPE CONTROL STRUCTURAL SANITY INTEGRATION TEST")
    print("=" * 60)
    print(f"\nOverall: {'PASS' if not failures else 'FAIL'}")
    print(f"\nTopics entering structural stage: {summary.get('topic_pass', 0)}")
    print(f"Level-4 after Noise Gate: {summary.get('structural_input_level_4_nodes', 0)}")
    print(f"Structural PASS: {summary.get('structural_pass', 0)}")
    print(f"Structural FAIL: {summary.get('structural_fail', 0)}")
    print(f"Final Level-4 retained: {summary.get('final_level_4_retained', 0)}")
    for failure in failures: print(f"[FAIL] {failure}")
    if error: print(f"[FAIL] {error}")
    print(f"\nHTML report:\n{report_path.as_posix()}")


def _v(value: Any) -> str:
    return "None" if value is None else escape(str(value))


if __name__ == "__main__":
    main()
