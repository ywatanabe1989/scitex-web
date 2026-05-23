#!/usr/bin/env python3
# File: ./tests/scitex_web/test__summarize_url.py
"""Tests for scitex_web._summarize_url.

Network and LLM collaborators are injected as keyword arguments and
replaced with hand-rolled fakes. No mocks, no patching of requests or
scitex_ai.GenAI.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field

import pytest
import requests

from scitex_web import (
    crawl_to_json,
    crawl_url,
    summarize_url,
)
from scitex_web._summarize_url import (
    extract_main_content,
    main,
    summarize_all,
)


@dataclass
class FakeResponse:
    """Minimal stand-in for the slice of ``requests.Response`` we use."""

    text: str = ""
    status_code: int = 200


@dataclass
class FakeHttpGet:
    """Fake HTTP GET: returns one canned response per URL the SUT visits.

    Unknown URLs (anything not in ``responses``) get a 404 — that lets the
    test assert breadth-first crawler termination without further setup.
    """

    responses: dict = field(default_factory=dict)
    raise_exception: Exception | None = None
    captured: list = field(default_factory=list)

    def __call__(self, url, *args, **kwargs):
        self.captured.append(url)
        if self.raise_exception is not None:
            raise self.raise_exception
        if url in self.responses:
            return self.responses[url]
        return FakeResponse(text="", status_code=404)


@dataclass
class FakeLLM:
    """Records each prompt and returns a deterministic canned summary."""

    canned: str = "fake-summary"
    prompts: list = field(default_factory=list)

    def __call__(self, prompt: str) -> str:
        self.prompts.append(prompt)
        return self.canned


class TestExtractMainContent:
    def test_returns_text_from_html_body(self):
        # Arrange
        html = "<html><body><p>hello world</p></body></html>"
        # Act
        result = extract_main_content(html)
        # Assert
        assert "hello world" in result

    def test_strips_html_tags_from_output(self):
        # Arrange
        html = "<html><body><p>hello world</p></body></html>"
        # Act
        result = extract_main_content(html)
        # Assert
        assert "<" not in result

    def test_collapses_consecutive_whitespace(self):
        # Arrange
        html = "<p>foo    bar</p>"
        # Act
        result = extract_main_content(html)
        # Assert
        assert "    " not in result


class TestCrawlUrl:
    def test_returns_empty_visited_set_when_request_raises(self):
        # Arrange
        fake = FakeHttpGet(raise_exception=requests.RequestException("boom"))
        # Act
        visited, _ = crawl_url("https://example.com", http_get=fake)
        # Assert
        assert visited == set()

    def test_returns_empty_contents_when_request_raises(self):
        # Arrange
        fake = FakeHttpGet(raise_exception=requests.RequestException("boom"))
        # Act
        _, contents = crawl_url("https://example.com", http_get=fake)
        # Assert
        assert contents == {}

    def test_visits_start_url_on_200(self):
        # Arrange
        fake = FakeHttpGet(
            responses={
                "https://example.com": FakeResponse(
                    text="<html><body><p>x</p></body></html>",
                    status_code=200,
                )
            }
        )
        # Act
        visited, _ = crawl_url("https://example.com", http_get=fake)
        # Assert
        assert "https://example.com" in visited

    def test_skips_start_url_on_non_200(self):
        # Arrange
        fake = FakeHttpGet(
            responses={
                "https://example.com": FakeResponse(text="", status_code=500)
            }
        )
        # Act
        visited, _ = crawl_url("https://example.com", http_get=fake)
        # Assert
        assert visited == set()

    def test_max_depth_zero_does_not_follow_links(self):
        # Arrange
        page = '<html><body><a href="/child">c</a></body></html>'
        fake = FakeHttpGet(
            responses={
                "https://example.com": FakeResponse(text=page, status_code=200),
                "https://example.com/child": FakeResponse(
                    text="<p>child</p>", status_code=200
                ),
            }
        )
        # Act
        visited, _ = crawl_url("https://example.com", max_depth=0, http_get=fake)
        # Assert
        assert visited == {"https://example.com"}

    def test_max_depth_one_follows_one_hop(self):
        # Arrange
        page = '<html><body><a href="/child">c</a></body></html>'
        fake = FakeHttpGet(
            responses={
                "https://example.com": FakeResponse(text=page, status_code=200),
                "https://example.com/child": FakeResponse(
                    text="<p>child</p>", status_code=200
                ),
            }
        )
        # Act
        visited, _ = crawl_url("https://example.com", max_depth=1, http_get=fake)
        # Assert
        assert "https://example.com/child" in visited


class TestCrawlToJson:
    @pytest.fixture
    def single_page_json(self) -> str:
        # Arrange
        html = "<html><body><p>page content</p></body></html>"
        http_get = FakeHttpGet(
            responses={
                "https://example.com": FakeResponse(text=html, status_code=200)
            }
        )
        llm = FakeLLM(canned="one-line-summary")
        # Act
        return crawl_to_json(
            "https://example.com", http_get=http_get, llm=llm
        )

    def test_includes_start_url_in_output(self, single_page_json):
        # Arrange
        data = json.loads(single_page_json)
        # Act
        # Assert
        assert data["start_url"] == "https://example.com"

    def test_includes_one_crawled_page_record(self, single_page_json):
        # Arrange
        data = json.loads(single_page_json)
        # Act
        # Assert
        assert len(data["crawled_pages"]) == 1

    def test_records_llm_summary_in_page_content(self, single_page_json):
        # Arrange
        data = json.loads(single_page_json)
        # Act
        # Assert
        assert data["crawled_pages"][0]["content"] == "one-line-summary"

    def test_prepends_https_scheme_when_missing(self):
        # Arrange
        http_get = FakeHttpGet()  # no responses → crawler yields empty
        llm = FakeLLM()
        # Act
        result = crawl_to_json("example.com", http_get=http_get, llm=llm)
        # Assert
        assert json.loads(result)["start_url"] == "https://example.com"

    def test_preserves_explicit_scheme(self):
        # Arrange
        http_get = FakeHttpGet()
        llm = FakeLLM()
        # Act
        result = crawl_to_json(
            "http://example.com", http_get=http_get, llm=llm
        )
        # Assert
        assert json.loads(result)["start_url"] == "http://example.com"


class TestSummarizeAll:
    def test_returns_llm_summary(self):
        # Arrange
        llm = FakeLLM(canned="five-bullet-summary")
        # Act
        result = summarize_all("{}", llm=llm)
        # Assert
        assert result == "five-bullet-summary"

    def test_passes_json_payload_into_llm_prompt(self):
        # Arrange
        llm = FakeLLM()
        payload = '{"abc": 123}'
        # Act
        summarize_all(payload, llm=llm)
        # Assert
        assert payload in llm.prompts[0]


class TestSummarizeUrl:
    @pytest.fixture
    def summary_result(self) -> tuple:
        # Arrange
        html = "<html><body><p>page</p></body></html>"
        http_get = FakeHttpGet(
            responses={
                "https://example.com": FakeResponse(text=html, status_code=200)
            }
        )
        llm = FakeLLM(canned="rolled-up-summary")
        # Act
        return summarize_url("https://example.com", http_get=http_get, llm=llm)

    def test_returns_summary_string_as_first_element(self, summary_result):
        # Arrange
        # Act
        # Assert
        assert summary_result[0] == "rolled-up-summary"

    def test_returns_json_string_as_second_element(self, summary_result):
        # Arrange
        # Act
        # Assert
        assert "crawled_pages" in summary_result[1]


class TestMain:
    def test_main_is_summarize_url_alias(self):
        # Arrange
        # Act
        # Assert
        assert main is summarize_url


if __name__ == "__main__":
    pytest.main([os.path.abspath(__file__), "-v"])

# EOF
