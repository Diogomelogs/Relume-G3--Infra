# relluna/config/settings.py

import os

MODE = os.getenv("RELLUNA_MODE", "test").lower()
IS_TEST_MODE = MODE == "test"
IS_REAL_MODE = MODE == "real"