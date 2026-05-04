---
description: |
  [TOPIC] scitex-web Python API
  [DETAILS] Top-level public callables — search_pubmed, get_crossref_metrics, summarize_url, crawl_url, crawl_to_json, get_urls, get_image_urls, download_images.
tags: [scitex-web-python-api]
---

# Python API

Public surface re-exported from `scitex_web` (see `__all__`).

## Public symbols

| Name                       | Purpose                                                  |
|----------------------------|----------------------------------------------------------|
| `__version__`              | Installed package version                                |
| `search_pubmed(query, n=20)` | Search NCBI PubMed; returns list of paper dicts        |
| `get_crossref_metrics(doi)`  | Fetch citation count + metadata from CrossRef          |
| `summarize_url(url)`         | Extract main content + summary from a URL              |
| `crawl_url(url, ...)`        | Crawl a single page (links, text, metadata)            |
| `crawl_to_json(url, ...)`    | Crawl and serialize result to JSON                     |
| `get_urls(html)`             | Extract all `href` targets from an HTML string         |
| `get_image_urls(html)`       | Extract all `<img src>` targets from an HTML string    |
| `download_images(urls, dir)` | Download a list of image URLs into a directory         |

## PubMed result shape

```python
papers = search_pubmed("CRISPR", n=5)
papers[0].keys()
# dict_keys(['pmid', 'title', 'abstract', 'doi', 'journal',
#            'authors', 'year', ...])
```

## Useful options

- `search_pubmed(query, n=N)` — `n` is the maximum hits returned
  (PubMed's hard cap per request applies).
- `get_crossref_metrics(doi)` — returns a dict; key fields:
  `citation_count`, `reference_count`, `is_referenced_by_count`.
- `download_images(urls, out_dir)` — skips already-downloaded files
  (idempotent on filename).

## Environment variables

| Variable          | Effect                                               |
|-------------------|------------------------------------------------------|
| `NCBI_API_KEY`    | Lift PubMed rate limit to ~10 req/s                  |
| `CROSSREF_MAILTO` | Use CrossRef polite pool (recommended)               |

## Not exposed

- Private `_search_pubmed`, `_fetch_details`, `_format_bibtex`, etc. —
  internal helpers; signatures may change.
- Heavy crawling — use a real crawler (Scrapy) for site-scale jobs.
