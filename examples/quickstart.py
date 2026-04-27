"""scitex-web quickstart: explore the public API surface (no network calls).

This script imports scitex-web and asserts that its declared public API is
fully wired up and callable. We deliberately avoid making real HTTP requests
so the smoke test stays fast and deterministic.
"""

import inspect

import scitex_web


def main():
    print("scitex_web", scitex_web.__version__)
    print("Public API:")
    for name in scitex_web.__all__:
        obj = getattr(scitex_web, name)
        kind = "coroutine" if inspect.iscoroutinefunction(obj) else type(obj).__name__
        sig = ""
        try:
            sig = str(inspect.signature(obj))
        except (TypeError, ValueError):
            pass
        print(f"  - {name:20s} {kind:18s} {sig}")
        assert callable(obj), f"{name} is not callable"

    # Sanity check: search_pubmed has a sensible signature with a 'query' arg.
    sig = inspect.signature(scitex_web.search_pubmed)
    assert any(
        p in sig.parameters for p in ("query", "term", "search_term", "keyword")
    ), f"unexpected search_pubmed signature: {sig}"
    print("\nsearch_pubmed signature looks reasonable:", sig)


if __name__ == "__main__":
    main()
