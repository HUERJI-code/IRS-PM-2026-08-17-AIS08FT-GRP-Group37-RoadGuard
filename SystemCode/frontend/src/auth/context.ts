import { createContext, useContext } from 'react'
import type { Model } from '../api/contracts'

export type AuthState = {
  session: Model<'SessionResponse'> | null
  invalidate: () => void
  logout: () => Promise<void>
}
export const AuthContext = createContext<AuthState | null>(null)
export const useAuth = () => useContext(AuthContext)
export const roleNames = { inspector: '巡查员', crew: '施工队', dispatcher: '中央调度员' }
export const homeFor = (role: Model<'Account'>['role']) => role === 'inspector' ? '/inspections/new' : role === 'crew' ? '/crew' : '/tasks'
export const canOpen = (role: Model<'Account'>['role'], path: string) => role === 'inspector'
  ? path === '/inspections/new'
  : role === 'crew' ? path === '/crew' : !['/inspections/new', '/crew'].includes(path)
