"""Tests for config_loader — YAML profile loading and validation."""

import os
import sys
import tempfile

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.config_loader import load_and_validate_profile
from core.models import ProfileConfig

# ─── Load real profile ────────────────────────────────────

class TestLoadProfile:
    """Loading and validating YAML profiles."""

    def test_load_real_profile_succeeds(self):
        """Loading the real ravi_raj.yaml should return a valid ProfileConfig."""
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        yaml_path = os.path.join(project_root, "config", "profiles", "ravi_raj.yaml")
        profile = load_and_validate_profile(yaml_path)
        assert isinstance(profile, ProfileConfig)
        assert profile.candidate.name  # name should be non-empty

    def test_missing_file_exits(self):
        """A missing file should cause sys.exit(1)."""
        with pytest.raises(SystemExit) as exc_info:
            load_and_validate_profile("/tmp/nonexistent_profile_xyz.yaml")
        assert exc_info.value.code == 1

    def test_invalid_yaml_exits(self):
        """Malformed YAML should cause sys.exit(1)."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".yaml", delete=False
        ) as f:
            f.write(":\n  bad:\n    - [unclosed\n")
            f.flush()
            path = f.name

        try:
            with pytest.raises(SystemExit) as exc_info:
                load_and_validate_profile(path)
            assert exc_info.value.code == 1
        finally:
            os.unlink(path)

    def test_empty_file_exits(self):
        """An empty YAML file should cause sys.exit(1)."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".yaml", delete=False
        ) as f:
            f.write("")
            f.flush()
            path = f.name

        try:
            with pytest.raises(SystemExit) as exc_info:
                load_and_validate_profile(path)
            assert exc_info.value.code == 1
        finally:
            os.unlink(path)

    def test_invalid_config_missing_required_field_exits(self):
        """YAML that parses but fails Pydantic validation should exit."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".yaml", delete=False
        ) as f:
            # Valid YAML but missing required fields (e.g. candidate, filters)
            f.write("search_preferences:\n  locations:\n    - Bengaluru\n")
            f.flush()
            path = f.name

        try:
            with pytest.raises(SystemExit) as exc_info:
                load_and_validate_profile(path)
            assert exc_info.value.code == 1
        finally:
            os.unlink(path)
