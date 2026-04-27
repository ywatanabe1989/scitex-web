# scitex-web

<!-- scitex-badges:start -->
[![PyPI](https://img.shields.io/pypi/v/scitex-web.svg)](https://pypi.org/project/scitex-web/)
[![Python](https://img.shields.io/pypi/pyversions/scitex-web.svg)](https://pypi.org/project/scitex-web/)
[![Tests](https://github.com/ywatanabe1989/scitex-web/actions/workflows/test.yml/badge.svg)](https://github.com/ywatanabe1989/scitex-web/actions/workflows/test.yml)
[![Install Test](https://github.com/ywatanabe1989/scitex-web/actions/workflows/install-test.yml/badge.svg)](https://github.com/ywatanabe1989/scitex-web/actions/workflows/install-test.yml)
[![Coverage](https://codecov.io/gh/ywatanabe1989/scitex-web/graph/badge.svg)](https://codecov.io/gh/ywatanabe1989/scitex-web)
[![Docs](https://readthedocs.org/projects/scitex-web/badge/?version=latest)](https://scitex-web.readthedocs.io/en/latest/)
[![License: AGPL v3](https://img.shields.io/badge/license-AGPL_v3-blue.svg)](https://www.gnu.org/licenses/agpl-3.0)
<!-- scitex-badges:end -->


Web scraping + PubMed search + URL summarization helpers, extracted from the [SciTeX](https://github.com/ywatanabe1989/scitex-python) ecosystem as a standalone package.

## Install

```bash
pip install scitex-web
pip install "scitex-web[readability]"   # readability-lxml for cleaner extraction
```

## API

```python
import scitex_web as web

# Scraping
web.get_urls(url, pattern=r"\.pdf$")
web.get_image_urls(url, min_size=128)
web.download_images(url, out_dir="imgs", same_domain=True)

# PubMed
web.search_pubmed("CRISPR Cas9 review", retmax=50)

# URL summarization (requires scitex.ai)
web.summarize_url("https://example.com/article")
```

## Status

Standalone fork of `scitex.web`. Deps: requests / aiohttp / bs4 / tqdm. The
umbrella package's `scitex.web` import path is preserved via a `sys.modules`-alias
bridge.

Decoupling notes:
- `scitex.logging.getLogger` → stdlib `logging.getLogger`.
- `scitex.str.printc` (colored print) → tiny inline ANSI helper.
- `scitex.ai.GenAI` (used by `summarize_url`) → deferred import that raises
  a clear ImportError if the umbrella `scitex` package isn't installed.

14/23 tests pass (7 pre-existing upstream failures around bs4 mocking that fail
in scitex-python too — unrelated to extraction; 2 skipped).

## License

AGPL-3.0-only (see [LICENSE](./LICENSE)).
