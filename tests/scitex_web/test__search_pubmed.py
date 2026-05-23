#!/usr/bin/env python3
# File: ./tests/scitex_web/test__search_pubmed.py
"""Tests for scitex_web._search_pubmed.

Network and downstream-lookup collaborators are injected as keyword
arguments and replaced with hand-rolled fakes. The pure functions
(_parse_abstract_xml, format_bibtex) get exercised directly. The async
path (fetch_async / batch__fetch_details) and the orchestration wrapper
(search_pubmed, run_main, parse_args sys.argv handling) are intentionally
NOT unit-tested here — those were pure mock theater in the previous test
file (patching aiohttp.ClientSession, asyncio.run, sys.argv, etc.) and
add no honest coverage. They are covered by the umbrella integration
suite when real network is available.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from io import StringIO
from typing import Any

import pytest

aiohttp = pytest.importorskip("aiohttp")  # used by _search_pubmed module imports
pytest.importorskip("scitex_web")

from scitex_web import (  # noqa: E402
    _fetch_details,
    _get_citation,
    _parse_abstract_xml,
    _search_pubmed,
    get_crossref_metrics,
    search_pubmed,
)
from scitex_web._search_pubmed import (  # noqa: E402
    format_bibtex,
    parse_args,
    save_bibtex,
)


@dataclass
class FakeResponse:
    """Slice of ``requests.Response`` that the SUT actually uses."""

    ok: bool = True
    text: str = ""
    payload: Any = None

    def json(self) -> Any:
        return self.payload


@dataclass
class FakeHttpGet:
    """Hand-rolled ``requests.get`` stand-in.

    Each call returns the next ``FakeResponse`` from ``responses``. Use
    ``raise_exception`` to simulate a network error. Captures the
    (url, params, kwargs) of every call.
    """

    responses: list = field(default_factory=list)
    raise_exception: Exception | None = None
    captured: list = field(default_factory=list)
    _idx: int = 0

    def __call__(self, url, **kwargs):
        self.captured.append({"url": url, **kwargs})
        if self.raise_exception is not None:
            raise self.raise_exception
        resp = self.responses[self._idx]
        self._idx += 1
        return resp


@dataclass
class FakeCitationLookup:
    """Records the pmids requested and returns canned bibtex per pmid."""

    canned: dict = field(default_factory=dict)
    default: str = ""
    requested: list = field(default_factory=list)

    def __call__(self, pmid: str) -> str:
        self.requested.append(pmid)
        return self.canned.get(pmid, self.default)


@dataclass
class FakeCrossrefLookup:
    """Records DOIs requested and returns canned metrics dicts."""

    canned: dict = field(default_factory=dict)
    requested: list = field(default_factory=list)

    def __call__(self, doi: str) -> dict:
        self.requested.append(doi)
        return self.canned.get(doi, {})


# --------------------------------------------------------------------------
# _search_pubmed
# --------------------------------------------------------------------------


class TestSearchPubmedSuccess:
    @pytest.fixture
    def search_response_payload(self) -> dict:
        return {"esearchresult": {"idlist": ["12345", "67890"], "count": "2"}}

    def test_returns_parsed_json_on_success(self, search_response_payload):
        # Arrange
        fake = FakeHttpGet(
            responses=[FakeResponse(ok=True, payload=search_response_payload)]
        )
        # Act
        result = _search_pubmed("test query", retmax=10, http_get=fake)
        # Assert
        assert result == search_response_payload

    def test_forwards_query_as_term_param(self, search_response_payload):
        # Arrange
        fake = FakeHttpGet(
            responses=[FakeResponse(ok=True, payload=search_response_payload)]
        )
        # Act
        _search_pubmed("epilepsy", retmax=500, http_get=fake)
        # Assert
        assert fake.captured[0]["params"]["term"] == "epilepsy"

    def test_forwards_retmax_param(self, search_response_payload):
        # Arrange
        fake = FakeHttpGet(
            responses=[FakeResponse(ok=True, payload=search_response_payload)]
        )
        # Act
        _search_pubmed("epilepsy", retmax=500, http_get=fake)
        # Assert
        assert fake.captured[0]["params"]["retmax"] == 500

    def test_uses_pubmed_db_param(self, search_response_payload):
        # Arrange
        fake = FakeHttpGet(
            responses=[FakeResponse(ok=True, payload=search_response_payload)]
        )
        # Act
        _search_pubmed("anything", http_get=fake)
        # Assert
        assert fake.captured[0]["params"]["db"] == "pubmed"


class TestSearchPubmedFailure:
    def test_returns_empty_dict_when_response_not_ok(self):
        # Arrange
        fake = FakeHttpGet(responses=[FakeResponse(ok=False)])
        # Act
        result = _search_pubmed("test query", http_get=fake)
        # Assert
        assert result == {}

    def test_returns_empty_dict_on_request_exception(self):
        # Arrange
        import requests as _requests

        fake = FakeHttpGet(
            raise_exception=_requests.exceptions.RequestException("boom")
        )
        # Act
        result = _search_pubmed("test query", http_get=fake)
        # Assert
        assert result == {}


# --------------------------------------------------------------------------
# _fetch_details
# --------------------------------------------------------------------------


class TestFetchDetailsSuccess:
    @pytest.fixture
    def details_result(self) -> dict:
        # Arrange — two responses: first XML abstracts, second JSON details
        fake = FakeHttpGet(
            responses=[
                FakeResponse(ok=True, text="<xml>abstract data</xml>"),
                FakeResponse(
                    ok=True, payload={"result": {"12345": {"title": "Test"}}}
                ),
            ]
        )
        # Act
        return _fetch_details(
            "webenv123", "query_key456", retstart=0, retmax=100, http_get=fake
        )

    def test_includes_xml_abstracts_text(self, details_result):
        # Arrange
        # Act
        # Assert
        assert details_result["abstracts"] == "<xml>abstract data</xml>"

    def test_includes_parsed_details_json(self, details_result):
        # Arrange
        # Act
        # Assert
        assert details_result["details"] == {"result": {"12345": {"title": "Test"}}}


class TestFetchDetailsFailure:
    def test_returns_empty_dict_when_abstract_response_not_ok(self):
        # Arrange
        fake = FakeHttpGet(
            responses=[
                FakeResponse(ok=False),
                FakeResponse(ok=True, payload={}),
            ]
        )
        # Act
        result = _fetch_details("env", "key", http_get=fake)
        # Assert
        assert result == {}

    def test_returns_empty_dict_when_details_response_not_ok(self):
        # Arrange
        fake = FakeHttpGet(
            responses=[
                FakeResponse(ok=True, text=""),
                FakeResponse(ok=False),
            ]
        )
        # Act
        result = _fetch_details("env", "key", http_get=fake)
        # Assert
        assert result == {}


class TestFetchDetailsParameters:
    @pytest.fixture
    def captured(self) -> list:
        # Arrange
        fake = FakeHttpGet(
            responses=[
                FakeResponse(ok=True, text=""),
                FakeResponse(ok=True, payload={}),
            ]
        )
        # Act
        _fetch_details("env123", "key456", retstart=100, retmax=50, http_get=fake)
        return fake.captured

    def test_makes_two_http_calls(self, captured):
        # Arrange
        # Act
        # Assert
        assert len(captured) == 2

    def test_first_call_forwards_webenv(self, captured):
        # Arrange
        # Act
        # Assert
        assert captured[0]["params"]["WebEnv"] == "env123"

    def test_first_call_forwards_query_key(self, captured):
        # Arrange
        # Act
        # Assert
        assert captured[0]["params"]["query_key"] == "key456"

    def test_first_call_forwards_retstart(self, captured):
        # Arrange
        # Act
        # Assert
        assert captured[0]["params"]["retstart"] == 100

    def test_first_call_forwards_retmax(self, captured):
        # Arrange
        # Act
        # Assert
        assert captured[0]["params"]["retmax"] == 50


# --------------------------------------------------------------------------
# _parse_abstract_xml (pure function — no injection)
# --------------------------------------------------------------------------


_COMPLETE_PUBMED_XML = """
<PubmedArticleSet>
    <PubmedArticle>
        <MedlineCitation>
            <PMID>12345</PMID>
            <Article>
                <Abstract>
                    <AbstractText>This is the abstract text.</AbstractText>
                </Abstract>
            </Article>
        </MedlineCitation>
        <PubmedData>
            <ArticleIdList>
                <ArticleId IdType="doi">10.1234/test.doi</ArticleId>
            </ArticleIdList>
        </PubmedData>
        <MeshHeadingList>
            <MeshHeading><DescriptorName>Keyword1</DescriptorName></MeshHeading>
            <MeshHeading><DescriptorName>Keyword2</DescriptorName></MeshHeading>
        </MeshHeadingList>
    </PubmedArticle>
</PubmedArticleSet>
"""


class TestParseAbstractXmlComplete:
    @pytest.fixture
    def parsed(self) -> dict:
        # Arrange / Act
        return _parse_abstract_xml(_COMPLETE_PUBMED_XML)

    def test_indexes_result_by_pmid_string(self, parsed):
        # Arrange
        # Act
        # Assert
        assert "12345" in parsed

    def test_first_tuple_element_is_abstract_text(self, parsed):
        # Arrange
        # Act
        # Assert
        assert parsed["12345"][0] == "This is the abstract text."

    def test_second_tuple_element_is_keyword_list(self, parsed):
        # Arrange
        # Act
        # Assert
        assert parsed["12345"][1] == ["Keyword1", "Keyword2"]

    def test_third_tuple_element_is_doi_string(self, parsed):
        # Arrange
        # Act
        # Assert
        assert parsed["12345"][2] == "10.1234/test.doi"


_MISSING_FIELDS_XML = """
<PubmedArticleSet>
    <PubmedArticle>
        <MedlineCitation>
            <PMID>67890</PMID>
            <Article>
                <Abstract />
            </Article>
        </MedlineCitation>
    </PubmedArticle>
</PubmedArticleSet>
"""


class TestParseAbstractXmlMissingFields:
    @pytest.fixture
    def parsed(self) -> dict:
        return _parse_abstract_xml(_MISSING_FIELDS_XML)

    def test_indexes_pmid_with_missing_fields(self, parsed):
        # Arrange
        # Act
        # Assert
        assert "67890" in parsed

    def test_empty_abstract_is_empty_string_or_none(self, parsed):
        # Arrange
        abstract = parsed["67890"][0]
        # Act
        # Assert
        assert abstract in ("", None)

    def test_missing_keywords_is_empty_list(self, parsed):
        # Arrange
        # Act
        # Assert
        assert parsed["67890"][1] == []

    def test_missing_doi_is_empty_string(self, parsed):
        # Arrange
        # Act
        # Assert
        assert parsed["67890"][2] == ""


_TWO_ARTICLE_XML = """
<PubmedArticleSet>
    <PubmedArticle>
        <MedlineCitation>
            <PMID>11111</PMID>
            <Article><Abstract><AbstractText>A</AbstractText></Abstract></Article>
        </MedlineCitation>
    </PubmedArticle>
    <PubmedArticle>
        <MedlineCitation>
            <PMID>22222</PMID>
            <Article><Abstract><AbstractText>B</AbstractText></Abstract></Article>
        </MedlineCitation>
    </PubmedArticle>
</PubmedArticleSet>
"""


class TestParseAbstractXmlMultipleArticles:
    @pytest.fixture
    def parsed(self) -> dict:
        return _parse_abstract_xml(_TWO_ARTICLE_XML)

    def test_emits_one_entry_per_article(self, parsed):
        # Arrange
        # Act
        # Assert
        assert len(parsed) == 2

    def test_emits_first_pmid_entry(self, parsed):
        # Arrange
        # Act
        # Assert
        assert "11111" in parsed

    def test_emits_second_pmid_entry(self, parsed):
        # Arrange
        # Act
        # Assert
        assert "22222" in parsed


# --------------------------------------------------------------------------
# _get_citation
# --------------------------------------------------------------------------


class TestGetCitation:
    def test_returns_response_text_when_ok(self):
        # Arrange
        fake = FakeHttpGet(
            responses=[FakeResponse(ok=True, text="@article{citation}")]
        )
        # Act
        result = _get_citation("12345", http_get=fake)
        # Assert
        assert result == "@article{citation}"

    def test_returns_empty_string_when_not_ok(self):
        # Arrange
        fake = FakeHttpGet(responses=[FakeResponse(ok=False)])
        # Act
        result = _get_citation("12345", http_get=fake)
        # Assert
        assert result == ""

    def test_forwards_pmid_to_id_param(self):
        # Arrange
        fake = FakeHttpGet(responses=[FakeResponse(ok=True, text="ok")])
        # Act
        _get_citation("12345", http_get=fake)
        # Assert
        assert fake.captured[0]["params"]["id"] == "12345"


# --------------------------------------------------------------------------
# get_crossref_metrics
# --------------------------------------------------------------------------


class TestGetCrossrefMetrics:
    @pytest.fixture
    def metrics(self) -> dict:
        # Arrange
        payload = {
            "message": {
                "is-referenced-by-count": 42,
                "type": "journal-article",
                "publisher": "Nature Publishing",
                "reference": [{"key": "1"}, {"key": "2"}, {"key": "3"}],
                "DOI": "10.1234/test",
            }
        }
        fake = FakeHttpGet(responses=[FakeResponse(ok=True, payload=payload)])
        # Act
        return get_crossref_metrics("10.1234/test", http_get=fake)

    def test_extracts_citations_count(self, metrics):
        # Arrange
        # Act
        # Assert
        assert metrics["citations"] == 42

    def test_extracts_type_from_message(self, metrics):
        # Arrange
        # Act
        # Assert
        assert metrics["type"] == "journal-article"

    def test_extracts_publisher_from_message(self, metrics):
        # Arrange
        # Act
        # Assert
        assert metrics["publisher"] == "Nature Publishing"

    def test_extracts_references_count(self, metrics):
        # Arrange
        # Act
        # Assert
        assert metrics["references"] == 3

    def test_extracts_doi_from_message(self, metrics):
        # Arrange
        # Act
        # Assert
        assert metrics["doi"] == "10.1234/test"

    def test_returns_empty_dict_when_response_not_ok(self):
        # Arrange
        fake = FakeHttpGet(responses=[FakeResponse(ok=False)])
        # Act
        result = get_crossref_metrics("10.1234/test", http_get=fake)
        # Assert
        assert result == {}


# --------------------------------------------------------------------------
# format_bibtex (pure function except crossref_lookup; we inject)
# --------------------------------------------------------------------------


class TestFormatBibtexComplete:
    @pytest.fixture
    def formatted(self) -> str:
        # Arrange
        paper = {
            "title": "Machine Learning for Medical Diagnosis",
            "authors": [{"name": "John A. Smith"}, {"name": "Jane B. Doe"}],
            "source": "Nature Medicine",
            "pubdate": "2023 Jul 15",
        }
        abstract_data = (
            "This is the abstract text.",
            ["Machine Learning", "Diagnosis"],
            "10.1038/s41591-023-12345",
        )
        crossref = FakeCrossrefLookup(
            canned={
                "10.1038/s41591-023-12345": {
                    "publisher": "Nature Publishing",
                    "references": 50,
                }
            }
        )
        # Act
        return format_bibtex(
            paper, "12345678", abstract_data, crossref_lookup=crossref
        )

    def test_emits_citation_key_with_first_author_and_year(self, formatted):
        # Arrange
        # Act
        # Assert
        assert "@article{John.Smith_2023_machine_learning" in formatted

    def test_includes_full_author_list(self, formatted):
        # Arrange
        # Act
        # Assert
        assert "author = {John A. Smith and Jane B. Doe}" in formatted

    def test_includes_title_field(self, formatted):
        # Arrange
        # Act
        # Assert
        assert "title = {Machine Learning for Medical Diagnosis}" in formatted

    def test_includes_journal_field(self, formatted):
        # Arrange
        # Act
        # Assert
        assert "journal = {Nature Medicine}" in formatted

    def test_includes_year_field(self, formatted):
        # Arrange
        # Act
        # Assert
        assert "year = {2023}" in formatted

    def test_includes_pmid_field(self, formatted):
        # Arrange
        # Act
        # Assert
        assert "pmid = {12345678}" in formatted

    def test_includes_doi_field(self, formatted):
        # Arrange
        # Act
        # Assert
        assert "doi = {10.1038/s41591-023-12345}" in formatted

    def test_includes_keywords_field(self, formatted):
        # Arrange
        # Act
        # Assert
        assert "keywords = {Machine Learning, Diagnosis}" in formatted

    def test_includes_abstract_field(self, formatted):
        # Arrange
        # Act
        # Assert
        assert "abstract = {This is the abstract text.}" in formatted


class TestFormatBibtexMinimal:
    @pytest.fixture
    def formatted(self) -> str:
        # Arrange
        paper = {
            "title": "A",
            "authors": [{"name": "X"}],
            "source": "Unknown Journal",
            "pubdate": "",
        }
        abstract_data = ("", [], "")
        # Act — empty doi means crossref_lookup is not called; default is fine
        return format_bibtex(paper, "99999", abstract_data)

    def test_emits_article_marker(self, formatted):
        # Arrange
        # Act
        # Assert
        assert "@article{" in formatted

    def test_emits_pmid_when_other_fields_minimal(self, formatted):
        # Arrange
        # Act
        # Assert
        assert "pmid = {99999}" in formatted


class TestFormatBibtexSpecialCharacters:
    def test_strips_non_alphanumeric_from_citation_key(self):
        # Arrange
        paper = {
            "title": "Test-Paper: With Special Characters!",
            "authors": [{"name": "O'Neill-Smith"}],
            "source": "Test Journal",
            "pubdate": "2023",
        }
        abstract_data = ("", [], "")
        # Act
        result = format_bibtex(paper, "11111", abstract_data)
        # Assert
        assert "@article{ONeillSmith.ONeillSmith_2023_testpaper_with" in result


# --------------------------------------------------------------------------
# save_bibtex — uses tmp_path for real filesystem
# --------------------------------------------------------------------------


class TestSaveBibtex:
    def test_writes_canned_citation_when_lookup_returns_text(self, tmp_path):
        # Arrange
        papers = {
            "12345": {
                "title": "Test Paper",
                "authors": [{"name": "John Doe"}],
                "source": "Test Journal",
                "pubdate": "2023",
            }
        }
        abstracts = {"12345": ("Abstract text", ["Keyword1"], "10.1234/test")}
        out_file = tmp_path / "test.bib"
        citation_lookup = FakeCitationLookup(
            canned={"12345": "@article{official_citation}"}
        )
        # Act
        save_bibtex(
            papers,
            abstracts,
            str(out_file),
            citation_lookup=citation_lookup,
            crossref_lookup=FakeCrossrefLookup(),
        )
        # Assert
        assert "@article{official_citation}" in out_file.read_text()

    def test_falls_back_to_format_bibtex_when_citation_empty(self, tmp_path):
        # Arrange
        papers = {
            "67890": {
                "title": "Test Paper Without Citation",
                "authors": [{"name": "Jane Smith"}],
                "source": "Another Journal",
                "pubdate": "2024",
            }
        }
        abstracts: dict = {}
        out_file = tmp_path / "fallback.bib"
        citation_lookup = FakeCitationLookup(default="")
        # Act
        save_bibtex(
            papers,
            abstracts,
            str(out_file),
            citation_lookup=citation_lookup,
            crossref_lookup=FakeCrossrefLookup(),
        )
        # Assert
        assert "@article{" in out_file.read_text()

    def test_skips_uids_key_when_iterating_papers(self, tmp_path):
        # Arrange
        papers = {
            "uids": ["12345"],
            "12345": {
                "title": "Real Paper",
                "authors": [{"name": "X"}],
                "source": "J",
                "pubdate": "2024",
            },
        }
        abstracts: dict = {}
        out_file = tmp_path / "skip.bib"
        citation_lookup = FakeCitationLookup(default="")
        # Act
        save_bibtex(
            papers,
            abstracts,
            str(out_file),
            citation_lookup=citation_lookup,
            crossref_lookup=FakeCrossrefLookup(),
        )
        # Assert — citation_lookup was queried only for the real pmid, not "uids"
        assert citation_lookup.requested == ["12345"]


# --------------------------------------------------------------------------
# parse_args
# --------------------------------------------------------------------------


@pytest.fixture
def argv(request):
    """`yield`-based replacement for ``patch.dict("sys.argv", [...])``.

    Pass ``request.param`` as the argv list; restored on teardown.
    """
    import sys

    previous = sys.argv
    sys.argv = list(request.param)
    try:
        yield list(request.param)
    finally:
        sys.argv = previous


class TestParseArgs:
    @pytest.mark.parametrize(
        "argv", [["prog", "--query", "epilepsy"]], indirect=True
    )
    def test_long_query_option_is_parsed(self, argv):
        # Arrange
        # Act
        args = parse_args()
        # Assert
        assert args.query == "epilepsy"

    @pytest.mark.parametrize("argv", [["prog"]], indirect=True)
    def test_default_n_entries_is_ten(self, argv):
        # Arrange
        # Act
        args = parse_args()
        # Assert
        assert args.n_entries == 10

    @pytest.mark.parametrize(
        "argv", [["prog", "-q", "diabetes", "-n", "5"]], indirect=True
    )
    def test_short_option_n_entries_is_parsed(self, argv):
        # Arrange
        # Act
        args = parse_args()
        # Assert
        assert args.n_entries == 5


if __name__ == "__main__":
    pytest.main([os.path.abspath(__file__), "-v"])

# EOF
