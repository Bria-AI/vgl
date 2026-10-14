"""Thales: VGL without scores, where edits state their change."""

from bria_vgl.dialects.thales.model import ThalesVGL
from bria_vgl.dialects.thales.payloads import EditImages, EditImageWithMask, Generate

__all__ = ["EditImageWithMask", "EditImages", "Generate", "ThalesVGL"]
