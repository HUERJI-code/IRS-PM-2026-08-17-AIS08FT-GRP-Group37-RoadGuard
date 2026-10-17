import { createContext, useContext } from 'react'
import type { ApiClient } from './client'
import type { MockScenario } from './mock/transport'

export type DataMode = 'live' | MockScenario
export type ApiContextValue = {
  mode: DataMode
  setMode: (mode: DataMode) => void
  api: ApiClient
  imageUrl: (path: string) => string
}
export const ApiContext = createContext<ApiContextValue | null>(null)
export function useApi() {
  const value = useContext(ApiContext)
  if (!value) throw new Error('API provider is required')
  return value
}
