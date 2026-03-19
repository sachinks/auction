"""
Flake8 linting tests — ensures the codebase stays clean.

Runs flake8 programmatically using the same .flake8 config that developers
use locally.  Any new violation will fail the test and print the offending
lines so CI feedback is immediate.
"""
import subprocess
import sys
from pathlib import Path

from django.test import SimpleTestCase

# The Django project root that contains .flake8 and .venv
DJANGO_ROOT = Path(__file__).resolve().parents[2]   # auction/auction/tests -> auction/
# The Python package to lint (auction/auction/)
AUCTION_PKG = DJANGO_ROOT / "auction"


class TestFlake8(SimpleTestCase):
    """Run flake8 over the auction package and fail on any violation."""

    def _run_flake8(self, *extra_args):
        result = subprocess.run(
            # Run from DJANGO_ROOT so .flake8 is found and excludes resolve correctly
            [sys.executable, "-m", "flake8", "auction/", *extra_args],
            capture_output=True,
            text=True,
            cwd=str(DJANGO_ROOT),
        )
        return result

    def test_no_flake8_violations(self):
        """The entire auction/ package must have zero flake8 violations."""
        result = self._run_flake8("--count", "--statistics")

        if result.returncode != 0:
            violations = result.stdout.strip()
            self.fail(
                f"flake8 found violations:\n\n{violations}\n\n"
                "Fix the issues above before committing."
            )

    def test_no_unused_imports(self):
        """No unused imports (F401) anywhere in the package."""
        result = self._run_flake8("--select=F401")

        if result.returncode != 0:
            self.fail(
                f"Unused imports found:\n\n{result.stdout.strip()}"
            )

    def test_no_undefined_names(self):
        """No undefined names (F821) — catches missing imports / typos."""
        result = self._run_flake8("--select=F821")

        if result.returncode != 0:
            self.fail(
                f"Undefined names found:\n\n{result.stdout.strip()}"
            )

    def test_no_bare_excepts(self):
        """No bare except: clauses (E722) — always catch a specific exception."""
        result = self._run_flake8("--select=E722")

        if result.returncode != 0:
            self.fail(
                f"Bare except clauses found:\n\n{result.stdout.strip()}"
            )
