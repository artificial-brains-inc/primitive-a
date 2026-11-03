import subprocess
import tempfile
import unittest
import venv
from pathlib import Path

from setup_project import ensure_environment


class InstallationTests(unittest.TestCase):
    def test_existing_environment_without_pip_is_repaired_in_place(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            environment = root / ".venv"
            venv.EnvBuilder(with_pip=False).create(environment)
            marker = environment / "keep.txt"
            marker.write_text("existing environment")
            before = subprocess.run([str(environment / "bin/python"), "-m", "pip", "--version"], capture_output=True)
            self.assertNotEqual(before.returncode, 0)
            python = ensure_environment(root)
            after = subprocess.run([str(python), "-m", "pip", "--version"], capture_output=True)
            self.assertEqual(after.returncode, 0, after.stderr)
            self.assertEqual(marker.read_text(), "existing environment")
            self.assertEqual(list(root.glob(".venv.backup-*")), [])

    def test_incomplete_environment_is_preserved_before_replacement(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / ".venv").mkdir()
            (root / ".venv/keep.txt").write_text("saved")
            python = ensure_environment(root)
            backups = list(root.glob(".venv.backup-*"))
            self.assertEqual(len(backups), 1)
            self.assertEqual((backups[0] / "keep.txt").read_text(), "saved")
            self.assertEqual(subprocess.run([str(python), "-m", "pip", "--version"], capture_output=True).returncode, 0)


if __name__ == "__main__":
    unittest.main()
