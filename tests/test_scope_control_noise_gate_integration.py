"""Frozen-pipeline integration audit for ScopeControl's deterministic Noise Gate."""

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
    """Apply ScopeControl to frozen data, report and print, then assert."""
    scoped: dict[str, Any] | None = None
    deduplicated: dict[str, Any] | None = None
    error: str | None = None
    try:
        collector = _load_snapshot()
        deduplicated = ExactEntryDeduplicator().deduplicate(NavigationOrchestrator().run(collector))
        scoped = ScopeControl().apply(deduplicated)
    except Exception as exception:
        error = f"{type(exception).__name__}: {exception}"

    evaluation = _evaluate(deduplicated, scoped, error)
    report_path = Path("reports") / "scope_control_noise_gate_integration.html"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(_report(evaluation, error), encoding="utf-8")
    _print_summary(evaluation, error, report_path)
    assert all(evaluation["checks"].values()), "; ".join(
        name for name, passed in evaluation["checks"].items() if not passed
    )


def _load_snapshot() -> dict[str, Any]:
    if not _SNAPSHOT_PATH.is_file():
        raise FileNotFoundError("Collector snapshot is missing; run the collector integration test to regenerate it.")
    with _SNAPSHOT_PATH.open(encoding="utf-8") as stream:
        snapshot = json.load(stream)
    if not isinstance(snapshot, dict) or snapshot.get("snapshot_version") != _SNAPSHOT_VERSION:
        version = snapshot.get("snapshot_version") if isinstance(snapshot, dict) else None
        raise ValueError(f"Unsupported collector snapshot version: {version}")
    output = snapshot.get("collector_output")
    if snapshot.get("source") != "amazon_department_collector" or not isinstance(output, dict):
        raise ValueError("Collector snapshot does not contain the expected collector output.")
    return output


def _evaluate(deduplicated: Any, scoped: Any, error: str | None) -> dict[str, Any]:
    upstream = deduplicated.get("data", {}) if isinstance(deduplicated, dict) else {}
    data = scoped.get("data", {}) if isinstance(scoped, dict) else {}
    input_entries = _list(upstream.get("entries"))
    entries = _list(data.get("entries"))
    failed_topics = _list(data.get("failed_topic_entries"))
    all_topic_gates = [entry.get("topic_noise_gate", {}) for entry in entries] + [
        item.get("topic_noise_gate", {}) for item in failed_topics
    ]
    all_records = [
        record for entry in entries for field in ("direct_top_nav", "level_4_nodes")
        for record in entry.get(field, {}).get("decisions", [])
    ]
    failed_records = [record for record in all_records if record["noise_gate"]["decision"] == "FAIL"]
    input_direct = [node for entry in input_entries for node in _list(entry.get("direct_top_nav"))]
    input_level_4 = [node for entry in input_entries for node in _list(entry.get("level_4_nodes"))]
    summary = scoped.get("summary", {}) if isinstance(scoped, dict) else {}
    edge = _edge_cases()
    checks = {
        "all_deduplicated_topics_accounted_for": len(entries) + len(failed_topics) == len(input_entries),
        "every_topic_has_noise_decision": all(gate.get("decision") in {"PASS", "FAIL"} for gate in all_topic_gates),
        "every_topic_has_reason_code": all(gate.get("reason_code") for gate in all_topic_gates),
        "every_topic_has_reason": all(gate.get("reason") for gate in all_topic_gates),
        "topic_pass_plus_fail_equals_input": summary.get("input_topic_entries") == summary.get("topic_pass", 0) + summary.get("topic_fail", 0),
        "failed_topics_preserved_for_audit": all(isinstance(item.get("entry"), dict) for item in failed_topics),
        "all_node_classification_accounting_consistent": (
            summary.get("total_node_input") == summary.get("total_node_pass", 0) + summary.get("total_node_fail", 0)
            and sum(len(entry[field]["decisions"]) for entry in entries for field in ("direct_top_nav", "level_4_nodes")) == summary.get("total_node_input")
        ),
        "all_direct_top_nav_nodes_classified": sum(len(entry["direct_top_nav"]["decisions"]) for entry in entries) == summary.get("input_direct_top_nav_nodes"),
        "all_level_4_nodes_classified": sum(len(entry["level_4_nodes"]["decisions"]) for entry in entries) == summary.get("input_level_4_nodes"),
        "every_node_has_decision": all(record.get("noise_gate", {}).get("decision") in {"PASS", "FAIL"} for record in all_records),
        "every_node_has_reason_code": all(record.get("noise_gate", {}).get("reason_code") for record in all_records),
        "every_node_has_reason": all(record.get("noise_gate", {}).get("reason") for record in all_records),
        "failed_nodes_preserved_for_audit": all(isinstance(record.get("node"), dict) for record in failed_records),
        "passed_nodes_data_unchanged": all(record["node"] in input_direct + input_level_4 for record in all_records if record["noise_gate"]["decision"] == "PASS"),
        "failed_nodes_data_unchanged": all(record["node"] in input_direct + input_level_4 for record in failed_records),
        "upstream_duplicate_entries_preserved": data.get("duplicate_entries") == upstream.get("duplicate_entries"),
        "upstream_failed_entries_preserved": data.get("failed_entries") == upstream.get("failed_entries"),
        "topic_order_preserved_within_outcomes": _topic_order_preserved(input_entries, entries, failed_topics),
        "original_node_order_preserved": _original_order_preserved(input_entries, entries),
        "navigation_action_noise_verified": _real_node_code(all_records, "Unsure? Click here", "FAIL_NAVIGATION_ACTION"),
        "digital_only_noise_verified": _real_node_code(all_records, "Mobile Apps", "FAIL_DIGITAL_ONLY"),
        "service_platform_noise_verified": _real_node_code(all_records, "Amazon Pickup Locations", "FAIL_SERVICE"),
        "service_topic_noise_verified": _real_topic_code(failed_topics, "Home Cinema Installation Services", "FAIL_SERVICE"),
        "broad_product_topics_pass": edge["broad_topics"],
        "ambiguous_topics_default_to_pass": edge["ambiguous_topics"],
        "deterministic_noise_rules_verified": edge["noise"],
        "no_relevance_logic_applied": all(set(record) == {"node", "noise_gate"} for record in all_records),
        "no_upstream_mutation": _upstream_unchanged(input_entries, entries, failed_topics),
        "no_scope_control_error": error is None,
    }
    return {
        "entries": entries,
        "failed_topics": failed_topics,
        "summary": summary,
        "checks": checks,
        "failed_records": failed_records,
        "topic_reason_counts": Counter(gate["reason_code"] for gate in all_topic_gates if gate.get("decision") == "FAIL"),
        "node_reason_counts": Counter(record["noise_gate"]["reason_code"] for record in failed_records),
    }


def _list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _topic_order_preserved(
    originals: list[dict[str, Any]], entries: list[dict[str, Any]], failed_topics: list[dict[str, Any]]
) -> bool:
    original_keys = [(item.get("category"), item.get("topic")) for item in originals]
    passed_keys = [(item.get("category"), item.get("topic")) for item in entries]
    failed_keys = [(item["entry"].get("category"), item["entry"].get("topic")) for item in failed_topics]
    return passed_keys == [key for key in original_keys if key in passed_keys] and failed_keys == [key for key in original_keys if key in failed_keys]


def _original_order_preserved(input_entries: list[dict[str, Any]], entries: list[dict[str, Any]]) -> bool:
    originals = {(entry.get("category"), entry.get("topic")): entry for entry in input_entries}
    return all(
        [record["node"] for record in entry[field]["decisions"]] == originals[(entry.get("category"), entry.get("topic"))][field]
        for entry in entries for field in ("direct_top_nav", "level_4_nodes")
    )


def _upstream_unchanged(
    originals: list[dict[str, Any]], entries: list[dict[str, Any]], failed_topics: list[dict[str, Any]]
) -> bool:
    source = {(entry.get("category"), entry.get("topic")): entry for entry in originals}
    return all(
        item["entry"] == source.get((item["entry"].get("category"), item["entry"].get("topic")))
        for item in failed_topics
    ) and all(
        entry.get("topic_noise_gate") and all(
            [record["node"] for record in entry[field]["decisions"]] == source[(entry.get("category"), entry.get("topic"))][field]
            for field in ("direct_top_nav", "level_4_nodes")
        ) for entry in entries
    )


def _real_node_code(records: list[dict[str, Any]], name: str, code: str) -> bool:
    matches = [record for record in records if record["node"].get("name") == name]
    return bool(matches) and all(record["noise_gate"]["reason_code"] == code for record in matches)


def _real_topic_code(failed_topics: list[dict[str, Any]], topic: str, code: str) -> bool:
    matches = [item for item in failed_topics if item["entry"].get("topic") == topic]
    return bool(matches) and all(item["topic_noise_gate"]["reason_code"] == code for item in matches)


def _edge_cases() -> dict[str, bool]:
    controller = ScopeControl()
    broad_topics = ["Camera & Photo", "Electronics"]
    ambiguous_topics = ["Software", "Amazon Business", "Resale", "Outlet", "Accessories"]
    expected = {
        "Unsure? Click here": "FAIL_NAVIGATION_ACTION",
        "Click here": "FAIL_NAVIGATION_ACTION",
        "Mobile Apps": "FAIL_DIGITAL_ONLY",
        "Amazon Pickup Locations": "FAIL_SERVICE",
        "Today's Deals": "FAIL_PROMOTIONAL",
        "Best Sellers": "FAIL_PROMOTIONAL",
        "Amazon Prime": "FAIL_MEMBERSHIP",
        "Wedding List": "FAIL_REGISTRY",
        "Prime Video": "FAIL_DIGITAL_ONLY",
        "Amazon App Store": "FAIL_DIGITAL_ONLY",
    }
    return {
        "broad_topics": all(controller._topic_noise_decision({"topic": name})[0] == "PASS_NOT_NOISE" for name in broad_topics),
        "ambiguous_topics": all(controller._topic_noise_decision({"topic": name})[0] == "PASS_NOT_NOISE" for name in ambiguous_topics),
        "noise": (
            controller._topic_noise_decision({"topic": "Home Cinema Installation Services"})[0] == "FAIL_SERVICE"
            and all(controller._noise_decision({"name": name})[0] == code for name, code in expected.items())
            and controller._noise_decision({"name": "Accessories"})[0] == "PASS_NOT_NOISE"
            and controller._noise_decision({"name": "Home Theatre"})[0] == "PASS_NOT_NOISE"
        ),
    }


def _report(evaluation: dict[str, Any], error: str | None) -> str:
    checks, summary = evaluation["checks"], evaluation["summary"]
    passed = all(checks.values())
    topic_sections = "".join(_topic_section(entry) for entry in evaluation["entries"])
    topic_sections += "".join(_failed_topic_section(item) for item in evaluation["failed_topics"])
    failed_rows = "".join(_failed_row(record, entry) for entry in evaluation["entries"] for field in ("direct_top_nav", "level_4_nodes") for record in entry[field]["failed"])
    failed_topic_rows = "".join(_failed_topic_row(item) for item in evaluation["failed_topics"])
    node_reason_rows = _reason_rows(evaluation["node_reason_counts"])
    topic_reason_rows = _reason_rows(evaluation["topic_reason_counts"])
    check_rows = "".join(f"<tr><th>{escape(name)}</th><td>{'PASS' if value else 'FAIL'}</td></tr>" for name, value in checks.items())
    no_failed_topics = '<tr><td colspan="7">No Topics failed the Noise Gate.</td></tr>'
    no_failed_nodes = '<tr><td colspan="8">No nodes failed the Noise Gate.</td></tr>'
    no_topic_reasons = '<tr><td colspan="2">No failed Topics.</td></tr>'
    no_node_reasons = '<tr><td colspan="2">No failed nodes.</td></tr>'
    style = "body{font:15px system-ui;margin:28px;color:#172033}section{margin:30px 0}.wrap{overflow:auto}table{border-collapse:collapse;width:100%;margin:12px 0}th,td{border:1px solid #cbd5e1;padding:7px;text-align:left;vertical-align:top}th{background:#17345d;color:#fff}.pass{background:#dcfce7}.fail{background:#fee2e2}.topic-excluded{border:3px solid #dc2626;padding:14px;background:#fff1f2}.result{padding:16px;font-size:24px;font-weight:700;background:" + ("#dcfce7" if passed else "#fee2e2") + "}"
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><title>Scope Control Noise Gate</title><style>{style}</style></head><body><h1>Scope Control / Noise Gate</h1><div class="result">{'PASS' if passed else 'FAIL'}</div><p>Generated: {escape(datetime.now(UTC).isoformat())}</p><p><strong>Input source:</strong> Frozen Collector Snapshot → Navigation Orchestrator → ExactEntryDeduplicator → ScopeControl / Noise Gate</p><h2>TOPICS</h2><table><tr><th>Input</th><th>PASS</th><th>FAIL</th></tr><tr><td>{summary.get('input_topic_entries', 0)}</td><td>{summary.get('topic_pass', 0)}</td><td>{summary.get('topic_fail', 0)}</td></tr></table><h2>Node-level summary</h2><table><tr><th></th><th>Input (Topic PASS only)</th><th>PASS</th><th>FAIL</th></tr><tr><th>Direct Top Nav</th><td>{summary.get('input_direct_top_nav_nodes', 0)}</td><td>{summary.get('direct_top_nav_pass', 0)}</td><td>{summary.get('direct_top_nav_fail', 0)}</td></tr><tr><th>Level-4</th><td>{summary.get('input_level_4_nodes', 0)}</td><td>{summary.get('level_4_pass', 0)}</td><td>{summary.get('level_4_fail', 0)}</td></tr><tr><th>TOTAL</th><td>{summary.get('total_node_input', 0)}</td><td>{summary.get('total_node_pass', 0)}</td><td>{summary.get('total_node_fail', 0)}</td></tr></table><p>Nodes under Topic-level FAIL entries are retained for audit but excluded before node-level classification: {summary.get('topic_fail_direct_top_nav_nodes_audited', 0)} Direct Top Nav and {summary.get('topic_fail_level_4_nodes_audited', 0)} Level-4.</p><h2>Contract checks</h2><table>{check_rows}</table><h2>Topic-by-topic decisions</h2>{topic_sections}<h2>FAILED TOPICS</h2><div class="wrap"><table><tr><th>Category</th><th>Topic</th><th>Topic URL</th><th>Reason Code</th><th>Reason</th><th>Direct Top Nav Count</th><th>Level-4 Count</th></tr>{failed_topic_rows or no_failed_topics}</table></div><h2>ALL FAILED NODES</h2><div class="wrap"><table><thead><tr><th>Category</th><th>Topic</th><th>Level</th><th>Name</th><th>Parent</th><th>URL</th><th>Reason Code</th><th>Reason</th></tr></thead><tbody>{failed_rows or no_failed_nodes}</tbody></table></div><h2>Topic-level reason summary</h2><table><tr><th>Reason Code</th><th>Count</th></tr>{topic_reason_rows or no_topic_reasons}</table><h2>Node-level reason summary</h2><table><tr><th>Reason Code</th><th>Count</th></tr>{node_reason_rows or no_node_reasons}</table><h2>ScopeControl error</h2><pre>{_v(error)}</pre></body></html>"""


def _topic_section(entry: dict[str, Any]) -> str:
    direct, level_4, gate = entry["direct_top_nav"], entry["level_4_nodes"], entry["topic_noise_gate"]
    return f"<section><h3>{_v(entry.get('category'))} → {_v(entry.get('topic'))}</h3><p>Topic URL: {_v(entry.get('topic_url'))}<br>Collector Status: {_v(entry.get('collector_status'))}<br>Topic Noise Gate: {gate['decision']}<br>Reason Code: {_v(gate['reason_code'])}<br>Reason: {_v(gate['reason'])}<br>Direct Top Nav: {len(direct['decisions'])} input / {len(direct['passed'])} pass / {len(direct['failed'])} fail<br>Level-4: {len(level_4['decisions'])} input / {len(level_4['passed'])} pass / {len(level_4['failed'])} fail</p>{_node_table('Direct Top Nav', direct['decisions'])}{_node_table('Level-4', level_4['decisions'])}</section>"


def _failed_topic_section(item: dict[str, Any]) -> str:
    entry, gate = item["entry"], item["topic_noise_gate"]
    return f"<section class=\"topic-excluded\"><h3>TOPIC EXCLUDED: {_v(entry.get('category'))} → {_v(entry.get('topic'))}</h3><p>Topic URL: {_v(entry.get('topic_url'))}<br>Collector Status: {_v(entry.get('collector_status'))}<br>Topic Noise Gate: FAIL<br>Reason Code: {_v(gate['reason_code'])}<br>Reason: {_v(gate['reason'])}</p>{_audit_node_table('Direct Top Nav audit (not node-classified)', _list(entry.get('direct_top_nav')))}{_audit_node_table('Level-4 audit (not node-classified)', _list(entry.get('level_4_nodes')))}</section>"


def _node_table(title: str, records: list[dict[str, Any]]) -> str:
    rows = "".join(_record_row(record) for record in records)
    return f'<h4>{title}</h4><div class="wrap"><table><tr><th>Level</th><th>Node Name</th><th>Parent Name</th><th>URL</th><th>Decision</th><th>Reason Code</th><th>Reason</th></tr>{rows}</table></div>'


def _audit_node_table(title: str, nodes: list[dict[str, Any]]) -> str:
    rows = "".join(f"<tr><td>{_v(node.get('level'))}</td><td>{_v(node.get('name'))}</td><td>{_v(node.get('parent_name'))}</td><td>{_v(node.get('url'))}</td><td colspan=\"3\">Excluded with Topic before node-level Noise Gate.</td></tr>" for node in nodes)
    return f'<h4>{title}</h4><div class="wrap"><table><tr><th>Level</th><th>Node Name</th><th>Parent Name</th><th>URL</th><th>Decision</th><th>Reason Code</th><th>Reason</th></tr>{rows}</table></div>'


def _record_row(record: dict[str, Any]) -> str:
    node, gate = record["node"], record["noise_gate"]
    css_class = "pass" if gate["decision"] == "PASS" else "fail"
    return f'<tr class="{css_class}"><td>{_v(node.get("level"))}</td><td>{_v(node.get("name"))}</td><td>{_v(node.get("parent_name"))}</td><td>{_v(node.get("url"))}</td><td>{gate["decision"]}</td><td>{_v(gate["reason_code"])}</td><td>{_v(gate["reason"])}</td></tr>'


def _failed_row(record: dict[str, Any], entry: dict[str, Any]) -> str:
    node, gate = record["node"], record["noise_gate"]
    return f"<tr><td>{_v(entry.get('category'))}</td><td>{_v(entry.get('topic'))}</td><td>{_v(node.get('level'))}</td><td>{_v(node.get('name'))}</td><td>{_v(node.get('parent_name'))}</td><td>{_v(node.get('url'))}</td><td>{_v(gate['reason_code'])}</td><td>{_v(gate['reason'])}</td></tr>"


def _failed_topic_row(item: dict[str, Any]) -> str:
    entry, gate = item["entry"], item["topic_noise_gate"]
    return f"<tr><td>{_v(entry.get('category'))}</td><td>{_v(entry.get('topic'))}</td><td>{_v(entry.get('topic_url'))}</td><td>{_v(gate['reason_code'])}</td><td>{_v(gate['reason'])}</td><td>{len(_list(entry.get('direct_top_nav')))}</td><td>{len(_list(entry.get('level_4_nodes')))}</td></tr>"


def _reason_rows(counts: Counter[str]) -> str:
    return "".join(f"<tr><td>{_v(code)}</td><td>{count}</td></tr>" for code, count in counts.items())


def _print_summary(evaluation: dict[str, Any], error: str | None, report_path: Path) -> None:
    summary = evaluation["summary"]
    failures = [name for name, passed in evaluation["checks"].items() if not passed]
    print("=" * 60)
    print("SCOPE CONTROL NOISE GATE INTEGRATION TEST")
    print("=" * 60)
    print("\nInput source: FROZEN COLLECTOR SNAPSHOT")
    print(f"\nOverall: {'PASS' if not failures else 'FAIL'}")
    print(f"\nTOPICS\nInput: {summary.get('input_topic_entries', 0)}\nPASS: {summary.get('topic_pass', 0)}\nFAIL: {summary.get('topic_fail', 0)}")
    print(f"\nDirect Top Nav (Topic PASS only)\nInput: {summary.get('input_direct_top_nav_nodes', 0)}\nPASS: {summary.get('direct_top_nav_pass', 0)}\nFAIL: {summary.get('direct_top_nav_fail', 0)}")
    print(f"\nLevel-4 (Topic PASS only)\nInput: {summary.get('input_level_4_nodes', 0)}\nPASS: {summary.get('level_4_pass', 0)}\nFAIL: {summary.get('level_4_fail', 0)}")
    print(f"\nTOTAL NODE-LEVEL\nInput: {summary.get('total_node_input', 0)}\nPASS: {summary.get('total_node_pass', 0)}\nFAIL: {summary.get('total_node_fail', 0)}")
    for failure in failures:
        print(f"[FAIL] {failure}")
    if error:
        print(f"[FAIL] {error}")
    print(f"\nHTML report:\n{report_path.as_posix()}")


def _v(value: Any) -> str:
    return "None" if value is None else escape(str(value))


if __name__ == "__main__":
    main()
