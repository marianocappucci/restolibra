import { createAuthContext } from 'libra-ui/AuthContext'
import { ApiError, type User } from '../api'

export const { AuthProvider, useAuth } = createAuthContext<User>({
  mePath: '/api/me',
  loginPath: '/api/login',
  logoutPath: '/api/logout',
  // Este producto sirve su API bajo `/api`, incluido el router de
  // Terminos. Sin esta linea el gate de libra-ui consultaria `/terminos`,
  // que aca no existe: la consulta fallaria, el gate no bloquearia y el
  // corte del backend se veria como un 403 crudo en la pantalla.
  terminosPath: '/api/terminos',
})

export { ApiError }
