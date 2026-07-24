import { useNavigate } from 'react-router-dom'
import { zodResolver } from '@hookform/resolvers/zod'
import { useForm } from 'react-hook-form'
import { z } from 'zod'
import { api, ApiError } from '../api'
import { useAuth } from '../context/AuthContext'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import {
  Form, FormControl, FormField, FormItem, FormLabel, FormMessage,
} from '@/components/ui/form'
import { Check, UserCircle } from 'lucide-react'
import { useState } from 'react'

const passwordSchema = z.object({
  new_password: z.string().min(6, 'Mínimo 6 caracteres'),
})
type PasswordFormValues = z.infer<typeof passwordSchema>

// Portado tal cual desde Contalibra (frontend/src/pages/MiCuenta.tsx).
// Autoservicio de cambio de contraseña -- PUT /api/usuarios/me/password,
// gateado en el backend solo por sesion activa (get_current_user_json),
// NO por require_admin_json, a diferencia del resto del modulo Usuarios --
// ver web/api/usuarios.py (me_router) y web/app.py. Corrige un bug
// preexistente del router HTML viejo (web/routers/usuarios.py), donde
// GET/POST /mi-cuenta estaba gateado con require_admin en vez de
// require_auth: un usuario no-admin (incluido el rol 'mozo', exclusivo de
// Restolibra) nunca pudo cambiar su propia contraseña por esa ruta. El link
// vive en el footer del sidebar (ver components/Layout.tsx), visible para
// cualquier usuario logueado sin importar su rol.
export function MiCuenta() {
  const { user } = useAuth()
  const navigate = useNavigate()
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [saved, setSaved] = useState(false)

  const form = useForm<PasswordFormValues>({
    resolver: zodResolver(passwordSchema),
    defaultValues: { new_password: '' },
  })

  function describeError(err: unknown): string {
    if (err instanceof ApiError) return err.detail
    return 'Error de conexión.'
  }

  async function handleSubmit(values: PasswordFormValues) {
    setSaving(true)
    setError(null)
    setSaved(false)
    try {
      await api.put('/api/usuarios/me/password', { new_password: values.new_password })
      form.reset({ new_password: '' })
      setSaved(true)
    } catch (err) {
      setError(describeError(err))
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="grid gap-4">
      <h2 className="flex items-center gap-2 text-lg font-semibold"><UserCircle className="size-5" />Mi cuenta</h2>

      <Card className="max-w-md">
        <CardHeader><CardTitle className="text-base">Datos de la cuenta</CardTitle></CardHeader>
        <CardContent className="grid gap-1.5 text-sm">
          <p><span className="text-muted-foreground">Usuario:</span> {user?.username}</p>
          <p><span className="text-muted-foreground">Nombre:</span> {user?.nombre}</p>
          <p className="capitalize"><span className="text-muted-foreground">Rol:</span> {user?.role}</p>
        </CardContent>
      </Card>

      <Card className="max-w-md">
        <CardHeader><CardTitle className="text-base">Cambiar contraseña</CardTitle></CardHeader>
        <CardContent>
          {error && <p className="mb-3 text-sm text-destructive">{error}</p>}
          {saved && <p className="mb-3 text-sm text-emerald-600 dark:text-emerald-400">Contraseña actualizada.</p>}
          <Form {...form}>
            <form className="grid gap-4" onSubmit={form.handleSubmit(handleSubmit)}>
              <FormField control={form.control} name="new_password" render={({ field }) => (
                <FormItem>
                  <FormLabel>Nueva contraseña</FormLabel>
                  <FormControl><Input type="password" {...field} placeholder="Mínimo 6 caracteres" autoFocus /></FormControl>
                  <FormMessage />
                </FormItem>
              )} />
              <div className="flex gap-2">
                <Button type="submit" disabled={saving}><Check />{saving ? 'Guardando…' : 'Cambiar contraseña'}</Button>
                <Button type="button" variant="outline" onClick={() => navigate('/dashboard')}>Volver</Button>
              </div>
            </form>
          </Form>
        </CardContent>
      </Card>
    </div>
  )
}
