"""Live Amazon direct-top-nav mega-menu integration test."""

from __future__ import annotations

from datetime import UTC, datetime
from html import escape
import json
import os
from pathlib import Path
from typing import Any

from collector.amazon_department import AmazonDepartmentCollector


_SNAPSHOT_PATH = (
    Path(__file__).resolve().parent
    / "fixtures"
    / "amazon_department_collector_snapshot.json"
)


def test_amazon_top_nav_mega_menu() -> None:
    result: dict[str, Any] | None = None
    collector_error: str | None = None
    try:
        result = AmazonDepartmentCollector(headless=False).collect()
    except Exception as error:
        collector_error = f"{type(error).__name__}: {error}"

    diagnostics = result.get("diagnostics", {}) if isinstance(result, dict) else {}
    top_nav = _top_nav_records(result)
    failures = _failures(result, top_nav, collector_error)
    report_path = Path("reports") / "amazon_top_nav_mega_menu.html"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        _report(result, diagnostics, top_nav, collector_error, failures),
        encoding="utf-8",
    )
    if not failures and isinstance(result, dict):
        _write_collector_snapshot(result)
    _print_summary(diagnostics, top_nav, collector_error, failures, report_path)
    if not failures and isinstance(result, dict):
        print(f"Collector snapshot written:\n{_snapshot_display_path()}")
    assert not failures, "; ".join(failures)


def _write_collector_snapshot(collector_output: dict[str, Any]) -> None:
    """Refresh the frozen fixture only after a validated real collector pass."""
    _SNAPSHOT_PATH.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = _SNAPSHOT_PATH.with_suffix(".json.tmp")
    payload = {
        "snapshot_version": 1,
        "source": "amazon_department_collector",
        "generated_from": "validated_real_integration_run",
        "collector_output": collector_output,
    }
    try:
        with temporary_path.open("w", encoding="utf-8", newline="\n") as stream:
            json.dump(payload, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
        os.replace(temporary_path, _SNAPSHOT_PATH)
    finally:
        if temporary_path.exists():
            temporary_path.unlink()


def _snapshot_display_path() -> str:
    return "tests/fixtures/amazon_department_collector_snapshot.json"


def _top_nav_records(result: Any) -> list[dict[str, Any]]:
    if not isinstance(result, dict):
        return []
    return [
        node
        for category in result.get("categories", [])
        if isinstance(category, dict)
        for topic in category.get("topics", [])
        if isinstance(topic, dict)
        for node in topic.get("top_nav", [])
        if isinstance(node, dict)
    ]


def _failures(
    result: Any,
    top_nav: list[dict[str, Any]],
    collector_error: str | None,
) -> list[str]:
    if collector_error:
        return [collector_error]
    failures = (
        []
        if isinstance(result, dict) and result.get("status") == "PASS"
        else ["Collector did not return PASS."]
    )
    failures.extend(
        f"{node.get('topic')} -> {node.get('name')}: "
        f"{node.get('mega_menu_error') or node.get('mega_menu_status')}"
        for node in top_nav
        if node.get("mega_menu_status")
        in {"MEGA_MENU_NOT_FOUND", "MEGA_MENU_COLLECTION_FAILED"}
    )
    failures.extend(
        f"{node.get('topic')} -> {node.get('name')}: "
        "visible usable links were not content-ready"
        for node in top_nav
        if (node.get("associated_flyout_visible_link_count") or 0) > 0
        and not node.get("flyout_content_ready")
    )
    failures.extend(
        f"{node.get('topic')} -> {node.get('name')}: "
        "readiness inspection used a 50ms operation timeout"
        for node in top_nav
        if "Timeout 50ms exceeded" in str(node.get("mega_menu_error"))
    )
    return failures


def _report(
    result: Any,
    diagnostics: dict[str, Any],
    top_nav: list[dict[str, Any]],
    collector_error: str | None,
    failures: list[str],
) -> str:
    nav_rows = "".join(
        "<tr>"
        f"<td>{_v(node.get('category'))}</td>"
        f"<td>{_v(node.get('topic'))}</td>"
        f"<td>{_v(node.get('name'))}</td>"
        f"<td>{_v(node.get('data_nav_key'))}</td>"
        f"<td>{_v(node.get('expected_flyout_id'))}</td>"
        f"<td>{_v(node.get('aria_expanded_before'))}</td>"
        f"<td>{_v(node.get('aria_expanded_after'))}</td>"
        f"<td>{_v(node.get('associated_flyout_found'))}</td>"
        f"<td>{_v(node.get('associated_flyout_visible'))}</td>"
        f"<td>{_v(node.get('mega_menu_dom_found'))}</td>"
        f"<td>{_v(node.get('associated_flyout_link_count'))}</td>"
        f"<td>{_v(node.get('associated_flyout_visible_link_count'))}</td>"
        f"<td>{_v(node.get('flyout_content_ready'))}</td>"
        f"<td>{_v(node.get('flyout_source_unavailable'))}</td>"
        f"<td>{_v(node.get('flyout_rendered_text'))}</td>"
        f"<td>{_v(node.get('collection_elapsed_ms'))}</td>"
        f"<td>{_v(node.get('mega_menu_status'))}</td>"
        f"<td>{_v(node.get('mega_menu_count'))}</td>"
        f"<td>{_v(node.get('mega_menu_error'))}</td>"
        "</tr>"
        for node in top_nav
    )
    level4_rows = "".join(
        "<tr>"
        f"<td>{_v(link.get('category'))}</td>"
        f"<td>{_v(link.get('topic'))}</td>"
        f"<td>{_v(link.get('parent_name'))}</td>"
        f"<td>{index}</td>"
        f"<td>{_v(link.get('name'))}</td>"
        f"<td>{_v(link.get('id'))}</td>"
        f"<td>{_v(link.get('level'))}</td>"
        f"<td>{_v(link.get('url'))}</td>"
        "</tr>"
        for node in top_nav
        for index, link in enumerate(node.get("mega_menu", []), 1)
        if isinstance(link, dict)
    )
    summary_keys = (
        "direct_top_nav_total_count",
        "expandable_top_nav_count",
        "non_expandable_top_nav_count",
        "mega_menu_success_count",
        "flyout_source_unavailable_count",
        "mega_menu_not_found_count",
        "mega_menu_collection_failure_count",
        "level_4_node_total_count",
    )
    summary_rows = "".join(
        f"<tr><th>{escape(key)}</th><td>{_v(diagnostics.get(key))}</td></tr>"
        for key in summary_keys
    )
    raw = json.dumps(result, ensure_ascii=False, indent=2, default=str)
    colour = "#dcfce7" if not failures else "#fee2e2"
    style = (
        "body{font:15px system-ui;margin:32px;color:#172033}"
        "h1,h2{color:#17345d}"
        ".result{padding:16px;font-size:26px;font-weight:800;background:RESULT}"
        "table{border-collapse:collapse;width:100%;margin:12px 0 28px}"
        "th,td{border:1px solid #cbd5e1;padding:8px;text-align:left;vertical-align:top}"
        "th{background:#17345d;color:#fff}.wrap{overflow:auto}"
        "pre{white-space:pre-wrap;background:#111827;color:#e5e7eb;padding:16px}"
    ).replace("RESULT", colour)
    errors = [collector_error] if collector_error else failures
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><title>Amazon Top Nav Mega Menu</title>
<style>{style}</style></head><body>
<h1>Amazon Top Nav Mega Menu</h1><div class="result">{'PASS' if not failures else 'FAIL'}</div>
<p>Execution timestamp: {escape(datetime.now(UTC).isoformat())}</p>
<h2>Frozen baseline</h2><p>Category -&gt; Topic -&gt; Topic Page -&gt; Direct Top Nav</p>
<h2>Current milestone</h2><p>Direct Top Nav -&gt; Expandable -&gt; Hover -&gt; Associated Flyout -&gt; Mega Menu -&gt; Level-4 Links</p>
<h2>Summary</h2><table><tbody>{summary_rows}</tbody></table>
<h2>Top-nav table</h2><div class="wrap"><table><thead><tr>
<th>Category</th><th>Topic</th><th>Top Nav</th><th>Data Nav Key</th><th>Expected Flyout ID</th>
<th>Aria Before</th><th>Aria After</th><th>Flyout Found</th><th>Flyout Visible</th><th>.mega-menu Found</th>
<th>Flyout Link Count</th><th>Visible Link Count</th><th>Content Ready</th><th>Source Unavailable</th>
<th>Flyout Rendered Text</th><th>Elapsed ms</th><th>Status</th><th>Level-4 Count</th><th>Error</th>
</tr></thead><tbody>{nav_rows}</tbody></table></div>
<h2>Level-4 detail table</h2><div class="wrap"><table><thead><tr>
<th>Category</th><th>Topic</th><th>Top Nav Parent</th><th>#</th><th>Name</th><th>Amazon Node ID</th><th>Level</th><th>URL</th>
</tr></thead><tbody>{level4_rows}</tbody></table></div>
<h2>Errors</h2>{_list(errors)}<h2>Raw JSON</h2><pre>{escape(raw)}</pre></body></html>"""


def _print_summary(
    diagnostics: dict[str, Any],
    top_nav: list[dict[str, Any]],
    collector_error: str | None,
    failures: list[str],
    report_path: Path,
) -> None:
    print("=" * 60)
    print("AMAZON TOP-NAV MEGA-MENU TEST")
    print("=" * 60)
    print(f"\nOverall: {'PASS' if not failures else 'FAIL'}")
    print(f"Topics processed: {len({node.get('topic') for node in top_nav})}")
    print(f"Direct top-nav items: {diagnostics.get('direct_top_nav_total_count', 0)}")
    print(f"\nExpandable top-nav: {diagnostics.get('expandable_top_nav_count', 0)}")
    print(f"Non-expandable top-nav: {diagnostics.get('non_expandable_top_nav_count', 0)}")
    print(f"\nMega-menu successes: {diagnostics.get('mega_menu_success_count', 0)}")
    print(f"Flyout source unavailable: {diagnostics.get('flyout_source_unavailable_count', 0)}")
    print(f"Mega-menu not found: {diagnostics.get('mega_menu_not_found_count', 0)}")
    print(
        "Mega-menu collection failures: "
        f"{diagnostics.get('mega_menu_collection_failure_count', 0)}"
    )
    print(f"\nLevel-4 nodes collected: {diagnostics.get('level_4_node_total_count', 0)}")
    print("\nTop Nav Results:")
    for node in top_nav:
        status = node.get("mega_menu_status")
        prefix = f"{node.get('topic')} -> {node.get('name')}"
        if status == "NOT_EXPANDABLE":
            print(f"[NO EXPAND] {prefix}")
        elif status == "MEGA_MENU_COLLECTED":
            print(f"[PASS] {prefix} - {node.get('mega_menu_count')} Level-4 nodes")
        elif status == "FLYOUT_SOURCE_UNAVAILABLE":
            print(f"[SOURCE UNAVAILABLE] {prefix}")
        else:
            print(f"[FAIL] {prefix} - {node.get('mega_menu_error') or status}")
    if collector_error:
        print(f"[FAIL] Collector - {collector_error}")
    print(f"\nHTML report:\n{report_path.as_posix()}\n{'=' * 60}")


def _list(values: list[str | None]) -> str:
    if not values:
        return "<p>None</p>"
    return "<ul>" + "".join(f"<li>{escape(str(value))}</li>" for value in values) + "</ul>"


def _v(value: Any) -> str:
    return "None" if value is None else escape(str(value))


if __name__ == "__main__":
    test_amazon_top_nav_mega_menu()
