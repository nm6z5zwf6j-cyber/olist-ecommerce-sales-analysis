"""Download and extract the public Olist dataset from Kaggle."""

from __future__ import annotations

import argparse
import shutil
import tempfile
import urllib.request
import zipfile
from pathlib import Path


DATASET_URL = "https://www.kaggle.com/api/v1/datasets/download/olistbr/brazilian-ecommerce"
EXPECTED_FILES = {
    "olist_customers_dataset.csv",
    "olist_order_items_dataset.csv",
    "olist_order_payments_dataset.csv",
    "olist_orders_dataset.csv",
    "olist_products_dataset.csv",
    "product_category_name_translation.csv",
}


def download(raw_dir: Path, force: bool = False) -> None:
    raw_dir.mkdir(parents=True, exist_ok=True)
    existing = {path.name for path in raw_dir.glob("*.csv")}
    if EXPECTED_FILES.issubset(existing) and not force:
        print("All required source files already exist; download skipped.")
        return

    with tempfile.TemporaryDirectory(prefix="olist_download_") as temp_dir:
        archive = Path(temp_dir) / "olist.zip"
        print("Downloading the Olist dataset...")
        with urllib.request.urlopen(DATASET_URL) as response, archive.open("wb") as output:
            shutil.copyfileobj(response, output)
        with zipfile.ZipFile(archive) as zipped:
            zipped.extractall(raw_dir)

    missing = EXPECTED_FILES - {path.name for path in raw_dir.glob("*.csv")}
    if missing:
        raise RuntimeError(f"Download finished, but required files are missing: {sorted(missing)}")
    print(f"Dataset extracted to {raw_dir}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true", help="Download again and replace files")
    args = parser.parse_args()
    project_root = Path(__file__).resolve().parents[1]
    download(project_root / "data" / "raw", force=args.force)

