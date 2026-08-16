import { createLogin } from 'libra-ui/Login'
import { LOGO, WORDMARK } from '@/branding'
import { useAuth } from '../context/AuthContext'
import type { User } from '../api'

export const Login = createLogin<User>({
  productName: 'Restolibra',
  productInitial: 'R',
  // El logo y el nombre en Montserrat Bold (libra-ui v0.23.0). `productInitial`
  // sigue arriba porque es el fallback del motor: si el asset no resuelve, la
  // pantalla muestra la inicial en vez de un hueco.
  logo: { src: LOGO, className: 'h-[72px] w-[72px]' },
  wordmarkClassName: `${WORDMARK} text-[22px]`,
  redirectTo: '/dashboard',
  useAuth,
  formatError: (err) => err.detail,
  // Enlace "¿Olvidaste tu contraseña?" -- va de la mano con los endpoints
  // /api/forgot-password y /api/reset-password de web/api/auth.py.
  forgotPasswordPath: '/forgot-password',
  // Boton "Entrar a la demo". El prefijo es /api, no /auth: este producto
  // tiene su propio router (web/api/auth.py) en vez del de libraauth.
  // Declararlo aca NO alcanza para que se muestre: libra-ui consulta
  // GET /api/demo al montar y solo lo pinta si la instancia contesta que es
  // una demo -- en sistema.restolibra.com.ar esa ruta da 404.
  demoPath: '/api/demo',
  // El rol mozo solo opera Salon/Pedidos -- cae directo ahi, nunca en el
  // dashboard (mismo comportamiento que el Jinja2 viejo, ver web/app.py:
  // login_post / wiki/entities/restolibra.md).
  onLoginSuccess: (user) => (user.role === 'mozo' ? '/salon' : '/dashboard'),
})
