from pathlib import Path


PRODUCT_NAME = "YARA"
PRODUCT_TAGLINE = "Your Archive & Retrieval Assistant"
PRODUCT_SLUG = "yara"
PRODUCT_VERSION = (
    Path(__file__).resolve().parents[1] / "VERSION"
).read_text(encoding="utf-8").strip()
