import { createAuthContext } from 'libra-ui/AuthContext'
import { ApiError, type User } from '../api'

export const { AuthProvider, useAuth } = createAuthContext<User>({
  mePath: '/api/me',
  loginPath: '/api/login',
  logoutPath: '/api/logout',
})

export { ApiError }
