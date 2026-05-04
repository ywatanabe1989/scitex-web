---
description: |
  [TOPIC] scitex-web Installation
  [DETAILS] pip install scitex-web (requests/BeautifulSoup-backed); smoke verify with search_pubmed.
tags: [scitex-web-installation]
---

# Installation

## Standard

```bash
pip install scitex-web
```

Pulls `requests`, `beautifulsoup4`, `lxml` and friends for HTML
scraping and NCBI E-utilities XML parsing.

## Umbrella

```bash
pip install scitex            # also exposes the same module as scitex.web
```

`pip install scitex-web` alone does NOT make `import scitex.web`
work — install the umbrella for that form. See
`../../general/02_interface-python-api.md`.

## Verify

```bash
python -c "import scitex_web; print(scitex_web.__version__)"
python -c "from scitex_web import search_pubmed; print(len(search_pubmed('CRISPR', n=3)))"
```

Expected: a version string, then `3` (or fewer if the NCBI rate-limit
kicks in — re-run a moment later).

## Notes

- NCBI E-utilities throttles to ~3 req/s anonymously; set
  `NCBI_API_KEY` in the environment to lift the limit to ~10 req/s.
- CrossRef metric lookups (`get_crossref_metrics`) honor the
  `CROSSREF_MAILTO` env var to use the polite pool.
