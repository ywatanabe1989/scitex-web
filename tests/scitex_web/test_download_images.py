#!/usr/bin/env python3
"""Tests for scitex_web.download_images public surface.

Network and Pillow-dependent paths are intentionally not exercised here —
we focus on the deterministic helpers (`_normalize_url_for_directory`,
`_is_direct_image_url`, `_get_default_download_dir`) that any reasonable
test environment can run without external services.
"""

import os

import pytest

from scitex_web.download_images import (
    _get_default_download_dir,
    _is_direct_image_url,
    _normalize_url_for_directory,
)


@pytest.fixture
def scitex_dir_env(tmp_path):
    """Set SCITEX_DIR to a tmp path for the test, restore afterward."""
    saved = os.environ.get("SCITEX_DIR")
    os.environ["SCITEX_DIR"] = str(tmp_path)
    try:
        yield str(tmp_path)
    finally:
        if saved is None:
            os.environ.pop("SCITEX_DIR", None)
        else:
            os.environ["SCITEX_DIR"] = saved


@pytest.fixture
def no_scitex_dir_env():
    """Ensure SCITEX_DIR is unset for the test, restore afterward."""
    saved = os.environ.pop("SCITEX_DIR", None)
    try:
        yield
    finally:
        if saved is not None:
            os.environ["SCITEX_DIR"] = saved


class TestNormalizeUrlForDirectory:
    def test_strips_www_and_uses_domain_only(self):
        # Arrange
        url = "https://www.example.com/"
        # Act
        out = _normalize_url_for_directory(url)
        # Assert
        assert out == "example.com"

    def test_path_components_retain_domain_segment(self):
        # Arrange
        url = "https://example.com/foo/bar"
        # Act
        out = _normalize_url_for_directory(url)
        # Assert
        assert "example.com" in out

    def test_path_components_join_with_dashes(self):
        # Arrange
        url = "https://example.com/foo/bar"
        # Act
        out = _normalize_url_for_directory(url)
        # Assert
        assert "foo-bar" in out

    def test_unsafe_query_mark_is_stripped(self):
        # Arrange
        url = "https://example.com/a?b=1&c=2"
        # Act
        out = _normalize_url_for_directory(url)
        # Assert
        assert "?" not in out

    def test_unsafe_ampersand_is_stripped(self):
        # Arrange
        url = "https://example.com/a?b=1&c=2"
        # Act
        out = _normalize_url_for_directory(url)
        # Assert
        assert "&" not in out

    def test_repeated_dashes_are_collapsed(self):
        # Arrange
        url = "https://example.com/a?b=1&c=2"
        # Act
        out = _normalize_url_for_directory(url)
        # Assert
        assert "--" not in out

    def test_long_paths_truncated_to_100_chars(self):
        # Arrange
        url = "https://example.com/" + "x" * 500
        # Act
        out = _normalize_url_for_directory(url)
        # Assert
        assert len(out) <= 100


class TestIsDirectImageUrl:
    @pytest.mark.parametrize(
        "url, expected",
        [
            ("https://example.com/photo.jpg", True),
            ("https://example.com/photo.JPEG", True),
            ("https://example.com/img.png", True),
            ("https://example.com/anim.gif", True),
            ("https://example.com/pic.webp", True),
            ("https://example.com/index.html", False),
            ("https://example.com/", False),
            ("https://example.com/folder", False),
        ],
    )
    def test_url_classification_matches_expected(self, url, expected):
        # Arrange
        # (url + expected are parametrized inputs)
        # Act
        result = _is_direct_image_url(url)
        # Assert
        assert result is expected


class TestGetDefaultDownloadDir:
    def test_default_dir_starts_with_scitex_dir_env(self, scitex_dir_env):
        # Arrange
        # (scitex_dir_env fixture sets SCITEX_DIR)
        # Act
        out = _get_default_download_dir()
        # Assert
        assert out.startswith(scitex_dir_env)

    def test_default_dir_ends_with_web_downloads(self, scitex_dir_env):
        # Arrange
        # (scitex_dir_env fixture sets SCITEX_DIR)
        # Act
        out = _get_default_download_dir()
        # Assert
        assert out.endswith(os.path.join("web", "downloads"))

    def test_default_dir_falls_back_to_home_when_env_unset(self, no_scitex_dir_env):
        # Arrange
        # (no_scitex_dir_env fixture clears SCITEX_DIR)
        # Act
        out = _get_default_download_dir()
        # Assert
        assert out.endswith(os.path.join(".scitex", "web", "downloads"))


if __name__ == "__main__":
    pytest.main([os.path.abspath(__file__), "-v"])

# EOF
