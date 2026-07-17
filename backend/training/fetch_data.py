"""Download the handwritten math-symbol dataset from Kaggle.

Prerequisite: a Kaggle API token. Either
  - an access token (KGAT_...) at ~/.kaggle/access_token, or
  - a classic kaggle.json ({"username":"...","key":"..."}) at ~/.kaggle/kaggle.json

On Windows ~ is C:\\Users\\<you>. Then run:  python training/fetch_data.py
It extracts to backend/training/data/, ready for train.py.
"""
import os
import sys

DATASET = 'xainano/handwrittenmathsymbols'
DEST = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data')


def main():
    os.makedirs(DEST, exist_ok=True)
    try:
        import kaggle
    except ImportError:
        sys.exit("the 'kaggle' package is not installed. Run: pip install kaggle")

    try:
        kaggle.api.authenticate()
        print(f'downloading {DATASET} to {DEST} (this is ~430MB, be patient)...')
        kaggle.api.dataset_download_files(DATASET, path=DEST, unzip=True, quiet=False)
    except Exception as exc:  # noqa: BLE001
        sys.exit(
            f"kaggle download failed: {exc}\n"
            "Check that your token is in place (see the instructions at the top of this file)."
        )
    print(f'dataset extracted to {DEST}')


if __name__ == '__main__':
    main()
