// Shim sobre libra-ui/FacturaDetalle (extraído 2026-08-03, era byte-idéntico
// con Contalibra: mismo md5, 530 líneas). Toda la pantalla vive en el paquete;
// acá sólo se le pasa el rol.
//
// El rol no puede leerse desde el paquete: cada producto arma su contexto con
// `createAuthContext`, así que el `useAuth` de libra-ui apunta a otro contexto
// y devolvería siempre vacío.
import { FacturaDetalle as FacturaDetalleCompartida } from 'libra-ui/FacturaDetalle'
import { useAuth } from '../context/AuthContext'

export function FacturaDetalle() {
  const { user } = useAuth()
  return <FacturaDetalleCompartida esAdmin={user?.role === 'admin'} />
}
