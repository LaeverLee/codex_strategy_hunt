import hashlib
from pathlib import Path
import unittest

class EngineManifestTests(unittest.TestCase):
    def test_all_seven_engine_files_match_manifest(self):
        root=Path(__file__).resolve().parents[1]
        entries=[line.split() for line in (root/'config/common-engine.sha256').read_text().splitlines()]
        self.assertEqual(len(entries),7)
        self.assertEqual({name for _,name in entries},{str(p.relative_to(root)) for p in (root/'engine').glob('*.py')})
        for digest,name in entries:
            with self.subTest(name=name): self.assertEqual(digest,hashlib.sha256((root/name).read_bytes()).hexdigest())
