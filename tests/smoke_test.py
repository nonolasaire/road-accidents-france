"""Headless smoke test of the Streamlit app: every scenario must run without exception.

Runs the whole page with Streamlit's AppTest (no browser), for the national view, several départements
(large, rural, Paris, Corsica) and edge cases (single year, single road user, very small selection).
Needs data/processed/ (built by scripts/build_data.py).

Usage:  .venv/Scripts/python.exe tests/smoke_test.py      (exit code 1 if a scenario fails)
The "missing ScriptRunContext" lines printed by AppTest are expected outside a real server and can be ignored.
"""
import sys
import time
from pathlib import Path

from streamlit.logger import set_log_level
from streamlit.testing.v1 import AppTest

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT))   # so that the app can import utils/ and sections/
set_log_level("error")             # fewer Streamlit log lines (AppTest still prints some, see docstring)

SCENARIOS = [  # (département, years, road users); None = default
    (None, None, None), ("29", None, None), ("48", None, None), ("75", None, None), ("2A", None, None),
    (None, (2024, 2024), None), (None, (2019, 2019), None), ("2A", (2024, 2024), None),
    (None, None, ["Bicycle"]), ("48", None, ["E-scooter / PMD"]), ("75", (2020, 2020), ["Heavy vehicle / bus"]),
]


def run(dep: str | None, years: tuple | None, modes: list | None) -> list[str]:
    """Run the app with these sidebar values; return the exceptions raised (empty list = OK)."""
    at = AppTest.from_file(str(PROJECT / "app.py"), default_timeout=180)
    at.run()
    if dep:
        at.sidebar.selectbox[0].set_value(dep)
    if years:
        at.sidebar.slider[0].set_value(years)
    if modes:
        at.sidebar.multiselect[0].set_value(modes)
    at.run()
    return [str(e.value) for e in at.exception]


def main() -> int:
    failed = 0
    for dep, years, modes in SCENARIOS:
        t0 = time.time()
        errors = run(dep, years, modes)
        failed += bool(errors)
        print(f"{'OK  ' if not errors else 'FAIL'} dep={dep} years={years} modes={modes} ({time.time() - t0:.1f}s)")
        for e in errors:
            print("     ", e[:1500])
    print(f"\n{len(SCENARIOS) - failed}/{len(SCENARIOS)} scenarios passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
