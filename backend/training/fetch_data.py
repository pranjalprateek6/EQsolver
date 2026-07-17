"""Download the handwritten math-symbol dataset from Kaggle.

Prerequisite: a Kaggle API token. Create one at
https://www.kaggle.com/settings (Account -> Create New API Token), then place
the downloaded kaggle.json at:
    Windows: C:\\Users\\<you>\\.kaggle\\kaggle.json
    Linux/macOS: ~/.kaggle/kaggle.json

Then run:  python training/fetch_data.py
It extracts to backend/training/data/, ready for train.py.
"""
import os
import subprocess
import sys

DATASET = 'xainano/handwrittenmathsymbols'
DEST = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data')


def main():
    os.makedirs(DEST, exist_ok=True)
    try:
        subprocess.run(
            ['kaggle', 'datasets', 'download', '-d', DATASET, '-p', DEST, '--unzip'],
            check=True,
        )
    except FileNotFoundError:
        sys.exit("the 'kaggle' CLI is not installed. Run: pip install kaggle")
    except subprocess.CalledProcessError:
        sys.exit(
            "kaggle download failed. Make sure kaggle.json is in place "
            "(see the instructions at the top of this file)."
        )
    print(f'dataset extracted to {DEST}')


if __name__ == '__main__':
    main()
