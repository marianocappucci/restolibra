"""Shim de compatibilidad — la implementación real vive en libracore (paquete
interno, ver pyproject.toml y wiki/entities/libracore.md). No editar el
comportamiento genérico acá; los cambios van en el repo libracore.

Los defaults propios del módulo restaurant (cargos automáticos de cubierto/
panera) se agregan acá como extra_defaults, ya que libracore no conoce nada
específico de Restolibra."""
from libracore import config_manager as _core
from libracore.config_manager import (  # noqa: F401
    CONFIG_PATH, LOGO_DIR, CERTS_DIR, resolve_logo_path, resolve_cert_paths,
)

_EXTRA_DEFAULTS = {
    # Restaurant — cargos automáticos por mesa
    "cubierto_activo":        "0",       # 0 | 1
    "cubierto_precio":        "0",       # precio por comensal
    "panera_activo":          "0",       # 0 | 1
    "panera_precio":          "0",       # precio por mesa (cantidad fija 1)
}

DEFAULTS = {**_core.DEFAULTS, **_EXTRA_DEFAULTS}


def load():
    return _core.load(extra_defaults=_EXTRA_DEFAULTS)


def save(data):
    return _core.save(data, extra_defaults=_EXTRA_DEFAULTS)
