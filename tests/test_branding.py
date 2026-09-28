import unittest

from config.branding import PRODUCT_NAME, PRODUCT_SLUG, PRODUCT_TAGLINE, PRODUCT_VERSION


class BrandingTests(unittest.TestCase):
    def test_product_identity(self):
        self.assertEqual(PRODUCT_NAME, "YARA")
        self.assertEqual(PRODUCT_SLUG, "yara")
        self.assertEqual(PRODUCT_TAGLINE, "Your Archive & Retrieval Assistant")
        self.assertIn("archive", PRODUCT_TAGLINE.lower())
        self.assertEqual(PRODUCT_VERSION, "1.1.0")


if __name__ == "__main__":
    unittest.main()
