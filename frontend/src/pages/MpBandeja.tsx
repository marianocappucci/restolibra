// La bandeja de MercadoPago: conciliar lo que entró a la cuenta y facturarlo.
//
// Re-export de `libra-ui/MpBandeja` desde la v0.45.0. Esta pantalla estaba
// escrita **dos veces** —508 líneas acá y 508 en el otro producto, con UNA
// línea de diferencia: el badge de la columna Estado del historial— y se
// unificó en el kit. LibraClub la estrena desde ahí, así que no llegó a haber
// una tercera copia.
//
// No hace falta ninguna prop: el backend ya estaba unificado antes que la
// pantalla. Los tres productos montan `libracore.mp_bandeja_router` bajo el
// mismo prefijo `/api/mp-bandeja`, y lo único que cada uno decide —qué
// `external_reference` omitir— se resuelve del lado del servidor.
export { MpBandeja } from 'libra-ui/MpBandeja'
