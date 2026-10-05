# Theme Agent Production V1.4 Repository Source of Truth

Status: Production V1.4 collected and frozen. This file is the repository-level authority for the active Theme Agent line and for this cleanup. It deliberately does not change the prompt, schema, scoring, threshold, Batch transport, or business output.

## Active production freeze

- Active version: `THEME_AGENT_SOURCE_OF_TRUTH_V1_1_LLM_ONLY_POC_V1_4`
- Prompt version: `THEME_AGENT_SOURCE_OF_TRUTH_V1_1_LLM_ONLY_POC_V1_4`
- Prompt SHA-256: `887d150f1214afd5d328f96b0f82899a395b0efcaa982245ccb115ca79b9f95b`
- Schema SHA-256: `73b17ddcff72987d9abcc32ce476febe4202fc21b54b6c17dcabea1496767e54`
- Model: `gpt-5.6-sol`
- Endpoint: `/v1/responses`
- Completion window: `24h`
- Decision threshold: `total_score > 3 -> generated`; `total_score <= 3 -> rejected`
- Authority: LLM-only for scores, decision, Themes, and seed baselines.
- Local code does not recalculate scores, rewrite decisions, run `pair_level_validation`, run a semantic validator, or use synchronous fallback.

## Production Batch evidence

- Source input: `data/THEME_AGENT_PAIR_INPUT_PRODUCTION_V1_FINAL.json`
- Source input SHA-256: `DB814F9435BBECAC0EFDE885ECA2B1F39A1392989F8C5B268F46908939692B4A`
- Pair count: `3525`; unique pair IDs: `3525`
- Batch request count: `3525`; completed: `3525`; failed: `0`; technical invalid: `0`
- Batch ID: `batch_6ac3a2de865c8190a1f2f8c961475c02`
- Batch input JSONL: `data/theme_agent/production_v1_4/THEME_AGENT_BATCH_INPUT_PRODUCTION_V1_4.jsonl`
- Batch input SHA-256: `7c13e3bbf83d530c8b504406354dd14c6ad61dfb1e16bf40262211c7cd9485a5`
- Transport SHA-256: `4771cc94ed1b2b1e14bc63fd15ac00ed8381d60d477c94a966bd3b94f8d7dc05`
- Manifest: `data/theme_agent/production_v1_4/THEME_AGENT_BATCH_MANIFEST_PRODUCTION_V1_4.json`
- Raw output: `data/theme_agent/production_v1_4/THEME_AGENT_BATCH_RAW_OUTPUT_PRODUCTION_V1_4.jsonl` (3525 parseable lines; retained locally)
- Raw errors: `data/theme_agent/production_v1_4/THEME_AGENT_BATCH_RAW_ERRORS_PRODUCTION_V1_4.jsonl` (0 lines; retained locally)
- Normalized output: `data/theme_agent/production_v1_4/THEME_AGENT_OUTPUT_PRODUCTION_V1_4.json` (3525 results; every result carries the corresponding LLM pair ID)
- Report: `reports/THEME_AGENT_PRODUCTION_REPORT_V1_4.html`
- Input file ID: `file-NGnRYJa527C1e2miLwhLgg`
- Output file ID: `file-AeXgWvEh7QLkEzks8Ma8oH`
- Error file ID: `null`
- Manifest status: `COLLECTED`; Batch status: `completed`; API fallback: `false`; production run: `false`.

## Required repository inventory (recorded before deletion)

All paths below were untracked in the pre-cleanup checkout unless otherwise noted. “Active references” means the current Production V1.4 import graph or required audit/test coverage. Large Batch JSONL artifacts are retained locally and are explicitly gitignored; they are not silently deleted.

### KEEP_AND_TRACK

| Path | Size | References / reason |
|---|---:|---|
| `data/THEME_AGENT_PAIR_INPUT_PRODUCTION_V1_FINAL.json` | 5,087,166 bytes | Frozen production source input; SHA is part of the freeze. |
| `data/theme_agent/production/Theme_Agent_Source_of_Truth_v1.1.docx` | 51,678 bytes | Official business specification. |
| `data/theme_agent/production_v1_4/THEME_AGENT_BATCH_MANIFEST_PRODUCTION_V1_4.json` | 2,932 bytes | Immutable Batch ID, file IDs, hashes, counts, timestamps, and final status. |
| `data/theme_agent/production_v1_4/THEME_AGENT_OUTPUT_PRODUCTION_V1_4.json` | 24,086,948 bytes | Formal normalized Production V1.4 business result. |
| `data/theme_agent/poc_v1_4/THEME_AGENT_30_PAIR_INPUT_V1_4.json` | 63,216 bytes | V1.4 selection evidence; 30-pair selection hash and content are recorded in the V1.4 manifest. |
| `data/theme_agent/poc_v1_4/THEME_AGENT_30_PAIR_MANIFEST_V1_4.json` | 274,407 bytes | V1.4 POC audit/selection evidence. |
| `data/theme_agent/poc_v1_3/THEME_AGENT_30_PAIR_INPUT_V1_3.json` | 63,216 bytes | Immutable V1.3 selection bytes required by the V1.4 verification helper; not an active request/output artifact. |
| `data/theme_agent/poc_v1_3/THEME_AGENT_30_PAIR_MANIFEST_V1_3.json` | 301,993 bytes | Historical V1.3 selection/hash evidence referenced by V1.4 verification; the V1.3 output/raw artifacts are deleted. |
| `processor/theme_agent_prompts.py` | pre-cleanup inventory | Imported by the unchanged Batch transport. |
| `processor/theme_agent_prompts_v1_4.py` | pre-cleanup inventory | Frozen V1.4 prompt and schema implementation. |
| `processor/theme_agent_poc.py` | pre-cleanup inventory | Imported by active production and unchanged transport compatibility helpers. |
| `processor/theme_agent_poc_v2.py` | pre-cleanup inventory | Imported by unchanged Batch transport. |
| `processor/theme_agent_poc_v3.py` | pre-cleanup inventory | Imported by unchanged Batch transport and shared test helper. |
| `processor/theme_agent_production_v1.py` | pre-cleanup inventory | Active V1.4 input/hash/validation dependency. |
| `processor/theme_agent_production_v1_batch.py` | pre-cleanup inventory | Active unchanged Batch transport; transport SHA is frozen above. |
| `processor/theme_agent_semantic_validator.py` | pre-cleanup inventory | Import-time compatibility dependency of `theme_agent_production_v1`; not invoked by V1.4. |
| `processor/theme_agent_prompt_v1_4.txt` | pre-cleanup inventory | Human-readable frozen prompt evidence. |
| `scripts/manual_theme_agent_production_v1_4.py` | pre-cleanup inventory | Production submit/status/collect/normalize/report state machine. |
| `tests/manual_theme_agent_30_poc_v1_4.py` | pre-cleanup inventory | V1.4 POC test helper. |
| `tests/manual_theme_agent_30_poc_v1_1.py` | pre-cleanup inventory | Shared deterministic selection/transport helper imported by the V1.4 POC helper. |
| `tests/manual_theme_agent_google_trends_test.py` | pre-cleanup inventory | Shared atomic/report helpers imported by Production V1.4. |
| `tests/test_theme_agent_poc_v1_4.py` | pre-cleanup inventory | V1.4 prompt/schema/POC coverage. |
| `tests/test_theme_agent_production_v1_4.py` | pre-cleanup inventory | V1.4 production state, parser, report, fallback, and manifest coverage. |
| `tests/test_theme_agent_production_v1.py` | pre-cleanup inventory | Coverage for the active production input/validation dependency. |
| `tests/test_theme_agent_production_v1_batch.py` | pre-cleanup inventory | Deterministic Batch transport coverage. |
| `docs/theme_agent/THEME_AGENT_PRODUCTION_V1_4_FREEZE.md` | pre-cleanup inventory | Production freeze record. |
| `reports/THEME_AGENT_30_PAIR_POC_REPORT_V1_4.html` | pre-cleanup inventory | Minimal V1.4 POC audit report. |
| `reports/THEME_AGENT_PRODUCTION_REPORT_V1_4.html` | pre-cleanup inventory | Final Production report. |
| `docs/theme_agent/THEME_AGENT_V1_4_REPOSITORY_SOURCE_OF_TRUTH.md` | new | This repository authority and cleanup inventory. |

### KEEP_LOCAL_OR_ARCHIVE

| Path | Size | References / reason |
|---|---:|---|
| `data/theme_agent/production_v1_4/THEME_AGENT_BATCH_INPUT_PRODUCTION_V1_4.jsonl` | 39,015,105 bytes | Reproducible Batch input retained locally; large artifact, gitignored. |
| `data/theme_agent/production_v1_4/THEME_AGENT_BATCH_RAW_OUTPUT_PRODUCTION_V1_4.jsonl` | 62,150,070 bytes | Sole raw Batch output retained locally; large artifact, gitignored. |
| `data/theme_agent/production_v1_4/THEME_AGENT_BATCH_RAW_ERRORS_PRODUCTION_V1_4.jsonl` | 0 bytes | Raw error artifact retained locally; gitignored with the raw files. |
| `data/theme_agent/archive/v1_1/*.jsonl` | 350,002 + 668,586 + 0 bytes | Immutable V1.1 JSONL evidence moved without content changes; no active import. SHA-256: `D760EDED4C6F89A4CE0ED5160EF1749B064007ED21B5044C6667CB515660D578`, `B194072A8145F6074787B420AB6A297C4C8C263D3421A712FF89749EB7CF1B4C`, `E3B0C44298FC1C149AFBF4C8996FB92427AE41E4649B934CA495991B7852B855`. |
| `data/theme_agent/archive/v1_2/*.jsonl` | 408,742 + 755,442 + 0 bytes | Immutable V1.2 JSONL evidence moved without content changes; no active import. SHA-256: `2C27B296809D0AAFE714C1793D612DE7485F4757B79A6D4AE91CFD7E99538CCE`, `980AEB618770A5A94B14DA57B1370D7363952C5B573F4BCA56E47E12F4E8530F`, `E3B0C44298FC1C149AFBF4C8996FB92427AE41E4649B934CA495991B7852B855`. |

The V1.1/V1.2 archive move records original paths, destination paths, and SHA-256 values in this document’s cleanup history below. Archived JSONL is historical evidence only and is not used by active request construction.

### DELETE

The following obsolete, reproducible, diagnostic, failed, or superseded files have no active Production V1.4 import and no unique coverage after V1.4 tests are retained:

- `data/theme_agent/diagnostic_batch/THEME_AGENT_30_PAIR_BATCH_INPUT.jsonl`
- `data/theme_agent/diagnostic_batch/THEME_AGENT_30_PAIR_BATCH_MANIFEST.json`
- `data/theme_agent/diagnostic_batch/THEME_AGENT_30_PAIR_BATCH_OUTPUT.jsonl`
- `data/theme_agent/diagnostic_batch/THEME_AGENT_30_PAIR_SELECTION.json`
- `data/theme_agent/diagnostic_batch/THEME_AGENT_BATCH_DIAGNOSTIC_INPUT.jsonl`
- `data/theme_agent/diagnostic_batch/THEME_AGENT_BATCH_DIAGNOSTIC_MANIFEST.json`
- `data/theme_agent/diagnostic_batch/THEME_AGENT_BATCH_MINIMAL_INPUT.jsonl`
- `data/theme_agent/diagnostic_batch/THEME_AGENT_BATCH_MINIMAL_MANIFEST.json`
- `data/theme_agent/diagnostic_batch/THEME_AGENT_BATCH_MINIMAL_OUTPUT.jsonl`
- `data/theme_agent/diagnostic_batch/THEME_AGENT_KEYWORD_REGRESSION_INPUT.jsonl`
- `data/theme_agent/diagnostic_batch/THEME_AGENT_KEYWORD_REGRESSION_MANIFEST.json`
- `data/theme_agent/diagnostic_batch/THEME_AGENT_KEYWORD_REGRESSION_OUTPUT.jsonl`
- `data/theme_agent/google_trends_test/` (all V1/V2 input, manifest, output, and selection artifacts)
- `data/theme_agent/poc/` (all V1/V2/V3 POC input and output JSON)
- `data/theme_agent/poc_v1_1/THEME_AGENT_30_PAIR_INPUT_V1_1.json`
- `data/theme_agent/poc_v1_1/THEME_AGENT_30_PAIR_MANIFEST_V1_1.json`
- `data/theme_agent/poc_v1_1/THEME_AGENT_30_PAIR_OUTPUT_V1_1.json`
- `data/theme_agent/poc_v1_2/THEME_AGENT_30_PAIR_INPUT_V1_2.json`
- `data/theme_agent/poc_v1_2/THEME_AGENT_30_PAIR_MANIFEST_V1_2.json`
- `data/theme_agent/poc_v1_2/THEME_AGENT_30_PAIR_OUTPUT_V1_2.json`
- `data/theme_agent/poc_v1_4/THEME_AGENT_30_PAIR_BATCH_INPUT_V1_4.jsonl`
- `data/theme_agent/poc_v1_4/THEME_AGENT_30_PAIR_OUTPUT_V1_4.json`
- `data/theme_agent/poc_v1_4/THEME_AGENT_30_PAIR_RAW_ERRORS_V1_4.jsonl`
- `data/theme_agent/poc_v1_4/THEME_AGENT_30_PAIR_RAW_OUTPUT_V1_4.jsonl`
- `data/theme_agent/poc_v1_3/THEME_AGENT_30_PAIR_BATCH_INPUT_V1_3.jsonl`
- `data/theme_agent/poc_v1_3/THEME_AGENT_30_PAIR_OUTPUT_V1_3.json`
- `data/theme_agent/poc_v1_3/THEME_AGENT_30_PAIR_RAW_ERRORS_V1_3.jsonl`
- `data/theme_agent/poc_v1_3/THEME_AGENT_30_PAIR_RAW_OUTPUT_V1_3.jsonl`
- `data/theme_agent/production/THEME_AGENT_BATCH_INPUT_PRODUCTION_V1.jsonl`
- `data/theme_agent/production/THEME_AGENT_BATCH_MANIFEST_PRODUCTION_V1.json`
- `processor/theme_agent_prompt_v1_3.txt`
- `tests/manual_theme_agent_30_batch.py`
- `tests/manual_theme_agent_30_poc_v1_2.py`
- `tests/manual_theme_agent_30_poc_v1_3.py`
- `tests/manual_theme_agent_batch_file_access_diagnostic.py`
- `tests/manual_theme_agent_batch_minimal.py`
- `tests/manual_theme_agent_keyword_regression.py`
- `tests/manual_theme_agent_prompt_refactor_audit.py`
- `tests/manual_theme_agent_rule_review_v1_3.py`
- `tests/test_theme_agent_poc.py`
- `tests/test_theme_agent_poc_v2.py`
- `tests/test_theme_agent_poc_v3.py`
- `tests/test_theme_agent_30_poc_v1_1.py`
- `tests/test_theme_agent_30_poc_v1_2.py`
- `tests/test_theme_agent_30_poc_v1_3.py` (not present in the pre-cleanup checkout; no deletion required)
- `tests/test_theme_agent_rule_review_v1_3.py`
- `reports/THEME_AGENT_30_PAIR_BATCH_REPORT.html`
- `reports/THEME_AGENT_30_PAIR_POC_REPORT_V1_1.html`
- `reports/THEME_AGENT_30_PAIR_POC_REPORT_V1_2.html`
- `reports/THEME_AGENT_30_PAIR_POC_REPORT_V1_3.html`
- `reports/THEME_AGENT_BATCH_MINIMAL_DIAGNOSTIC.html`
- `reports/THEME_AGENT_GOOGLE_TRENDS_TEST_REPORT_V1.html`
- `reports/THEME_AGENT_GOOGLE_TRENDS_TEST_REPORT_V2.html`
- `reports/THEME_AGENT_KEYWORD_REGRESSION_REPORT.html`
- `reports/THEME_AGENT_POC_REPORT_V1.html`
- `reports/THEME_AGENT_POC_REPORT_V2.html`
- `reports/THEME_AGENT_POC_REPORT_V3.html`
- `reports/THEME_AGENT_PRODUCTION_REPORT_V1.html`
- `reports/THEME_AGENT_RULE_CHANGE_REVIEW_V1_3.html`

Deletion is limited to these explicit Theme Agent paths. No Amazon Expansion, Lifestyle Expansion, Embedding, Similarity, Quality Gate, Relationship Agent/Mapper, frozen canonical data, `.env`, API key, remote, branch, or unrelated user file is in scope.

## Historical and active-path statement

The V1.1/V1.2 JSONL files are immutable historical evidence, not active inputs. The V1.4 POC report plus its manifest and selection JSON are retained as the minimum calibration evidence. Old POC, diagnostic, keyword-regression, rule-review, and failed-production reports are not active pipeline artifacts. The old POC modules are retained only where the unchanged Batch transport or active import graph requires them; they are not an alternative active business implementation.

## Git record

- Required cleanup commit message: `chore(theme-agent): freeze production v1.4 and remove obsolete POC files`
- Cleanup commit hash: pending until the commit is created; a post-commit documentation follow-up will record the exact hash without rewriting history.
- Branch: `recovery/relationship-v3-minimal-batch`
- Push target: `origin/recovery/relationship-v3-minimal-batch`
- No force push, reset, checkout, merge, remote change, or history rewrite is permitted.

## Cleanup verification record

- Pre-deletion Production gate: passed (`COLLECTED`, completed 3525/3525, failed 0, raw output present, raw errors 0, normalized output present, report present).
- Pre-deletion raw line count: 3525; raw custom IDs unique: 3525; inner LLM JSON pair IDs unique: 3525.
- Pre-deletion normalized result count: 3525; normalized IDs unique: 3525; normalized LLM pair IDs present: 3525.
- Theme Agent focused tests after cleanup: `28/28 passed`.
- Baseline HEAD: `2a82d9d69bf382835ac6c96656d47459f5e4046b`.
- Baseline command (run in a clean detached worktree): `& '.\\.venv\\Scripts\\python.exe' -B -m unittest discover -v` using the same absolute project virtualenv executable.
- Baseline result: `1 test`, `0 passed`, `1 import error` for missing `collector.amazon_category`; the HEAD tree does not contain the current untracked Theme/Relationship test set, so it cannot reproduce the current suite composition.
- Current result: `30 tests`, `28 passed`, `2 import errors` for missing `collector.amazon_category` and missing `tests.test_relationship_matrix_poc`.
- The cleanup deletion list contains neither missing module, and the current Relationship Mapper test is an untracked retained file, but the HEAD baseline does not exercise that untracked test. Therefore the required identical-error baseline was not established; these failures are not classified as pre-existing and regression delta remains undetermined.
- Temporary baseline worktree was removed safely. Full-suite gate remains blocked; no commit or push has been made.
