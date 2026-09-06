import { Productos as ProductosComercio } from 'libra-ui/comercio/Productos'
import { ESTACIONES } from '../api'

// La pantalla vive en el kit desde P9-M1 (2026-09-06). Lo que decide este
// producto: estacion de comanda, el switch vendible (insumo vs. plato), el
// codigo autogenerado y el link a la receta, que es pantalla propia.
export function Productos() {
  return (
    <ProductosComercio
      estaciones={[...ESTACIONES]}
      conVendible
      codigoAutogenerado
      rutaDeReceta={(id) => `/productos/${id}/receta`}
    />
  )
}
