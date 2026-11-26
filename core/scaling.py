# -*- coding: utf-8 -*-
"""界面缩放：按比例重写 QSS 中的 px 值，实现运行时可调的全局缩放。"""
import re

DEFAULT_SCALE = 1.0
MIN_SCALE = 0.8
MAX_SCALE = 1.6
STEP = 0.1

_scale = DEFAULT_SCALE
_base_qss = ""
_px_re = re.compile(r"(?<![\w.-])(\d+(?:\.\d+)?)px")


def set_base_stylesheet(qss):
    """保存未缩放的原始 QSS（每次缩放都从它重新计算）。"""
    global _base_qss
    _base_qss = qss or ""


def clamp_scale(value):
    try:
        value = float(value)
    except (TypeError, ValueError):
        return DEFAULT_SCALE
    return max(MIN_SCALE, min(MAX_SCALE, value))


def set_scale(value):
    global _scale
    _scale = clamp_scale(value)
    return _scale


def get_scale():
    return _scale


def scale_px(value):
    """把逻辑像素值按当前缩放比换算。"""
    return max(1, int(round(value * _scale)))


def scale_stylesheet(qss=None):
    """返回按当前缩放比放大/缩小后的 QSS。"""
    source = _base_qss if qss is None else qss
    return _px_re.sub(lambda m: "%dpx" % scale_px(float(m.group(1))), source)
