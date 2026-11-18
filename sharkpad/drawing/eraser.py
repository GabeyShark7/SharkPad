import math

from PySide6.QtCore import QRectF

from sharkpad.drawing.items import Stroke


def erase_segment(items, a, b, radius):
    steps = max(1, int(math.hypot(b.x() - a.x(), b.y() - a.y()) // max(1.0, radius / 2)))
    centers = [(a.x() + (b.x() - a.x()) * i / steps, a.y() + (b.y() - a.y()) * i / steps) for i in range(steps + 1)]
    area = QRectF(min(a.x(), b.x()) - radius, min(a.y(), b.y()) - radius,
                  abs(b.x() - a.x()) + 2 * radius, abs(b.y() - a.y()) + 2 * radius)
    result, touched = [], False
    for item in items:
        if not isinstance(item, Stroke) or not item.bounds().intersects(area):
            result.append(item)
            continue
        reach = (radius + item.width / 3) ** 2
        runs, run = [], []
        for px, py in item.points:
            if any((px - cx) ** 2 + (py - cy) ** 2 <= reach for cx, cy in centers):
                if run:
                    runs.append(run)
                run = []
            else:
                run.append((px, py))
        if run:
            runs.append(run)
        if len(runs) == 1 and len(runs[0]) == len(item.points):
            result.append(item)
            continue
        touched = True
        result.extend(Stroke(r, item.color, item.width, item.highlight) for r in runs if len(r) > 1)
    return result if touched else None
