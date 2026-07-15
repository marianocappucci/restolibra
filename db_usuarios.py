"""Shim: la lógica de usuarios ahora vive en libracore.db.usuarios (Fase 3
de LibraCore, migración real, ver wiki/entities/libracore.md)."""
from libracore.db.usuarios import (  # noqa: F401
    _hash_password,
    _verify_password,
    _DUMMY_PASSWORD_HASH,
    create_usuario,
    get_usuario_by_username,
    get_usuario_by_id,
    get_all_usuarios,
    update_usuario,
    update_usuario_password,
    delete_usuario,
    check_usuario_credentials,
    ensure_admin_user,
)
