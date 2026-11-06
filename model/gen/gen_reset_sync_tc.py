#!/usr/bin/env python3
"""Generate reset timings. Expected behavior is checked from RST-01 in the TB."""
import argparse
import json
from pathlib import Path
import random

ROOT = Path(__file__).resolve().parents[2]


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--seed', type=int, required=True, help='first data seed')
    ap.add_argument('--count', type=int, default=1, help='consecutive data seeds')
    ap.add_argument('--vectors', type=int, default=4, help='reset pulses per TC')
    ap.add_argument('--out', type=Path, default=ROOT / 'src/tc/unit/reset_sync')
    args = ap.parse_args()
    if args.seed < 1 or args.count < 1 or not 1 <= args.vectors <= 100:
        ap.error('seed/count >= 1; vectors in 1..100')
    for seed in range(args.seed, args.seed + args.count):
        rng = random.Random(seed)
        out = args.out / f'random_s{seed}'
        out.mkdir(parents=True, exist_ok=False)
        rows = [(rng.randint(1, 10), rng.randint(1, 3)) for _ in range(args.vectors)]
        (out / 'stim.txt').write_text(''.join(f'{h} {d}\n' for h, d in rows))
        (out / 'meta.json').write_text(json.dumps(dict(data_seed=seed, vectors=args.vectors,
            format_version=1, requirement='RST-01', generator='model/gen/gen_reset_sync_tc.py'), indent=2) + '\n')
        print(out)


if __name__ == '__main__':
    main()
