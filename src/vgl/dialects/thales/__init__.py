"""Thales: VGL without scores, where edits state their change."""

from vgl.dialects.thales.model import ThalesVGL
from vgl.dialects.thales.payloads import EditImages, EditImageWithMask, Generate

__all__ = ["EditImageWithMask", "EditImages", "Generate", "ThalesVGL"]
