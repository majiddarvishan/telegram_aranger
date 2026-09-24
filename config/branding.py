from pathlib import Path


PRODUCT_NAME = "Telegram Harbor"
PRODUCT_TAGLINE = "Multi-account Telegram message and media manager"
PRODUCT_SLUG = "telegram-harbor"
PRODUCT_VERSION = (
    Path(__file__).resolve().parents[1] / "VERSION"
).read_text(encoding="utf-8").strip()
