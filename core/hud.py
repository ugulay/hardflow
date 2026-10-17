# Pure HUD-layout + viewport-guide math -- stdlib only, no gpu / blf / bpy.
#
# Module 2 (viewport polish, BoxCutter parity) adds two on-screen aids: a premium
# translucent *shortcut bar* along the bottom of the viewport, and *dynamic
# alignment guides* that light up when the cursor lines up with an earlier point.
# Both need only a little screen-space geometry -- packing a centered row of chips
# and testing axis alignment -- so, exactly like core/preview_cache.py, it lives
# in the pure core where tests/test_core.py can cover it without a live GPU.
# ui/draw.py measures the text and renders; the arithmetic is all here.


def shortcut_bar_layout(chip_widths, region_width, margin=24.0, gap=8.0,
                        height=26.0, bottom=14.0, row_gap=6.0):
    """Pack a row of shortcut chips of the given pixel `chip_widths`, centered
    along the bottom edge of a `region_width`-wide viewport.

    Returns ``{'bar': (x, y, w, h), 'chips': [(x, w), ...], 'rows': [i, ...],
    'row_height': h, 'row_gap': g}`` in screen pixels with a bottom-left origin:
    'bar' is the box enclosing every row, each chip its own left edge + width,
    and 'rows' the row each chip landed on (0 = top row, the last row sits at
    `bottom`) so the caller can place it vertically.

    Chips that would not fit inside `region_width` minus both margins **wrap**
    onto further rows instead of running off the right edge -- a dozen chips at a
    high UI scale, or a narrow viewport with the sidebar open, used to push the
    last ones out of sight. Each row is centered on its own; a row still wider
    than the viewport (a single over-wide chip) is left-anchored at `margin` so
    its first chips never slide off the left edge. Non-positive widths are
    dropped; empty input yields an empty layout. Pure, unit-tested."""
    widths = [w for w in chip_widths if w > 0]
    if not widths:
        return {'bar': (0.0, bottom, 0.0, height), 'chips': [], 'rows': [],
                'row_height': height, 'row_gap': row_gap}
    avail = max(region_width - 2.0 * margin, 0.0)
    # Greedy wrap: start a new row as soon as the next chip would overflow. A
    # lone chip wider than the available width keeps its own row -- there is
    # nothing left to split.
    rows, used = [[]], 0.0
    for w in widths:
        step = w if not rows[-1] else gap + w
        if rows[-1] and used + step > avail:
            rows.append([w])
            used = w
        else:
            rows[-1].append(w)
            used += step
    n = len(rows)
    bar_h = n * height + (n - 1) * row_gap
    chips, chip_rows, lefts, totals = [], [], [], []
    for r, row in enumerate(rows):
        total = sum(row) + gap * (len(row) - 1)
        x = (region_width - total) / 2.0
        if x < margin:
            x = margin
        lefts.append(x)
        totals.append(total)
        for w in row:
            chips.append((x, w))
            chip_rows.append(r)
            x += w + gap
    return {'bar': (min(lefts), bottom, max(totals), bar_h),
            'chips': chips, 'rows': chip_rows,
            'row_height': height, 'row_gap': row_gap}


def axis_alignment(pa, pb, tol=6.0):
    """Whether two screen points line up on an axis, within `tol` pixels: 'V' when
    they share an X (a vertical guide would pass through both), 'H' when they share
    a Y (horizontal), else None. Vertical wins when both hold (a near-coincident
    point), so a single guide is emitted rather than a cross. Pure."""
    if abs(pa[0] - pb[0]) <= tol:
        return 'V'
    if abs(pa[1] - pb[1]) <= tol:
        return 'H'
    return None


def alignment_guides(anchors, cursor, region_size, tol=6.0):
    """Full-span guide segments for every anchor the `cursor` currently lines up
    with -- the BoxCutter-style dynamic alignment hint. A vertical alignment gives
    the screen-tall line at the anchor's X; a horizontal one the screen-wide line
    at the anchor's Y. `region_size` is (width, height); each segment is
    ``((x1, y1), (x2, y2))`` in screen pixels. Several anchors on the same guide
    line collapse to one segment (deduped by axis + rounded coordinate). Returns
    [] when nothing aligns. Pure, unit-tested."""
    w, h = region_size
    seen = set()
    guides = []
    for a in anchors:
        kind = axis_alignment(a, cursor, tol)
        if kind == 'V':
            key = ('V', round(a[0], 1))
            if key not in seen:
                seen.add(key)
                guides.append(((a[0], 0.0), (a[0], h)))
        elif kind == 'H':
            key = ('H', round(a[1], 1))
            if key not in seen:
                seen.add(key)
                guides.append(((0.0, a[1]), (w, a[1])))
    return guides
