"""
Make the repo's screenshots: full screens trimmed below the content, and
zooms of the single-line samples with their labels.

usage: crops.py <out-dir> <work-dir>

<work-dir> holds the captures: capture-ios.sh output with the prefixes
ios088-default, ios088-axm (0.88.0, stock and patched), ios081-default and
ios081-axm (0.81.6), and `adb exec-out screencap -p` screenshots named
android-default.png and android-scale2.png.
"""

import sys

import numpy as np
from PIL import Image

sys.path.insert(0, __file__.rsplit('/', 1)[0])
from measure import measure  # noqa: E402

out, work = sys.argv[1:]


def trim(src, dst):
    """Drop the empty white space below the content, keeping a margin."""
    img = Image.open(f'{work}/{src}').convert('RGB')
    a = np.asarray(img).astype(int)
    nonwhite = np.flatnonzero((np.abs(a - 255).sum(2) > 30).sum(1) > 0)
    # Ignore the home indicator at the very bottom.
    nonwhite = nonwhite[nonwhite < a.shape[0] - 120]
    bottom = min(a.shape[0], nonwhite[-1] + 60)
    img.crop((0, 0, a.shape[1], bottom)).save(f'{out}/{dst}', optimize=True)


def zoom(src, dst, rows=9):
    """The single-line samples (not the wrapped paragraph), with their labels."""
    img = Image.open(f'{work}/{src}').convert('RGB')
    m = measure(f'{work}/{src}', 3)[:rows]
    top = m[0]['top'] - 32
    bottom = m[-1]['hairline'] + 50
    right = max(r['hairline_right'] for r in m) + 20
    img.crop((30, top, right, bottom)).save(f'{out}/{dst}', optimize=True)


for src, dst in [
    ('ios088-default-stock.png', 'ios-0.88-stock.png'),
    ('ios088-default-patched.png', 'ios-0.88-patched.png'),
    ('ios088-axm-stock.png', 'ios-0.88-stock-ax.png'),
    ('ios088-axm-stock-bottom.png', 'ios-0.88-stock-ax-end.png'),
    ('ios088-axm-patched.png', 'ios-0.88-patched-ax.png'),
    ('ios088-axm-patched-bottom.png', 'ios-0.88-patched-ax-end.png'),
    ('ios081-default-stock.png', 'ios-0.81.6.png'),
    ('ios081-axm-stock.png', 'ios-0.81.6-ax.png'),
    ('ios081-axm-stock-bottom.png', 'ios-0.81.6-ax-end.png'),
    ('android-default.png', 'android-0.88.png'),
    ('android-scale2.png', 'android-0.88-scale-2.png'),
]:
    trim(src, dst)

for src, dst in [
    ('ios088-default-stock.png', 'zoom-ios-0.88-stock.png'),
    ('ios088-default-patched.png', 'zoom-ios-0.88-patched.png'),
    ('ios081-default-stock.png', 'zoom-ios-0.81.6.png'),
    ('android-default.png', 'zoom-android-0.88.png'),
]:
    zoom(src, dst)
