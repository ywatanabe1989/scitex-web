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

<p align="center">
  <a href="https://scitex.ai">
    <img src="docs/scitex-logo-blue-cropped.png" alt="SciTeX" width="400">
  </a>
</p>

<p align="center"><b>Web scraping + PubMed search + URL summarization helpers.</b></p>

<p align="center">
  <a href="https://scitex-web.readthedocs.io/">Full Documentation</a> · <code>pip install scitex-web</code>
</p>

---

## Installation

```bash
pip install scitex-web
pip install "scitex-web[readability]"   # readability-lxml for cleaner extraction
```

## Quick Start

```python
import scitex_web as web

results = web.search_pubmed("CRISPR Cas9 review", retmax=5)
images = web.get_image_urls("https://example.com/gallery", min_size=128)
```

## 1 Interfaces

<details>
<summary><strong>Python API</strong></summary>

<br>

```python
import scitex_web as web

# Scraping
web.get_urls(url, pattern=r"\.pdf$")
web.get_image_urls(url, min_size=128)
web.download_images(url, out_dir="imgs", same_domain=True)

# PubMed
web.search_pubmed("CRISPR Cas9 review", retmax=50)

# URL summarization (requires scitex.ai umbrella)
web.summarize_url("https://example.com/article")
```

</details>

## Status

Standalone fork of `scitex.web`. Deps: requests / aiohttp / bs4 / tqdm. The
umbrella package's `scitex.web` import path is preserved via a
`sys.modules`-alias bridge.

Decoupling notes:
- `scitex.logging.getLogger` → stdlib `logging.getLogger`.
- `scitex.str.printc` (colored print) → tiny inline ANSI helper.
- `scitex.ai.GenAI` (used by `summarize_url`) → deferred import that raises
  a clear ImportError if the umbrella `scitex` package isn't installed.

## Part of SciTeX

`scitex-web` is part of [**SciTeX**](https://scitex.ai). Install via
the umbrella with `pip install scitex[web]` to use as
`scitex.web` (Python) or `scitex web ...` (CLI).

>Four Freedoms for Research
>
>0. The freedom to **run** your research anywhere — your machine, your terms.
>1. The freedom to **study** how every step works — from raw data to final manuscript.
>2. The freedom to **redistribute** your workflows, not just your papers.
>3. The freedom to **modify** any module and share improvements with the community.
>
>AGPL-3.0 — because we believe research infrastructure deserves the same freedoms as the software it runs on.

## License

AGPL-3.0-only (see [LICENSE](./LICENSE)).

---

<p align="center">
  <a href="https://scitex.ai" target="_blank"><img src="docs/scitex-icon-navy-inverted.png" alt="SciTeX" width="40"/></a>
</p>
