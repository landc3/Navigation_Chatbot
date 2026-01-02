"""
Test runner hardening.

On some Windows/Python 3.12 setups, third-party pytest plugins installed globally
(e.g. langsmith) may be auto-loaded and crash due to dependency/version conflicts
unrelated to this repo.

Setting PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 prevents pytest from auto-loading
external plugins, keeping the test environment deterministic.
"""

import os

os.environ.setdefault("PYTEST_DISABLE_PLUGIN_AUTOLOAD", "1")


