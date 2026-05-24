#!./env/bin/python3
# -*- coding: utf-8 -*-
# Time-stamp: "2024-07-29 21:43:30 (ywatanabe)"
# ./src/scitex/web/_crawl.py


import json
import urllib.parse
from concurrent.futures import ThreadPoolExecutor, as_completed
from pprint import pprint

import requests
from bs4 import BeautifulSoup
from scitex_dev import try_import_optional
from tqdm import tqdm

Document = try_import_optional(
    "readability", "Document", extra="readability", pkg="scitex-web"
)
if Document is None:
    # Older readability-lxml layouts (pre-0.8) shipped ``Document`` under
    # ``readability.readability`` instead of the package root. Fall back
    # transparently so callers don't have to care.
    Document = try_import_optional(
        "readability.readability",
        "Document",
        extra="readability",
        pkg="scitex-web",
    )

import re

# def crawl_url(url, max_depth=1):
#     print("\nCrawling...")
#     visited = set()
#     to_visit = [(url, 0)]
#     contents = {}

#     while to_visit:
#         current_url, depth = to_visit.pop(0)
#         if current_url in visited or depth > max_depth:
#             continue

#         try:
#             response = requests.get(current_url)
#             if response.status_code == 200:
#                 visited.add(current_url)
#                 contents[current_url] = response.text
#                 soup = BeautifulSoup(response.text, "html.parser")

#                 for link in soup.find_all("a", href=True):
#                     absolute_link = urllib.parse.urljoin(
#                         current_url, link["href"]
#                     )
#                     if absolute_link not in visited:
#                         to_visit.append((absolute_link, depth + 1))

#         except requests.RequestException:
#             pass

#     return visited, contents


_DOCUMENT_DEFAULT = object()  # sentinel: "caller did not specify"


def extract_main_content(html, *, document_cls=_DOCUMENT_DEFAULT):
    """Extract readable text from raw HTML.

    When ``document_cls`` is omitted it uses the module-level ``Document``
    (the readability extractor). Pass ``document_cls=None`` explicitly to
    force the tag-stripping fallback, or pass a different extractor class.
    Callers normally omit it.
    """
    if document_cls is _DOCUMENT_DEFAULT:
        document_cls = Document

    if document_cls is None:
        # Fallback: just strip HTML tags
        content = re.sub("<[^<]+?>", "", html)
        content = " ".join(content.split())
        return content[:5_000]  # Limit to first 5000 chars

    doc = document_cls(html)
    content = doc.summary()
    # Remove HTML tags
    content = re.sub("<[^<]+?>", "", content)
    # Remove extra whitespace
    content = " ".join(content.split())
    return content


def crawl_url(url, max_depth=1):
    print("\nCrawling...")
    visited = set()
    to_visit = [(url, 0)]
    contents = {}

    while to_visit:
        current_url, depth = to_visit.pop(0)
        if current_url in visited or depth > max_depth:
            continue

        try:
            response = requests.get(current_url)
            if response.status_code == 200:
                visited.add(current_url)
                main_content = extract_main_content(response.text)
                contents[current_url] = main_content
                soup = BeautifulSoup(response.text, "html.parser")

                for link in soup.find_all("a", href=True):
                    absolute_link = urllib.parse.urljoin(current_url, link["href"])
                    if absolute_link not in visited:
                        to_visit.append((absolute_link, depth + 1))

        except requests.RequestException:
            pass

    return visited, contents


def crawl_to_json(start_url, *, crawler=None, genai_factory=None):
    """Crawl ``start_url`` and summarize each page into a JSON document.

    ``crawler`` defaults to :func:`crawl_url`; ``genai_factory`` defaults to
    :func:`_get_genai`. Both are injectable so callers can supply a real
    local crawler / a deterministic summarizer without monkey-patching.
    """
    if crawler is None:
        crawler = crawl_url
    if genai_factory is None:
        genai_factory = _get_genai

    if not start_url.startswith("http"):
        start_url = "https://" + start_url
    crawled_urls, contents = crawler(start_url)

    print("\nSummalizing as json...")

    def process_url(url):
        llm = genai_factory("gpt-4o-mini")
        return {
            "url": url,
            "content": llm(f"Summarize this page in 1 line:\n\n{contents[url]}"),
        }

    with ThreadPoolExecutor() as executor:
        future_to_url = {executor.submit(process_url, url): url for url in crawled_urls}
        crawled_pages = []
        for future in tqdm(
            as_completed(future_to_url),
            total=len(crawled_urls),
            desc="Processing URLs",
        ):
            crawled_pages.append(future.result())

    result = {"start_url": start_url, "crawled_pages": crawled_pages}

    return json.dumps(result, indent=2)


def _get_genai(model: str):
    """Lazy-load scitex.ai.GenAI; raise a clear ImportError if scitex isn't installed."""
    try:
        from scitex_ai import GenAI  # type: ignore
    except ImportError as e:
        raise ImportError(
            "summarize_url / summarize_all require the 'scitex' umbrella package "
            "for scitex.ai.GenAI. Install with: pip install scitex"
        ) from e
    return GenAI(model)


def summarize_all(json_contents, *, genai_factory=None):
    """Summarize a crawled-JSON document into bullet points via an LLM.

    ``genai_factory`` defaults to :func:`_get_genai`; injectable so callers
    can pass a deterministic summarizer.
    """
    if genai_factory is None:
        genai_factory = _get_genai
    llm = genai_factory("gpt-4o-mini")
    out = llm(f"Summarize this json file with 5 bullet points:\n\n{json_contents}")
    return out


def summarize_url(start_url, *, crawl_fn=None, summarize_fn=None):
    """Crawl ``start_url`` then summarize it.

    ``crawl_fn`` defaults to :func:`crawl_to_json`; ``summarize_fn`` defaults
    to :func:`summarize_all`. Both are injectable so the composition can be
    exercised with deterministic stand-ins.
    """
    if crawl_fn is None:
        crawl_fn = crawl_to_json
    if summarize_fn is None:
        summarize_fn = summarize_all

    json_result = crawl_fn(start_url)
    ground_summary = summarize_fn(json_result)

    pprint(ground_summary)
    return ground_summary, json_result


main = summarize_url

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="")
    parser.add_argument("--url", "-u", type=str, help="(default: %(default)s)")
    args = parser.parse_args()
    print(f"Args: {args}")

    main(args.url)
