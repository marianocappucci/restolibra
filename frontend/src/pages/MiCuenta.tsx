import { useNavigate } from 'react-router-dom'
import { zodResolver } from '@hookform/resolvers/zod'
import { useForm } from 'react-hook-form'
import { z } from 'zod'
import { api, ApiError } from '../api'
import { useAuth } from '../context/AuthContext'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import {
  Form, FormControl, FormField, FormItem, FormLabel, FormMessage,
} from '@/components/ui/form'
import { PasswordInput } from 'libra-ui/PasswordInput'
import { Check, UserCircle } from 'lucide-react'
import { useState } from 'react'
import { TituloPantalla } from 'libra-ui/titulo-pantalla'

const passwordSchema = z.object({
  current_password: z.string().min(1, 'Ingresá tu contraseña actual'),
  new_password: z.string().min(6, 'Mínimo 6 caracteres'),
})
type PasswordFormValues = z.infer<typeof passwordSchema>

// Autoservicio de cambio de contraseña. Visible para cualquier usuario
// logueado sin importar su rol (incluido 'mozo', exclusivo de Restolibra) --
// el link vive en el footer del sidebar (ver components/Layout.tsx).
//
// **2026-09-13 (ADR-018, libraauth v0.43.0): dejó de llamar
// `PUT /api/usuarios/me/password`.** Ese endpoint vivía en `me_router`
// (`app/web/api/usuarios.py`), un router aparte que este producto tuvo que
// crear porque el router admin-only común no le servía para un autoservicio
// de "cualquier rol" -- y cambiaba la contraseña SIN pedir la actual. La
// contraparte del motor, `POST /api/change-password`
// (`build_json_api_auth_router(prefix="/api")`, ya montado en
// `app/web/api/auth.py`), YA es autoservicio para cualquier rol sin
// necesidad de un router propio, y sí pide la actual -- por eso el
// formulario suma el campo. No se usa el diálogo compartido
// `libra-ui/CambiarPassword`: llama a una ruta hardcodeada `/auth/
// change-password`, y este producto sirve su auth bajo `/api`, no `/auth`.
export function MiCuenta() {
  const { user } = useAuth()
  const navigate = useNavigate()
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [saved, setSaved] = useState(false)

  const form = useForm<PasswordFormValues>({
    resolver: zodResolver(passwordSchema),
    defaultValues: { current_password: '', new_password: '' },
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
      await api.post('/api/change-password', {
        current_password: values.current_password, new_password: values.new_password,
      })
      form.reset({ current_password: '', new_password: '' })
      setSaved(true)
    } catch (err) {
      setError(describeError(err))
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="grid gap-4">
      <TituloPantalla icono={UserCircle}>Mi cuenta</TituloPantalla>

      <Card className="max-w-md">
        <CardHeader><CardTitle className="text-base">Datos de la cuenta</CardTitle></CardHeader>
        <CardContent className="grid gap-2 text-sm">
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
              <FormField control={form.control} name="current_password" render={({ field }) => (
                <FormItem>
                  <FormLabel>Contraseña actual</FormLabel>
                  <FormControl><PasswordInput {...field} autoFocus /></FormControl>
                  <FormMessage />
                </FormItem>
              )} />
              <FormField control={form.control} name="new_password" render={({ field }) => (
                <FormItem>
                  <FormLabel>Nueva contraseña</FormLabel>
                  <FormControl><PasswordInput {...field} placeholder="Mínimo 6 caracteres" /></FormControl>
                  <FormMessage />
                </FormItem>
              )} />
              <div className="flex gap-2">
                <Button type="submit" disabled={saving}><Check />{saving ? 'Guardando…' : 'Cambiar contraseña'}</Button>
                <Button type="button" variant="outline" onClick={() => navigate('/salon')}>Volver</Button>
              </div>
            </form>
          </Form>
        </CardContent>
      </Card>
    </div>
  )
}
