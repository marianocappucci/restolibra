import { useEffect, useRef, useState, type ChangeEvent, type ReactNode } from 'react'
import { api, ApiError, type ArcaConfig, type Backup, type ConfigCfg } from '../api'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import { Label } from '@/components/ui/label'
import { Badge } from '@/components/ui/badge'
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from '@/components/ui/select'
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { ConfirmDialog } from '@/components/confirm-dialog'
import { PasswordInput } from 'libra-ui/PasswordInput'
import {
  Ban, Building2, Check, CheckCircle2, ChevronDown, Copy, Database, Download,
  ExternalLink, Info, Mail, Pause, Phone, Power, Printer, Save, Send,
  Settings, ShieldCheck, ToggleRight, Upload,
} from 'lucide-react'

// Portado desde Contalibra (frontend/src/pages/Config.tsx), mismo backend
// libracore (config_manager/db_arca_config.py) -- ver web/api/config.py.
// Estructura de navegación calcada de web/templates/config.html de
// Restolibra: 5 tabs de primer nivel (Empresa / Integraciones / Servicio /
// Ticket / Datos) + el botón "Backup rápido" fijo al final de la barra.
// "Integraciones" agrupa MercadoPago/ARCA/Email en una sub-navegación
// lateral, no como tabs propias -- igual que el Jinja2 original.
//
// A diferencia de Contalibra, acá NO hay tab "Categorías": en Restolibra
// las categorías de producto/egreso son páginas Jinja2 propias
// (/config/categorias-producto, /config/categorias-egreso) linkeadas
// directo desde el sidebar (ver Layout.tsx, sección Productos) -- no forman
// parte de /config. Portarlas queda para los módulos Productos/Egresos.
const TABS = [
  { id: 'empresa', label: 'Empresa', icon: Building2 },
  { id: 'integraciones', label: 'Integraciones', icon: Power },
  { id: 'servicio', label: 'Servicio', icon: ToggleRight },
  { id: 'ticket', label: 'Ticket / Impresora', icon: Printer },
  { id: 'datos', label: 'Datos / Backup', icon: Database },
] as const
type TabId = typeof TABS[number]['id']

// Tutoriales colapsables portados tal cual del contenido REAL de
// web/templates/config.html de Restolibra (no el de Contalibra -- mismos
// pasos en general porque ambos productos comparten backend, pero con las
// menciones a "Restolibra" propias del texto original, ver Gmail más abajo),
// adaptados de Bootstrap/collapse a <details>/Tailwind. Ver
// DatosTab/MpTab/ArcaTab/EmailTab más abajo.
function Tutorial({ badge, badgeClassName, title, children }: {
  badge: string; badgeClassName: string; title: string; children: ReactNode
}) {
  return (
    <details className="group mb-4 rounded-md border bg-muted/30 px-4 py-3 text-sm">
      <summary className="flex cursor-pointer list-none items-center gap-2 [&::-webkit-details-marker]:hidden">
        <span className={`rounded px-2 py-0.5 text-xs font-semibold text-white ${badgeClassName}`}>{badge}</span>
        <span className="font-medium">{title}</span>
        <ChevronDown className="ml-auto size-4 shrink-0 text-muted-foreground transition-transform group-open:rotate-180" />
      </summary>
      <div className="mt-3 grid gap-3 border-t pt-3">{children}</div>
    </details>
  )
}

function TutorialStep({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div>
      <p className="mb-1 text-sm font-semibold text-foreground">{title}</p>
      <ol className="ml-4 list-decimal space-y-1.5 text-sm text-muted-foreground">{children}</ol>
    </div>
  )
}

function TutorialLink({ href, children }: { href: string; children: ReactNode }) {
  return (
    <a href={href} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 font-medium text-primary hover:underline">
      {children}<ExternalLink className="size-3" />
    </a>
  )
}

function TutorialCode({ children }: { children: ReactNode }) {
  return <code className="mt-1 mb-1 block rounded border bg-background px-2 py-1 font-mono text-xs">{children}</code>
}

function TutorialNote({ tone = 'info', children }: { tone?: 'info' | 'warning' | 'success'; children: ReactNode }) {
  const styles: Record<string, string> = {
    info: 'border-blue-300 bg-blue-50 text-blue-800 dark:border-blue-900 dark:bg-blue-950/40 dark:text-blue-300',
    warning: 'border-amber-300 bg-amber-50 text-amber-800 dark:border-amber-900 dark:bg-amber-950/40 dark:text-amber-300',
    success: 'border-emerald-300 bg-emerald-50 text-emerald-800 dark:border-emerald-900 dark:bg-emerald-950/40 dark:text-emerald-300',
  }
  return (
    <p className={`flex items-start gap-2 rounded-md border px-3 py-2 text-xs ${styles[tone]}`}>
      <Info className="mt-0.5 size-3.5 shrink-0" />{children}
    </p>
  )
}

export function Config() {
  const [tab, setTab] = useState<TabId>('empresa')
  const [cfg, setCfg] = useState<ConfigCfg | null>(null)
  const [arca, setArca] = useState<ArcaConfig | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [saved, setSaved] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    load()
  }, [])

  function describeError(err: unknown): string {
    if (err instanceof ApiError) return err.detail
    return 'Error de conexión.'
  }

  async function load() {
    setLoading(true)
    setError(null)
    try {
      const data = await api.get<{ cfg: ConfigCfg; arca: ArcaConfig }>('/api/config')
      setCfg(data.cfg)
      setArca(data.arca)
    } catch (err) {
      setError(describeError(err))
    } finally {
      setLoading(false)
    }
  }

  async function guardar<T>(path: string, payload: T, onDone?: () => void) {
    setSaving(true)
    setError(null)
    setSaved(null)
    try {
      await api.put(path, payload)
      setSaved(tab)
      onDone?.()
      await load()
    } catch (err) {
      setError(describeError(err))
    } finally {
      setSaving(false)
    }
  }

  async function subirArchivo(path: string, field: string, file: File) {
    setSaving(true)
    setError(null)
    try {
      const form = new FormData()
      form.append(field, file)
      await api.postForm(path, form)
      await load()
    } catch (err) {
      setError(describeError(err))
    } finally {
      setSaving(false)
    }
  }

  if (loading || !cfg) {
    return <p className="py-6 text-center text-sm text-muted-foreground">Cargando…</p>
  }

  return (
    <div className="grid gap-4">
      <h2 className="flex items-center gap-2 text-lg font-semibold"><Settings className="size-5" />Configuración</h2>

      <div className="flex flex-wrap items-center justify-between gap-2 border-b pb-2">
        <Tabs value={tab} onValueChange={(v) => { setTab(v as TabId); setSaved(null); setError(null) }}>
          <TabsList>
            {TABS.map((t) => (
              <TabsTrigger key={t.id} value={t.id}><t.icon />{t.label}</TabsTrigger>
            ))}
          </TabsList>
        </Tabs>
        <Button asChild size="sm" variant="outline">
          <a href="/config/backup-db" download><Download />Backup rápido</a>
        </Button>
      </div>

      {error && <p className="text-sm text-destructive">{error}</p>}
      {saved === tab && <p className="text-sm text-emerald-600 dark:text-emerald-400">Guardado.</p>}

      {tab === 'empresa' && <EmpresaTab cfg={cfg} setCfg={setCfg} saving={saving} guardar={guardar} subirArchivo={subirArchivo} />}
      {tab === 'integraciones' && (
        <IntegracionesTab cfg={cfg} setCfg={setCfg} arca={arca} setArca={setArca} saving={saving} guardar={guardar} subirArchivo={subirArchivo} />
      )}
      {tab === 'servicio' && <ServicioTab cfg={cfg} setCfg={setCfg} saving={saving} guardar={guardar} />}
      {tab === 'ticket' && <TicketTab cfg={cfg} setCfg={setCfg} saving={saving} guardar={guardar} />}
      {tab === 'datos' && <DatosTab saving={saving} setSaving={setSaving} setError={setError} describeError={describeError} />}
    </div>
  )
}

function IntegracionesTab({ cfg, setCfg, arca, setArca, saving, guardar, subirArchivo }: {
  cfg: ConfigCfg; setCfg: (c: ConfigCfg) => void
  arca: ArcaConfig | null; setArca: (a: ArcaConfig) => void
  saving: boolean; guardar: GuardarFn
  subirArchivo: (path: string, field: string, file: File) => Promise<void>
}) {
  const SUB = [
    { id: 'mp', label: 'MercadoPago', icon: Phone },
    { id: 'arca', label: 'ARCA / AFIP', icon: ShieldCheck },
    { id: 'mail', label: 'Email / SMTP', icon: Mail },
  ] as const
  const [seccion, setSeccion] = useState<typeof SUB[number]['id']>('mp')

  return (
    <div className="flex flex-col gap-4 sm:flex-row">
      <div className="flex shrink-0 flex-row gap-1 sm:w-48 sm:flex-col sm:border-r sm:pr-2">
        {SUB.map((s) => (
          <button
            key={s.id} type="button" onClick={() => setSeccion(s.id)}
            className={`flex items-center gap-2 rounded-md border-l-2 px-3 py-2 text-left text-sm transition-colors ${
              seccion === s.id ? 'border-primary bg-primary/5 font-medium text-primary' : 'border-transparent text-muted-foreground hover:bg-muted'
            }`}
          >
            <s.icon className="size-4" />{s.label}
          </button>
        ))}
      </div>
      <div className="max-w-2xl flex-1">
        {seccion === 'mp' && <MpTab cfg={cfg} setCfg={setCfg} saving={saving} guardar={guardar} />}
        {seccion === 'arca' && <ArcaTab arca={arca} setArca={setArca} saving={saving} guardar={guardar} subirArchivo={subirArchivo} />}
        {seccion === 'mail' && <EmailTab cfg={cfg} setCfg={setCfg} saving={saving} guardar={guardar} />}
      </div>
    </div>
  )
}

type GuardarFn = <T>(path: string, payload: T, onDone?: () => void) => Promise<void>

function EmpresaTab({ cfg, setCfg, saving, guardar, subirArchivo }: {
  cfg: ConfigCfg; setCfg: (c: ConfigCfg) => void; saving: boolean
  guardar: GuardarFn; subirArchivo: (path: string, field: string, file: File) => Promise<void>
}) {
  function handleLogo(e: ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0]
    if (file) subirArchivo('/api/config/empresa/logo', 'logo', file)
  }

  return (
    <Card>
      <CardHeader><CardTitle className="flex items-center gap-2 text-base"><Building2 className="size-4" />Datos de la empresa</CardTitle></CardHeader>
      <CardContent className="grid gap-3 sm:grid-cols-2">
        <Field label="Nombre" value={cfg.empresa_nombre} onChange={(v) => setCfg({ ...cfg, empresa_nombre: v })} />
        <Field label="CUIT" value={cfg.empresa_cuit} onChange={(v) => setCfg({ ...cfg, empresa_cuit: v })} />
        <Field label="Dirección" value={cfg.empresa_direccion} onChange={(v) => setCfg({ ...cfg, empresa_direccion: v })} />
        <Field label="Teléfono" value={cfg.empresa_telefono} onChange={(v) => setCfg({ ...cfg, empresa_telefono: v })} />
        <Field label="Email" value={cfg.empresa_email} onChange={(v) => setCfg({ ...cfg, empresa_email: v })} />
        <Field label="Ingresos Brutos" value={cfg.empresa_iibb} onChange={(v) => setCfg({ ...cfg, empresa_iibb: v })} />
        <div className="grid gap-1.5">
          <Label>Condición de IVA</Label>
          <Select value={cfg.empresa_iva_condition} onValueChange={(v) => setCfg({ ...cfg, empresa_iva_condition: v })}>
            <SelectTrigger><SelectValue /></SelectTrigger>
            <SelectContent>
              <SelectItem value="Monotributista">Monotributista (emite Factura C)</SelectItem>
              <SelectItem value="Responsable Inscripto">Responsable Inscripto (emite Factura A y B)</SelectItem>
              <SelectItem value="IVA Exento">IVA Exento (emite Factura B)</SelectItem>
            </SelectContent>
          </Select>
        </div>
        <Field label="Inicio de actividades" type="date" value={cfg.empresa_inicio_actividades} onChange={(v) => setCfg({ ...cfg, empresa_inicio_actividades: v })} />
        <div className="col-span-full grid gap-1.5">
          <Label>Logo (PNG o JPG)</Label>
          {cfg.logo_path && (
            <div className="flex items-center gap-3">
              <img src="/config/empresa/logo" alt="Logo actual" className="h-16 max-w-48 rounded-md border bg-white object-contain p-1.5" />
              <Badge className="bg-emerald-600 text-white hover:bg-emerald-600/90 dark:bg-emerald-500"><CheckCircle2 />Logo cargado</Badge>
            </div>
          )}
          <Input type="file" accept=".png,.jpg,.jpeg" onChange={handleLogo} disabled={saving} className="max-w-sm" />
          <p className="text-xs text-muted-foreground">PNG o JPG. Dejalo vacío para mantener el logo actual.</p>
        </div>
        <div className="col-span-full">
          <Button disabled={saving} onClick={() => guardar('/api/config/empresa', {
            empresa_nombre: cfg.empresa_nombre, empresa_direccion: cfg.empresa_direccion,
            empresa_cuit: cfg.empresa_cuit, empresa_telefono: cfg.empresa_telefono,
            empresa_email: cfg.empresa_email, empresa_iibb: cfg.empresa_iibb,
            empresa_iva_condition: cfg.empresa_iva_condition,
            empresa_inicio_actividades: cfg.empresa_inicio_actividades,
          })}>
            <Save />{saving ? 'Guardando…' : 'Guardar datos de empresa'}
          </Button>
        </div>
      </CardContent>
    </Card>
  )
}

function MpTab({ cfg, setCfg, saving, guardar }: {
  cfg: ConfigCfg; setCfg: (c: ConfigCfg) => void; saving: boolean; guardar: GuardarFn
}) {
  const [probando, setProbando] = useState(false)
  const [resultado, setResultado] = useState<string | null>(null)
  const [copiado, setCopiado] = useState(false)
  const webhookUrl = `${window.location.origin}/webhooks/mercadopago`

  async function probar() {
    setProbando(true)
    setResultado(null)
    try {
      const r = await api.get<{ ok: boolean; nickname?: string; error?: string }>('/api/mp/probar')
      setResultado(r.ok ? `Conectado — ${r.nickname}` : r.error ?? 'Error')
    } catch (err) {
      setResultado(err instanceof ApiError ? err.detail : 'Error de conexión.')
    } finally {
      setProbando(false)
    }
  }

  function copiarWebhook() {
    navigator.clipboard.writeText(webhookUrl).then(() => {
      setCopiado(true)
      setTimeout(() => setCopiado(false), 2000)
    })
  }

  return (
    <Card>
      <CardHeader><CardTitle className="flex items-center gap-2 text-base"><Phone className="size-4" />MercadoPago</CardTitle></CardHeader>
      <CardContent className="grid gap-3 sm:grid-cols-2">
        <div className="col-span-full">
          <Tutorial badge="MercadoPago" badgeClassName="bg-[#009ee3]" title="¿Cómo obtener el Access Token, User ID, POS ID y Webhook Secret?">
            <TutorialStep title="1 — Access Token (token de producción)">
              <li>Ingresá a <TutorialLink href="https://www.mercadopago.com.ar/developers/panel/app">mercadopago.com.ar/developers/panel/app</TutorialLink></li>
              <li>Creá una nueva aplicación (o seleccioná una existente)</li>
              <li>En la aplicación, andá a la pestaña <strong>Credenciales de producción</strong></li>
              <li>Copiá el <strong>Access token</strong> (empieza con <code className="rounded bg-background px-1 py-0.5 font-mono text-xs">APP_USR-</code>) y pegalo abajo</li>
            </TutorialStep>
            <TutorialStep title="2 — User ID del vendedor">
              <li>Iniciá sesión en <TutorialLink href="https://www.mercadopago.com.ar">mercadopago.com.ar</TutorialLink></li>
              <li>Hacé clic en tu avatar (arriba a la derecha) → <strong>Tu perfil</strong></li>
              <li>El <strong>User ID</strong> es el número que aparece abajo de tu nombre (ej: <code className="rounded bg-background px-1 py-0.5 font-mono text-xs">123456789</code>)</li>
              <li>También lo encontrás en el panel de desarrolladores al ver las credenciales de tu app</li>
            </TutorialStep>
            <TutorialStep title="3 — POS ID (External ID del punto de venta)">
              <li>En <TutorialLink href="https://www.mercadopago.com.ar/stores">mercadopago.com.ar/stores</TutorialLink> creá o seleccioná una <strong>Sucursal</strong></li>
              <li>Dentro de la sucursal, creá un <strong>Punto de venta</strong> (tipo: <em>PDV</em>)</li>
              <li>Al crearlo, completá el campo <strong>External ID</strong> con un código propio (ej: <code className="rounded bg-background px-1 py-0.5 font-mono text-xs">CAJA01</code>) — ese valor es el que va acá</li>
            </TutorialStep>
            <TutorialStep title="4 — Webhook Secret">
              <li>En el panel de desarrolladores, entrá a tu aplicación y luego a <strong>Webhooks</strong></li>
              <li>Registrá la URL: <code className="rounded bg-background px-1 py-0.5 font-mono text-xs">https://tu-dominio/webhooks/mercadopago</code> y seleccioná el evento <strong>Pagos (payment)</strong></li>
              <li>MercadoPago te mostrará una <strong>firma secreta (secret)</strong> — copiala y pegala en el campo Webhook Secret</li>
            </TutorialStep>
            <TutorialNote tone="warning">Usá siempre las credenciales de <strong>producción</strong>, no las de prueba, para cobros reales.</TutorialNote>
          </Tutorial>
        </div>
        <Field label="Access Token" type="password" value={cfg.mp_access_token} onChange={(v) => setCfg({ ...cfg, mp_access_token: v })} />
        <Field label="Webhook Secret" type="password" value={cfg.mp_webhook_secret} onChange={(v) => setCfg({ ...cfg, mp_webhook_secret: v })} />
        <Field label="Descripción del cobro" value={cfg.mp_concepto_descripcion} onChange={(v) => setCfg({ ...cfg, mp_concepto_descripcion: v })} />
        <div className="grid gap-1.5">
          <Label>Alícuota IVA</Label>
          <Select value={cfg.mp_iva_rate || '0'} onValueChange={(v) => setCfg({ ...cfg, mp_iva_rate: v })}>
            <SelectTrigger><SelectValue /></SelectTrigger>
            <SelectContent>
              <SelectItem value="0">Sin IVA (Monotributista / Exento)</SelectItem>
              <SelectItem value="0.21">21%</SelectItem>
              <SelectItem value="0.105">10,5%</SelectItem>
            </SelectContent>
          </Select>
        </div>
        <Field label="User ID (QR)" value={cfg.mp_user_id} onChange={(v) => setCfg({ ...cfg, mp_user_id: v })} />
        <Field label="POS ID (QR)" value={cfg.mp_pos_id} onChange={(v) => setCfg({ ...cfg, mp_pos_id: v })} />
        <div className="col-span-full grid gap-1.5 rounded-md border bg-muted/40 p-3 text-sm">
          <p className="font-medium">URL del webhook para registrar en MercadoPago</p>
          <div className="flex gap-2">
            <Input readOnly value={webhookUrl} className="font-mono text-xs" />
            <Button type="button" size="sm" variant="outline" onClick={copiarWebhook}>
              {copiado ? <Check /> : <Copy />}{copiado ? 'Copiado' : 'Copiar'}
            </Button>
          </div>
          <p className="text-xs text-muted-foreground">Evento a suscribir: Pagos (payment). El Webhook Secret lo genera MP al guardar el webhook.</p>
        </div>
        <div className="col-span-full flex items-center gap-3">
          <Button disabled={saving} onClick={() => guardar('/api/config/mp', {
            mp_access_token: cfg.mp_access_token, mp_webhook_secret: cfg.mp_webhook_secret,
            mp_concepto_descripcion: cfg.mp_concepto_descripcion, mp_iva_rate: cfg.mp_iva_rate,
            mp_user_id: cfg.mp_user_id, mp_pos_id: cfg.mp_pos_id,
          })}>
            <Save />{saving ? 'Guardando…' : 'Guardar MercadoPago'}
          </Button>
          {cfg.mp_access_token && (
            <Button type="button" variant="outline" disabled={probando} onClick={probar}>
              <Send />{probando ? 'Probando…' : 'Probar conexión'}
            </Button>
          )}
          {resultado && <span className="text-sm text-muted-foreground">{resultado}</span>}
        </div>
      </CardContent>
    </Card>
  )
}

function EmailTab({ cfg, setCfg, saving, guardar }: {
  cfg: ConfigCfg; setCfg: (c: ConfigCfg) => void; saving: boolean; guardar: GuardarFn
}) {
  const [probando, setProbando] = useState(false)
  const [resultado, setResultado] = useState<string | null>(null)

  async function probar() {
    setProbando(true)
    setResultado(null)
    try {
      const r = await api.get<{ ok: boolean; host?: string; error?: string }>('/api/email/probar')
      setResultado(r.ok ? `Conectado — ${r.host}` : r.error ?? 'Error')
    } catch (err) {
      setResultado(err instanceof ApiError ? err.detail : 'Error de conexión.')
    } finally {
      setProbando(false)
    }
  }

  return (
    <Card>
      <CardHeader><CardTitle className="flex items-center gap-2 text-base"><Mail className="size-4" />Email (SMTP)</CardTitle></CardHeader>
      <CardContent className="grid gap-3 sm:grid-cols-2">
        <div className="col-span-full">
          <Tutorial badge="Gmail" badgeClassName="bg-destructive" title="¿Cómo configurar Gmail con una contraseña de aplicación?">
            <p className="text-sm text-muted-foreground">
              Gmail <strong>no permite usar tu contraseña normal</strong> para enviar emails desde apps externas.
              Necesitás generar una <strong>contraseña de aplicación</strong> de 16 caracteres. Seguí estos pasos:
            </p>
            <ol className="ml-4 list-decimal space-y-1.5 text-sm text-muted-foreground">
              <li>Ingresá a tu cuenta de Google en <TutorialLink href="https://myaccount.google.com">myaccount.google.com</TutorialLink></li>
              <li>En el menú izquierdo hacé clic en <strong>Seguridad</strong></li>
              <li>Asegurate de tener activada la <strong>Verificación en dos pasos</strong> (es un requisito de Google)</li>
              <li>Buscá <em>&quot;contraseñas de aplicación&quot;</em> en el buscador de configuración de Google o ingresá directamente a <TutorialLink href="https://myaccount.google.com/apppasswords">myaccount.google.com/apppasswords</TutorialLink></li>
              <li>En el campo <strong>Nombre de la app</strong> escribí <em>Restolibra</em> y hacé clic en <strong>Crear</strong></li>
              <li>Google te mostrará una contraseña de <strong>16 caracteres</strong> — copiala en ese momento (no se vuelve a mostrar)</li>
              <li>Pegá esa contraseña en el campo <strong>Contraseña</strong> del formulario de abajo y guardá</li>
            </ol>
            <TutorialNote tone="info">
              <strong>Valores recomendados para Gmail:</strong> Servidor: <code className="rounded bg-background px-1 py-0.5 font-mono text-xs">smtp.gmail.com</code> · Puerto: <code className="rounded bg-background px-1 py-0.5 font-mono text-xs">587</code> · Usuario: tu dirección de Gmail completa
            </TutorialNote>
          </Tutorial>
        </div>
        <Field label="Host SMTP" value={cfg.email_smtp_host} onChange={(v) => setCfg({ ...cfg, email_smtp_host: v })} />
        <Field label="Puerto" value={cfg.email_smtp_port} onChange={(v) => setCfg({ ...cfg, email_smtp_port: v })} />
        <Field label="Usuario" value={cfg.email_smtp_user} onChange={(v) => setCfg({ ...cfg, email_smtp_user: v })} />
        <Field label="Contraseña (dejar vacío para no cambiar)" type="password" value={cfg.email_smtp_password} onChange={(v) => setCfg({ ...cfg, email_smtp_password: v })} />
        <Field label="Remitente" value={cfg.email_from} onChange={(v) => setCfg({ ...cfg, email_from: v })} />
        <Field label="Nombre del remitente" value={cfg.email_from_name} onChange={(v) => setCfg({ ...cfg, email_from_name: v })} />
        <div className="col-span-full flex items-center gap-3">
          <Button disabled={saving} onClick={() => guardar('/api/config/email', {
            email_smtp_host: cfg.email_smtp_host, email_smtp_port: cfg.email_smtp_port,
            email_smtp_user: cfg.email_smtp_user, email_smtp_password: cfg.email_smtp_password,
            email_from: cfg.email_from, email_from_name: cfg.email_from_name,
          })}>
            <Save />{saving ? 'Guardando…' : 'Guardar email'}
          </Button>
          {cfg.email_smtp_host && cfg.email_smtp_user && cfg.email_smtp_password && (
            <Button type="button" variant="outline" disabled={probando} onClick={probar}>
              <Send />{probando ? 'Probando…' : 'Probar conexión'}
            </Button>
          )}
          {resultado && <span className="text-sm text-muted-foreground">{resultado}</span>}
        </div>
      </CardContent>
    </Card>
  )
}

function ArcaTab({ arca, setArca, saving, guardar, subirArchivo }: {
  arca: ArcaConfig | null; setArca: (a: ArcaConfig) => void; saving: boolean
  guardar: GuardarFn; subirArchivo: (path: string, field: string, file: File) => Promise<void>
}) {
  const [probando, setProbando] = useState(false)
  const [resultado, setResultado] = useState<string | null>(null)
  const a: ArcaConfig = arca ?? { empresa: 'default', cuit: '', punto_venta: 1, ambiente: 'homologacion', alias: '', clave_path: '', certificado_path: '' }

  async function probar() {
    setProbando(true)
    setResultado(null)
    try {
      const r = await api.get<{ ok: boolean; ambiente?: string; error?: string }>('/api/arca/probar')
      setResultado(r.ok ? `Autenticado OK (${r.ambiente})` : r.error ?? 'Error')
    } catch (err) {
      setResultado(err instanceof ApiError ? err.detail : 'Error de conexión.')
    } finally {
      setProbando(false)
    }
  }

  return (
    <Card>
      <CardHeader><CardTitle className="flex items-center gap-2 text-base"><ShieldCheck className="size-4" />ARCA (facturación electrónica)</CardTitle></CardHeader>
      <CardContent className="grid gap-3 sm:grid-cols-2">
        <div className="col-span-full">
          <Tutorial badge="ARCA / AFIP" badgeClassName="bg-[#1a3a5c]" title="¿Cómo obtener el certificado digital y la clave privada?">
            <TutorialStep title="1 — Generar la clave privada y el CSR (en tu PC)">
              <li>Instalá <strong>OpenSSL</strong> (en Windows podés usar Git Bash o WSL; en Linux/Mac ya viene incluido)</li>
              <li>
                Abrí una terminal y ejecutá:
                <TutorialCode>openssl genrsa -out clave_privada.key 2048</TutorialCode>
              </li>
              <li>
                Luego generá el CSR (pedido de certificado):
                <TutorialCode>openssl req -new -key clave_privada.key -subj "/C=AR/O=Mi Empresa/CN=CUIT 20123456789" -out mi_empresa.csr</TutorialCode>
                Reemplazá <em>CUIT 20123456789</em> con tu CUIT sin guiones.
              </li>
              <li>Guardá bien el archivo <strong>clave_privada.key</strong> — es el que subís al campo <em>Clave privada</em> de abajo</li>
            </TutorialStep>
            <TutorialStep title="2 — Obtener el certificado desde el portal ARCA">
              <li>Ingresá con CUIT y Clave Fiscal (nivel 3 o superior) a <TutorialLink href="https://auth.afip.gob.ar">auth.afip.gob.ar</TutorialLink></li>
              <li>Buscá el servicio <strong>&quot;Administración de Certificados Digitales&quot;</strong> en el listado de servicios habilitados</li>
              <li>Hacé clic en <strong>Nueva solicitud de certificado</strong></li>
              <li>Pegá el contenido del archivo <code className="rounded bg-background px-1 py-0.5 font-mono text-xs">mi_empresa.csr</code> generado en el paso anterior</li>
              <li>Descargá el certificado resultante (<code className="rounded bg-background px-1 py-0.5 font-mono text-xs">.crt</code> o <code className="rounded bg-background px-1 py-0.5 font-mono text-xs">.pem</code>) — ese archivo es el que subís al campo <em>Certificado</em> de abajo</li>
            </TutorialStep>
            <TutorialStep title="3 — Punto de venta">
              <li>En el portal ARCA / AFIP, buscá el servicio <strong>&quot;ABM de Puntos de Venta&quot;</strong></li>
              <li>Creá un punto de venta de tipo <strong>Facturación electrónica — Web Services</strong></li>
              <li>El número asignado es el que ingresás en el campo <em>Punto de venta</em> de abajo (ej: <code className="rounded bg-background px-1 py-0.5 font-mono text-xs">5</code>)</li>
            </TutorialStep>
            <TutorialNote tone="info">Usá el ambiente <strong>Homologación</strong> para hacer pruebas sin emitir comprobantes reales. Cambiá a <strong>Producción</strong> recién cuando todo funcione correctamente.</TutorialNote>
            <TutorialNote tone="warning">La <strong>clave privada</strong> nunca se comparte ni se sube a ningún sitio externo. Solo la subís una vez a este servidor, que es tuyo.</TutorialNote>
          </Tutorial>
          <Tutorial badge="ARCA / AFIP" badgeClassName="bg-[#1a3a5c]" title="¿Qué servicio debo habilitar para consultar datos de clientes por CUIT?">
            <p className="text-sm text-muted-foreground">
              El botón <strong>&quot;Consultar ARCA&quot;</strong> en el formulario de clientes completa automáticamente nombre, domicilio y condición de IVA a partir del CUIT.
              Para que funcione, tu certificado debe tener acceso al webservice de Padrón Alcance 13.
            </p>
            <TutorialStep title="1 — Ingresar al Administrador de Relaciones">
              <li>Ingresá con CUIT y Clave Fiscal a <TutorialLink href="https://auth.afip.gob.ar">auth.afip.gob.ar</TutorialLink></li>
              <li>Buscá y abrí el servicio <strong>&quot;Administrador de Relaciones de Clave Fiscal&quot;</strong></li>
              <li>Hacé clic en <strong>Nueva Relación</strong></li>
            </TutorialStep>
            <TutorialStep title="2 — Crear la relación para Padrón Alcance 13">
              <li>En <em>Servicio</em>, buscá y seleccioná: <strong>Consulta a Padrón Alcance 13</strong> (ws_sr_padron_a13)</li>
              <li>En <em>Representante</em>, seleccioná el certificado que ya configuraste en Restolibra</li>
              <li>Confirmá la relación</li>
            </TutorialStep>
            <TutorialNote tone="success">Una vez habilitado, el botón <strong>&quot;Consultar ARCA&quot;</strong> en el alta de clientes funcionará automáticamente.</TutorialNote>
            <TutorialNote tone="info">Este servicio es distinto al de facturación (WSFE). Necesitás habilitarlos por separado usando el mismo certificado.</TutorialNote>
          </Tutorial>
        </div>
        <Field label="CUIT" value={a.cuit} onChange={(v) => setArca({ ...a, cuit: v })} />
        <Field label="Punto de venta" value={String(a.punto_venta)} onChange={(v) => setArca({ ...a, punto_venta: Number(v) || 1 })} />
        <div className="grid gap-1.5">
          <Label>Ambiente</Label>
          <Select value={a.ambiente} onValueChange={(v) => setArca({ ...a, ambiente: v })}>
            <SelectTrigger><SelectValue /></SelectTrigger>
            <SelectContent>
              <SelectItem value="homologacion">Homologación (pruebas)</SelectItem>
              <SelectItem value="produccion">Producción</SelectItem>
            </SelectContent>
          </Select>
        </div>
        <Field label="Alias" value={a.alias} onChange={(v) => setArca({ ...a, alias: v })} />
        <div className="grid gap-1.5">
          <Label>Certificado (.crt)</Label>
          {a.certificado_path && (
            <Badge className="w-fit bg-emerald-600 text-white hover:bg-emerald-600/90 dark:bg-emerald-500"><CheckCircle2 />Cargado</Badge>
          )}
          <Input type="file" accept=".crt,.pem" disabled={saving}
            onChange={(e) => { const f = e.target.files?.[0]; if (f) subirArchivo(`/api/config/arca/certificados?empresa=${a.empresa}`, 'certificado', f) }} />
          {a.certificado_path && <p className="truncate text-xs text-muted-foreground">Actual: {a.certificado_path}</p>}
        </div>
        <div className="grid gap-1.5">
          <Label>Clave privada (.key)</Label>
          {a.clave_path && (
            <Badge className="w-fit bg-emerald-600 text-white hover:bg-emerald-600/90 dark:bg-emerald-500"><CheckCircle2 />Cargada</Badge>
          )}
          <Input type="file" accept=".key,.pem" disabled={saving}
            onChange={(e) => { const f = e.target.files?.[0]; if (f) subirArchivo(`/api/config/arca/certificados?empresa=${a.empresa}`, 'clave_privada', f) }} />
          {a.clave_path && <p className="truncate text-xs text-muted-foreground">Actual: {a.clave_path}</p>}
        </div>
        <div className="col-span-full flex items-center gap-3">
          <Button disabled={saving} onClick={() => guardar('/api/config/arca', {
            empresa: a.empresa, cuit: a.cuit, punto_venta: a.punto_venta, ambiente: a.ambiente, alias: a.alias,
          })}>
            <Save />{saving ? 'Guardando…' : 'Guardar ARCA'}
          </Button>
          {a.certificado_path && a.clave_path && (
            <Button type="button" variant="outline" disabled={probando} onClick={probar}>
              <Send />{probando ? 'Probando…' : 'Probar conexión'}
            </Button>
          )}
          {resultado && <span className="text-sm text-muted-foreground">{resultado}</span>}
        </div>
      </CardContent>
    </Card>
  )
}

function ServicioTab({ cfg, setCfg, saving, guardar }: {
  cfg: ConfigCfg; setCfg: (c: ConfigCfg) => void; saving: boolean; guardar: GuardarFn
}) {
  const ESTADOS: { value: ConfigCfg['servicio_estado']; icon: typeof CheckCircle2; color: string; border: string; label: string; desc: string }[] = [
    { value: 'activo', icon: CheckCircle2, color: 'text-emerald-600 dark:text-emerald-400', border: 'border-emerald-600/40 bg-emerald-500/5', label: 'Activo', desc: 'Operación normal. Todos los usuarios tienen acceso completo.' },
    { value: 'pausado', icon: Pause, color: 'text-amber-600 dark:text-amber-400', border: 'border-amber-500/40 bg-amber-500/5', label: 'Pausado', desc: 'Los usuarios pueden ingresar pero ven un banner de aviso. Útil para avisar antes de un corte.' },
    { value: 'suspendido', icon: Ban, color: 'text-destructive', border: 'border-destructive/40 bg-destructive/5', label: 'Suspendido', desc: 'Acceso bloqueado por completo. Se muestra la página de suspensión. Reactivar desde el panel admin del servidor o cambiando a Activo antes de guardar.' },
  ]

  return (
    <Card className="max-w-xl">
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-base"><ToggleRight className="size-4" />Estado del servicio</CardTitle>
        <CardDescription>Controlá el acceso al sistema para esta instancia. Este ajuste también puede cambiarse desde <code>panel_admin.py</code> en el servidor.</CardDescription>
      </CardHeader>
      <CardContent className="grid gap-4">
        <div className="grid gap-2">
          <Label>Estado actual</Label>
          {ESTADOS.map((e) => (
            <label
              key={e.value}
              className={`flex cursor-pointer items-start gap-2 rounded-md border p-3 text-sm ${cfg.servicio_estado === e.value ? e.border : ''}`}
            >
              <input
                type="radio" name="servicio_estado" className="mt-1" checked={cfg.servicio_estado === e.value}
                onChange={() => setCfg({ ...cfg, servicio_estado: e.value })}
              />
              <span>
                <span className={`flex items-center gap-1.5 font-semibold ${e.color}`}><e.icon className="size-4" />{e.label}</span>
                <span className="mt-0.5 block text-muted-foreground">{e.desc}</span>
              </span>
            </label>
          ))}
        </div>
        <div className="grid gap-1.5">
          <Label>Mensaje personalizado <span className="font-normal text-muted-foreground">(opcional)</span></Label>
          <Textarea rows={2} value={cfg.servicio_mensaje} onChange={(e) => setCfg({ ...cfg, servicio_mensaje: e.target.value })}
            placeholder="Ej: Servicio suspendido por falta de pago. Contactar a soporte@restolibra.com.ar" />
        </div>
        <div>
          <Button disabled={saving} onClick={() => guardar('/api/config/servicio', {
            servicio_estado: cfg.servicio_estado, servicio_mensaje: cfg.servicio_mensaje,
          })}>
            <Check />{saving ? 'Guardando…' : 'Guardar estado'}
          </Button>
        </div>
      </CardContent>
    </Card>
  )
}

function TicketTab({ cfg, setCfg, saving, guardar }: {
  cfg: ConfigCfg; setCfg: (c: ConfigCfg) => void; saving: boolean; guardar: GuardarFn
}) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-base"><Printer className="size-4" />Impresora de tickets / ticketeadora térmica</CardTitle>
        <CardDescription>Configurá cómo se imprime el ticket en impresoras de rollo (Epson TM, Star, Bixolon, etc.). El ticket se genera como PDF angosto descargable desde cada venta o factura.</CardDescription>
      </CardHeader>
      <CardContent className="grid gap-3 sm:grid-cols-2">
        <div className="grid gap-1.5">
          <Label>Ancho del rollo</Label>
          <Select value={cfg.ticket_ancho_mm} onValueChange={(v) => setCfg({ ...cfg, ticket_ancho_mm: v })}>
            <SelectTrigger><SelectValue /></SelectTrigger>
            <SelectContent>
              <SelectItem value="80">80 mm (estándar)</SelectItem>
              <SelectItem value="58">58 mm (mini)</SelectItem>
            </SelectContent>
          </Select>
        </div>
        <div className="grid gap-1.5">
          <Label>Tamaño de fuente</Label>
          <Select value={cfg.ticket_fuente_size} onValueChange={(v) => setCfg({ ...cfg, ticket_fuente_size: v })}>
            <SelectTrigger><SelectValue /></SelectTrigger>
            <SelectContent>
              <SelectItem value="7">7 pt — muy pequeño</SelectItem>
              <SelectItem value="8">8 pt — pequeño</SelectItem>
              <SelectItem value="9">9 pt — normal (recomendado)</SelectItem>
              <SelectItem value="10">10 pt — grande</SelectItem>
              <SelectItem value="11">11 pt — muy grande</SelectItem>
            </SelectContent>
          </Select>
        </div>
        <Field label="Texto al pie" value={cfg.ticket_pie} onChange={(v) => setCfg({ ...cfg, ticket_pie: v })} />
        <div className="grid content-center gap-2">
          <label className="flex items-center gap-2 text-sm">
            <input type="checkbox" checked={cfg.ticket_mostrar_logo === '1'} onChange={(e) => setCfg({ ...cfg, ticket_mostrar_logo: e.target.checked ? '1' : '0' })} />
            Mostrar logo de la empresa
          </label>
          <label className="flex items-center gap-2 text-sm">
            <input type="checkbox" checked={cfg.ticket_linea_corte === '1'} onChange={(e) => setCfg({ ...cfg, ticket_linea_corte: e.target.checked ? '1' : '0' })} />
            Imprimir línea de corte al final
          </label>
        </div>
        <div className="col-span-full">
          <Button disabled={saving} onClick={() => guardar('/api/config/ticket', {
            ticket_ancho_mm: cfg.ticket_ancho_mm, ticket_fuente_size: cfg.ticket_fuente_size,
            ticket_mostrar_logo: cfg.ticket_mostrar_logo === '1', ticket_linea_corte: cfg.ticket_linea_corte === '1',
            ticket_pie: cfg.ticket_pie,
          })}>
            <Check />{saving ? 'Guardando…' : 'Guardar configuración'}
          </Button>
        </div>
      </CardContent>
    </Card>
  )
}

function DatosTab({ saving, setSaving, setError, describeError }: {
  saving: boolean; setSaving: (v: boolean) => void
  setError: (v: string | null) => void; describeError: (err: unknown) => string
}) {
  const [backups, setBackups] = useState<Backup[]>([])
  const [restoreMsg, setRestoreMsg] = useState<string | null>(null)
  const [restoreFile, setRestoreFile] = useState<File | null>(null)
  const [confirmRestore, setConfirmRestore] = useState(false)
  const fileInputRef = useRef<HTMLInputElement>(null)

  useEffect(() => { cargar() }, [])

  async function cargar() {
    try {
      setBackups(await api.get<Backup[]>('/api/config/backups'))
    } catch (err) {
      setError(describeError(err))
    }
  }

  function seleccionarArchivo(e: ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0]
    if (!file) return
    setRestoreFile(file)
    setConfirmRestore(true)
  }

  function cancelarRestauracion() {
    setConfirmRestore(false)
    setRestoreFile(null)
    if (fileInputRef.current) fileInputRef.current.value = ''
  }

  async function restaurar() {
    if (!restoreFile) return
    setSaving(true)
    setError(null)
    setRestoreMsg(null)
    try {
      const form = new FormData()
      form.append('backup_file', restoreFile)
      await api.postForm('/api/config/restore-db', form)
      setRestoreMsg('Base de datos restaurada correctamente. Se guardó un backup automático antes de reemplazar.')
      await cargar()
    } catch (err) {
      setError(describeError(err))
    } finally {
      setSaving(false)
      setRestoreFile(null)
      if (fileInputRef.current) fileInputRef.current.value = ''
    }
  }

  return (
    <div className="grid gap-4 sm:grid-cols-2">
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-base"><Download className="size-4" />Backup manual</CardTitle>
          <CardDescription>Descargá una copia completa de la base de datos en este momento.</CardDescription>
        </CardHeader>
        <CardContent>
          <Button asChild className="w-full">
            <a href="/config/backup-db" download><Download />Descargar backup ahora</a>
          </Button>
          <p className="mt-2 text-xs text-muted-foreground">El archivo .db contiene todos tus datos: clientes, facturas, ventas, caja, etc.</p>
        </CardContent>
      </Card>

      <Card className="border-amber-500/40">
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-base text-amber-600 dark:text-amber-400"><Upload className="size-4" />Restaurar base de datos</CardTitle>
          <CardDescription>Esto reemplaza todos los datos actuales con el backup seleccionado.</CardDescription>
        </CardHeader>
        <CardContent className="grid gap-3">
          <div className="grid gap-1.5">
            <Label>Archivo de backup (.db)</Label>
            <Input ref={fileInputRef} type="file" accept=".db" disabled={saving} onChange={seleccionarArchivo} />
          </div>
          {restoreMsg && <p className="text-sm text-emerald-600 dark:text-emerald-400">{restoreMsg}</p>}
        </CardContent>
      </Card>

      <Card className="sm:col-span-2">
        <CardHeader><CardTitle className="flex items-center gap-2 text-base"><Database className="size-4" />Backups automáticos guardados en el servidor</CardTitle></CardHeader>
        <CardContent>
          {backups.length === 0 ? (
            <p className="py-4 text-center text-sm text-muted-foreground">Sin backups automáticos todavía. Se generan automáticamente antes de cada restauración.</p>
          ) : (
            <>
              <ul className="divide-y">
                {backups.map((b) => (
                  <li key={b.filename} className="flex items-center justify-between py-2 text-sm">
                    <div>
                      <p className="font-mono font-medium">{b.filename}</p>
                      <p className="text-muted-foreground">{b.mtime} — {b.size_mb} MB</p>
                    </div>
                    <Button asChild size="sm" variant="outline">
                      <a href={`/config/backup-db/${b.filename}`} download><Download />Descargar</a>
                    </Button>
                  </li>
                ))}
              </ul>
              <p className="mt-2 text-xs text-muted-foreground">Se conservan los últimos 10 backups automáticos.</p>
            </>
          )}
        </CardContent>
      </Card>

      <ConfirmDialog
        open={confirmRestore}
        onOpenChange={(o) => !o && cancelarRestauracion()}
        title="¿Estás seguro?"
        description="Se reemplazarán TODOS los datos actuales."
        confirmLabel="Restaurar"
        onConfirm={() => { setConfirmRestore(false); restaurar() }}
      />
    </div>
  )
}

function Field({ label, value, onChange, type = 'text' }: {
  label: string; value: string; onChange: (v: string) => void; type?: string
}) {
  // Los campos secretos (token de MercadoPago, webhook secret, clave SMTP)
  // se declaran con type="password" en sus call sites: el ojito se
  // resuelve acá una sola vez en vez de en cada uno.
  const Campo = type === 'password'
    ? <PasswordInput value={value} onChange={(e) => onChange(e.target.value)} />
    : <Input type={type} value={value} onChange={(e) => onChange(e.target.value)} />
  return (
    <div className="grid gap-1.5">
      <Label>{label}</Label>
      {Campo}
    </div>
  )
}
