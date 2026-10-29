"""Every scenario of a built step (docs/spec/*.feature) has a test carrying
its number, and every such test belongs to a scenario that exists."""

from pathlib import Path
import re

ROOT = Path(__file__).resolve().parent.parent

# The steps of each feature (its scenario prefix) that are built.
BUILT_STEPS: dict[str, set[int]] = {
    "FZ": {1, 2, 3, 5},  # docs/spec/fritz.md, Steps
}

_TAG = re.compile(r"^\s*@step(\d+)\b")
_SCENARIO = re.compile(r"^\s*Scenario:\s*([A-Z]+)-([0-9A-Z]+)\b")
_TEST = re.compile(r"^(?:async )?def test_([A-Z]{2}[0-9A-Z]+)_\w*\(")


def _scenarios() -> dict[str, int]:
    out = {}
    for feature in sorted((ROOT / "docs" / "spec").glob("*.feature")):
        step = 0
        for line in feature.read_text().splitlines():
            if m := _TAG.match(line):
                step = int(m[1])
            elif m := _SCENARIO.match(line):
                out[m[1] + m[2]] = step
    return out


def _tests() -> set[str]:
    return {
        m[1]
        for path in (ROOT / "tests").rglob("test_*.py")
        for line in path.read_text().splitlines()
        if (m := _TEST.match(line))
    }


def test_scenarios_have_tests():
    scenarios, tests = _scenarios(), _tests()
    missing = [s for s, step in scenarios.items() if step in BUILT_STEPS.get(s[:2], set()) and s not in tests]
    assert not missing, f"scenarios of built steps without a test: {missing}"
    assert not tests - scenarios.keys(), f"tests of no scenario: {sorted(tests - scenarios.keys())}"
