"""
Content shared across more than one `arklight new` template.

Currently just the scaffolded `arklight.config.py` -- every template
writes the same one, so it lives here once rather than being
duplicated per-template and risking drift between copies.
"""

from __future__ import annotations

ARKLIGHT_CONFIG_PY = '''\
"""
ARKlight project configuration -- optional.

ARKlight works fine without this file; every section below is
commented out and only takes effect once you uncomment it. See the
"Configuration" section of the ARKlight README (or `arklight/config.py`
in the ARKlight source) for the full, current list of sections.
"""

CONFIG = {
    # Settings for `arklight live-streaming` (the dev server that
    # rebuilds and live-reloads on save). Only read when you use
    # `--subscribe`; irrelevant to a plain `arklight build`.
    # "live_streaming": {
    #     "host": "127.0.0.1",
    #     "port": 8347,
    # },
}
'''
