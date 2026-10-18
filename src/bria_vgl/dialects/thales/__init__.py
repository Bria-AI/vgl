"""Thales: VGL without scores, where edits state their change."""

from bria_vgl.dialects.thales.model import ThalesVGL
from bria_vgl.dialects.thales.payloads import EditImages, EditImageWithMask, Generate, Inspire, Style

__all__ = ["EditImageWithMask", "EditImages", "Generate", "Inspire", "Style", "ThalesVGL"]
