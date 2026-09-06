import pathlib
import subprocess
import tempfile
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
SOURCE = ROOT / "android/h700-android10/device/roc/rgsp/rgsp_kmsg_logger.c"


class LoggerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.build = tempfile.TemporaryDirectory()
        cls.binary = pathlib.Path(cls.build.name) / "logger"
        subprocess.run(
            ["cc", "-Wall", "-Wextra", "-Werror", str(SOURCE), "-o", str(cls.binary)],
            check=True,
        )

    @classmethod
    def tearDownClass(cls):
        cls.build.cleanup()

    def test_rotation_retains_latest_bytes_and_bounds_every_file(self):
        with tempfile.TemporaryDirectory() as folder:
            log = pathlib.Path(folder) / "kernel.log"
            data = bytes(range(200))
            subprocess.run([self.binary, log, "32", "--stdin"], input=data, check=True)
            chunks = [(pathlib.Path(str(log) + suffix)).read_bytes()
                      for suffix in (".3", ".2", ".1", "")]
            self.assertTrue(all(len(chunk) <= 32 for chunk in chunks))
            self.assertEqual(b"".join(chunks), data[-104:])
            self.assertFalse(pathlib.Path(str(log) + ".4").exists())

    def test_restart_appends_without_exceeding_limit(self):
        with tempfile.TemporaryDirectory() as folder:
            log = pathlib.Path(folder) / "kernel.log"
            for data in (b"a" * 24, b"b" * 24):
                subprocess.run([self.binary, log, "32", "--stdin"], input=data, check=True)
            self.assertEqual(pathlib.Path(str(log) + ".1").read_bytes(), b"a" * 24 + b"b" * 8)
            self.assertEqual(log.read_bytes(), b"b" * 16)

    def test_rejects_symlink_output(self):
        with tempfile.TemporaryDirectory() as folder:
            target = pathlib.Path(folder) / "untouched"
            target.write_bytes(b"original")
            log = pathlib.Path(folder) / "kernel.log"
            log.symlink_to(target)
            result = subprocess.run([self.binary, log, "32", "--stdin"], input=b"changed")
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(target.read_bytes(), b"original")


if __name__ == "__main__":
    unittest.main()
