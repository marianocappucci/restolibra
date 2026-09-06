import { Stock as StockComercio } from 'libra-ui/comercio/Stock'

// La pantalla vive en el kit desde P9-M1 (2026-09-06). Lo que decide este
// producto: el historial es pagina propia y la entrada convierte unidad de
// compra. La merma aparece porque el backend declara motivos.
export function Stock() {
  return <StockComercio rutaDeMovimientos={(id) => `/stock/movimientos?producto_id=${id}`} conConversionDeUnidad />
}
