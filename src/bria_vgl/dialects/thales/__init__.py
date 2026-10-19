"""Thales: VGL without scores, where edits state their change."""

from bria_vgl.dialects.thales.model import ThalesVGL
from bria_vgl.dialects.thales.payloads import Caption, EditImages, EditImageWithMask, Generate, Inspire

__all__ = ["Caption", "EditImageWithMask", "EditImages", "Generate", "Inspire", "ThalesVGL"]
