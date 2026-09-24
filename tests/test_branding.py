import unittest

from config.branding import PRODUCT_NAME, PRODUCT_SLUG, PRODUCT_TAGLINE


class BrandingTests(unittest.TestCase):
    def test_product_identity(self):
        self.assertEqual(PRODUCT_NAME, "Telegram Harbor")
        self.assertEqual(PRODUCT_SLUG, "telegram-harbor")
        self.assertIn("Telegram", PRODUCT_TAGLINE)
        self.assertIn("media", PRODUCT_TAGLINE.lower())


if __name__ == "__main__":
    unittest.main()
