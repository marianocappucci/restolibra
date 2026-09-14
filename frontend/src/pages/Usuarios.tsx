// Shim sobre libra-ui/Usuarios (mismo patrón que el resto de la familia --
// ver LibraDesk). Reemplaza la pantalla propia (Dialogs de alta/edición
// inline, contrato `{nombre, activo}`) el 2026-09-13, al adoptar
// `libraauth.usuarios.build_users_router` en el backend (ADR-018): el
// backend ya habla el contrato único (`name`/`active`/`email`, `id: string`,
// `DELETE` en 204), así que la pantalla compartida se pinta contra él sin
// traducir nada.
import { UserCog } from 'lucide-react'
import { Usuarios as UsuariosBase } from 'libra-ui/Usuarios'
import { useAuth } from '../context/AuthContext'

// Los mismos cuatro roles que ya validaba `ROLES` en api.ts (y que valida
// ahora `build_users_router(roles=ROLES, ...)` en el backend, ver
// `app/db_usuarios.py`) -- "mozo" es el rol exclusivo de Restolibra, sin
// equivalente en Contalibra.
const ROLES = [
  { value: 'admin', label: 'Admin' },
  { value: 'operador', label: 'Operador' },
  { value: 'cajero', label: 'Cajero' },
  { value: 'mozo', label: 'Mozo' },
]

// Este producto monta su router de usuarios en `/api/usuarios`, no en el
// `/users` por defecto del componente -- ver `app/web/app.py`.
export function Usuarios() {
  const { user: me } = useAuth()
  return (
    <UsuariosBase
      icono={UserCog}
      basePath="/api/usuarios"
      roles={ROLES}
      // El backend nuevo trae `DELETE /api/usuarios/{id}` con las guardas
      // del único admin (no degradarlo, no desactivarlo, no borrarlo) --
      // antes de esta adopción esas guardas eran más flojas (sólo cubrían
      // "degradar"/"borrar", no "desactivar") y estaban escritas a mano acá.
      permitirEliminar
      usuarioActualId={me?.id}
    />
  )
}
