---
name: scitex-web
description: |
  [WHAT] Web scraping + PubMed search + URL summarization.
  [WHEN] User asks about scitex-web functionality.
  [HOW] `pip install scitex-web` then `import scitex_web`; see leaf skills for details.
tags: [scitex-web]
primary_interface: python
interfaces:
  python: 2
  cli: 1
  mcp: 0
  skills: 2
  http: 0
---

> **Interfaces:** Python ⭐⭐ · CLI ⭐ · MCP — · Skills ⭐⭐ · Hook — · HTTP —

# scitex-web

Web scraping + PubMed search + URL summarization. `get_urls(html)`/`get_image_urls(html)` extract href/src; `search_pubmed(query, n=20)` returns structured paper records via NCBI E-utilities; `get_crossref_metrics(doi)` fetches citation counts. Drop-in replacement for BeautifulSoup boilerplate and bespoke E-utilities XML parsers.

See README.md and the package's public `__init__.py` for the full
function list. This skill leaf exists so agents discover the package
exists and roughly what shape it has — refer to the source for
signatures.

## Sub-skills

- [01_installation.md](01_installation.md) — pip install + smoke verify
- [02_quick-start.md](02_quick-start.md) — PubMed + scrape + summarize examples
- [03_python-api.md](03_python-api.md) — public callables reference
