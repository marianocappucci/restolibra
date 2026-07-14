"""Shim: la lógica de módulos ahora vive en libracore.db.modulos."""
from libracore.db.modulos import get_modulos, apply_plan  # noqa: F401
