from __future__ import annotations

import re

_CAMEL_BOUNDARY = re.compile(r"(?<=[a-z0-9])(?=[A-Z])")


def tokenize(name: str) -> list[str]:
    """Split `PascalCase`/`camelCase`/`snake_case`/`kebab-case` into
    lowercase tokens."""
    spaced = _CAMEL_BOUNDARY.sub(" ", name).replace("_", " ").replace("-", " ")
    return [t.lower() for t in spaced.split() if t]
