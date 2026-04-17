import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core.scrcpy_metadata import parse_device_name, parse_codec_meta


class TestScrcpyMetadataParsing(unittest.TestCase):
    def test_parse_without_dummy(self):
        name64 = b"Android Phone\x00" + b"\x00" * (64 - len("Android Phone") - 1)
        meta12 = (1).to_bytes(4, "big") + (1920).to_bytes(4, "big") + (840).to_bytes(4, "big")
        self.assertEqual(parse_device_name(name64), "Android Phone")
        self.assertEqual(parse_codec_meta(meta12), (1, 1920, 840))

    def test_parse_with_dummy_shifted(self):
        raw = b"\x00" + (b"Android\x00" + b"\x00" * (63 - len("Android") - 1))
        name64 = raw[1:] + b"\x00"
        meta12 = (1).to_bytes(4, "big") + (1080).to_bytes(4, "big") + (472).to_bytes(4, "big")
        self.assertEqual(parse_device_name(name64), "Android")
        self.assertEqual(parse_codec_meta(meta12), (1, 1080, 472))


if __name__ == "__main__":
    unittest.main()

