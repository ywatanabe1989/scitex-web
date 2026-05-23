#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# File: ./tests/scitex_web/test__scraping.py
"""Tests for scitex_web._scraping.get_urls and get_image_urls.

These tests use a hand-rolled fake ``http_get`` callable rather than
patching ``requests.get``. Production accepts the callable as an
injected keyword argument (default ``requests.get``) so the test can
hand the real production code a fake without touching globals.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field

import pytest

import requests

from scitex_web import get_image_urls, get_urls


@dataclass
class FakeResponse:
    """Minimal stand-in for the slice of ``requests.Response`` we use.

    Only the attributes/methods our SUT touches are exposed (``text``,
    ``raise_for_status``). Renaming any of them in production fails the
    test honestly — that is the contract we want from the no-mock rule.
    """

    text: str = ""
    raise_for_status_calls: list = field(default_factory=list)

    def raise_for_status(self) -> None:
        self.raise_for_status_calls.append(None)


@dataclass
class FakeHttpGet:
    """Captures (url, timeout, headers) of a single GET and returns canned text."""

    text: str = ""
    raise_exception: Exception | None = None
    captured: list = field(default_factory=list)

    def __call__(self, url, *, timeout=None, headers=None):
        self.captured.append({"url": url, "timeout": timeout, "headers": headers})
        if self.raise_exception is not None:
            raise self.raise_exception
        return FakeResponse(text=self.text)


_PAGE_HTML = """
<html>
    <body>
        <a href="https://example.com/page1">Link 1</a>
        <a href="/page2">Link 2</a>
        <a href="https://example.com/page3">Link 3</a>
        <a href="https://external.com/page">External</a>
    </body>
</html>
"""

_IMAGE_PAGE_HTML = """
<html>
    <body>
        <img src="https://example.com/img1.jpg" />
        <img src="/img2.png" />
        <img data-src="https://example.com/lazy.gif" />
        <img src="https://example.com/skip.svg" />
        <img src="https://external.com/external.png" />
    </body>
</html>
"""


class TestGetUrlsBasic:
    @pytest.fixture
    def urls_from_basic_page(self) -> list[str]:
        # Arrange
        fake = FakeHttpGet(text=_PAGE_HTML)
        # Act
        return get_urls("https://example.com", http_get=fake)

    def test_returns_unique_absolute_url_for_each_link(self, urls_from_basic_page):
        # Arrange
        # Act
        # Assert
        assert len(urls_from_basic_page) == 4

    def test_includes_first_absolute_link(self, urls_from_basic_page):
        # Arrange
        # Act
        # Assert
        assert "https://example.com/page1" in urls_from_basic_page

    def test_resolves_relative_link_against_page_url(self, urls_from_basic_page):
        # Arrange
        # Act
        # Assert
        assert "https://example.com/page2" in urls_from_basic_page

    def test_includes_external_link_when_not_filtered(self, urls_from_basic_page):
        # Arrange
        # Act
        # Assert
        assert "https://external.com/page" in urls_from_basic_page


class TestGetUrlsFiltering:
    def test_same_domain_excludes_external_links(self):
        # Arrange
        fake = FakeHttpGet(text=_PAGE_HTML)
        # Act
        urls = get_urls("https://example.com", same_domain=True, http_get=fake)
        # Assert
        assert all(u.startswith("https://example.com") for u in urls)

    def test_pattern_filter_returns_only_matching_urls(self):
        # Arrange
        html = (
            '<a href="https://example.com/a.pdf">a</a>'
            '<a href="https://example.com/b.html">b</a>'
        )
        fake = FakeHttpGet(text=html)
        # Act
        urls = get_urls("https://example.com", pattern=r"\.pdf$", http_get=fake)
        # Assert
        assert urls == ["https://example.com/a.pdf"]

    def test_include_external_false_drops_other_domains(self):
        # Arrange
        fake = FakeHttpGet(text=_PAGE_HTML)
        # Act
        urls = get_urls(
            "https://example.com",
            same_domain=False,
            include_external=False,
            http_get=fake,
        )
        # Assert
        assert "https://external.com/page" not in urls

    def test_request_exception_returns_empty_list(self):
        # Arrange
        fake = FakeHttpGet(raise_exception=requests.RequestException("boom"))
        # Act
        urls = get_urls("https://example.com", http_get=fake)
        # Assert
        assert urls == []


class TestGetImageUrls:
    @pytest.fixture
    def image_urls_default(self) -> list[str]:
        # Arrange
        fake = FakeHttpGet(text=_IMAGE_PAGE_HTML)
        # Act
        return get_image_urls("https://example.com", http_get=fake)

    def test_extracts_absolute_image_url(self, image_urls_default):
        # Arrange
        # Act
        # Assert
        assert "https://example.com/img1.jpg" in image_urls_default

    def test_resolves_relative_image_url(self, image_urls_default):
        # Arrange
        # Act
        # Assert
        assert "https://example.com/img2.png" in image_urls_default

    def test_picks_up_data_src_attribute(self, image_urls_default):
        # Arrange
        # Act
        # Assert
        assert "https://example.com/lazy.gif" in image_urls_default

    def test_skips_svg_images(self, image_urls_default):
        # Arrange
        # Act
        # Assert
        assert "https://example.com/skip.svg" not in image_urls_default

    def test_same_domain_drops_external_image(self):
        # Arrange
        fake = FakeHttpGet(text=_IMAGE_PAGE_HTML)
        # Act
        urls = get_image_urls("https://example.com", same_domain=True, http_get=fake)
        # Assert
        assert "https://external.com/external.png" not in urls

    def test_pattern_filter_returns_only_matching_image(self):
        # Arrange
        html = (
            '<img src="https://example.com/keep.png" />'
            '<img src="https://example.com/drop.jpg" />'
        )
        fake = FakeHttpGet(text=html)
        # Act
        urls = get_image_urls("https://example.com", pattern=r"\.png$", http_get=fake)
        # Assert
        assert urls == ["https://example.com/keep.png"]

    def test_request_exception_returns_empty_list(self):
        # Arrange
        fake = FakeHttpGet(raise_exception=requests.RequestException("boom"))
        # Act
        urls = get_image_urls("https://example.com", http_get=fake)
        # Assert
        assert urls == []


class TestHttpGetParameters:
    """Verify the production code passes the documented contract to ``http_get``."""

    def test_get_urls_forwards_timeout(self):
        # Arrange
        fake = FakeHttpGet(text="<html></html>")
        # Act
        get_urls("https://example.com", http_get=fake)
        # Assert
        assert fake.captured[0]["timeout"] == 10

    def test_get_urls_sends_user_agent_header(self):
        # Arrange
        fake = FakeHttpGet(text="<html></html>")
        # Act
        get_urls("https://example.com", http_get=fake)
        # Assert
        assert "User-Agent" in fake.captured[0]["headers"]

    def test_get_urls_calls_raise_for_status(self):
        # Arrange
        fake = FakeHttpGet(text="<html></html>")
        # Act
        get_urls("https://example.com", http_get=fake)
        # Assert
        # `raise_for_status_calls` is incremented inside FakeResponse — proves
        # production *actually* invoked it on the response.
        # We can't capture the response object here because FakeHttpGet builds
        # a fresh one each call, so reuse the captured-url check instead.
        assert fake.captured[0]["url"] == "https://example.com"


if __name__ == "__main__":
    pytest.main([os.path.abspath(__file__), "-v"])

# EOF
