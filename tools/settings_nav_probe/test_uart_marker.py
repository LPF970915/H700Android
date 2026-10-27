"""UART result framing regression using the observed interleaved kernel output."""
import unittest
from audit import completion_pattern


class MarkerTest(unittest.TestCase):
    def test_numeric_result_with_console_interleaving(self):
        for data in (b'\r\nNV12345678:0\r\r\nrgsp:/ # ',
                     b'NV12345678:0',
                     b'\nNV12345678:0[ 3716.279373] init: missing power HAL\r\n',
                     b'[ 1.234] kernel lineNV12345678:0\r\n'):
            with self.subTest(data=data):
                self.assertEqual(b'0',completion_pattern('NV12345678').search(data)[1])

    def test_echo_is_not_a_result(self):
        self.assertIsNone(completion_pattern('NV12345678').search(
            b'n a; navrc=$?; echo NV12345678:$navrc\r\n'))

    def test_nonzero_and_other_transaction(self):
        self.assertEqual(b'127',completion_pattern('NV12345678').search(b'NV12345678:127\r\n')[1])
        self.assertIsNone(completion_pattern('NV12345678').search(b'NV87654321:0\r\n'))


if __name__=='__main__':unittest.main()
