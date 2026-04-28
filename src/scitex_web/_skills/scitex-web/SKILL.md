---
name: scitex-web
description: Web scraping + PubMed search + URL summarization. `get_urls(html)`/`get_image_urls(html)` extract href/src; `search_pubmed(query, n=20)` returns structured paper records via NCBI E-utilities; `get_crossref_metrics(doi)` fetches citation counts. Drop-in replacement for BeautifulSoup boilerplate and bespoke E-utilities XML parsers.
primary_interface: python
interfaces:
  python: 2
  cli: 1
  mcp: 0
  skills: 2
  hook: 0
  http: 0
canonical-location: scitex-web/src/scitex_web/_skills/scitex-web/SKILL.md
tags: [scitex-web, scitex-package]
---

> **Interfaces:** Python ⭐⭐ · CLI ⭐ · MCP — · Skills ⭐⭐ · Hook — · HTTP —

# scitex-web

Web scraping + PubMed search + URL summarization. `get_urls(html)`/`get_image_urls(html)` extract href/src; `search_pubmed(query, n=20)` returns structured paper records via NCBI E-utilities; `get_crossref_metrics(doi)` fetches citation counts. Drop-in replacement for BeautifulSoup boilerplate and bespoke E-utilities XML parsers.

See README.md and the package's public `__init__.py` for the full
function list. This skill leaf exists so agents discover the package
exists and roughly what shape it has — refer to the source for
signatures.

<!-- EOF -->
