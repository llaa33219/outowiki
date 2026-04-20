from __future__ import annotations

from datetime import datetime

import pytest
from pydantic import ValidationError

from outowiki.models.analysis import AnalysisResult, IntentAnalysis
from outowiki.models.content import DocumentMetadata, RawContent, WikiDocument
from outowiki.models.plans import (
    CreatePlan,
    DeletePlan,
    MergePlan,
    ModifyPlan,
    Plan,
    PlanType,
    SplitPlan,
)
from outowiki.models.search import SearchQuery, SearchResult


@pytest.fixture
def fixed_now():
    return datetime(2025, 1, 15, 12, 0, 0)


@pytest.fixture
def sample_raw_content():
    return RawContent(
        content="Hello world",
        content_type="conversation",
    )


@pytest.fixture
def sample_wiki_document():
    return WikiDocument(
        path="knowledge/python",
        title="Python",
        content="# Python\n\nA programming language.",
        frontmatter={"tags": ["python"], "category": "knowledge"},
        created=datetime(2024, 1, 1),
        modified=datetime(2024, 6, 1),
        category="knowledge",
    )


@pytest.fixture
def sample_metadata():
    return DocumentMetadata(
        title="Test Doc",
        category="test",
    )


@pytest.fixture
def sample_analysis_result():
    return AnalysisResult(
        information_type="conversation",
        key_topic="python",
        specific_content="User likes Python",
        confidence_score=0.9,
        importance_score=0.8,
        suggested_action=PlanType.CREATE,
    )


@pytest.fixture
def sample_intent_analysis():
    return IntentAnalysis(
        information_type="knowledge",
        specificity_level="general",
        temporal_interest="all_time",
        exploration_start="root",
        confidence_requirement="low",
    )


class TestRawContent:

    def test_creation_with_required_fields(self, sample_raw_content):
        assert sample_raw_content.content == "Hello world"
        assert sample_raw_content.content_type == "conversation"

    def test_default_timestamp_is_set(self, sample_raw_content):
        assert sample_raw_content.timestamp is not None
        assert isinstance(sample_raw_content.timestamp, datetime)

    def test_default_metadata_is_none(self, sample_raw_content):
        assert sample_raw_content.metadata is None

    def test_metadata_can_be_provided(self):
        raw = RawContent(
            content="data",
            content_type="structured",
            metadata={"source": "api", "version": 2},
        )
        assert raw.metadata == {"source": "api", "version": 2}

    def test_custom_timestamp(self, fixed_now):
        raw = RawContent(
            content="test",
            content_type="external",
            timestamp=fixed_now,
        )
        assert raw.timestamp == fixed_now

    @pytest.mark.parametrize("valid_type", [
        "conversation",
        "agent_internal",
        "external",
        "structured",
    ])
    def test_valid_content_types(self, valid_type):
        raw = RawContent(content="test", content_type=valid_type)
        assert raw.content_type == valid_type

    def test_invalid_content_type_raises(self):
        with pytest.raises(ValidationError):
            RawContent(content="test", content_type="invalid_type")

    def test_missing_content_raises(self):
        with pytest.raises(ValidationError):
            RawContent(content_type="conversation")

    def test_missing_content_type_raises(self):
        with pytest.raises(ValidationError):
            RawContent(content="some content")


class TestWikiDocument:

    def test_creation_with_all_fields(self, sample_wiki_document):
        doc = sample_wiki_document
        assert doc.path == "knowledge/python"
        assert doc.title == "Python"
        assert doc.category == "knowledge"
        assert doc.frontmatter["tags"] == ["python"]

    def test_default_empty_backlinks(self, sample_wiki_document):
        assert sample_wiki_document.backlinks == []

    def test_default_empty_tags(self, sample_wiki_document):
        assert sample_wiki_document.tags == []

    def test_default_empty_related(self, sample_wiki_document):
        assert sample_wiki_document.related == []

    def test_frontmatter_dict_handling(self):
        fm = {
            "tags": ["a", "b"],
            "category": "notes",
            "custom_field": 42,
            "nested": {"key": "value"},
        }
        doc = WikiDocument(
            path="notes/test",
            title="Test",
            content="body",
            frontmatter=fm,
            created=datetime(2024, 1, 1),
            modified=datetime(2024, 1, 1),
            category="notes",
        )
        assert doc.frontmatter == fm
        assert doc.frontmatter["nested"]["key"] == "value"

    def test_lists_can_be_populated(self):
        doc = WikiDocument(
            path="a/b",
            title="T",
            content="c",
            frontmatter={},
            created=datetime(2024, 1, 1),
            modified=datetime(2024, 1, 1),
            category="cat",
            backlinks=["x/y"],
            tags=["tag1", "tag2"],
            related=["r1", "r2"],
        )
        assert doc.backlinks == ["x/y"]
        assert doc.tags == ["tag1", "tag2"]
        assert doc.related == ["r1", "r2"]

    def test_missing_required_field_raises(self):
        with pytest.raises(ValidationError):
            WikiDocument(
                title="No path",
                content="content",
                frontmatter={},
                created=datetime(2024, 1, 1),
                modified=datetime(2024, 1, 1),
                category="test",
            )


class TestDocumentMetadata:

    def test_required_fields_only(self, sample_metadata):
        assert sample_metadata.title == "Test Doc"
        assert sample_metadata.category == "test"

    def test_default_empty_tags(self, sample_metadata):
        assert sample_metadata.tags == []

    def test_default_empty_related(self, sample_metadata):
        assert sample_metadata.related == []

    def test_default_empty_custom(self, sample_metadata):
        assert sample_metadata.custom == {}

    def test_all_fields_populated(self):
        meta = DocumentMetadata(
            title="Full",
            tags=["t1", "t2"],
            category="cat",
            related=["r1"],
            custom={"key": "val"},
        )
        assert meta.tags == ["t1", "t2"]
        assert meta.related == ["r1"]
        assert meta.custom == {"key": "val"}

    def test_missing_title_raises(self):
        with pytest.raises(ValidationError):
            DocumentMetadata(category="test")

    def test_category_is_optional(self):
        doc = DocumentMetadata(title="No category")
        assert doc.category is None


class TestSearchQuery:

    def test_creation_with_query_only(self):
        q = SearchQuery(query="python")
        assert q.query == "python"
        assert q.context is None
        assert q.category_filter is None
        assert q.time_range is None

    def test_default_max_results(self):
        q = SearchQuery(query="test")
        assert q.max_results == 10

    def test_default_return_mode(self):
        q = SearchQuery(query="test")
        assert q.return_mode == "path"

    @pytest.mark.parametrize("mode", ["path", "summary", "full"])
    def test_valid_return_modes(self, mode):
        q = SearchQuery(query="test", return_mode=mode)
        assert q.return_mode == mode

    def test_invalid_return_mode_raises(self):
        with pytest.raises(ValidationError):
            SearchQuery(query="test", return_mode="invalid")

    def test_custom_max_results(self):
        q = SearchQuery(query="test", max_results=50)
        assert q.max_results == 50

    def test_all_optional_fields(self):
        start = datetime(2024, 1, 1)
        end = datetime(2024, 12, 31)
        q = SearchQuery(
            query="test",
            context="some context",
            category_filter="knowledge",
            time_range=(start, end),
            max_results=5,
            return_mode="full",
        )
        assert q.context == "some context"
        assert q.category_filter == "knowledge"
        assert q.time_range == (start, end)
        assert q.max_results == 5
        assert q.return_mode == "full"

    def test_missing_query_raises(self):
        with pytest.raises(ValidationError):
            SearchQuery()


class TestSearchResult:

    def test_creation_with_paths_only(self):
        sr = SearchResult(paths=["a/b", "c/d"])
        assert sr.paths == ["a/b", "c/d"]
        assert sr.summaries is None
        assert sr.documents is None
        assert sr.query_analysis is None

    def test_with_summaries(self):
        sr = SearchResult(
            paths=["a/b"],
            summaries={"a/b": "A summary"},
        )
        assert sr.summaries == {"a/b": "A summary"}

    def test_with_documents(self, sample_wiki_document):
        sr = SearchResult(
            paths=["knowledge/python"],
            documents={"knowledge/python": sample_wiki_document},
        )
        assert "knowledge/python" in sr.documents
        assert sr.documents["knowledge/python"].title == "Python"

    def test_with_query_analysis(self, sample_intent_analysis):
        sr = SearchResult(
            paths=["x"],
            query_analysis=sample_intent_analysis,
        )
        assert sr.query_analysis.information_type == "knowledge"

    def test_empty_paths_list(self):
        sr = SearchResult(paths=[])
        assert sr.paths == []

    def test_missing_paths_raises(self):
        with pytest.raises(ValidationError):
            SearchResult()


class TestAnalysisResult:

    def test_creation_with_required_fields(self, sample_analysis_result):
        ar = sample_analysis_result
        assert ar.information_type == "conversation"
        assert ar.key_topic == "python"
        assert ar.specific_content == "User likes Python"
        assert ar.confidence_score == 0.9
        assert ar.importance_score == 0.8
        assert ar.suggested_action == PlanType.CREATE

    def test_default_empty_existing_relations(self, sample_analysis_result):
        assert sample_analysis_result.existing_relations == []

    def test_default_none_temporal_range(self, sample_analysis_result):
        assert sample_analysis_result.temporal_range is None

    def test_default_empty_target_documents(self, sample_analysis_result):
        assert sample_analysis_result.target_documents == []

    @pytest.mark.parametrize("score", [0.0, 0.5, 1.0])
    def test_confidence_score_valid_bounds(self, score):
        ar = AnalysisResult(
            information_type="test",
            key_topic="test",
            specific_content="test",
            confidence_score=score,
            importance_score=0.5,
            suggested_action=PlanType.MODIFY,
        )
        assert ar.confidence_score == score

    @pytest.mark.parametrize("score", [0.0, 0.5, 1.0])
    def test_importance_score_valid_bounds(self, score):
        ar = AnalysisResult(
            information_type="test",
            key_topic="test",
            specific_content="test",
            confidence_score=0.5,
            importance_score=score,
            suggested_action=PlanType.MODIFY,
        )
        assert ar.importance_score == score

    def test_confidence_score_below_zero_raises(self):
        with pytest.raises(ValidationError):
            AnalysisResult(
                information_type="test",
                key_topic="test",
                specific_content="test",
                confidence_score=-0.1,
                importance_score=0.5,
                suggested_action=PlanType.CREATE,
            )

    def test_confidence_score_above_one_raises(self):
        with pytest.raises(ValidationError):
            AnalysisResult(
                information_type="test",
                key_topic="test",
                specific_content="test",
                confidence_score=1.1,
                importance_score=0.5,
                suggested_action=PlanType.CREATE,
            )

    def test_importance_score_below_zero_raises(self):
        with pytest.raises(ValidationError):
            AnalysisResult(
                information_type="test",
                key_topic="test",
                specific_content="test",
                confidence_score=0.5,
                importance_score=-0.01,
                suggested_action=PlanType.CREATE,
            )

    def test_importance_score_above_one_raises(self):
        with pytest.raises(ValidationError):
            AnalysisResult(
                information_type="test",
                key_topic="test",
                specific_content="test",
                confidence_score=0.5,
                importance_score=1.5,
                suggested_action=PlanType.CREATE,
            )

    def test_all_fields_populated(self):
        ar = AnalysisResult(
            information_type="agent_internal",
            key_topic="design",
            specific_content="Architecture decision",
            existing_relations=["a/b", "c/d"],
            temporal_range="2024-Q1",
            confidence_score=0.75,
            importance_score=0.6,
            suggested_action=PlanType.MERGE,
            target_documents=["x/y"],
        )
        assert ar.existing_relations == ["a/b", "c/d"]
        assert ar.temporal_range == "2024-Q1"
        assert ar.target_documents == ["x/y"]


class TestIntentAnalysis:

    def test_creation_with_required_fields(self, sample_intent_analysis):
        ia = sample_intent_analysis
        assert ia.information_type == "knowledge"
        assert ia.exploration_start == "root"

    @pytest.mark.parametrize("level", [
        "very_specific",
        "specific",
        "general",
        "very_general",
    ])
    def test_valid_specificity_levels(self, level):
        ia = IntentAnalysis(
            information_type="test",
            specificity_level=level,
            temporal_interest="all_time",
            exploration_start="root",
            confidence_requirement="low",
        )
        assert ia.specificity_level == level

    def test_invalid_specificity_level_raises(self):
        with pytest.raises(ValidationError):
            IntentAnalysis(
                information_type="test",
                specificity_level="moderate",
                temporal_interest="all_time",
                exploration_start="root",
                confidence_requirement="low",
            )

    @pytest.mark.parametrize("temporal", [
        "recent",
        "all_time",
        "specific_period",
    ])
    def test_valid_temporal_interest_values(self, temporal):
        ia = IntentAnalysis(
            information_type="test",
            specificity_level="general",
            temporal_interest=temporal,
            exploration_start="root",
            confidence_requirement="low",
        )
        assert ia.temporal_interest == temporal

    def test_invalid_temporal_interest_raises(self):
        with pytest.raises(ValidationError):
            IntentAnalysis(
                information_type="test",
                specificity_level="general",
                temporal_interest="yesterday",
                exploration_start="root",
                confidence_requirement="low",
            )

    @pytest.mark.parametrize("req", ["high", "medium", "low"])
    def test_valid_confidence_requirements(self, req):
        ia = IntentAnalysis(
            information_type="test",
            specificity_level="general",
            temporal_interest="all_time",
            exploration_start="root",
            confidence_requirement=req,
        )
        assert ia.confidence_requirement == req

    def test_invalid_confidence_requirement_raises(self):
        with pytest.raises(ValidationError):
            IntentAnalysis(
                information_type="test",
                specificity_level="general",
                temporal_interest="all_time",
                exploration_start="root",
                confidence_requirement="critical",
            )

    def test_missing_required_field_raises(self):
        with pytest.raises(ValidationError):
            IntentAnalysis(
                information_type="test",
                specificity_level="general",
                temporal_interest="all_time",
            )


class TestPlanType:

    @pytest.mark.parametrize("member, value", [
        (PlanType.CREATE, "create"),
        (PlanType.MODIFY, "modify"),
        (PlanType.MERGE, "merge"),
        (PlanType.SPLIT, "split"),
        (PlanType.DELETE, "delete"),
    ])
    def test_enum_values(self, member, value):
        assert member.value == value

    def test_all_five_members_exist(self):
        assert len(PlanType) == 5

    def test_from_string(self):
        assert PlanType("create") is PlanType.CREATE

    def test_from_invalid_string_raises(self):
        with pytest.raises(ValueError):
            PlanType("nonexistent")


class TestPlan:

    def test_creation(self):
        plan = Plan(
            plan_type=PlanType.CREATE,
            target_path="a/b",
            reason="test reason",
        )
        assert plan.plan_type == PlanType.CREATE
        assert plan.target_path == "a/b"
        assert plan.reason == "test reason"
        assert plan.priority == 0

    def test_custom_priority(self):
        plan = Plan(
            plan_type=PlanType.MODIFY,
            target_path="x",
            reason="r",
            priority=5,
        )
        assert plan.priority == 5


class TestCreatePlan:

    def test_default_plan_type(self):
        plan = CreatePlan(
            target_path="new/doc",
            reason="new info",
            content="# New Doc\n\nContent here.",
            metadata=DocumentMetadata(title="New Doc", category="notes"),
        )
        assert plan.plan_type == PlanType.CREATE

    def test_required_fields(self):
        plan = CreatePlan(
            target_path="a/b",
            reason="test",
            content="body",
            metadata=DocumentMetadata(title="T", category="c"),
        )
        assert plan.content == "body"
        assert plan.metadata.title == "T"

    def test_default_empty_backlinks_to_add(self):
        plan = CreatePlan(
            target_path="x",
            reason="r",
            content="c",
            metadata=DocumentMetadata(title="T", category="c"),
        )
        assert plan.backlinks_to_add == []

    def test_with_backlinks(self):
        plan = CreatePlan(
            target_path="x",
            reason="r",
            content="c",
            metadata=DocumentMetadata(title="T", category="c"),
            backlinks_to_add=["ref/one", "ref/two"],
        )
        assert plan.backlinks_to_add == ["ref/one", "ref/two"]

    def test_missing_content_raises(self):
        with pytest.raises(ValidationError):
            CreatePlan(
                target_path="x",
                reason="r",
                metadata=DocumentMetadata(title="T", category="c"),
            )

    def test_missing_metadata_raises(self):
        with pytest.raises(ValidationError):
            CreatePlan(
                target_path="x",
                reason="r",
                content="c",
            )


class TestModifyPlan:

    def test_default_plan_type(self):
        plan = ModifyPlan(
            target_path="docs/existing",
            reason="update needed",
            modifications=[{"section": "intro", "op": "replace", "content": "new intro"}],
        )
        assert plan.plan_type == PlanType.MODIFY

    def test_required_fields(self):
        plan = ModifyPlan(
            target_path="a/b",
            reason="r",
            modifications=[{"key": "val"}],
        )
        assert plan.modifications == [{"key": "val"}]

    def test_default_empty_backlinks_to_update(self):
        plan = ModifyPlan(
            target_path="x",
            reason="r",
            modifications=[],
        )
        assert plan.backlinks_to_update == []

    def test_with_backlinks(self):
        plan = ModifyPlan(
            target_path="x",
            reason="r",
            modifications=[],
            backlinks_to_update=["b1", "b2"],
        )
        assert plan.backlinks_to_update == ["b1", "b2"]

    def test_missing_modifications_raises(self):
        with pytest.raises(ValidationError):
            ModifyPlan(
                target_path="x",
                reason="r",
            )


class TestMergePlan:

    def test_default_plan_type(self):
        plan = MergePlan(
            target_path="merged/doc",
            reason="consolidate",
            source_paths=["a", "b"],
            merged_content="# Merged\n\nCombined.",
        )
        assert plan.plan_type == PlanType.MERGE

    def test_required_fields(self):
        plan = MergePlan(
            target_path="x",
            reason="r",
            source_paths=["s1", "s2"],
            merged_content="merged",
        )
        assert plan.source_paths == ["s1", "s2"]
        assert plan.merged_content == "merged"

    def test_default_redirect_sources_true(self):
        plan = MergePlan(
            target_path="x",
            reason="r",
            source_paths=["a"],
            merged_content="c",
        )
        assert plan.redirect_sources is True

    def test_redirect_sources_can_be_false(self):
        plan = MergePlan(
            target_path="x",
            reason="r",
            source_paths=["a"],
            merged_content="c",
            redirect_sources=False,
        )
        assert plan.redirect_sources is False

    def test_missing_source_paths_raises(self):
        with pytest.raises(ValidationError):
            MergePlan(
                target_path="x",
                reason="r",
                merged_content="c",
            )


class TestSplitPlan:

    def test_default_plan_type(self):
        plan = SplitPlan(
            target_path="big/doc",
            reason="too large",
            sections_to_split=[{"title": "Part A", "path": "big/part-a"}],
            summary_for_main="See sub-documents.",
        )
        assert plan.plan_type == PlanType.SPLIT

    def test_required_fields(self):
        plan = SplitPlan(
            target_path="x",
            reason="r",
            sections_to_split=[{"title": "Sec", "path": "x/sec"}],
            summary_for_main="summary text",
        )
        assert plan.sections_to_split == [{"title": "Sec", "path": "x/sec"}]
        assert plan.summary_for_main == "summary text"

    def test_missing_sections_to_split_raises(self):
        with pytest.raises(ValidationError):
            SplitPlan(
                target_path="x",
                reason="r",
                summary_for_main="s",
            )

    def test_missing_summary_raises(self):
        with pytest.raises(ValidationError):
            SplitPlan(
                target_path="x",
                reason="r",
                sections_to_split=[],
            )


class TestDeletePlan:

    def test_default_plan_type(self):
        plan = DeletePlan(
            target_path="old/doc",
            reason="obsolete",
        )
        assert plan.plan_type == PlanType.DELETE

    def test_required_fields_only(self):
        plan = DeletePlan(
            target_path="x",
            reason="r",
        )
        assert plan.target_path == "x"
        assert plan.reason == "r"

    def test_default_remove_backlinks_true(self):
        plan = DeletePlan(target_path="x", reason="r")
        assert plan.remove_backlinks is True

    def test_remove_backlinks_can_be_false(self):
        plan = DeletePlan(target_path="x", reason="r", remove_backlinks=False)
        assert plan.remove_backlinks is False

    def test_default_redirect_to_none(self):
        plan = DeletePlan(target_path="x", reason="r")
        assert plan.redirect_to is None

    def test_redirect_to_can_be_set(self):
        plan = DeletePlan(
            target_path="x",
            reason="r",
            redirect_to="new/location",
        )
        assert plan.redirect_to == "new/location"

    def test_missing_target_path_raises(self):
        with pytest.raises(ValidationError):
            DeletePlan(reason="r")
