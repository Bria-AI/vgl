"""Thales: the FIBO language without scores, where edits state their change."""

from vgl.languages.fibo.dialects.thales.model import ThalesVGL
from vgl.languages.fibo.dialects.thales.payloads import EditImages, EditImageWithMask, Generate

__all__ = ["EditImageWithMask", "EditImages", "Generate", "ThalesVGL"]
