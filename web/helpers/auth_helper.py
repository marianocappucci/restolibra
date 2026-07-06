import database as db


def get_current_user_id(username: str):
    return (db.get_usuario_by_username(username) or {}).get("id")
