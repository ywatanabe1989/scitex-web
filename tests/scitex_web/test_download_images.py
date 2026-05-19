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


class TestNormalizeUrlForDirectory:
    def test_strips_www_and_uses_domain(self):
        # Arrange
        # Act
        # Arrange
        # Act
        # Arrange
        # Act
        out = _normalize_url_for_directory("https://www.example.com/")
        # Assert
        # Assert
        # Assert
        assert out == "example.com"

    def test_path_components_become_dashes_example_com_in_out(self):
        # Arrange
        # Arrange
        # Act
        # Arrange
        # Act
        out = _normalize_url_for_directory("https://example.com/foo/bar")
        # Act
        # Assert
        # Assert
        # Assert
        assert "example.com" in out

    def test_path_components_become_dashes_foo_bar_in_out(self):
        # Arrange
        # Arrange
        # Act
        # Arrange
        # Act
        out = _normalize_url_for_directory("https://example.com/foo/bar")
        # Act
        # Assert
        # Assert
        # Assert
        assert "foo-bar" in out


    def test_unsafe_chars_collapsed_not_in_out(self):
        # Arrange
        # Arrange
        # Act
        # Arrange
        # Act
        out = _normalize_url_for_directory("https://example.com/a?b=1&c=2")
        # Act
        # Assert
        # Assert
        # Assert
        assert "?" not in out

    def test_unsafe_chars_collapsed_not_in_out(self):
        # Arrange
        # Arrange
        # Act
        # Arrange
        # Act
        out = _normalize_url_for_directory("https://example.com/a?b=1&c=2")
        # Act
        # Assert
        # Assert
        # Assert
        assert "&" not in out

    def test_unsafe_chars_collapsed_not_in_out(self):
        # Arrange
        # Arrange
        # Act
        # Arrange
        # Act
        out = _normalize_url_for_directory("https://example.com/a?b=1&c=2")
        # Act
        # Assert
        # Assert
        # Assert
        assert "--" not in out


    def test_long_paths_truncated_to_100_chars(self):
        # Arrange
        # Act
        # Arrange
        # Act
        # Arrange
        # Act
        out = _normalize_url_for_directory("https://example.com/" + "x" * 500)
        # Assert
        # Assert
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
    def test_url_classification_is_direct_image_url_url_is_expected(self, url, expected):
        # Arrange
        # Act
        # Assert
        # Arrange
        # Act
        # Assert
        # Arrange
        # Act
        # Assert
        assert _is_direct_image_url(url) is expected


class TestGetDefaultDownloadDir:
    def test_uses_scitex_dir_env_out_startswith_str_tmp_path(self, monkeypatch, tmp_path):
        # Arrange
        # Arrange
        # Arrange
        monkeypatch.setenv("SCITEX_DIR", str(tmp_path))
        # Act
        # Act
        out = _get_default_download_dir()
        # Act
        # Assert
        # Assert
        # Assert
        assert out.startswith(str(tmp_path))

    def test_uses_scitex_dir_env_out_endswith_os_path_join_web_downloads(self, monkeypatch, tmp_path):
        # Arrange
        # Arrange
        # Arrange
        monkeypatch.setenv("SCITEX_DIR", str(tmp_path))
        # Act
        # Act
        out = _get_default_download_dir()
        # Act
        # Assert
        # Assert
        # Assert
        assert out.endswith(os.path.join("web", "downloads"))


    def test_falls_back_to_home_when_env_unset(self, monkeypatch):
        # Arrange
        # Arrange
        # Arrange
        monkeypatch.delenv("SCITEX_DIR", raising=False)
        # Act
        # Act
        # Act
        out = _get_default_download_dir()
        # Assert
        # Assert
        # Assert
        assert out.endswith(os.path.join(".scitex", "web", "downloads"))


if __name__ == "__main__":
    pytest.main([os.path.abspath(__file__), "-v"])

# EOF
