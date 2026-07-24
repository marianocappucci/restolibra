import { clsx, type ClassValue } from 'clsx'
import { twMerge } from 'tailwind-merge'

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

// Redondeo a entero para mostrar cantidades de stock -- equivalente al
// filtro Jinja `entero` de web/templates_config.py (round + int). Solo para
// visualizacion; los valores reales siguen siendo float en la API.
export function formatEntero(value: number): string {
  if (value === null || value === undefined || Number.isNaN(value)) return String(value)
  return String(Math.round(value))
}
