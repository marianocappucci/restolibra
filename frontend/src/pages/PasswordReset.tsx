// Shim sobre libra-ui/PasswordReset (mismo patrón que Login).
//
// `basePath: '/api'` y no el default '/auth': Restolibra no monta el router
// de libraauth, tiene sus propios endpoints JSON en `web/api/auth.py` bajo el
// prefijo `/api` (igual que `/api/login`).
//
// Las dos pantallas son públicas: van fuera del guard de sesión en App.tsx,
// porque quien las usa justamente no puede entrar.
import { createForgotPassword, createResetPassword } from 'libra-ui/PasswordReset'

const branding = { productName: 'Restolibra', productInitial: 'R', basePath: '/api' }

export const ForgotPassword = createForgotPassword(branding)
export const ResetPassword = createResetPassword(branding)
