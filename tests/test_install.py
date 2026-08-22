from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class InstallTests(unittest.TestCase):
    def test_installer_exposes_skills_and_cli_without_python_package_install(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory)
            skills = target / "skills"
            binary = target / "bin"
            subprocess.run(
                [str(ROOT / "scripts" / "install"), str(skills), str(binary)],
                cwd=ROOT,
                capture_output=True,
                text=True,
                check=True,
            )
            self.assertTrue((skills / "design-language" / "SKILL.md").is_file())
            self.assertTrue((skills / "reference-intelligence" / "SKILL.md").is_file())
            self.assertTrue((binary / "design-intelligence").is_symlink())
            result = subprocess.run(
                [str(binary / "design-intelligence"), "--help"],
                cwd=target,
                capture_output=True,
                text=True,
                check=True,
            )
            self.assertIn("design-intelligence", result.stdout)


if __name__ == "__main__":
    unittest.main()
