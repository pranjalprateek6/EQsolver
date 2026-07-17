# Training the Level 2 symbol model

A small CNN that recognizes handwritten math symbols (digits, `+ - × ÷ / = ( )`,
variables `x y z`, `√`, decimal point). It replaces the old EMNIST-letters model
and the `t → +` / `S → =` substitution hacks.

Training and inference share the same aspect-preserving preprocessing in
`backend/preprocess.py`, so what the model learns matches what it sees at runtime.

## Steps

Everything runs in the backend venv.

```
cd backend
.venv\Scripts\pip install -r training/requirements.txt

# 1. get the dataset (needs a Kaggle API token, see fetch_data.py header)
.venv\Scripts\python training/fetch_data.py

# 2. train (CPU is fine, the model is small)
.venv\Scripts\python training/train.py --data-dir training/data/extracted_images --epochs 15

# 3. drop the result into the app
move /Y model_v2.h5 model.h5
move /Y mapper_v2.csv mapper.csv
```

Use `--smoke` for a tiny synthetic run that just proves the pipeline works.

## Which symbols

`train.py`'s `CLASS_MAP` picks only the math-relevant folders from the dataset
and maps each to the symbol the app uses. Edit it to add or drop symbols; the
exported `mapper.csv` follows automatically.
