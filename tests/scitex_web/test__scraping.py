#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# File: ./tests/scitex_web/test__scraping.py

"""Tests for web scraping utilities.

`get_urls` and `get_image_urls` fetch a page via `requests.get` and parse it
with BeautifulSoup. We exercise the real functions against a real loopback
HTTP server (no mocks): the server serves the test HTML, and assertions are
made relative to the actual served base URL.

`download_images` is covered separately in `test_download_images.py`; its
network/Pillow paths are not duplicated here.
"""

import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from scitex_web import get_image_urls, get_urls


def _make_handler(routes):
    """BaseHTTPRequestHandler serving a {path: (status, body)} map."""

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
def serve_html():
    """Serve HTML on a loopback port; yields a function (html) -> page_url."""
    routes = {}
    server = HTTPServer(("127.0.0.1", 0), _make_handler(routes))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host, port = server.server_address
    base = f"http://{host}:{port}"

    def _serve(html, path="/"):
        routes[path] = (200, html)
        return base + path

    try:
        yield _serve, base
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


class TestGetUrls:
    def test_extracts_all_three_links(self, serve_html):
        # Arrange
        serve, base = serve_html
        html = (
            "<html><body>"
            f'<a href="{base}/page1">L1</a>'
            '<a href="/page2">L2</a>'
            f'<a href="{base}/page3">L3</a>'
            "</body></html>"
        )
        page_url = serve(html)
        # Act
        urls = get_urls(page_url)
        # Assert
        assert len(urls) == 3

    def test_absolute_link_appears_in_result(self, serve_html):
        # Arrange
        serve, base = serve_html
        html = f'<html><body><a href="{base}/page1">L1</a></body></html>'
        page_url = serve(html)
        # Act
        urls = get_urls(page_url)
        # Assert
        assert f"{base}/page1" in urls

    def test_relative_link_resolved_against_base(self, serve_html):
        # Arrange
        serve, base = serve_html
        html = '<html><body><a href="/page2">L2</a></body></html>'
        page_url = serve(html)
        # Act
        urls = get_urls(page_url)
        # Assert
        assert f"{base}/page2" in urls

    def test_pattern_filters_to_pdf_links_only(self, serve_html):
        # Arrange
        serve, base = serve_html
        html = (
            "<html><body>"
            f'<a href="{base}/doc.pdf">pdf</a>'
            f'<a href="{base}/page.html">html</a>'
            f'<a href="{base}/report.pdf">pdf2</a>'
            "</body></html>"
        )
        page_url = serve(html)
        # Act
        urls = get_urls(page_url, pattern=r"\.pdf$")
        # Assert
        assert len(urls) == 2

    def test_pattern_result_entries_all_match(self, serve_html):
        # Arrange
        serve, base = serve_html
        html = (
            "<html><body>"
            f'<a href="{base}/doc.pdf">pdf</a>'
            f'<a href="{base}/page.html">html</a>'
            "</body></html>"
        )
        page_url = serve(html)
        # Act
        urls = get_urls(page_url, pattern=r"\.pdf$")
        # Assert
        assert all(url.endswith(".pdf") for url in urls)

    def test_same_domain_excludes_other_hosts(self, serve_html):
        # Arrange
        serve, base = serve_html
        html = (
            "<html><body>"
            f'<a href="{base}/a">internal</a>'
            '<a href="https://other.example/b">external</a>'
            "</body></html>"
        )
        page_url = serve(html)
        # Act
        urls = get_urls(page_url, same_domain=True)
        # Assert
        assert urls == [f"{base}/a"]

    def test_duplicate_links_are_deduplicated(self, serve_html):
        # Arrange
        serve, base = serve_html
        html = (
            "<html><body>"
            f'<a href="{base}/x">one</a>'
            f'<a href="{base}/x">again</a>'
            "</body></html>"
        )
        page_url = serve(html)
        # Act
        urls = get_urls(page_url)
        # Assert
        assert urls == [f"{base}/x"]

    def test_empty_page_returns_empty_list(self, serve_html):
        # Arrange
        serve, _base = serve_html
        page_url = serve("<html><body>no links</body></html>")
        # Act
        urls = get_urls(page_url)
        # Assert
        assert urls == []

    def test_request_failure_returns_empty_list(self, refused_url):
        # Arrange
        # (refused_url points at a closed port)
        # Act
        urls = get_urls(refused_url)
        # Assert
        assert urls == []


class TestGetImageUrls:
    def test_extracts_all_image_sources(self, serve_html):
        # Arrange
        serve, base = serve_html
        html = (
            "<html><body>"
            f'<img src="{base}/image1.jpg">'
            f'<img src="{base}/images/image2.png">'
            f'<img src="{base}/image3.gif">'
            "</body></html>"
        )
        page_url = serve(html)
        # Act
        img_urls = get_image_urls(page_url)
        # Assert
        assert len(img_urls) == 3

    def test_absolute_image_appears_in_result(self, serve_html):
        # Arrange
        serve, base = serve_html
        html = f'<html><body><img src="{base}/image1.jpg"></body></html>'
        page_url = serve(html)
        # Act
        img_urls = get_image_urls(page_url)
        # Assert
        assert f"{base}/image1.jpg" in img_urls

    def test_svg_images_are_skipped(self, serve_html):
        # Arrange
        serve, base = serve_html
        html = (
            "<html><body>"
            f'<img src="{base}/logo.svg">'
            f'<img src="{base}/photo.jpg">'
            "</body></html>"
        )
        page_url = serve(html)
        # Act
        img_urls = get_image_urls(page_url)
        # Assert
        assert img_urls == [f"{base}/photo.jpg"]

    def test_pattern_filters_to_jpg_images(self, serve_html):
        # Arrange
        serve, base = serve_html
        html = (
            "<html><body>"
            f'<img src="{base}/a.jpg">'
            f'<img src="{base}/b.png">'
            f'<img src="{base}/c.jpg">'
            "</body></html>"
        )
        page_url = serve(html)
        # Act
        img_urls = get_image_urls(page_url, pattern=r"\.jpg$")
        # Assert
        assert len(img_urls) == 2

    def test_pattern_result_entries_all_match(self, serve_html):
        # Arrange
        serve, base = serve_html
        html = (
            "<html><body>"
            f'<img src="{base}/a.jpg">'
            f'<img src="{base}/b.png">'
            "</body></html>"
        )
        page_url = serve(html)
        # Act
        img_urls = get_image_urls(page_url, pattern=r"\.jpg$")
        # Assert
        assert all(url.endswith(".jpg") for url in img_urls)

    def test_same_domain_excludes_other_hosts(self, serve_html):
        # Arrange
        serve, base = serve_html
        html = (
            "<html><body>"
            f'<img src="{base}/local.jpg">'
            '<img src="https://cdn.other.example/x.jpg">'
            "</body></html>"
        )
        page_url = serve(html)
        # Act
        img_urls = get_image_urls(page_url, same_domain=True)
        # Assert
        assert img_urls == [f"{base}/local.jpg"]

    def test_request_failure_returns_empty_list(self, refused_url):
        # Arrange
        # (refused_url points at a closed port)
        # Act
        img_urls = get_image_urls(refused_url)
        # Assert
        assert img_urls == []

    def test_page_without_images_returns_empty_list(self, serve_html):
        # Arrange
        serve, _base = serve_html
        page_url = serve("<html><body>No images here</body></html>")
        # Act
        img_urls = get_image_urls(page_url)
        # Assert
        assert img_urls == []


class TestScrapingModuleImport:
    def test_get_urls_is_exported(self):
        # Arrange
        import scitex_web

        # Act
        present = hasattr(scitex_web, "get_urls")
        # Assert
        assert present

    def test_get_image_urls_is_exported(self):
        # Arrange
        import scitex_web

        # Act
        present = hasattr(scitex_web, "get_image_urls")
        # Assert
        assert present

    def test_download_images_is_exported(self):
        # Arrange
        import scitex_web

        # Act
        present = hasattr(scitex_web, "download_images")
        # Assert
        assert present

    def test_get_urls_is_callable(self):
        # Arrange
        import scitex_web

        # Act
        ok = callable(scitex_web.get_urls)
        # Assert
        assert ok

    def test_get_image_urls_is_callable(self):
        # Arrange
        import scitex_web

        # Act
        ok = callable(scitex_web.get_image_urls)
        # Assert
        assert ok

    def test_download_images_is_callable(self):
        # Arrange
        import scitex_web

        # Act
        ok = callable(scitex_web.download_images)
        # Assert
        assert ok


if __name__ == "__main__":
    import os

    pytest.main([os.path.abspath(__file__)])

# EOF
