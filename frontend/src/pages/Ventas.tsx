import { Ventas as VentasComercio } from 'libra-ui/comercio/Ventas'
import { useAuth } from '../context/AuthContext'

// La pantalla vive en el kit desde P9-M3 (2026-09-06). Lo que decide este
// producto: quien puede anular es el rol admin de la sesion.
export function Ventas() {
  const { user } = useAuth()
  return <VentasComercio puedeAnular={user?.role === 'admin'} />
}
