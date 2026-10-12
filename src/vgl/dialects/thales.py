"""Thales dialect: the FIBO language without scores, where edits state their change.

The canonical implementation lives in `vgl.languages.fibo.dialects.thales`; this is its public home.
"""

from vgl.languages.fibo.dialects.thales import EditImages, EditImageWithMask, Generate, ThalesVGL

__all__ = ["EditImageWithMask", "EditImages", "Generate", "ThalesVGL"]
