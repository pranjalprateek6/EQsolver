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

## Measuring accuracy on whole equations

Per-glyph validation accuracy (about 98%) overstates what users see: an
equation is only right if every glyph is segmented, classified and placed
correctly. `eval_equations.py` builds equation images from real handwritten
glyphs (linear and quadratic equations, arithmetic, parentheses, powers,
fractions and roots), runs the full pipeline and reports:

- **ExpRate**: share of equations read exactly right (same syntax tree)
- **Answer**: share whose solution matches the true solution
- **SegRate**: share where segmentation found the right number of glyphs
- **SER**: symbol error rate

Glyphs are drawn only from files the training run did not pick, except for
the folders smaller than the training cap (`div`, `times`, `z`, and some
digits), which were used whole; the report says how many glyphs came from
those.

```
.venv\Scripts\python training/eval_equations.py --n 600
.venv\Scripts\python training/compare_pipelines.py --n 600   # each change on the same images
```

Results on 600 equations. The tuning was done on seed 7 and checked on
seed 11, which it never saw:

| pipeline | ExpRate (seed 7) | ExpRate (seed 11) |
|---|---|---|
| original (greedy, no stroke merging, fraction bars ≥1.6× glyph height) | 57.7% | n/a |
| + fraction bars detected by layout, not width | 66.2% | 66.5% |
| + stroke merging in the segmenter | 71.3% | 70.0% |
| + context decoder (shipped) | 74.3% | 76.5% |

What each change does:

- **Fraction bars by layout**: a bar with symbols directly above and below
  it is a fraction however narrow it is; single-digit fractions were missed.
- **Stroke merging** (`segmentor.py`): pieces that share a column with no bar
  between them are one glyph written in several strokes (`y`, `x`, `4`); a
  bar inside a glyph's box is its crossbar (`z`, `7`); stacked bars are an
  `=`; dot-bar-dot is a `÷`.
- **Context decoder** (`decode.py`): scores whole readings built from each
  glyph's top 3 guesses, penalizing readings that do not parse, have
  variables but nothing to solve, put a letter in an exponent, or write a
  variable directly before a digit. Stroke geometry is trusted over the
  classifier: a single bar is always a minus, two merged bars always `=`.

Limits of this benchmark: glyphs come from one dataset (the one the model
trained on), are pasted on a clean baseline, and do not include photos of
paper. It is a regression gate and a way to compare changes, not a promise
of accuracy on every user's handwriting.

### Several lines (check my work)

`--lines K` builds pages of K equations written one under another, the ink
of consecutive lines 0.4 to 1.2 glyph heights apart, reads them with the line
splitter (`segmentor.split_lines`) and adds **LineRate**, the share of pages
split into the right number of lines. ExpRate is then per line.

```
.venv\Scripts\python training/eval_equations.py --n 150 --lines 3
```

| pages | LineRate | ExpRate per line |
|---|---|---|
| 150 × 3 lines (seed 7) | 97.3% | 72.9% |
| 100 × 5 lines (seed 11) | 97.0% | 71.4% |

The splitter cuts on vertical gaps of at least 0.35 median glyph heights,
and never between a thin fraction bar and the numerator or denominator
centred on it, so loosely written fractions stay in one line. Per-line
ExpRate stays close to the single-line figure (74.5% on seed 7).

### Accuracy gate in CI

The dataset is too large to commit, so CI checks a fixed sample instead:
`backend/tests/fixtures/equations/` holds the first 60 images of the seed-7
benchmark and `truths.json` with what each says, saved with

```
.venv\Scripts\python training/eval_equations.py --n 60 --save-dir tests/fixtures/equations
```

`tests/test_accuracy.py` runs the full pipeline on them and fails if ExpRate
drops below 73% (today: 78.3%, 47 of 60), so a change to segmentation, the
model, the decoder or the parser that costs four or more equations fails the
build. Switching to the greedy decoder, for example, scores 71.7% and fails.
When a change genuinely improves accuracy, raise `BASELINE` and `THRESHOLD`
in the test so the gain is kept.
