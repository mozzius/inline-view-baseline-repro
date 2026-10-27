"""
Measure inline-view offsets from a screenshot of the repro screen.

For each blue view (#0000ff), find the red baseline hairline (#ff0000) of its
line and report:
  - view: (bottom edge of the blue view) - (top of the hairline), in px and pt
  - letters: (bottom edge of the letters on that line) - (top of the hairline),
    the most common value across the letter columns, in px

usage: measure.py <png> <scale> [<png> <scale> ...]
"""

import sys
from collections import Counter, deque

import numpy as np
from PIL import Image


def runs(mask_row, min_len):
    xs = np.flatnonzero(mask_row)
    if xs.size == 0:
        return []
    out = []
    start = prev = xs[0]
    for x in xs[1:]:
        if x != prev + 1:
            if prev - start + 1 >= min_len:
                out.append((start, prev))
            start = x
        prev = x
    if prev - start + 1 >= min_len:
        out.append((start, prev))
    return out


def components(mask):
    """4-connected components of a sparse mask, as bounding boxes."""
    seen = np.zeros_like(mask, dtype=bool)
    ys, xs = np.nonzero(mask)
    boxes = []
    h, w = mask.shape
    for y0, x0 in zip(ys, xs):
        if seen[y0, x0]:
            continue
        q = deque([(y0, x0)])
        seen[y0, x0] = True
        top, bottom, left, right, n = y0, y0, x0, x0, 0
        while q:
            y, x = q.popleft()
            n += 1
            top, bottom = min(top, y), max(bottom, y)
            left, right = min(left, x), max(right, x)
            for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                ny, nx = y + dy, x + dx
                if 0 <= ny < h and 0 <= nx < w and mask[ny, nx] and not seen[ny, nx]:
                    seen[ny, nx] = True
                    q.append((ny, nx))
        if n >= 30:
            boxes.append([top, bottom, left, right])
    return boxes


def merge_across_hairlines(boxes, red):
    """Join blue boxes split by a 1px red hairline drawn over them."""
    boxes = sorted(boxes)
    merged = []
    for b in boxes:
        for m in merged:
            overlap = min(m[3], b[3]) - max(m[2], b[2])
            gap = b[0] - m[1] - 1
            if overlap > 0 and 0 <= gap <= 2 and all(
                red[m[1] + 1 + i, (max(m[2], b[2]) + min(m[3], b[3])) // 2] for i in range(gap)
            ):
                m[1] = max(m[1], b[1])
                m[2], m[3] = min(m[2], b[2]), max(m[3], b[3])
                m.append('split')
                break
        else:
            merged.append(list(b))
    return merged


def measure(path, scale):
    img = np.asarray(Image.open(path).convert('RGB')).astype(int)
    r, g, b = img[..., 0], img[..., 1], img[..., 2]
    blue = (b > 200) & (r < 60) & (g < 60)
    red = (r > 200) & (g < 60) & (b < 60)
    lum = 0.299 * r + 0.587 * g + 0.114 * b
    dark = (lum < 110) & ~red & ~blue

    hairlines = []
    for y in range(img.shape[0]):
        for x0, x1 in runs(red[y], 20):
            # A hairline is 1px tall: skip rows that continue a red block.
            hairlines.append((y, x0, x1))

    squares = merge_across_hairlines(components(blue), red)
    results = []
    for sq in sorted(squares, key=lambda s: s[0]):
        top, bottom_row, left, right = sq[:4]
        split = 'split' in sq
        bottom = bottom_row + 1
        cx = (left + right) // 2
        cands = [h for h in hairlines if h[1] <= cx <= h[2] and h[0] > top]
        if not cands:
            continue
        hy, hx0, hx1 = min(cands, key=lambda h: abs(h[0] - bottom))
        # Letters on the same line, left of the view.
        text_left = max(hx0 + int(8 * scale), 0)
        text_right = left - int(2 * scale)
        if text_right - text_left < 10:
            # View at the start of a line: use the letters to its right.
            text_left, text_right = right + int(2 * scale), min(hx1 - int(8 * scale), img.shape[1])
        win_top, win_bottom = hy - int(14 * scale), hy + int(8 * scale)
        bottoms = []
        for x in range(text_left, text_right):
            col = np.flatnonzero(dark[win_top:win_bottom, x])
            if col.size:
                low = win_top + col[-1] + 1
                if hy - 4 <= low <= hy + int(6 * scale):
                    bottoms.append(low - hy)
        letters = Counter(bottoms).most_common(1)[0][0] if bottoms else None
        results.append(
            dict(
                top=top,
                bottom=bottom,
                height_px=bottom - top,
                width_px=right - left + 1,
                hairline=hy,
                hairline_right=hx1,
                view_px=bottom - hy,
                view_pt=(bottom - hy) / scale,
                letters_px=letters,
                split=split,
            )
        )
    return results


if __name__ == '__main__':
    args = sys.argv[1:]
    for path, scale in zip(args[::2], args[1::2]):
        scale = float(scale)
        print(f'== {path} (scale {scale:g})')
        print(f"{'#':>2} {'view WxH px':>12} {'hairline y':>10} {'view - baseline':>17} {'letters - baseline':>19}")
        for i, m in enumerate(measure(path, scale), 1):
            note = ' (hairline over view)' if m['split'] else ''
            print(
                f"{i:>2} {m['width_px']:>5}x{m['height_px']:<6} {m['hairline']:>10} "
                f"{m['view_px']:>+5d}px {m['view_pt']:>+7.2f}pt "
                f"{(str(m['letters_px']) + 'px') if m['letters_px'] is not None else '-':>19}{note}"
            )
