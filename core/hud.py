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
                        height=26.0, bottom=14.0):
    """Pack a row of shortcut chips of the given pixel `chip_widths`, centered
    along the bottom edge of a `region_width`-wide viewport.

    Returns ``{'bar': (x, y, w, h), 'chips': [(x, w), ...]}`` in screen pixels with
    a bottom-left origin: 'bar' is the enclosing strip, each chip its own left edge
    + width. The row is centered on the viewport; when it is wider than the
    viewport minus both margins it is left-anchored at `margin` instead, so the
    first chips never slide off the left edge. Non-positive widths are dropped;
    empty input yields an empty layout. Pure, unit-tested."""
    widths = [w for w in chip_widths if w > 0]
    if not widths:
        return {'bar': (0.0, bottom, 0.0, height), 'chips': []}
    total = sum(widths) + gap * (len(widths) - 1)
    x0 = (region_width - total) / 2.0
    if x0 < margin:
        x0 = margin
    chips = []
    x = x0
    for w in widths:
        chips.append((x, w))
        x += w + gap
    return {'bar': (x0, bottom, total, height), 'chips': chips}


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
