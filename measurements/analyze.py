"""
Compare the predicted stock error (from font metrics alone) with what the
patch logged and what the screenshots show.

usage: analyze.py <log> <scale> <stock-top.png> <stock-bottom.png> <patched-top.png> <patched-bottom.png> [labels...]

The top and bottom screenshots are merged: rows come from the bottom (scrolled
to the end) screenshot where they are fully on screen, and from the top one
otherwise. Rows seen in both must agree.
"""

import re
import sys

sys.path.insert(0, __file__.rsplit('/', 1)[0])
from measure import measure  # noqa: E402

LINE = re.compile(
    r'\[inline-baseline\] (?P<mode>stock|patched): view (?P<w>[\d.]+)x(?P<h>[\d.]+) \| '
    r'text font (?P<font>\S+) (?P<size>[\d.]+) \(ascender (?P<asc>[-\d.]+), descender (?P<desc>[-\d.]+), '
    r'lineHeight (?P<flh>[\d.]+), leading (?P<leading>[-\d.]+)\), paragraph lineHeight (?P<plh>[\d.]+), '
    r'baseline offset (?P<boff>[-\d.]+) \| line (?P<l0>[-\d.]+)\.\.(?P<l1>[-\d.]+), glyph rect (?P<g0>[-\d.]+)\.\.(?P<g1>[-\d.]+), '
    r'glyph location y (?P<gly>[-\d.]+), baseline (?P<baseline>[-\d.]+) \| attachment font (?P<afont>\S+) (?P<asize>[\d.]+) '
    r'\(descender (?P<adesc>[-\d.]+)\) \| stock bottom (?P<sbottom>[-\d.]+) \((?P<serr>[-+\d.]+) from baseline\), '
    r'fixed bottom (?P<fbottom>[-\d.]+)'
)


def parse(path):
    rows = {}
    for line in open(path):
        m = LINE.search(line)
        if not m or m['mode'] != 'stock':
            continue
        d = {k: (v if k in ('mode', 'font', 'afont') else float(v)) for k, v in m.groupdict().items()}
        d['mixed'] = not d['plh'] and abs((d['l1'] - d['l0']) - d['flh']) > 0.01
        key = (d['w'], d['size'], d['plh'], d['l0'], d['l1'])
        rows[key] = d  # the last layout of each sample wins
    def order(d):
        return (d['l0'] > 0, d['mixed'], d['w'] > 50, d['size'], d['plh'])
    return sorted(rows.values(), key=order)


def predicted_error(d, line_descender):
    """
    Stock error from font metrics alone: the line's descent (the largest
    descender of the fonts on the line) + RCTApplyBaselineOffset's offset + the
    12pt Helvetica descender (-2.76).
    """
    L, flh = d['plh'], d['flh']
    offset = (L - flh) / 2 if L and L >= flh else 0.0
    return -line_descender + offset + -2.76, offset


def merge(top, bottom, n):
    """Rows 0..n-1 from a top and a scrolled-to-the-end screenshot."""
    # The first row of the scrolled screenshot may be cut off at the top edge.
    tail = bottom[1:] if len(bottom) > 1 else bottom
    tail = tail[-n:]
    head = top[: n - len(tail)]
    rows = head + tail
    overlap = top[n - len(tail) : n - len(tail) + len(tail)]
    for a, b in zip(overlap, tail):
        if a['view_px'] != b['view_px'] and a['bottom'] < 2600:
            raise SystemExit(f'top/bottom disagree: {a} vs {b}')
    return rows


def main():
    log, scale, stock_top, stock_bottom, patched_top, patched_bottom, *labels = sys.argv[1:]
    scale = float(scale)
    rows = parse(log)
    n = len(rows)
    stock = merge(measure(stock_top, scale), measure(stock_bottom, scale), n)
    patched = merge(measure(patched_top, scale), measure(patched_bottom, scale), n)
    # A mixed-size line descends as far as its largest font: take that font's
    # descender from the row that uses it on its own (the same size, no lineHeight).
    by_size = {d['size']: d['desc'] for d in rows if not d['plh'] and not d['mixed']}
    print(
        '| Sample | Font | Line descender | `lineHeight` | Font line height | Baseline offset '
        '| **Predicted** | Logged | Predicted on screen | Stock on screen | Patched on screen | Letters |'
    )
    print('| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |')
    for i, d in enumerate(rows):
        line_descender = d['desc']
        if d['mixed']:
            line_descender = min(v for k, v in by_size.items() if k > d['size'])
        pred, offset = predicted_error(d, line_descender)
        # Fabric rounds the view's origin to the pixel grid and its size up to
        # it, and Yoga rounds the hairline's position the same way.
        h = d['h']
        oy = d['sbottom'] - h
        pred_px = round(oy * scale) + round(h * scale) - round(d['baseline'] * scale)
        s = stock[i]
        p = patched[i]
        label = labels[i] if i < len(labels) else str(i + 1)
        weight = ' bold' if 'Bold' in d['font'] else ''
        letters = {s['letters_px'], p['letters_px']}
        print(
            f"| {label} | SF {d['size']:g}{weight} | {line_descender:.3f} "
            f"| {d['plh']:.2f} | {d['flh']:.3f} | {offset:.3f} | **{pred:+.3f}** | {d['serr']:+.3f} "
            f"| {pred_px / scale:+.2f} | {s['view_pt']:+.2f} | {p['view_pt']:+.2f} "
            f"| {'0' if letters == {0} else letters} |"
            .replace('| 0.00 |', '| none |')
            .replace('| -0.00 |', '| 0 |')
            .replace('| +0.00 |', '| 0 |')
        )
        assert abs(pred - d['serr']) < 0.005, (label, pred, d['serr'])
        assert pred_px == s['view_px'], (label, pred_px, s['view_px'])
        assert p['view_px'] == 0, (label, p)


if __name__ == '__main__':
    main()
