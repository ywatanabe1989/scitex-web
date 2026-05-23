#!/usr/bin/env python3
"""Tests for scitex_web.download_images public surface.

Network and Pillow-dependent paths are intentionally not exercised here —
we focus on the deterministic helpers (`_normalize_url_for_directory`,
`_is_direct_image_url`, `_get_default_download_dir`) that any reasonable
test environment can run without external services.
"""

from __future__ import annotations

import os
from collections.abc import Iterator

import pytest

from scitex_web.download_images import (
    _get_default_download_dir,
    _is_direct_image_url,
    _normalize_url_for_directory,
)


@pytest.fixture
def scitex_dir_env(tmp_path) -> Iterator[str]:
    """Set ``SCITEX_DIR`` to a tmp dir for the duration of one test.

    `yield`-based env fixture, the canonical no-mock replacement for
    ``monkeypatch.setenv``. The original value is restored on teardown.
    """
    # Arrange
    previous = os.environ.get("SCITEX_DIR")
    os.environ["SCITEX_DIR"] = str(tmp_path)
    try:
        yield str(tmp_path)
    finally:
        if previous is None:
            os.environ.pop("SCITEX_DIR", None)
        else:
            os.environ["SCITEX_DIR"] = previous


@pytest.fixture
def scitex_dir_unset() -> Iterator[None]:
    """Ensure ``SCITEX_DIR`` is unset for the test, restored on teardown."""
    # Arrange
    previous = os.environ.pop("SCITEX_DIR", None)
    try:
        yield None
    finally:
        if previous is not None:
            os.environ["SCITEX_DIR"] = previous


class TestNormalizeUrlForDirectory:
    def test_strips_www_prefix_from_domain(self):
        # Arrange
        url = "https://www.example.com/"
        # Act
        out = _normalize_url_for_directory(url)
        # Assert
        assert out == "example.com"

    def test_includes_domain_when_path_present(self):
        # Arrange
        url = "https://example.com/foo/bar"
        # Act
        out = _normalize_url_for_directory(url)
        # Assert
        assert "example.com" in out

    def test_joins_path_segments_with_dashes(self):
        # Arrange
        url = "https://example.com/foo/bar"
        # Act
        out = _normalize_url_for_directory(url)
        # Assert
        assert "foo-bar" in out

    def test_strips_question_mark_from_query_string(self):
        # Arrange
        url = "https://example.com/a?b=1&c=2"
        # Act
        out = _normalize_url_for_directory(url)
        # Assert
        assert "?" not in out

    def test_strips_ampersand_from_query_string(self):
        # Arrange
        url = "https://example.com/a?b=1&c=2"
        # Act
        out = _normalize_url_for_directory(url)
        # Assert
        assert "&" not in out

    def test_collapses_consecutive_dashes(self):
        # Arrange
        url = "https://example.com/a?b=1&c=2"
        # Act
        out = _normalize_url_for_directory(url)
        # Assert
        assert "--" not in out

    def test_truncates_long_paths_to_100_chars(self):
        # Arrange
        url = "https://example.com/" + "x" * 500
        # Act
        out = _normalize_url_for_directory(url)
        # Assert
        assert len(out) <= 100


class TestIsDirectImageUrl:
    @pytest.mark.parametrize(
        "url",
        [
            "https://example.com/photo.jpg",
            "https://example.com/photo.JPEG",
            "https://example.com/img.png",
            "https://example.com/anim.gif",
            "https://example.com/pic.webp",
        ],
    )
    def test_returns_true_for_recognised_image_extensions(self, url):
        # Arrange
        # Act
        result = _is_direct_image_url(url)
        # Assert
        assert result is True

    @pytest.mark.parametrize(
        "url",
        [
            "https://example.com/index.html",
            "https://example.com/",
            "https://example.com/folder",
        ],
    )
    def test_returns_false_for_non_image_urls(self, url):
        # Arrange
        # Act
        result = _is_direct_image_url(url)
        # Assert
        assert result is False


class TestGetDefaultDownloadDir:
    def test_returns_path_under_scitex_dir_env(self, scitex_dir_env):
        # Arrange
        # Act
        out = _get_default_download_dir()
        # Assert
        assert out.startswith(scitex_dir_env)

    def test_returns_path_ending_in_web_downloads_when_env_set(
        self, scitex_dir_env
    ):
        # Arrange
        # Act
        out = _get_default_download_dir()
        # Assert
        assert out.endswith(os.path.join("web", "downloads"))

    def test_falls_back_to_home_dotscitex_when_env_unset(self, scitex_dir_unset):
        # Arrange
        # Act
        out = _get_default_download_dir()
        # Assert
        assert out.endswith(os.path.join(".scitex", "web", "downloads"))


if __name__ == "__main__":
    pytest.main([os.path.abspath(__file__), "-v"])

# EOF
