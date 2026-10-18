// Re-export de la primitiva canónica de la familia: la implementación vive en libra-ui (`libra-ui/ui/tabs`). Trae la fila de pestañas que se parte en renglones (`flex-wrap`, ADR-067 del kit).
// Acá sólo se re-exporta para que el resto del producto la importe desde @/components/ui/tabs como siempre. Si este
// producto la necesitara distinta, reemplazá este archivo por una copia propia.
export * from "libra-ui/ui/tabs"
