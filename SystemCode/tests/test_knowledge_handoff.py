"""Static knowledge integrity, canonical facts and future assistant acceptance specs."""

import hashlib
import json
from pathlib import Path, PurePosixPath, PureWindowsPath
import re

import pytest


ROOT = Path(__file__).resolve().parents[2]
PACKAGE = ROOT / "SystemCode/backend/knowledge"
MANIFEST = json.loads((PACKAGE / "manifest.json").read_text(encoding="utf-8"))
SOURCES = {item["source_id"]: item for item in MANIFEST["sources"] + MANIFEST["context_sources"]}
CITATIONS = {
    section["citation_id"]: (document, section)
    for document in MANIFEST["documents"] for section in document["sections"]
}


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def text(document_id):
    entry = next(item for item in MANIFEST["documents"] if item["document_id"] == document_id)
    return (PACKAGE / entry["path"]).read_text(encoding="utf-8")


def source_json(source_id):
    return json.loads((ROOT / SOURCES[source_id]["path"]).read_text(encoding="utf-8"))


def local_path(base, relative):
    assert not PurePosixPath(relative).is_absolute()
    assert not PureWindowsPath(relative).is_absolute()
    assert ".." not in PurePosixPath(relative).parts
    path = (base / relative).resolve()
    assert path.is_relative_to(ROOT)
    assert path.is_file()
    return path


def test_manifest_records_versions_and_truthful_review_basis():
    assert MANIFEST["package_id"] == "roadguard-a-knowledge"
    assert MANIFEST["package_version"] == "a-knowledge-v8"
    assert MANIFEST["owner"] == "A"
    assert MANIFEST["review_basis"] == "repository_consistency_review"
    assert MANIFEST["review"]["performed_by"] == "coding_agent_on_behalf_of_A"
    assert MANIFEST["review"]["human_or_expert_approval"] is False
    assert MANIFEST["hash_algorithm"] == "sha256_raw_file_bytes"
    assert 4 <= len(MANIFEST["documents"]) <= 6
    assert len({document["document_id"] for document in MANIFEST["documents"]}) == len(MANIFEST["documents"])
    assert len(CITATIONS) == sum(len(document["sections"]) for document in MANIFEST["documents"])
    assert len(SOURCES) == len(MANIFEST["sources"]) + len(MANIFEST["context_sources"])
    project = source_json("src-project-config")
    assert MANIFEST["versions"]["scope_version"] == project["scenario"]["study_boundary"]["scope_version"]
    assert MANIFEST["versions"]["depot_version"] == project["scenario"]["depot"]["depot_version"]
    assert MANIFEST["versions"]["label_schema_version"] == source_json("src-label-schema")["schema_version"]
    assert MANIFEST["versions"]["rule_version"] == source_json("src-demo-rules")["rule_version"]
    assert MANIFEST["versions"]["workflow_contract_version"] == "a-workflow-v5"


@pytest.mark.parametrize("source", MANIFEST["sources"], ids=lambda item: item["source_id"])
def test_pinned_source_hashes_match_canonical_repository_files(source):
    path = local_path(ROOT, source["path"])
    assert re.fullmatch(r"[0-9a-f]{64}", source["sha256"])
    assert digest(path) == source["sha256"]


def test_mutable_background_documents_are_explicitly_unhashed():
    mutable = {
        "AGENTS.md", "Miscellaneous/PROJECT_SCOPE.md", "Miscellaneous/TEAM_WORK_ALLOCATION.md",
        "Miscellaneous/API_CONTRACT.md", "README.md", "Miscellaneous/IMPLEMENTATION_PLAN.md",
        "Miscellaneous/INSPECTION_REVIEW_TASK_WORKFLOW.md",
    }
    assert not mutable.intersection(source["path"] for source in MANIFEST["sources"])
    for source in MANIFEST["context_sources"]:
        assert source["integrity"] == "unhashed_mutable_context"
        assert "sha256" not in source
        local_path(ROOT, source["path"])


@pytest.mark.parametrize("document", MANIFEST["documents"], ids=lambda item: item["document_id"])
def test_document_hashes_metadata_anchors_classifications_and_sources(document):
    path = local_path(PACKAGE, document["path"])
    content = path.read_text(encoding="utf-8")
    assert digest(path) == document["sha256"]
    assert document["owner"] == "A"
    versions = {"rg-kb-workflow": "5", "rg-kb-pending": "4", "rg-kb-labels": "2", "rg-kb-demo-rules": "2", "rg-kb-assistant": "2"}
    assert document["document_version"] == versions.get(document["document_id"], "1")
    assert document["review_basis"] == "repository_consistency_review"
    assert f'document_id：`{document["document_id"]}`' in content
    assert f'document_version：`{document["document_version"]}`' in content
    anchors = re.findall(r'<a id="([a-z0-9-]+)"></a>', content)
    assert len(anchors) == len(set(anchors))
    assert set(anchors) == {section["section_id"] for section in document["sections"]}
    for section in document["sections"]:
        assert section["citation_id"] == document["document_id"] + "#" + section["section_id"]
        assert section["classification"] in MANIFEST["classification_vocabulary"]
        block = content.split(f'<a id="{section["section_id"]}"></a>', 1)[1].split('<a id="', 1)[0]
        assert f'classification：`{section["classification"]}`' in block
        assert f'citation_id：`{section["citation_id"]}`' in block
        assert section["source_ids"]
        for source_id in section["source_ids"]:
            assert source_id in SOURCES
            assert f'[{source_id}](' in block


def test_every_markdown_link_is_a_valid_local_repository_reference():
    for path in PACKAGE.glob("*.md"):
        content = path.read_text(encoding="utf-8")
        assert not re.search(r"[A-Za-z]:[\\/]|file://|/Users/|/home/", content)
        for label, href in re.findall(r"\[([^\]]+)\]\(([^)]+)\)", content):
            target_path, _, anchor = href.partition("#")
            assert "://" not in href
            target = (path.parent / target_path).resolve()
            assert target.is_relative_to(ROOT) and target.is_file()
            if label in SOURCES:
                assert target == (ROOT / SOURCES[label]["path"]).resolve()
            if anchor:
                assert f'<a id="{anchor}"></a>' in target.read_text(encoding="utf-8")


def test_all_eight_label_definitions_exactly_match_central_schema():
    entries = source_json("src-label-schema")["classes"]
    rows = [
        [cell.strip() for cell in line.strip("|").split("|")]
        for line in text("rg-kb-labels").splitlines() if re.match(r"^\| [0-7] \|", line)
    ]
    expected = [
        [str(entry[key]) for key in (
            "class_id", "source_name", "label_key", "display_name_zh",
            "base_rdd2022_category_code", "source_visual_qualifier",
        )]
        for entry in entries
    ]
    assert len(rows) == 8 and rows == expected
    assert "不是量测" in text("rg-kb-labels")
    assert "不证明损坏轻微" in text("rg-kb-labels")


def test_demo_rule_table_and_gate_are_exact_and_marked_as_assumptions():
    source = source_json("src-demo-rules")
    content = text("rg-kb-demo-rules")
    rows = [
        [cell.strip() for cell in line.strip("|").split("|")]
        for line in content.splitlines() if line.startswith("| ") and not line.startswith("| label_key ") and not line.startswith("| ---")
    ]
    assert len(rows) == 8
    assert {row[0] for row in rows} == set(source["rules"])
    for label, severity, priority, minutes in rows:
        rule = source["rules"][label]
        assert (severity, priority, minutes) == (rule["severity"], rule["priority"], str(rule["service_minutes"]))
    assert source["is_demo"] is True and source["status"] == "demonstration_assumptions"
    assert f'confidence_threshold={source["confidence_threshold"]:.2f}' in content
    assert f'selection_strategy={source["selection_strategy"]}' in content
    assert "任一检测低于阈值" in content and "全部大于等于阈值" in content
    assert all(section["classification"] == "demo_assumption" for document in MANIFEST["documents"] if document["document_id"] == "rg-kb-demo-rules" for section in document["sections"])


def test_scope_numbers_crews_unknown_return_and_evidence_limits_match_config():
    project = source_json("src-project-config")
    content = text("rg-kb-scope")
    for crew_id in project["planning"]["crew_ids"]:
        assert f"`{crew_id}`" in content
    for field in ("latitude", "longitude", "depot_version"):
        assert str(project["scenario"]["depot"][field]) in content
    assert project["planning"]["default_crew_count"] == 4
    assert project["planning"]["return_to_depot"] is None
    assert "待确认" in content and "不能默认为不返回" in content
    assert "不是道路网络" in content and "user_declared" in content


def test_ten_acceptance_cases_use_valid_sources_and_grounded_support_statuses():
    entry = MANIFEST["acceptance_cases"]
    path = local_path(PACKAGE, entry["path"])
    assert digest(path) == entry["sha256"]
    suite = json.loads(path.read_text(encoding="utf-8"))
    assert suite["package_version"] == MANIFEST["package_version"]
    assert suite["purpose"] == "synthetic_acceptance_specs_not_executed_assistant_results"
    cases = suite["cases"]
    assert len(cases) == entry["case_count"] == 10
    assert len({case["case_id"] for case in cases}) == 10
    assert {case["expected_status"] for case in cases} == {"supported", "insufficient_data"}
    for case in cases:
        assert case["is_synthetic_case"] is True
        assert case["expected_supported"] is (case["expected_status"] == "supported")
        assert case["question"] and case["expected_grounded_points"] and case["forbidden_claims"]
        assert case["expected_citations"] and all(citation in CITATIONS for citation in case["expected_citations"])
        expected_sources = {source for citation in case["expected_citations"] for source in CITATIONS[citation][1]["source_ids"]}
        assert set(case["source_ids"]) == expected_sources
        assert bool(case["required_runtime_evidence"]) is (case["expected_status"] == "insufficient_data")
    mismatch = next(case for case in cases if case["case_id"] == "qa-06")
    assert mismatch["provided_context"]["rule_version"] != MANIFEST["versions"]["rule_version"]
    assert mismatch["expected_status"] == "insufficient_data"
    assert "matching_rule_version" in mismatch["required_runtime_evidence"]
    assert "不能默默改用最新静态表格" in text("rg-kb-assistant")


def test_ingestion_guide_and_package_have_no_machine_specific_paths_or_runtime_code():
    guide = MANIFEST["ingestion_guide"]
    assert digest(local_path(PACKAGE, guide["path"])) == guide["sha256"]
    for path in PACKAGE.iterdir():
        assert path.suffix in {".md", ".json"}
        assert not re.search(r"[A-Za-z]:[\\/]|file://|/Users/|/home/", path.read_text(encoding="utf-8"))


def test_shipped_knowledge_files_use_lf_so_git_normalization_preserves_hashes():
    for path in PACKAGE.iterdir():
        if path.suffix in {".md", ".json"}:
            content = path.read_bytes()
            assert b"\r" not in content, f"{path.name} must use LF before hashing"
            assert content.endswith(b"\n")
