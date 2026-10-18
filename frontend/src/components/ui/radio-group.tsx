// Re-export de la primitiva canónica de la familia: la implementación vive en libra-ui (`libra-ui/ui/radio-group`). Era la copia byte a byte de la del kit (ADR-076 del kit).
// Acá sólo se re-exporta para que el resto del producto la importe desde @/components/ui/radio-group como siempre. Si este
// producto la necesitara distinta, reemplazá este archivo por una copia propia.
export * from "libra-ui/ui/radio-group"
