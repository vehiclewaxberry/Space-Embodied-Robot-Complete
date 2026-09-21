import hashlib
import tempfile
import unittest
from pathlib import Path

from f3r2_path_resolver import ResolutionError, resolve_asset


class ResolverTests(unittest.TestCase):
    def test_hash_verified_reanchor(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            target = root / "03_native_cad" / "mesh" / "finger.stl"
            target.parent.mkdir(parents=True)
            target.write_bytes(b"solid-test")
            digest = hashlib.sha256(b"solid-test").hexdigest()
            result = resolve_asset(
                "Z:/old/F3R2_MECHANICAL_TERMINAL_CLOSURE_20260807/"
                "03_native_cad/mesh/finger.stl",
                digest,
                [root],
            )
            self.assertEqual(Path(result.resolved_path), target.resolve())
            self.assertEqual(result.resolution_method, "SHA256_VERIFIED_REANCHOR")

    def test_hash_mismatch_fails_closed(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            target = root / "20_engineering" / "part.step"
            target.parent.mkdir(parents=True)
            target.write_bytes(b"wrong")
            with self.assertRaises(ResolutionError):
                resolve_asset(
                    "Z:/old/20_engineering/part.step", "0" * 64, [root]
                )

    def test_same_name_without_suffix_or_hash_is_forbidden(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "part.step").write_bytes(b"x")
            with self.assertRaises(ResolutionError):
                resolve_asset("Z:/old/part.step", roots=[root])

    def test_ambiguous_suffix_without_hash_fails(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            roots = [base / "a", base / "b"]
            for root in roots:
                target = root / "20_engineering" / "cad" / "part.step"
                target.parent.mkdir(parents=True)
                target.write_bytes(root.name.encode())
            with self.assertRaises(ResolutionError):
                resolve_asset("Z:/old/20_engineering/cad/part.step", roots=roots)


if __name__ == "__main__":
    unittest.main()
