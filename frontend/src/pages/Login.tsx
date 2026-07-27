import { createLogin } from 'libra-ui/Login'
import { useAuth } from '../context/AuthContext'
import type { User } from '../api'

export const Login = createLogin<User>({
  productName: 'Restolibra',
  productInitial: 'R',
  redirectTo: '/dashboard',
  useAuth,
  formatError: (err) => err.detail,
  // El rol mozo solo opera Salon/Pedidos -- cae directo ahi, nunca en el
  // dashboard (mismo comportamiento que el Jinja2 viejo, ver web/app.py:
  // login_post / wiki/entities/restolibra.md).
  onLoginSuccess: (user) => (user.role === 'mozo' ? '/salon' : '/dashboard'),
})
