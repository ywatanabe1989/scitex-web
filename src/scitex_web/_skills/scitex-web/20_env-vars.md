---
description: |
  [TOPIC] Environment variables — scitex-web
  [DETAILS] Single `SCITEX_WEB_*` env var read by the package: `SCITEX_WEB_DOWNLOADS_DIR` (image download destination, used by `download_images.py`).
tags: [scitex-web-env-vars]
---

# Environment variables — scitex-web

scitex-web reads the following `SCITEX_WEB_*` variables at runtime.

| Variable | Default | Purpose |
|----------|---------|---------|
| `SCITEX_WEB_DOWNLOADS_DIR` | unset (caller must supply `output_dir`) | Default destination for `download_images()` when no `output_dir` argument is passed. Read at call time via `os.environ.get(...)` in `src/scitex_web/download_images.py`. |

## Usage

```bash
export SCITEX_WEB_DOWNLOADS_DIR=~/Downloads/scitex-web
python -c "import scitex_web; scitex_web.download_images(html_or_url)"
```

If the variable is unset and no `output_dir` is supplied, the caller is
responsible for choosing a destination. There are no other `SCITEX_WEB_*`
variables; the package leaves credential / network configuration to the
underlying `requests` / `urllib` stack and to NCBI E-utilities defaults.

## Source of truth

```text
src/scitex_web/download_images.py:218
    output_dir = os.environ.get("SCITEX_WEB_DOWNLOADS_DIR")
```

If a future commit adds another `SCITEX_WEB_*` variable, update this
table — the audit-skills SK111 rule re-greps the source on every run.
