import { RemitoNuevo as RemitoNuevoKit } from 'libra-ui/RemitoNuevo'

// La pantalla vive en el kit desde el pase de comprobantes al kit (2026-09-07); acá sólo se monta.
export function RemitoNuevo() {
  return <RemitoNuevoKit />
}
