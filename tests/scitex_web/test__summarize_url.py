#!/usr/bin/env python3
# File: ./tests/scitex_web/test__summarize_url.py

"""Tests for URL summarization functionality.

These exercise real collaborators: a local in-process HTTP server for the
crawler, the real readability ``Document`` for content extraction, and
hand-rolled fake LLM callables injected through the production seams
(``genai_factory`` / ``crawl_fn`` / ``summarize_fn``). No mocks.
"""

import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

pytest.importorskip("aiohttp")

from scitex_web._summarize_url import (  # noqa: E402
    crawl_to_json,
    crawl_url,
    extract_main_content,
    main,
    summarize_all,
    summarize_url,
)


# --------------------------------------------------------------------------
# Real collaborators
# --------------------------------------------------------------------------
def _make_handler(routes):
    """Build a BaseHTTPRequestHandler class serving a {path: (status, body)} map."""

    class _Handler(BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802 (http.server API)
            status, body = routes.get(self.path, (404, ""))
            self.send_response(status)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(body.encode("utf-8"))

        def log_message(self, *args):  # silence access log
            pass

    return _Handler


@pytest.fixture
def http_server():
    """Spin a real loopback HTTP server; yields a routes-dict + base URL setter."""
    routes = {}
    server = HTTPServer(("127.0.0.1", 0), _make_handler(routes))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host, port = server.server_address
    base = f"http://{host}:{port}"
    try:
        yield base, routes
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


@pytest.fixture
def refused_url():
    """A URL bound but never listening → requests refuses instantly.

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


class _FakeLLM:
    """Records every prompt; returns a fixed reply (or one per call)."""

    def __init__(self, reply="canned reply", replies=None):
        self.reply = reply
        self.replies = list(replies) if replies is not None else None
        self.prompts = []

    def __call__(self, prompt):
        self.prompts.append(prompt)
        if self.replies is not None:
            return self.replies.pop(0)
        return self.reply


def _fake_genai_factory(llm):
    """Return a genai_factory that ignores the model name and yields `llm`."""

    def factory(model):
        return llm

    return factory


# --------------------------------------------------------------------------
# extract_main_content — real readability Document + real regex fallback
# --------------------------------------------------------------------------
class TestExtractMainContent:
    def test_readability_extraction_keeps_main_title_text(self):
        # Arrange
        html = "<html><body><h1>Main Title</h1><p>This is the main content.</p></body></html>"
        # Act
        result = extract_main_content(html)
        # Assert
        assert "Main Title" in result

    def test_readability_extraction_keeps_body_text(self):
        # Arrange
        html = "<html><body><h1>Main Title</h1><p>This is the main content.</p></body></html>"
        # Act
        result = extract_main_content(html)
        # Assert
        assert "This is the main content" in result

    def test_readability_extraction_strips_html_tags(self):
        # Arrange
        html = "<html><body><h1>Main Title</h1><p>This is the main content.</p></body></html>"
        # Act
        result = extract_main_content(html)
        # Assert
        assert "<" not in result

    def test_fallback_strips_tags_when_no_extractor(self):
        # Arrange
        html = "<p>Test content</p>"
        # Act
        result = extract_main_content(html, document_cls=None)
        # Assert
        assert result == "Test content"

    def test_fallback_collapses_extra_whitespace(self):
        # Arrange
        html = "<p>Real   content   with   spaces</p>"
        # Act
        result = extract_main_content(html, document_cls=None)
        # Assert
        assert result == "Real content with spaces"

    def test_fallback_returns_empty_for_empty_html(self):
        # Arrange
        html = ""
        # Act
        result = extract_main_content(html, document_cls=None)
        # Assert
        assert result == ""

    def test_fallback_passes_plain_text_through(self):
        # Arrange
        plain_text = "Just plain text without HTML"
        # Act
        result = extract_main_content(plain_text, document_cls=None)
        # Assert
        assert result == plain_text

    def test_fallback_truncates_to_5000_chars(self):
        # Arrange
        html = "x" * 6000
        # Act
        result = extract_main_content(html, document_cls=None)
        # Assert
        assert len(result) == 5000


# --------------------------------------------------------------------------
# crawl_url — real requests.get against a real local HTTP server
# --------------------------------------------------------------------------
class TestCrawlUrl:
    def test_single_page_is_recorded_in_visited(self, http_server):
        # Arrange
        base, routes = http_server
        routes["/"] = (200, "<html><body><p>Test content</p></body></html>")
        # Act
        visited, _contents = crawl_url(base + "/", max_depth=0)
        # Assert
        assert base + "/" in visited

    def test_single_page_content_is_extracted(self, http_server):
        # Arrange
        base, routes = http_server
        routes["/"] = (200, "<html><body><p>Test content</p></body></html>")
        # Act
        _visited, contents = crawl_url(base + "/", max_depth=0)
        # Assert
        assert "Test content" in contents[base + "/"]

    def test_max_depth_zero_visits_only_initial_url(self, http_server):
        # Arrange
        base, routes = http_server
        routes["/"] = (200, '<html><body><a href="/deep">Link</a></body></html>')
        routes["/deep"] = (200, "<p>deep</p>")
        # Act
        visited, _contents = crawl_url(base + "/", max_depth=0)
        # Assert
        assert len(visited) == 1

    def test_links_are_followed_at_depth_one(self, http_server):
        # Arrange
        base, routes = http_server
        routes["/"] = (200, f'<html><body><a href="{base}/page2">P2</a></body></html>')
        routes["/page2"] = (200, "<p>page two</p>")
        # Act
        visited, _contents = crawl_url(base + "/", max_depth=1)
        # Assert
        assert base + "/page2" in visited

    def test_request_exception_yields_empty_visited(self, refused_url):
        # Arrange
        # (refused_url is a bound-but-not-listening port → ConnectionError)
        # Act
        visited, _contents = crawl_url(refused_url)
        # Assert
        assert len(visited) == 0

    def test_non_200_status_yields_empty_visited(self, http_server):
        # Arrange
        base, routes = http_server
        routes["/"] = (404, "")
        # Act
        visited, _contents = crawl_url(base + "/")
        # Assert
        assert len(visited) == 0

    def test_self_link_is_not_visited_twice(self, http_server):
        # Arrange
        base, routes = http_server
        routes["/"] = (200, f'<html><body><a href="{base}/">Home</a></body></html>')
        # Act
        visited, _contents = crawl_url(base + "/", max_depth=1)
        # Assert
        assert visited == {base + "/"}


# --------------------------------------------------------------------------
# crawl_to_json — real crawl logic + injected fake crawler/LLM
# --------------------------------------------------------------------------
class TestCrawlToJson:
    def test_start_url_recorded_for_single_page(self):
        # Arrange
        urls = {"http://test.com"}
        contents = {"http://test.com": "Test page content"}
        crawler = lambda _url: (urls, contents)  # noqa: E731
        llm = _FakeLLM(reply="Summary of test page")
        # Act
        result = crawl_to_json(
            "test.com", crawler=crawler, genai_factory=_fake_genai_factory(llm)
        )
        # Assert
        assert json.loads(result)["start_url"] == "https://test.com"

    def test_single_page_produces_one_crawled_page(self):
        # Arrange
        urls = {"http://test.com"}
        contents = {"http://test.com": "Test page content"}
        crawler = lambda _url: (urls, contents)  # noqa: E731
        llm = _FakeLLM(reply="Summary of test page")
        # Act
        result = crawl_to_json(
            "test.com", crawler=crawler, genai_factory=_fake_genai_factory(llm)
        )
        # Assert
        assert len(json.loads(result)["crawled_pages"]) == 1

    def test_crawled_page_carries_its_url(self):
        # Arrange
        urls = {"http://test.com"}
        contents = {"http://test.com": "Test page content"}
        crawler = lambda _url: (urls, contents)  # noqa: E731
        llm = _FakeLLM(reply="Summary of test page")
        # Act
        result = crawl_to_json(
            "test.com", crawler=crawler, genai_factory=_fake_genai_factory(llm)
        )
        # Assert
        assert json.loads(result)["crawled_pages"][0]["url"] == "http://test.com"

    def test_bare_domain_gets_https_prefix(self):
        # Arrange
        crawler = lambda _url: (set(), {})  # noqa: E731
        llm = _FakeLLM()
        # Act
        result = crawl_to_json(
            "example.com", crawler=crawler, genai_factory=_fake_genai_factory(llm)
        )
        # Assert
        assert json.loads(result)["start_url"] == "https://example.com"

    def test_existing_protocol_is_preserved(self):
        # Arrange
        crawler = lambda _url: (set(), {})  # noqa: E731
        llm = _FakeLLM()
        # Act
        result = crawl_to_json(
            "http://example.com",
            crawler=crawler,
            genai_factory=_fake_genai_factory(llm),
        )
        # Assert
        assert json.loads(result)["start_url"] == "http://example.com"

    def test_multiple_pages_produce_multiple_entries(self):
        # Arrange
        urls = {"http://test.com", "http://test.com/page2"}
        contents = {
            "http://test.com": "Main content",
            "http://test.com/page2": "Page 2 content",
        }
        crawler = lambda _url: (urls, contents)  # noqa: E731
        llm = _FakeLLM(reply="a summary")
        # Act
        result = crawl_to_json(
            "test.com", crawler=crawler, genai_factory=_fake_genai_factory(llm)
        )
        # Assert
        assert len(json.loads(result)["crawled_pages"]) == 2


# --------------------------------------------------------------------------
# summarize_all — injected fake LLM
# --------------------------------------------------------------------------
class TestSummarizeAll:
    def test_returns_the_llm_reply(self):
        # Arrange
        json_content = json.dumps({"start_url": "http://test.com", "crawled_pages": []})
        llm = _FakeLLM(reply="• Point 1\n• Point 2\n• Point 3\n• Point 4\n• Point 5")
        # Act
        result = summarize_all(json_content, genai_factory=_fake_genai_factory(llm))
        # Assert
        assert "Point 1" in result

    def test_prompt_requests_five_bullet_points(self):
        # Arrange
        json_content = json.dumps({"start_url": "http://test.com", "crawled_pages": []})
        llm = _FakeLLM(reply="anything")
        # Act
        summarize_all(json_content, genai_factory=_fake_genai_factory(llm))
        # Assert
        assert "5 bullet points" in llm.prompts[0]

    def test_prompt_embeds_the_json_content(self):
        # Arrange
        json_content = json.dumps({"start_url": "http://test.com", "crawled_pages": []})
        llm = _FakeLLM(reply="anything")
        # Act
        summarize_all(json_content, genai_factory=_fake_genai_factory(llm))
        # Assert
        assert json_content in llm.prompts[0]

    def test_empty_json_still_returns_llm_reply(self):
        # Arrange
        empty_json = json.dumps({"start_url": "", "crawled_pages": []})
        llm = _FakeLLM(reply="No content to summarize")
        # Act
        result = summarize_all(empty_json, genai_factory=_fake_genai_factory(llm))
        # Assert
        assert result == "No content to summarize"


# --------------------------------------------------------------------------
# summarize_url — injected crawl_fn / summarize_fn
# --------------------------------------------------------------------------
class TestSummarizeUrl:
    def test_returns_summary_from_summarize_fn(self):
        # Arrange
        crawl_fn = lambda _url: '{"start_url": "https://test.com"}'  # noqa: E731
        summarize_fn = lambda _json: "• Summary point 1"  # noqa: E731
        # Act
        ground_summary, _json_result = summarize_url(
            "test.com", crawl_fn=crawl_fn, summarize_fn=summarize_fn
        )
        # Assert
        assert ground_summary == "• Summary point 1"

    def test_returns_json_from_crawl_fn(self):
        # Arrange
        crawl_fn = lambda _url: '{"start_url": "https://test.com"}'  # noqa: E731
        summarize_fn = lambda _json: "• Summary point 1"  # noqa: E731
        # Act
        _ground_summary, json_result = summarize_url(
            "test.com", crawl_fn=crawl_fn, summarize_fn=summarize_fn
        )
        # Assert
        assert json_result == '{"start_url": "https://test.com"}'

    def test_propagates_crawl_failure(self):
        # Arrange
        def crawl_fn(_url):
            raise RuntimeError("Crawl error")

        # Act
        ctx = pytest.raises(RuntimeError)
        # Assert
        with ctx:
            summarize_url("test.com", crawl_fn=crawl_fn)

    def test_summarize_fn_receives_crawl_output(self):
        # Arrange
        received = []
        crawl_fn = lambda _url: '{"crawled": true}'  # noqa: E731
        summarize_fn = lambda j: received.append(j) or "ok"  # noqa: E731
        # Act
        summarize_url("test.com", crawl_fn=crawl_fn, summarize_fn=summarize_fn)
        # Assert
        assert received == ['{"crawled": true}']


# --------------------------------------------------------------------------
# main alias + module surface
# --------------------------------------------------------------------------
class TestMain:
    def test_main_is_summarize_url_alias(self):
        # Arrange
        # (module-level `main = summarize_url`)
        # Act
        same = main is summarize_url
        # Assert
        assert same

    def test_main_returns_summary_via_injected_deps(self):
        # Arrange
        crawl_fn = lambda _url: '{"test": "data"}'  # noqa: E731
        summarize_fn = lambda _json: "Test summary"  # noqa: E731
        # Act
        result = main(
            "http://example.com", crawl_fn=crawl_fn, summarize_fn=summarize_fn
        )
        # Assert
        assert result == ("Test summary", '{"test": "data"}')

    def test_module_exposes_document_attribute(self):
        # Arrange
        from scitex_web import _summarize_url

        # Act
        has_document = hasattr(_summarize_url, "Document")
        # Assert
        assert has_document


if __name__ == "__main__":
    import os

    pytest.main([os.path.abspath(__file__)])

# EOF
