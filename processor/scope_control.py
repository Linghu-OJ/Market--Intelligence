"""Conservative, audit-preserving commercial exploration scope control."""

from __future__ import annotations

from datetime import UTC, datetime
import re
from typing import Any


class ScopeControl:
    """Apply frozen Noise Gates and a Level-4 structural sanity check."""

    _ACCOUNT_NAMES = {
        "sign in", "your account", "account", "your profile", "profile", "orders",
        "customer service",
    }
    _PROMOTIONAL_NAMES = {
        "today's deals", "todays deals", "best sellers", "new arrivals",
        "vouchers", "voucher", "outlet", "deals", "deal", "shop now",
    }
    _MEMBERSHIP_NAMES = {"amazon prime", "prime", "prime student", "subscribe & save"}
    _REGISTRY_NAMES = {"wishlist", "wish list", "baby wishlist", "wedding list"}
    _DIGITAL_ONLY_NAMES = {
        "prime video", "amazon appstore", "amazon app store", "mobile apps",
    }
    _NAVIGATION_NAMES = {
        "see all", "shop all", "back", "home", "next page", "previous page",
        "click here", "click here.", "unsure? click here", "unsure? click here.",
    }
    _PLATFORM_SERVICE_NAMES = {"amazon pickup locations"}
    _TOPIC_SERVICE_PATTERN = re.compile(
        r"\b(?:installation|assembly|repair|service booking|services?)\b"
    )
    _NODE_SERVICE_PHRASES = (" assembly", "installation", "repair service", "service booking")

    def apply(self, deduplicator_output: dict[str, Any]) -> dict[str, Any]:
        """Classify Topics first, then nodes only for Topics retained downstream."""
        entries, duplicate_entries, failed_entries = self._input_data(deduplicator_output)
        scoped_entries: list[dict[str, Any]] = []
        failed_topic_entries: list[dict[str, Any]] = []
        for entry in entries:
            topic_gate = self._topic_decision_record(entry)
            if topic_gate["decision"] == "FAIL":
                failed_topic_entries.append({"entry": entry, "topic_noise_gate": topic_gate})
            else:
                scoped_entries.append(self._scope_entry(entry, topic_gate))
        summary = self._summary(scoped_entries, failed_topic_entries)
        return {
            "source": "scope_control",
            "timestamp": datetime.now(UTC).isoformat(),
            "data": {
                "entries": scoped_entries,
                "failed_topic_entries": failed_topic_entries,
                "duplicate_entries": duplicate_entries,
                "failed_entries": failed_entries,
            },
            "summary": summary,
        }

    @staticmethod
    def _input_data(
        deduplicator_output: Any,
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
        if not isinstance(deduplicator_output, dict):
            raise ValueError("deduplicator_output must be a dictionary.")
        data = deduplicator_output.get("data")
        if not isinstance(data, dict):
            raise ValueError("deduplicator_output requires a data dictionary.")
        entries = data.get("entries")
        duplicates = data.get("duplicate_entries", [])
        failed_entries = data.get("failed_entries", [])
        if not all(isinstance(value, list) for value in (entries, duplicates, failed_entries)):
            raise ValueError("deduplicator output entries and audit lists must be lists.")
        for entry in entries:
            if not isinstance(entry, dict):
                raise ValueError("Each retained Topic entry must be a dictionary.")
            for field in ("direct_top_nav", "level_4_nodes"):
                if not isinstance(entry.get(field), list):
                    raise ValueError(f"Each retained Topic entry requires {field} as a list.")
                if not all(isinstance(node, dict) for node in entry[field]):
                    raise ValueError("Each navigation node must be a dictionary.")
        return entries, duplicates, failed_entries

    def _topic_decision_record(self, entry: dict[str, Any]) -> dict[str, str]:
        code, reason = self._topic_noise_decision(entry)
        return {
            "decision": "PASS" if code == "PASS_NOT_NOISE" else "FAIL",
            "reason_code": code,
            "reason": reason,
        }

    def _topic_noise_decision(self, entry: dict[str, Any]) -> tuple[str, str]:
        topic = self._normalise(entry.get("topic"))
        if self._TOPIC_SERVICE_PATTERN.search(topic):
            return "FAIL_SERVICE", "Clearly service, installation, assembly, or repair Topic."
        if topic in self._REGISTRY_NAMES:
            return "FAIL_REGISTRY", "Wishlist or registry Topic."
        if topic in self._ACCOUNT_NAMES:
            return "FAIL_ACCOUNT", "Account or authentication Topic."
        if topic in self._MEMBERSHIP_NAMES:
            return "FAIL_MEMBERSHIP", "Amazon membership or platform feature Topic."
        if topic in self._DIGITAL_ONLY_NAMES:
            return "FAIL_DIGITAL_ONLY", "Clearly digital-only Topic."
        if topic in self._PLATFORM_SERVICE_NAMES:
            return "FAIL_SERVICE", "Platform or logistics service destination Topic."
        return "PASS_NOT_NOISE", "No deterministic Topic noise rule matched."

    def _scope_entry(
        self, entry: dict[str, Any], topic_noise_gate: dict[str, str]
    ) -> dict[str, Any]:
        """Keep Topic metadata and source order while separating node pass/fail audits."""
        direct = [self._decision_record(node) for node in entry["direct_top_nav"]]
        level_4 = [self._decision_record(node) for node in entry["level_4_nodes"]]
        structural_records = [
            self._structural_decision_record(entry, record)
            for record in level_4
            if record["noise_gate"]["decision"] == "PASS"
        ]
        level_4_partition = self._partition(level_4)
        level_4_partition.update({
            "structural_decisions": structural_records,
            "structural_passed": [
                record for record in structural_records
                if record["structural_check"]["decision"] == "PASS"
            ],
            "structural_failed": [
                record for record in structural_records
                if record["structural_check"]["decision"] == "FAIL"
            ],
        })
        scoped = dict(entry)
        scoped.update({
            "topic_noise_gate": topic_noise_gate,
            "direct_top_nav": self._partition(direct),
            "level_4_nodes": level_4_partition,
        })
        return scoped

    def _decision_record(self, node: dict[str, Any]) -> dict[str, Any]:
        code, reason = self._noise_decision(node)
        return {
            "node": node,
            "noise_gate": {
                "decision": "PASS" if code == "PASS_NOT_NOISE" else "FAIL",
                "reason_code": code,
                "reason": reason,
            },
        }

    def _noise_decision(self, node: dict[str, Any]) -> tuple[str, str]:
        """Fail only clear deterministic non-product exploration navigation."""
        name = self._normalise(node.get("name"))
        url = self._normalise(node.get("url"))
        if name in self._ACCOUNT_NAMES or "/signin" in url:
            return "FAIL_ACCOUNT", "Account or authentication navigation node."
        if name in self._PROMOTIONAL_NAMES:
            return "FAIL_PROMOTIONAL", "Promotional navigation node."
        if name in self._MEMBERSHIP_NAMES:
            return "FAIL_MEMBERSHIP", "Amazon membership or platform feature."
        if name in self._REGISTRY_NAMES or "/wedding" in url or "/baby-reg" in url:
            return "FAIL_REGISTRY", "Wishlist or registry navigation node."
        if name in self._DIGITAL_ONLY_NAMES:
            return "FAIL_DIGITAL_ONLY", "Clearly digital-only navigation node."
        if name in self._NAVIGATION_NAMES:
            return "FAIL_NAVIGATION_ACTION", "Generic navigation/action node rather than a product exploration branch."
        if name in self._PLATFORM_SERVICE_NAMES:
            return "FAIL_SERVICE", "Platform or logistics service destination."
        if any(phrase in f" {name}" for phrase in self._NODE_SERVICE_PHRASES):
            return "FAIL_SERVICE", "Service or booking navigation node."
        return "PASS_NOT_NOISE", "No deterministic noise rule matched."

    def _structural_decision_record(
        self, entry: dict[str, Any], record: dict[str, Any]
    ) -> dict[str, Any]:
        """Validate Level-4 linkage only; representative Topic has no semantic role."""
        code, reason = self._structural_decision(entry.get("direct_top_nav", []), record["node"])
        enriched = dict(record)
        enriched["structural_check"] = {
            "decision": "FAIL" if code.startswith("FAIL_") else "PASS",
            "reason_code": code,
            "reason": reason,
        }
        return enriched

    def _structural_decision(
        self, direct_top_nav: Any, node: Any
    ) -> tuple[str, str]:
        """Fail only required-field or parent-linkage violations in the frozen schema."""
        if not isinstance(node, dict) or node.get("level") != 4:
            return "FAIL_INVALID_LEVEL4_NODE", "Level-4 node does not satisfy the frozen Level-4 schema."
        if not all(isinstance(node.get(field), str) and node[field].strip() for field in ("name", "url")):
            return "FAIL_INVALID_LEVEL4_NODE", "Level-4 node is missing a required name or URL."
        parent_name = node.get("parent_name")
        if not isinstance(parent_name, str) or not parent_name.strip():
            return "FAIL_PARENT_MISSING", "Level-4 node is missing its required Level-3 parent reference."
        parent_names = {
            self._normalise(parent.get("name"))
            for parent in direct_top_nav
            if isinstance(parent, dict) and parent.get("level") == 3
        } if isinstance(direct_top_nav, list) else set()
        if self._normalise(parent_name) not in parent_names:
            return "FAIL_PARENT_NOT_FOUND", "Level-4 parent reference is not present among this entry's Level-3 nodes."
        return "PASS_STRUCTURALLY_VALID", "Level-4 node has a valid Level-3 parent linkage."

    @staticmethod
    def _partition(records: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
        return {
            "decisions": records,
            "passed": [record for record in records if record["noise_gate"]["decision"] == "PASS"],
            "failed": [record for record in records if record["noise_gate"]["decision"] == "FAIL"],
        }

    @staticmethod
    def _normalise(value: Any) -> str:
        return re.sub(r"\s+", " ", value).strip().casefold() if isinstance(value, str) else ""

    @staticmethod
    def _summary(
        entries: list[dict[str, Any]], failed_topic_entries: list[dict[str, Any]]
    ) -> dict[str, int]:
        def counts(field: str) -> tuple[int, int, int]:
            input_count = sum(len(entry[field]["decisions"]) for entry in entries)
            passed = sum(len(entry[field]["passed"]) for entry in entries)
            return input_count, passed, input_count - passed

        def failed_topic_nodes(field: str) -> int:
            return sum(len(item["entry"][field]) for item in failed_topic_entries)

        direct_input, direct_pass, direct_fail = counts("direct_top_nav")
        level_4_input, level_4_pass, level_4_fail = counts("level_4_nodes")
        structural_input = sum(len(entry["level_4_nodes"]["structural_decisions"]) for entry in entries)
        structural_pass = sum(len(entry["level_4_nodes"]["structural_passed"]) for entry in entries)
        return {
            "input_topic_entries": len(entries) + len(failed_topic_entries),
            "topic_pass": len(entries),
            "topic_fail": len(failed_topic_entries),
            "input_direct_top_nav_nodes": direct_input,
            "direct_top_nav_pass": direct_pass,
            "direct_top_nav_fail": direct_fail,
            "input_level_4_nodes": level_4_input,
            "level_4_pass": level_4_pass,
            "level_4_fail": level_4_fail,
            "total_node_input": direct_input + level_4_input,
            "total_node_pass": direct_pass + level_4_pass,
            "total_node_fail": direct_fail + level_4_fail,
            # Retained aliases preserve the prior node-summary contract.
            "total_input_nodes": direct_input + level_4_input,
            "total_pass": direct_pass + level_4_pass,
            "total_fail": direct_fail + level_4_fail,
            "topic_fail_direct_top_nav_nodes_audited": failed_topic_nodes("direct_top_nav"),
            "topic_fail_level_4_nodes_audited": failed_topic_nodes("level_4_nodes"),
            "structural_input_level_4_nodes": structural_input,
            "structural_pass": structural_pass,
            "structural_fail": structural_input - structural_pass,
            "final_level_4_retained": structural_pass,
        }
