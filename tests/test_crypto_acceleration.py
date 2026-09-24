import unittest
from importlib import metadata

import tgcrypto


class CryptoAccelerationTests(unittest.TestCase):
    def test_tgcrypto2_package_is_installed(self):
        version = metadata.version("tgcrypto2")
        self.assertTrue(version)

    def test_drop_in_tgcrypto_module_is_available(self):
        self.assertTrue(callable(tgcrypto.ige256_encrypt))
        self.assertTrue(callable(tgcrypto.ige256_decrypt))
        self.assertTrue(callable(tgcrypto.ctr256_encrypt))
        self.assertTrue(callable(tgcrypto.ctr256_decrypt))


if __name__ == "__main__":
    unittest.main()
