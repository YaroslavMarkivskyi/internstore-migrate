"""Every test under evals/ is auto-marked `eval` (deselected by the default
`pytest` run — see pyproject `addopts`). Running them hits a real Gemini
model and costs a few cents; each eval module skips itself unless
`GCP_PROJECT` is set.
"""

from pathlib import Path

import pytest

_EVALS_DIR = Path(__file__).parent


def pytest_collection_modifyitems(config, items):
    for item in items:
        try:
            item.path.relative_to(_EVALS_DIR)
        except ValueError:
            continue
        item.add_marker(pytest.mark.eval)
