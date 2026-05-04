---
description: |
  [TOPIC] scitex-web Quick Start
  [DETAILS] Smallest example — search PubMed, scrape href/img URLs, summarize a page.
tags: [scitex-web-quick-start]
---

# Quick Start

## Search PubMed

```python
from scitex_web import search_pubmed

papers = search_pubmed("phase amplitude coupling", n=10)
for p in papers:
    print(p["title"], p["doi"])
```

Returns a list of dicts with `pmid`, `title`, `abstract`, `doi`,
`journal`, `authors`, `year`, etc.

## Scrape URLs from HTML

```python
import requests
from scitex_web import get_urls, get_image_urls

html = requests.get("https://example.com").text
print(get_urls(html))         # all href targets
print(get_image_urls(html))   # all <img src> targets
```

Drop-in replacement for the BeautifulSoup boilerplate.

## Summarize a URL

```python
from scitex_web import summarize_url

result = summarize_url("https://example.com/article")
print(result["title"], result["summary"])
```

Extracts the main article text and returns a dict with title, summary,
and metadata.

## CrossRef citation count

```python
from scitex_web import get_crossref_metrics

m = get_crossref_metrics("10.1038/s41586-020-2649-2")
print(m["citation_count"])
```
