import re
import shutil
import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest


class WorkerStartupTest(unittest.TestCase):
    def test_browser_manifest_can_start_engine_in_isolation(self):
        root = Path(__file__).resolve().parents[1]
        worker = (root / 'engine-worker.mjs').read_text()
        manifest = re.search(r'const files\s*=\s*\[([^\]]+)\]', worker)
        self.assertIsNotNone(manifest)
        modules = re.findall(r"'([a-z_0-9]+)'", manifest[1])
        with TemporaryDirectory() as directory:
            for name in modules:
                shutil.copyfile(root / 'engine' / f'{name}.py', Path(directory) / f'{name}.py')
            smoke = """
import json
import sys
sys.path.insert(0, sys.argv[1])
from pages_bridge import handle
assert json.loads(handle('state', '{}'))['phase'] == 'tutorial'
saved = json.loads(handle('export_save', '{}'))
assert json.loads(handle('import_save', json.dumps({'save': saved})))['phase'] == 'tutorial'
"""
            result = subprocess.run([sys.executable, '-I', '-c', smoke, directory],
                                    capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
