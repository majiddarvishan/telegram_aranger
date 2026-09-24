import unittest

from config.branding import PRODUCT_NAME, PRODUCT_SLUG, PRODUCT_TAGLINE, PRODUCT_VERSION


class BrandingTests(unittest.TestCase):
    def test_product_identity(self):
        self.assertEqual(PRODUCT_NAME, "Telegram Harbor")
        self.assertEqual(PRODUCT_SLUG, "telegram-harbor")
        self.assertIn("Telegram", PRODUCT_TAGLINE)
        self.assertIn("media", PRODUCT_TAGLINE.lower())
        self.assertEqual(PRODUCT_VERSION, "1.0.0")


if __name__ == "__main__":
    unittest.main()
