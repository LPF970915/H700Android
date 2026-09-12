import struct
import unittest
import zlib

from audit_rgsp_single_card_boot import STAMP, gpt, package


class BootAuditTests(unittest.TestCase):
    def candidate(self):
        data = bytearray(2048)
        data[:8] = b"TOC1.GLH"
        struct.pack_into("<II", data, 16, 0x89119800, STAMP)
        struct.pack_into("<II", data, 32, 3, len(data))
        for i, name in enumerate((b"u-boot", b"monitor", b"dtb")):
            start = 64 + i * 368
            data[start:start + len(name)] = name
            struct.pack_into("<II", data, start + 64, 1536 + i * 64, 64)
        self.checksum(data)
        return data

    def checksum(self, data):
        struct.pack_into("<I", data, 20, STAMP)
        struct.pack_into("<I", data, 20,
                         sum(struct.unpack(f"<{len(data) // 4}I", data)) & 0xFFFFFFFF)

    def test_valid_package(self):
        self.assertEqual(package(self.candidate())["bytes"], 2048)

    def test_absent_package(self):
        with self.assertRaisesRegex(ValueError, "magic"):
            package(bytes(2048))

    def test_truncated_package(self):
        with self.assertRaisesRegex(ValueError, "Truncated"):
            package(self.candidate()[:1500])

    def test_checksum(self):
        data = self.candidate()
        data[1700] ^= 1
        with self.assertRaisesRegex(ValueError, "checksum"):
            package(data)

    def test_out_of_range_item(self):
        data = self.candidate()
        struct.pack_into("<I", data, 64 + 64, 3000)
        self.checksum(data)
        with self.assertRaisesRegex(ValueError, "outside"):
            package(data)

    def test_missing_uboot(self):
        data = self.candidate()
        data[64:70] = b"unused"
        self.checksum(data)
        with self.assertRaisesRegex(ValueError, "components"):
            package(data)

    def test_gpt_crc(self):
        data = bytearray(2048)
        data[512:520] = b"EFI PART"
        struct.pack_into("<I", data, 524, 92)
        struct.pack_into("<QIII", data, 584, 2, 8, 128, zlib.crc32(data[1024:]))
        struct.pack_into("<I", data, 528, zlib.crc32(data[512:604]))
        self.assertEqual(gpt(data), [])
        data[530] ^= 1
        with self.assertRaisesRegex(ValueError, "CRC"):
            gpt(data)


if __name__ == "__main__":
    unittest.main()
