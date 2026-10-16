"""Whole-equation accuracy benchmark.

Per-glyph validation accuracy (what train.py reports) says little about what
users see: an equation is only right if every glyph is segmented, classified
and placed correctly. This script builds equation images from real
handwritten glyphs, runs the full pipeline (segment -> classify -> spatial
parse -> solve) and reports:

  ExpRate   share of equations read exactly right (same syntax tree)
  Answer    share whose solution matches the true solution
  SegRate   share where segmentation found the right number of glyphs
  SER       symbol error rate (edit distance over symbols / true length)

Glyphs come from the dataset folders train.py uses. Where a folder had more
files than the training cap, only files the training run did NOT pick are
used, so most glyphs are unseen by the model. Folders smaller than the cap
(div, times, z) were used whole in training, so those glyphs are not held
out; the report says how many glyphs were drawn from them.

With --lines K, each test image is a page of K equations written one under
another (as in "check my work"), read with the line splitter, and it also
reports LineRate: the share of pages split into the right number of lines.
ExpRate is then per line.

Usage (from backend/):
    python training/eval_equations.py --n 400
    python training/eval_equations.py --n 400 --decoder greedy   # compare
    python training/eval_equations.py --n 150 --lines 3          # pages of working
"""
import argparse
import io
import os
import random
import sys
from collections import Counter

import cv2
import numpy as np
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from train import CLASS_MAP  # noqa: E402

DEFAULT_DATA = os.path.join(ROOT, 'training', 'data', 'extracted_images')
TRAIN_CAP = 6000  # --per-class-limit the shipped model was trained with
GLYPH_H = 72      # height of a full-size glyph in the rendered equation

# symbol as written in an equation -> dataset folder
SYMBOL_FOLDER = {v: k for k, v in CLASS_MAP.items()}
SMALL = set('+-=×÷')


def held_out_files(data_dir, cap=TRAIN_CAP):
    """Reproduce train.py's per-folder random pick and return, per symbol,
    the files it did not train on (or every file when none were held out)."""
    rng = np.random.RandomState(42)
    pools, leaked = {}, set()
    for folder in sorted(os.listdir(data_dir)):
        symbol = CLASS_MAP.get(folder)
        path = os.path.join(data_dir, folder)
        if symbol is None or not os.path.isdir(path):
            continue
        files = sorted(os.listdir(path))
        if len(files) > cap:
            picked = set(rng.permutation(len(files))[:cap])
            rest = [f for i, f in enumerate(files) if i not in picked]
        else:
            rest = files
            leaked.add(symbol)
        pools[symbol] = [os.path.join(path, f) for f in rest]
    return pools, leaked


def ink_crop(path):
    """Load a dataset glyph as an ink mask (ink=255) cropped to its ink."""
    gray = cv2.imread(path, cv2.IMREAD_GRAYSCALE)
    _, mask = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV | cv2.THRESH_OTSU)
    ys, xs = np.where(mask > 0)
    return mask[ys.min():ys.max() + 1, xs.min():xs.max() + 1]


def scaled(mask, height=None, width=None):
    """Resize an ink mask. With both sizes given it is stretched to exactly
    that box; with one, the other follows the aspect ratio."""
    h, w = mask.shape
    if height is None:
        height = h * width / w
    if width is None:
        width = w * height / h
    size = (max(1, int(round(width))), max(1, int(round(height))))
    out = cv2.resize(mask, size, interpolation=cv2.INTER_AREA)
    return (out > 64).astype(np.uint8) * 255


def fitted(mask, height, max_aspect=1.3):
    """Scale to the given height, but never wider than max_aspect times it
    (a few dataset glyphs have long stray tails)."""
    h, w = mask.shape
    if w / h > max_aspect:
        return scaled(mask, width=height * max_aspect)
    return scaled(mask, height=height)


# --- equation generation --------------------------------------------------
# An equation is a list of items:
#   ('g', symbol)            a glyph on the baseline
#   ('sup', [items])         a raised exponent attached to the previous item
#   ('frac', [num], [den])   a stacked fraction
#   ('sqrt', [items])        a radical over its radicand
# plus a ground-truth expression in safe_parse syntax and its true solution.

def _num(rng, lo=1, hi=99):
    return str(rng.randint(lo, hi))


def _glyphs(text):
    return [('g', c) for c in text]


def make_equation(rng):
    var = rng.choice('xyz')
    kind = rng.choice(['arith2', 'arith3', 'paren', 'linear', 'linear2',
                       'square', 'quadratic', 'fraction', 'sqrt'])
    if kind == 'arith2':
        a, b = _num(rng), _num(rng)
        op = rng.choice('+-×÷')
        return _glyphs(a + op + b), f'{a}{op}{b}'
    if kind == 'arith3':
        a, b, c = _num(rng, 1, 20), _num(rng, 1, 20), _num(rng, 1, 20)
        o1, o2 = rng.choice('+-×'), rng.choice('+-×')
        return _glyphs(a + o1 + b + o2 + c), f'{a}{o1}{b}{o2}{c}'
    if kind == 'paren':
        a, b, c = _num(rng, 1, 20), _num(rng, 1, 20), _num(rng, 2, 9)
        return _glyphs(f'({a}+{b})×{c}'), f'({a}+{b})×{c}'
    if kind == 'linear':
        a, b, c = _num(rng, 2, 9), _num(rng, 1, 30), _num(rng, 1, 60)
        op = rng.choice('+-')
        return _glyphs(f'{a}{var}{op}{b}={c}'), f'{a}{var}{op}{b}={c}'
    if kind == 'linear2':
        a, b, c = _num(rng, 2, 9), _num(rng, 1, 9), _num(rng, 1, 20)
        return _glyphs(f'{a}{var}={b}{var}+{c}'), f'{a}{var}={b}{var}+{c}'
    if kind == 'square':
        n = str(rng.choice([4, 9, 16, 25, 36, 49]))
        return [('g', var), ('sup', _glyphs('2'))] + _glyphs('=' + n), f'{var}^2={n}'
    if kind == 'quadratic':
        r1, r2 = rng.randint(1, 6), rng.randint(1, 6)
        b, c = r1 + r2, r1 * r2
        items = [('g', var), ('sup', _glyphs('2'))] + _glyphs(f'+{b}{var}+{c}=0')
        return items, f'{var}^2+{b}{var}+{c}=0'
    if kind == 'fraction':
        a, b, c = _num(rng, 1, 9), _num(rng, 2, 9), _num(rng, 1, 9)
        return [('frac', _glyphs(a), _glyphs(b))] + _glyphs('+' + c), f'({a})/({b})+{c}'
    n = str(rng.choice([4, 9, 16, 25, 36, 49, 64, 81, 100, 144]))
    return [('sqrt', _glyphs(n))], f'sqrt({n})'


# --- rendering ------------------------------------------------------------

class Renderer:
    def __init__(self, pools, rng):
        self.pools = pools
        self.rng = rng
        self.drawn = Counter()

    def glyph(self, symbol, height):
        self.drawn[symbol] += 1
        mask = ink_crop(self.rng.choice(self.pools[symbol]))
        if symbol == '-':
            # a minus is a thin bar; keep it about stroke-thin
            return scaled(mask, height=max(4, int(height * 0.08)), width=int(height * 0.55))
        if symbol == '=':
            return fitted(mask, int(height * 0.4), max_aspect=1.6)
        target = int(height * (0.6 if symbol in SMALL else 1.0))
        return fitted(mask, target)

    def gap(self):
        self.last_gap = self.rng.randint(8, 22)
        return self.last_gap

    def layout(self, items, height):
        """Return a list of (mask, x, centre_y) placed left to right with
        centre_y relative to the row's midline."""
        placed, x = [], 0
        for item in items:
            kind = item[0]
            if kind == 'g':
                m = self.glyph(item[1], height)
                placed.append((m, x, 0))
                x += m.shape[1] + self.gap()
            elif kind == 'sup':
                # an exponent sits close after its base, but not touching it
                x -= getattr(self, 'last_gap', 0) - self.rng.randint(4, 8)
                sub, w = self._row(item[1], int(height * 0.55))
                placed += [(m, x + px, py - int(height * 0.55)) for m, px, py in sub]
                x += w + self.gap()
            elif kind == 'frac':
                num, wn = self._row(item[1], int(height * 0.8))
                den, wd = self._row(item[2], int(height * 0.8))
                width = max(wn, wd) + 16
                bar = scaled(ink_crop(self.rng.choice(self.pools['-'])),
                             height=max(4, int(height * 0.07)), width=width)
                self.drawn['-'] += 1
                placed.append((bar, x, 0))
                off = int(height * 0.55)
                placed += [(m, x + (width - wn) // 2 + px, py - off) for m, px, py in num]
                placed += [(m, x + (width - wd) // 2 + px, py + off) for m, px, py in den]
                x += width + self.gap()
            elif kind == 'sqrt':
                inner, wi = self._row(item[1], height)
                rad = self.glyph('√', int(height * 1.3))
                placed.append((rad, x, -int(height * 0.1)))
                start = x + rad.shape[1] + 4
                placed += [(m, start + px, py) for m, px, py in inner]
                x = start + wi + self.gap()
        return placed, x

    def _row(self, items, height):
        placed, x = self.layout(items, height)
        return placed, max(0, x - self.gap())

    def render(self, items):
        placed, width = self.layout(items, GLYPH_H)
        pad = 40
        top = min(cy - m.shape[0] // 2 for m, _, cy in placed)
        bottom = max(cy + (m.shape[0] - m.shape[0] // 2) for m, _, cy in placed)
        canvas = np.zeros((bottom - top + 2 * pad, width + 2 * pad), np.uint8)
        for m, x, cy in placed:
            y0 = cy - m.shape[0] // 2 - top + pad
            region = canvas[y0:y0 + m.shape[0], x + pad:x + pad + m.shape[1]]
            np.maximum(region, m[:region.shape[0], :region.shape[1]], out=region)
        # slightly thicker strokes, like a pen on the canvas
        canvas = cv2.dilate(canvas, np.ones((2, 2), np.uint8))
        buf = io.BytesIO()
        Image.fromarray(255 - canvas).save(buf, 'PNG')
        return buf.getvalue()


def count_glyphs(items):
    n = 0
    for item in items:
        if item[0] == 'g':
            n += 1
        elif item[0] == 'sup':
            n += count_glyphs(item[1])
        elif item[0] == 'frac':
            n += 1 + count_glyphs(item[1]) + count_glyphs(item[2])
        elif item[0] == 'sqrt':
            n += 1 + count_glyphs(item[1])
    return n


def edit_distance(a, b):
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--data-dir', default=DEFAULT_DATA)
    parser.add_argument('--n', type=int, default=400)
    parser.add_argument('--seed', type=int, default=7)
    parser.add_argument('--decoder', choices=['greedy', 'context'], default=None,
                        help='override the decoder (default: the app default)')
    parser.add_argument('--no-merge', action='store_true',
                        help='disable stroke merging in the segmenter (old behaviour)')
    parser.add_argument('--show-errors', type=int, default=0)
    parser.add_argument('--save-dir', default=None, help='write the rendered images here')
    parser.add_argument('--lines', type=int, default=1,
                        help='equations per page, read with the line splitter')
    args = parser.parse_args()

    import main as pipeline
    from calculator import normalize, solve_job
    from safe_parse import ParseError, parse_tree
    from structure import build_expression

    if args.decoder:
        os.environ['EQSOLVER_DECODER'] = args.decoder
    if args.no_merge:
        import segmentor
        segmentor._merge_strokes = lambda rects: rects
        segmentor._merge_division_signs = lambda rects: rects

    pools, leaked = held_out_files(args.data_dir)
    rng = random.Random(args.seed)
    renderer = Renderer(pools, rng)

    if args.lines > 1:
        return eval_pages(args, renderer, rng)

    totals = Counter()
    errors = []
    sym_err = sym_len = 0
    for i in range(args.n):
        items, truth = make_equation(rng)
        png = renderer.render(items)
        if args.save_dir:
            os.makedirs(args.save_dir, exist_ok=True)
            with open(os.path.join(args.save_dir, f'{i:04d}.png'), 'wb') as f:
                f.write(png)
        truth_tree = parse_tree(normalize(truth))
        truth_answer = solve_job(truth)['solution']
        try:
            tokens = pipeline.recognize(io.BytesIO(png), decoder=args.decoder)
        except ValueError:
            tokens = []
        read = build_expression(tokens) if tokens else ''
        try:
            exact = parse_tree(normalize(read)) == truth_tree
        except ParseError:
            exact = False
        answer = solve_job(read)['solution'] if read else None

        truth_syms = [c for c in truth if c not in '()^']
        read_syms = [t['char'] for t in tokens]
        totals['n'] += 1
        totals['exact'] += exact
        totals['answer'] += answer is not None and answer == truth_answer
        totals['seg'] += len(tokens) == count_glyphs(items)
        sym_err += edit_distance(read_syms, [c for c in truth_syms])
        sym_len += len(truth_syms)
        if not exact:
            errors.append((truth, read))

    n = totals['n']
    print(f'equations: {n}   decoder: {args.decoder or os.environ.get("EQSOLVER_DECODER", "default")}')
    print(f'ExpRate  {totals["exact"] / n:6.1%}   exact expression')
    print(f'Answer   {totals["answer"] / n:6.1%}   correct solution')
    print(f'SegRate  {totals["seg"] / n:6.1%}   right glyph count')
    print(f'SER      {sym_err / max(1, sym_len):6.1%}   symbol error rate')
    seen = sum(renderer.drawn[s] for s in leaked)
    total = sum(renderer.drawn.values())
    print(f'glyphs drawn: {total}, of which {seen} ({seen / max(1, total):.0%}) from folders '
          f'not held out from training ({", ".join(sorted(leaked))})')
    for truth, read in errors[:args.show_errors]:
        print(f'  want {truth!r:22} read {read!r}')


def stack_lines(pngs, rng):
    """One page with each rendered equation on its own line, the ink of
    consecutive lines 0.4 to 1.2 glyph heights apart."""
    lines = []
    for png in pngs:
        ink = 255 - np.array(Image.open(io.BytesIO(png)).convert('L'))
        rows = np.where(ink.any(axis=1))[0]
        lines.append(ink[rows[0]:rows[-1] + 1])
    pad = 40
    gaps = [rng.randint(int(0.4 * GLYPH_H), int(1.2 * GLYPH_H)) for _ in lines[1:]]
    height = sum(line.shape[0] for line in lines) + sum(gaps) + 2 * pad
    page = np.zeros((height, max(line.shape[1] for line in lines)), np.uint8)
    y = pad
    for line, gap in zip(lines, gaps + [0], strict=True):
        page[y:y + line.shape[0], :line.shape[1]] = line
        y += line.shape[0] + gap
    buf = io.BytesIO()
    Image.fromarray(255 - page).save(buf, 'PNG')
    return buf.getvalue()


def eval_pages(args, renderer, rng):
    import main as pipeline
    from calculator import normalize
    from safe_parse import ParseError, parse_tree
    from structure import build_expression

    totals = Counter()
    errors = []
    for i in range(args.n):
        equations = [make_equation(rng) for _ in range(args.lines)]
        png = stack_lines([renderer.render(items) for items, _ in equations], rng)
        if args.save_dir:
            os.makedirs(args.save_dir, exist_ok=True)
            with open(os.path.join(args.save_dir, f'page{i:04d}.png'), 'wb') as f:
                f.write(png)
        try:
            token_lines = pipeline.recognize_lines(io.BytesIO(png), decoder=args.decoder)
        except ValueError:
            token_lines = []
        totals['pages'] += 1
        totals['split'] += len(token_lines) == len(equations)
        reads = [build_expression(t) for t in token_lines]
        for k, (_, truth) in enumerate(equations):
            read = reads[k] if k < len(reads) and len(reads) == len(equations) else ''
            try:
                exact = parse_tree(normalize(read)) == parse_tree(normalize(truth))
            except ParseError:
                exact = False
            totals['lines'] += 1
            totals['exact'] += exact
            if not exact:
                errors.append((truth, read))

    print(f'pages: {totals["pages"]} of {args.lines} lines   '
          f'decoder: {args.decoder or os.environ.get("EQSOLVER_DECODER", "default")}')
    print(f'LineRate {totals["split"] / totals["pages"]:6.1%}   right number of lines')
    print(f'ExpRate  {totals["exact"] / totals["lines"]:6.1%}   exact expression, per line')
    for truth, read in errors[:args.show_errors]:
        print(f'  want {truth!r:22} read {read!r}')


if __name__ == '__main__':
    main()
