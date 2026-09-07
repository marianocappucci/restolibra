import { Turnos as TurnosComercio } from 'libra-ui/comercio/Turnos'
import { useAuth } from '../context/AuthContext'

// La pantalla vive en el kit desde P9-M3 (2026-09-06). Lo que decide este
// producto: el admin ve los turnos de todos los cajeros.
export function Turnos() {
  const { user } = useAuth()
  return <TurnosComercio esAdmin={user?.role === 'admin'} />
}
