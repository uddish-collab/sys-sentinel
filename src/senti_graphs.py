"""Live hardware metric graph widget rendered with QPainter."""

import time
from typing import Optional, List, Tuple
from PySide6.QtCore import Qt, QRectF, QPointF
from PySide6.QtGui import (
    QPainter,
    QPen,
    QColor,
    QFont,
    QLinearGradient,
    QPainterPath,
)
from PySide6.QtWidgets import QWidget

from senti_state import MetricHistory


class LineGraph(QWidget):
    """Accurate live graph with right-aligned history, dashed thresholds, and stats."""

    def __init__(
        self,
        title: str,
        unit: str,
        history: MetricHistory,
        warn_thresh: float,
        crit_thresh: float,
        y_max: float = 100.0,
        line_color: str = "#00e5ff",
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self.title = title
        self.unit = unit
        self.history = history
        self.warn_thresh = warn_thresh
        self.crit_thresh = crit_thresh
        self.y_max = y_max
        self.line_color = QColor(line_color)

        self.duration_seconds: float = 300.0  # Default 5 minutes
        self.setMinimumHeight(125)

    def set_duration(self, seconds: float):
        self.duration_seconds = seconds
        self.update()

    def set_line_color(self, color: QColor):
        self.line_color = QColor(color)
        self.update()

    def paintEvent(self, event):
        del event
        p = QPainter()
        if not p.begin(self):
            return
        try:
            p.setRenderHint(QPainter.RenderHint.Antialiasing)

            w = self.width()
            h = self.height()

            # Fill card background
            p.fillRect(0, 0, w, h, QColor("#111a30"))

            now = time.time()
            samples = self.history.get_range(self.duration_seconds, now=now)
            current_val, avg_val, peak_val = self.history.stats(self.duration_seconds, now=now)

            # 1. Header / Stats Bar
            p.setFont(QFont("Segoe UI", 9, QFont.Weight.DemiBold))
            p.setPen(QColor("#cdd9ed"))
            p.drawText(12, 18, self.title)

            stats_font = QFont("Segoe UI", 8)
            p.setFont(stats_font)

            if current_val is not None:
                c_str = f"Current: {current_val:.0f}{self.unit}"
                a_str = f"Avg: {avg_val:.0f}{self.unit}" if avg_val is not None else ""
                p_str = f"Peak: {peak_val:.0f}{self.unit}" if peak_val is not None else ""
                stats_text = f"{c_str}   |   {a_str}   |   {p_str}"
                p.setPen(QColor("#8c9dbd"))
                p.drawText(w - 220, 18, stats_text)
            else:
                p.setPen(QColor("#687894"))
                p.drawText(w - 120, 18, "No active data")

            # 2. Graph Rect Bounds
            margin_left = 34
            margin_right = 16
            margin_top = 30
            margin_bottom = 24
            gw = w - margin_left - margin_right
            gh = h - margin_top - margin_bottom
            graph_rect = QRectF(margin_left, margin_top, gw, gh)

            # Plot area background
            p.fillRect(graph_rect, QColor("#0c1324"))
            p.setPen(QPen(QColor("#1b2947"), 1))
            p.drawRect(graph_rect)

            # 3. Y Axis Gridlines (4 divisions)
            p.setFont(QFont("Segoe UI", 8))
            for step in (0.0, 0.25, 0.5, 0.75, 1.0):
                val = self.y_max * step
                gy = graph_rect.bottom() - (gh * step)

                # Gridline
                p.setPen(QPen(QColor("#18253f"), 1))
                p.drawLine(QPointF(graph_rect.left(), gy), QPointF(graph_rect.right(), gy))

                # Y-axis label
                p.setPen(QColor("#5a6c8a"))
                label = f"{val:.0f}"
                p.drawText(QRectF(2, gy - 8, margin_left - 6, 16), Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, label)

            # 4. Reference Threshold Lines (Dashed)
            # Warning line
            if 0.0 < self.warn_thresh < self.y_max:
                warn_y = graph_rect.bottom() - (gh * (self.warn_thresh / self.y_max))
                dash_pen = QPen(QColor("#ffb020"), 1, Qt.PenStyle.DashLine)
                dash_pen.setDashPattern([4, 4])
                p.setPen(dash_pen)
                p.drawLine(QPointF(graph_rect.left(), warn_y), QPointF(graph_rect.right(), warn_y))

                # WARN label positioned BELOW its line
                p.setPen(QColor("#ffb020"))
                p.drawText(int(graph_rect.right() - 65), int(warn_y + 13), f"WARN {self.warn_thresh:.0f}{self.unit}")

            # Critical line
            if 0.0 < self.crit_thresh < self.y_max:
                crit_y = graph_rect.bottom() - (gh * (self.crit_thresh / self.y_max))
                dash_pen_crit = QPen(QColor("#ff3b4a"), 1, Qt.PenStyle.DashLine)
                dash_pen_crit.setDashPattern([4, 4])
                p.setPen(dash_pen_crit)
                p.drawLine(QPointF(graph_rect.left(), crit_y), QPointF(graph_rect.right(), crit_y))

                # CRIT label positioned ABOVE its line (never overlaps WARN!)
                p.setPen(QColor("#ff3b4a"))
                p.drawText(int(graph_rect.right() - 65), int(crit_y - 4), f"CRIT {self.crit_thresh:.0f}{self.unit}")

            # 5. X Axis Time Labels
            if self.duration_seconds >= 600:
                x_labels = [("-15m", 0.0), ("-10m", 0.333), ("-5m", 0.666), ("now", 1.0)]
            elif self.duration_seconds >= 240:
                x_labels = [("-5m", 0.0), ("-2.5m", 0.5), ("now", 1.0)]
            else:
                x_labels = [("-60s", 0.0), ("-30s", 0.5), ("now", 1.0)]

            p.setPen(QColor("#5a6c8a"))
            for text, frac in x_labels:
                lx = graph_rect.left() + (gw * frac)
                p.drawText(QRectF(lx - 25, graph_rect.bottom() + 4, 50, 16), Qt.AlignmentFlag.AlignCenter, text)

            # 6. Plot Data Series (Right-Aligned by Age)
            valid_points_exist = any(v is not None for _, v in samples)

            if not valid_points_exist:
                # Clear message when no data exists (e.g. no temperature sensor)
                p.setPen(QColor("#687894"))
                p.setFont(QFont("Segoe UI", 9))
                msg = f"No {self.title.lower()} sensor data available on this PC"
                p.drawText(graph_rect, Qt.AlignmentFlag.AlignCenter, msg)
                return

            # Split into continuous segments (None breaks the line)
            segments: List[List[QPointF]] = []
            current_segment: List[QPointF] = []

            for ts, val in samples:
                if val is None:
                    if current_segment:
                        segments.append(current_segment)
                        current_segment = []
                else:
                    age = max(0.0, now - ts)
                    if age <= self.duration_seconds:
                        # Right-aligned X coordinate
                        x = graph_rect.right() - (age / self.duration_seconds) * gw
                        # Clamped Y coordinate
                        y_ratio = max(0.0, min(1.0, val / self.y_max))
                        y = graph_rect.bottom() - (y_ratio * gh)
                        current_segment.append(QPointF(x, y))

            if current_segment:
                segments.append(current_segment)

            # Render segments with gradient area fill and bright stroke
            for seg in segments:
                if not seg:
                    continue

                # Fill area beneath
                fill_path = QPainterPath()
                fill_path.moveTo(seg[0].x(), graph_rect.bottom())
                for pt in seg:
                    fill_path.lineTo(pt)
                fill_path.lineTo(seg[-1].x(), graph_rect.bottom())
                fill_path.closeSubpath()

                area_grad = QLinearGradient(0, graph_rect.top(), 0, graph_rect.bottom())
                area_grad.setColorAt(0.0, QColor(self.line_color.red(), self.line_color.green(), self.line_color.blue(), 60))
                area_grad.setColorAt(1.0, QColor(self.line_color.red(), self.line_color.green(), self.line_color.blue(), 5))
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(area_grad)
                p.drawPath(fill_path)

                # Draw the line
                line_pen = QPen(self.line_color, 1.8, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
                p.setPen(line_pen)
                p.setBrush(Qt.BrushStyle.NoBrush)

                if len(seg) == 1:
                    # Single point
                    p.drawPoint(seg[0])
                else:
                    for p1, p2 in zip(seg, seg[1:]):
                        p.drawLine(p1, p2)
        finally:
            p.end()
