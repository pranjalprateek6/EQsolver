"""Run the equation benchmark for each pipeline variant on identical images,
so improvements are measured against the same baseline.

Usage (from backend/):
    python training/compare_pipelines.py --n 600
"""
import argparse
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))

VARIANTS = [
    ('baseline: greedy, no stroke merging', ['--decoder', 'greedy', '--no-merge']),
    ('+ stroke merging', ['--decoder', 'greedy']),
    ('+ context decoder (shipped)', ['--decoder', 'context']),
]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--n', type=int, default=600)
    parser.add_argument('--seed', type=int, default=7)
    args = parser.parse_args()

    env = {**os.environ, 'PYTHONIOENCODING': 'utf-8'}
    print(f'| variant ({args.n} equations, seed {args.seed}) | ExpRate | Answer | SegRate | SER |')
    print('|---|---|---|---|---|')
    for name, flags in VARIANTS:
        out = subprocess.run(
            [sys.executable, os.path.join(HERE, 'eval_equations.py'),
             '--n', str(args.n), '--seed', str(args.seed), *flags],
            capture_output=True, text=True, env=env, check=True).stdout
        metrics = {line.split()[0]: line.split()[1] for line in out.splitlines()
                   if line.split() and line.split()[0] in ('ExpRate', 'Answer', 'SegRate', 'SER')}
        print(f"| {name} | {metrics['ExpRate']} | {metrics['Answer']} | "
              f"{metrics['SegRate']} | {metrics['SER']} |")


if __name__ == '__main__':
    main()
