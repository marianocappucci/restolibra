// Shim sobre libra-ui/Facturas (extraído el 2026-08-27; era la misma pantalla
// que la de Contalibra, con 26 líneas de diferencia y todas en las etiquetas de
// los badges de tipo). La pantalla vive en el paquete; acá queda lo que es de
// este producto: el alta.
//
// ⚠️ **Cambio visible**: las etiquetas de tipo pasan de `Fact. A` / `NC-A` a
// `FA` / `NCA`, con el nombre completo en el tooltip. Se unificó en la forma de
// Contalibra porque la columna Tipo ocupa menos y el nombre no se pierde.
//
// El PDF lo sirve el router Jinja2 viejo, no la API, así que la URL se pasa
// desde acá.
import { Link } from 'react-router-dom'
import { FileMinus, FilePlus, FileText, Plus } from 'lucide-react'
import { Facturas as FacturasCompartida } from 'libra-ui/Facturas'

import { Button } from '@/components/ui/button'
import {
  DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'

function Nuevo() {
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button><Plus />Nuevo</Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end">
        <DropdownMenuItem asChild>
          <Link to="/facturas/nueva"><FileText className="text-primary" />Factura</Link>
        </DropdownMenuItem>
        <DropdownMenuSeparator />
        {/* Las notas se emiten desde el detalle de la factura que anulan o
            ajustan: sin comprobante asociado no existen. */}
        <DropdownMenuItem disabled className="flex-col items-start gap-0.5">
          <span className="flex items-center gap-2"><FileMinus className="text-amber-500" />Nota de Crédito</span>
          <span className="pl-6 text-xs text-muted-foreground">Generá desde el detalle de una factura</span>
        </DropdownMenuItem>
        <DropdownMenuItem disabled className="flex-col items-start gap-0.5">
          <span className="flex items-center gap-2"><FilePlus className="text-sky-500" />Nota de Débito</span>
          <span className="pl-6 text-xs text-muted-foreground">Generá desde el detalle de una factura</span>
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  )
}

export function Facturas() {
  return (
    <FacturasCompartida
      urlDelPdf={(id) => `/facturas/${id}/pdf`}
      rutaDelDetalle={(id) => `/facturas/${id}`}
      acciones={<Nuevo />}
      mensajeVacio="No hay facturas registradas aún."
    />
  )
}
