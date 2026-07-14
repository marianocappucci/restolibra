"""Shim: la construcción de templates ahora vive en libracore.admin.templates_config."""
import os

from libracore.admin.templates_config import create_templates

_TEMPLATES_DIR = os.path.join(os.path.dirname(__file__), "templates")

templates = create_templates(_TEMPLATES_DIR)
