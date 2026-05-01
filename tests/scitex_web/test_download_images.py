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
        out = _normalize_url_for_directory("https://www.example.com/")
        assert out == "example.com"

    def test_path_components_become_dashes(self):
        out = _normalize_url_for_directory("https://example.com/foo/bar")
        assert "example.com" in out
        assert "foo-bar" in out

    def test_unsafe_chars_collapsed(self):
        out = _normalize_url_for_directory("https://example.com/a?b=1&c=2")
        assert "?" not in out
        assert "&" not in out
        assert "--" not in out

    def test_long_paths_truncated_to_100_chars(self):
        out = _normalize_url_for_directory("https://example.com/" + "x" * 500)
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
    def test_url_classification(self, url, expected):
        assert _is_direct_image_url(url) is expected


class TestGetDefaultDownloadDir:
    def test_uses_scitex_dir_env(self, monkeypatch, tmp_path):
        monkeypatch.setenv("SCITEX_DIR", str(tmp_path))
        out = _get_default_download_dir()
        assert out.startswith(str(tmp_path))
        assert out.endswith(os.path.join("web", "downloads"))

    def test_falls_back_to_home_when_env_unset(self, monkeypatch):
        monkeypatch.delenv("SCITEX_DIR", raising=False)
        out = _get_default_download_dir()
        assert out.endswith(os.path.join(".scitex", "web", "downloads"))


if __name__ == "__main__":
    pytest.main([os.path.abspath(__file__), "-v"])

# EOF
