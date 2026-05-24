#!/usr/bin/env python3
# File: ./tests/scitex_web/test__search_pubmed.py

"""Tests for PubMed search functionality.

Network functions are exercised against a real loopback HTTP server (the
production functions accept a ``base_url`` seam) and the async helpers against
a real aiohttp test server. Pure functions (`_parse_abstract_xml`,
`format_bibtex`, `save_bibtex`, the `search_pubmed` orchestrator) run with
hand-rolled fake collaborators. No mocks.
"""

import asyncio
import json
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlparse

import pytest

aiohttp = pytest.importorskip("aiohttp")

from scitex_web._search_pubmed import (  # noqa: E402
    _fetch_details,
    _get_citation,
    _parse_abstract_xml,
    _search_pubmed,
    batch__fetch_details,
    fetch_async,
    format_bibtex,
    get_crossref_metrics,
    parse_args,
    run_main,
    save_bibtex,
    search_pubmed,
)


# --------------------------------------------------------------------------
# Real loopback HTTP server (sync requests path)
# --------------------------------------------------------------------------
def _make_handler(responder):
    class _Handler(BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802 (http.server API)
            status, content_type, body = responder(self.path)
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.end_headers()
            self.wfile.write(body.encode("utf-8"))

        def log_message(self, *args):
            pass

    return _Handler


@pytest.fixture
def eutils_server():
    """Serve a fixed responder; yields (base_url, recorded_paths)."""
    recorded = []
    state = {"responder": lambda path: (200, "application/json", "{}")}

    def _responder(path):
        recorded.append(path)
        return state["responder"](path)

    server = HTTPServer(("127.0.0.1", 0), _make_handler(_responder))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host, port = server.server_address
    base = f"http://{host}:{port}/"

    def set_responder(fn):
        state["responder"] = fn

    try:
        yield base, recorded, set_responder
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


@pytest.fixture
def refused_url():
    """A base URL bound but never listening → requests refuses instantly.

    The socket is held (bound, no ``listen``) for the test's lifetime so
    connects get an immediate RST instead of a slow connect-timeout, then
    closed on teardown.
    """
    import socket

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    try:
        yield f"http://127.0.0.1:{port}/"
    finally:
        sock.close()


# --------------------------------------------------------------------------
# Shared XML fixtures
# --------------------------------------------------------------------------
_XML_COMPLETE = """
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

_XML_MISSING_FIELDS = """
<PubmedArticleSet>
    <PubmedArticle>
        <MedlineCitation><PMID>67890</PMID></MedlineCitation>
    </PubmedArticle>
</PubmedArticleSet>
"""

_XML_TWO_ARTICLES = """
<PubmedArticleSet>
    <PubmedArticle>
        <MedlineCitation><PMID>11111</PMID></MedlineCitation>
    </PubmedArticle>
    <PubmedArticle>
        <MedlineCitation><PMID>22222</PMID></MedlineCitation>
    </PubmedArticle>
</PubmedArticleSet>
"""


# --------------------------------------------------------------------------
# _search_pubmed — real requests.get against local server (base_url seam)
# --------------------------------------------------------------------------
class TestSearchPubmed:
    def test_success_returns_parsed_json(self, eutils_server):
        # Arrange
        base, _recorded, set_responder = eutils_server
        payload = {"esearchresult": {"idlist": ["12345", "67890"], "count": "2"}}
        set_responder(lambda path: (200, "application/json", json.dumps(payload)))
        # Act
        result = _search_pubmed("test query", retmax=10, base_url=base)
        # Assert
        assert result == payload

    def test_failure_status_returns_empty_dict(self, eutils_server):
        # Arrange
        base, _recorded, set_responder = eutils_server
        set_responder(lambda path: (500, "application/json", "{}"))
        # Act
        result = _search_pubmed("test query", base_url=base)
        # Assert
        assert result == {}

    def test_network_error_returns_empty_dict(self, refused_url):
        # Arrange
        # (refused_url points at a closed port → ConnectionError)
        # Act
        result = _search_pubmed("test query", base_url=refused_url)
        # Assert
        assert result == {}

    def test_query_term_is_sent_as_param(self, eutils_server):
        # Arrange
        base, recorded, set_responder = eutils_server
        set_responder(lambda path: (200, "application/json", '{"esearchresult": {}}'))
        # Act
        _search_pubmed("epilepsy", retmax=500, base_url=base)
        # Assert
        assert parse_qs(urlparse(recorded[0]).query)["term"] == ["epilepsy"]

    def test_retmax_is_sent_as_param(self, eutils_server):
        # Arrange
        base, recorded, set_responder = eutils_server
        set_responder(lambda path: (200, "application/json", '{"esearchresult": {}}'))
        # Act
        _search_pubmed("epilepsy", retmax=500, base_url=base)
        # Assert
        assert parse_qs(urlparse(recorded[0]).query)["retmax"] == ["500"]


# --------------------------------------------------------------------------
# _fetch_details — two real GETs against local server
# --------------------------------------------------------------------------
class TestFetchDetails:
    def test_success_returns_abstracts_text(self, eutils_server):
        # Arrange
        base, _recorded, set_responder = eutils_server

        def responder(path):
            if "efetch" in path:
                return (200, "text/xml", "<xml>abstract data</xml>")
            return (200, "application/json", '{"result": {"12345": {"title": "T"}}}')

        set_responder(responder)
        # Act
        result = _fetch_details("webenv123", "qkey456", base_url=base)
        # Assert
        assert result["abstracts"] == "<xml>abstract data</xml>"

    def test_success_returns_details_json(self, eutils_server):
        # Arrange
        base, _recorded, set_responder = eutils_server

        def responder(path):
            if "efetch" in path:
                return (200, "text/xml", "<xml/>")
            return (200, "application/json", '{"result": {"12345": {"title": "T"}}}')

        set_responder(responder)
        # Act
        result = _fetch_details("webenv123", "qkey456", base_url=base)
        # Assert
        assert result["details"] == {"result": {"12345": {"title": "T"}}}

    def test_non_ok_status_returns_empty_dict(self, eutils_server):
        # Arrange
        base, _recorded, set_responder = eutils_server
        set_responder(lambda path: (500, "text/xml", ""))
        # Act
        result = _fetch_details("webenv123", "qkey456", base_url=base)
        # Assert
        assert result == {}

    def test_webenv_is_sent_as_param(self, eutils_server):
        # Arrange
        base, recorded, set_responder = eutils_server

        def responder(path):
            if "efetch" in path:
                return (200, "text/xml", "<xml/>")
            return (200, "application/json", "{}")

        set_responder(responder)
        # Act
        _fetch_details("env123", "key456", retstart=100, retmax=50, base_url=base)
        # Assert
        assert parse_qs(urlparse(recorded[0]).query)["WebEnv"] == ["env123"]


# --------------------------------------------------------------------------
# _parse_abstract_xml — pure
# --------------------------------------------------------------------------
class TestParseAbstractXml:
    def test_complete_article_pmid_present(self):
        # Arrange
        # (module-level _XML_COMPLETE)
        # Act
        result = _parse_abstract_xml(_XML_COMPLETE)
        # Assert
        assert "12345" in result

    def test_complete_article_abstract_text(self):
        # Arrange
        # Act
        result = _parse_abstract_xml(_XML_COMPLETE)
        # Assert
        assert result["12345"][0] == "This is the abstract text."

    def test_complete_article_keywords(self):
        # Arrange
        # Act
        result = _parse_abstract_xml(_XML_COMPLETE)
        # Assert
        assert result["12345"][1] == ["Keyword1", "Keyword2"]

    def test_complete_article_doi(self):
        # Arrange
        # Act
        result = _parse_abstract_xml(_XML_COMPLETE)
        # Assert
        assert result["12345"][2] == "10.1234/test.doi"

    def test_missing_fields_pmid_present(self):
        # Arrange
        # Act
        result = _parse_abstract_xml(_XML_MISSING_FIELDS)
        # Assert
        assert "67890" in result

    def test_missing_fields_abstract_empty(self):
        # Arrange
        # Act
        result = _parse_abstract_xml(_XML_MISSING_FIELDS)
        # Assert
        assert result["67890"][0] == ""

    def test_missing_fields_keywords_empty(self):
        # Arrange
        # Act
        result = _parse_abstract_xml(_XML_MISSING_FIELDS)
        # Assert
        assert result["67890"][1] == []

    def test_missing_fields_doi_empty(self):
        # Arrange
        # Act
        result = _parse_abstract_xml(_XML_MISSING_FIELDS)
        # Assert
        assert result["67890"][2] == ""

    def test_two_articles_yields_two_entries(self):
        # Arrange
        # Act
        result = _parse_abstract_xml(_XML_TWO_ARTICLES)
        # Assert
        assert len(result) == 2

    def test_two_articles_first_pmid_present(self):
        # Arrange
        # Act
        result = _parse_abstract_xml(_XML_TWO_ARTICLES)
        # Assert
        assert "11111" in result

    def test_two_articles_second_pmid_present(self):
        # Arrange
        # Act
        result = _parse_abstract_xml(_XML_TWO_ARTICLES)
        # Assert
        assert "22222" in result


# --------------------------------------------------------------------------
# _get_citation — real GET against local server
# --------------------------------------------------------------------------
class TestGetCitation:
    def test_success_returns_response_text(self, eutils_server):
        # Arrange
        base, _recorded, set_responder = eutils_server
        set_responder(lambda path: (200, "text/plain", "@article{test_citation}"))
        # Act
        result = _get_citation("12345", base_url=base)
        # Assert
        assert result == "@article{test_citation}"

    def test_failure_status_returns_empty_string(self, eutils_server):
        # Arrange
        base, _recorded, set_responder = eutils_server
        set_responder(lambda path: (500, "text/plain", ""))
        # Act
        result = _get_citation("12345", base_url=base)
        # Assert
        assert result == ""

    def test_pmid_is_sent_as_param(self, eutils_server):
        # Arrange
        base, recorded, set_responder = eutils_server
        set_responder(lambda path: (200, "text/plain", ""))
        # Act
        _get_citation("99999", base_url=base)
        # Assert
        assert parse_qs(urlparse(recorded[0]).query)["id"] == ["99999"]


# --------------------------------------------------------------------------
# get_crossref_metrics — real GET against local server
# --------------------------------------------------------------------------
class TestGetCrossrefMetrics:
    _MESSAGE = {
        "message": {
            "is-referenced-by-count": 42,
            "type": "journal-article",
            "publisher": "Test Publisher",
            "reference": [1, 2, 3],
            "DOI": "10.1234/test",
        }
    }

    def test_success_returns_citation_count(self, eutils_server):
        # Arrange
        base, _recorded, set_responder = eutils_server
        set_responder(lambda path: (200, "application/json", json.dumps(self._MESSAGE)))
        # Act
        result = get_crossref_metrics("10.1234/test", base_url=base)
        # Assert
        assert result["citations"] == 42

    def test_success_returns_reference_count(self, eutils_server):
        # Arrange
        base, _recorded, set_responder = eutils_server
        set_responder(lambda path: (200, "application/json", json.dumps(self._MESSAGE)))
        # Act
        result = get_crossref_metrics("10.1234/test", base_url=base)
        # Assert
        assert result["references"] == 3

    def test_failure_status_returns_empty_dict(self, eutils_server):
        # Arrange
        base, _recorded, set_responder = eutils_server
        set_responder(lambda path: (500, "application/json", "{}"))
        # Act
        result = get_crossref_metrics("10.1234/test", base_url=base)
        # Assert
        assert result == {}

    def test_missing_fields_default_citations_zero(self, eutils_server):
        # Arrange
        base, _recorded, set_responder = eutils_server
        set_responder(lambda path: (200, "application/json", '{"message": {}}'))
        # Act
        result = get_crossref_metrics("10.1234/test", base_url=base)
        # Assert
        assert result["citations"] == 0


# --------------------------------------------------------------------------
# save_bibtex — real file write (tmp_path) + injected collaborators
# --------------------------------------------------------------------------
class TestSaveBibtex:
    def test_official_citation_written_verbatim(self, tmp_path):
        # Arrange
        papers = {"12345": {"title": "T", "authors": [{"name": "John Doe"}]}}
        out = tmp_path / "test.bib"
        # Act
        save_bibtex(
            papers,
            {},
            str(out),
            citation_fn=lambda pmid: "@article{official}",
            format_fn=lambda *a, **k: "UNUSED",
        )
        # Assert
        assert out.read_text() == "@article{official}"

    def test_formatted_entry_used_when_no_citation(self, tmp_path):
        # Arrange
        papers = {"67890": {"title": "T", "authors": [{"name": "Jane Smith"}]}}
        out = tmp_path / "test.bib"
        # Act
        save_bibtex(
            papers,
            {},
            str(out),
            citation_fn=lambda pmid: "",
            format_fn=lambda *a, **k: "@article{formatted}",
        )
        # Assert
        assert out.read_text() == "@article{formatted}\n"

    def test_uids_key_is_skipped(self, tmp_path):
        # Arrange
        papers = {"uids": ["12345"], "12345": {"title": "Real"}}
        out = tmp_path / "test.bib"
        formatted_for = []
        # Act
        save_bibtex(
            papers,
            {},
            str(out),
            citation_fn=lambda pmid: "",
            format_fn=lambda paper, pmid, data: formatted_for.append(pmid) or "X",
        )
        # Assert
        assert formatted_for == ["12345"]


# --------------------------------------------------------------------------
# format_bibtex — pure (doi="") + injected metrics for the DOI path
# --------------------------------------------------------------------------
class TestFormatBibtex:
    _COMPLETE_PAPER = {
        "title": "Machine Learning for Medical Diagnosis",
        "authors": [{"name": "John A. Smith"}, {"name": "Jane B. Doe"}],
        "source": "Nature Medicine",
        "pubdate": "2023 Jul 15",
    }
    _COMPLETE_ABSTRACT = (
        "This is the abstract text.",
        ["Machine Learning", "Diagnosis"],
        "10.1038/s41591-023-12345",
    )

    def _format_complete(self):
        return format_bibtex(
            self._COMPLETE_PAPER,
            "12345678",
            self._COMPLETE_ABSTRACT,
            metrics_fn=lambda doi: {"publisher": "Nature Publishing", "references": 50},
        )

    def test_complete_entry_has_citation_key(self):
        # Arrange
        # Act
        result = self._format_complete()
        # Assert
        assert "@article{John.Smith_2023_machine_learning" in result

    def test_complete_entry_has_author_line(self):
        # Arrange
        # Act
        result = self._format_complete()
        # Assert
        assert "author = {John A. Smith and Jane B. Doe}" in result

    def test_complete_entry_has_doi_line(self):
        # Arrange
        # Act
        result = self._format_complete()
        # Assert
        assert "doi = {10.1038/s41591-023-12345}" in result

    def test_complete_entry_has_keywords_line(self):
        # Arrange
        # Act
        result = self._format_complete()
        # Assert
        assert "keywords = {Machine Learning, Diagnosis}" in result

    def test_minimal_entry_has_article_marker(self):
        # Arrange
        paper = {"title": "A", "authors": [{"name": "X"}], "source": "U", "pubdate": ""}
        # Act
        result = format_bibtex(paper, "99999", ("", [], ""))
        # Assert
        assert "@article{" in result

    def test_minimal_entry_has_pmid_line(self):
        # Arrange
        paper = {"title": "A", "authors": [{"name": "X"}], "source": "U", "pubdate": ""}
        # Act
        result = format_bibtex(paper, "99999", ("", [], ""))
        # Assert
        assert "pmid = {99999}" in result

    def test_special_chars_cleaned_in_citation_key(self):
        # Arrange
        paper = {
            "title": "Test-Paper: With Special Characters!",
            "authors": [{"name": "O'Neill-Smith"}],
            "source": "Test Journal",
            "pubdate": "2023",
        }
        # Act
        result = format_bibtex(paper, "11111", ("", [], ""))
        # Assert
        assert "@article{ONeillSmith.ONeillSmith_2023_testpaper_with" in result


# --------------------------------------------------------------------------
# async helpers — real aiohttp test server
# --------------------------------------------------------------------------
@pytest.fixture
def aiohttp_server_factory():
    """Build an aiohttp app serving fixed JSON or XML; yields a runner factory."""
    from aiohttp import web

    runners = []

    async def _start(handler):
        app = web.Application()
        app.router.add_get("/{tail:.*}", handler)
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, "127.0.0.1", 0)
        await site.start()
        runners.append(runner)
        port = site._server.sockets[0].getsockname()[1]
        return f"http://127.0.0.1:{port}"

    yield _start

    async def _cleanup():
        for r in runners:
            await r.cleanup()

    asyncio.get_event_loop().run_until_complete(_cleanup())


class TestAsyncFunctions:
    @pytest.mark.asyncio
    async def test_fetch_async_returns_json_for_json_retmode(
        self, aiohttp_server_factory
    ):
        # Arrange
        from aiohttp import web

        async def handler(request):
            return web.json_response({"test": "data"})

        url = await aiohttp_server_factory(handler)
        # Act
        async with aiohttp.ClientSession() as session:
            result = await fetch_async(session, url, {"retmode": "json"})
        # Assert
        assert result == {"test": "data"}

    @pytest.mark.asyncio
    async def test_fetch_async_returns_text_for_xml_retmode(
        self, aiohttp_server_factory
    ):
        # Arrange
        from aiohttp import web

        async def handler(request):
            return web.Response(text="<xml>test</xml>")

        url = await aiohttp_server_factory(handler)
        # Act
        async with aiohttp.ClientSession() as session:
            result = await fetch_async(session, url, {"retmode": "xml"})
        # Assert
        assert result == "<xml>test</xml>"

    @pytest.mark.asyncio
    async def test_fetch_async_returns_empty_on_non_200(self, aiohttp_server_factory):
        # Arrange
        from aiohttp import web

        async def handler(request):
            return web.Response(status=404)

        url = await aiohttp_server_factory(handler)
        # Act
        async with aiohttp.ClientSession() as session:
            result = await fetch_async(session, url, {})
        # Assert
        assert result == {}


# --------------------------------------------------------------------------
# search_pubmed orchestrator — injected collaborators
# --------------------------------------------------------------------------
class TestSearchPubmedOrchestrator:
    def test_empty_search_returns_one(self):
        # Arrange
        # Act
        result = search_pubmed("test query", n_entries=10, search_fn=lambda q: {})
        # Assert
        assert result == 1

    def test_filename_sanitizes_spaces_to_underscores(self, tmp_path):
        # Arrange
        import os

        cwd = os.getcwd()
        os.chdir(tmp_path)
        search_fn = lambda q: {"esearchresult": {"idlist": [], "count": "0"}}  # noqa: E731
        # Act
        try:
            search_pubmed(
                "test query with spaces",
                n_entries=0,
                search_fn=search_fn,
                fetch_fn=lambda ids: [],
            )
            produced = list(tmp_path.glob("*.bib"))
        finally:
            os.chdir(cwd)
        # Assert
        assert produced[0].name == "pubmed_test_query_with_spaces.bib"


# --------------------------------------------------------------------------
# parse_args — real argv (save/restore, no mocks)
# --------------------------------------------------------------------------
@pytest.fixture
def argv():
    """Set sys.argv for the test, restore afterward."""
    saved = sys.argv
    try:
        yield lambda new: setattr(sys, "argv", new)
    finally:
        sys.argv = saved


class TestParseArgs:
    def test_long_query_flag_is_parsed(self, argv):
        # Arrange
        argv(["script.py", "--query", "epilepsy prediction", "--n_entries", "20"])
        # Act
        args = parse_args()
        # Assert
        assert args.query == "epilepsy prediction"

    def test_long_n_entries_flag_is_parsed(self, argv):
        # Arrange
        argv(["script.py", "--query", "x", "--n_entries", "20"])
        # Act
        args = parse_args()
        # Assert
        assert args.n_entries == 20

    def test_query_defaults_to_none(self, argv):
        # Arrange
        argv(["script.py"])
        # Act
        args = parse_args()
        # Assert
        assert args.query is None

    def test_n_entries_defaults_to_ten(self, argv):
        # Arrange
        argv(["script.py"])
        # Act
        args = parse_args()
        # Assert
        assert args.n_entries == 10

    def test_short_flags_are_parsed(self, argv):
        # Arrange
        argv(["script.py", "-q", "test", "-n", "5"])
        # Act
        args = parse_args()
        # Assert
        assert args.n_entries == 5


# --------------------------------------------------------------------------
# module surface
# --------------------------------------------------------------------------
class TestModuleSurface:
    def test_run_main_is_callable(self):
        # Arrange
        # (run_main needs the scitex umbrella for session handling; here we
        # only assert it is exposed as a callable entry point.)
        # Act
        ok = callable(run_main)
        # Assert
        assert ok


if __name__ == "__main__":
    import os

    pytest.main([os.path.abspath(__file__)])

# EOF
