# -*- coding: utf-8 -*-
"""轻量时间序列折线图（QPainter 自绘，无第三方依赖）。"""
import datetime

from PyQt5 import QtCore, QtGui, QtWidgets


class TimeSeriesPlot(QtWidgets.QWidget):
    """折线图：x 轴为 Unix 时间（显示 HH:MM:SS），y 轴为数值（显示 ms）。

    支持在指定 x 位置绘制跳变标记（红色虚线 + 圆点）。
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._samples = []   # [(t_unix, value)]
        self._marks = []     # [t_unix] 跳变发生时刻
        self._max_points = 1200
        self._margin = 46
        self.setMinimumHeight(180)

    def add_sample(self, t, value):
        self._samples.append((t, value))
        if len(self._samples) > self._max_points:
            self._samples = self._samples[-self._max_points:]
        self.update()

    def add_mark(self, t):
        self._marks.append(t)
        if len(self._marks) > self._max_points:
            self._marks = self._marks[-self._max_points:]
        self.update()

    def clear(self):
        self._samples = []
        self._marks = []
        self.update()

    def sample_count(self):
        return len(self._samples)

    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        rect = self.rect()
        w, h = rect.width(), rect.height()
        m = self._margin
        painter.fillRect(rect, QtGui.QColor("#171b22"))

        if not self._samples:
            painter.setPen(QtGui.QColor("#5b6572"))
            painter.drawText(rect, QtCore.Qt.AlignCenter, "（等待采样数据…）")
            return

        plot_rect = QtCore.QRectF(m, 10, w - m - 10, h - 10 - 30)

        ys = [s[1] for s in self._samples]
        vmin, vmax = min(ys), max(ys)
        if vmax - vmin < 1e-9:
            vmax += 0.5
            vmin -= 0.5
        pad = (vmax - vmin) * 0.12
        vmin -= pad
        vmax += pad

        def y_of(v):
            return plot_rect.bottom() - (v - vmin) / (vmax - vmin) * plot_rect.height()

        # 水平网格 + Y 标签
        for i in range(5):
            frac = i / 4.0
            v = vmin + (vmax - vmin) * frac
            y = y_of(v)
            painter.setPen(QtGui.QColor("#2c3440"))
            painter.drawLine(QtCore.QPointF(plot_rect.left(), y),
                             QtCore.QPointF(plot_rect.right(), y))
            painter.setPen(QtGui.QColor("#8b95a5"))
            painter.drawText(QtCore.QRectF(2, y - 8, m - 6, 16),
                             QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter,
                             f"{v * 1000:.0f}ms")

        # X 范围与标签
        tmin = self._samples[0][0]
        tmax = self._samples[-1][0]
        if tmax - tmin < 1e-9:
            tmax = tmin + 1

        def x_of(t):
            return plot_rect.left() + (t - tmin) / (tmax - tmin) * plot_rect.width()

        painter.setPen(QtGui.QColor("#8b95a5"))
        for i in range(4):
            frac = i / 3.0
            t = tmin + (tmax - tmin) * frac
            x = x_of(t)
            label = datetime.datetime.fromtimestamp(t).strftime("%H:%M:%S")
            painter.drawText(QtCore.QRectF(x - 42, plot_rect.bottom() + 4, 84, 18),
                             QtCore.Qt.AlignCenter, label)

        # 零线
        if vmin < 0 < vmax:
            painter.setPen(QtGui.QPen(QtGui.QColor("#4a5568"), 1, QtCore.Qt.DotLine))
            painter.drawLine(QtCore.QPointF(plot_rect.left(), y_of(0)),
                             QtCore.QPointF(plot_rect.right(), y_of(0)))

        # 跳变标记
        for t in self._marks:
            if t < tmin or t > tmax:
                continue
            x = x_of(t)
            painter.setPen(QtGui.QPen(QtGui.QColor("#e06c75"), 1, QtCore.Qt.DashLine))
            painter.drawLine(QtCore.QPointF(x, plot_rect.top()),
                             QtCore.QPointF(x, plot_rect.bottom()))
            painter.setPen(QtGui.QPen(QtGui.QColor("#e06c75")))
            painter.setBrush(QtGui.QColor("#e06c75"))
            painter.drawEllipse(QtCore.QPointF(x, plot_rect.top() + 8), 3, 3)

        # 折线
        painter.setPen(QtGui.QPen(QtGui.QColor("#3b82f6"), 1.6))
        painter.setBrush(QtCore.Qt.NoBrush)
        path = QtGui.QPainterPath()
        first = True
        for t, v in self._samples:
            x = x_of(t)
            y = y_of(v)
            if first:
                path.moveTo(x, y)
                first = False
            else:
                path.lineTo(x, y)
        painter.drawPath(path)
