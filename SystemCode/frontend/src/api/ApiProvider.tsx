import { useMemo, useState, type ReactNode } from 'react'
import { createApiClient, resolveImageUrl } from './client'
import { ApiContext, type DataMode } from './context'
import { createMockTransport } from './mock/transport'
import { useAuth } from '../auth/context'

export default function ApiProvider({ children }: { children: ReactNode }) {
  const auth = useAuth()
  const csrf = auth?.session?.csrf_token
  const invalidate = auth?.invalidate
  const [mode, setMode] = useState<DataMode>('live')
  const value = useMemo(
    () => ({
      mode,
      setMode,
      api:
        mode === 'live'
          ? createApiClient(undefined, 8000, { csrfToken: () => csrf, onUnauthorized: () => invalidate?.() })
          : createApiClient(createMockTransport(mode)),
      imageUrl: (path: string) => {
        const checked = resolveImageUrl(path)
        return mode === 'live' ? checked : '/mock/inspection.png'
      },
    }),
    [mode, csrf, invalidate],
  )
  // Switching source remounts consumers, aborting requests and removing old data.
  return (
    <ApiContext.Provider value={value}>
      <div key={mode}>{children}</div>
    </ApiContext.Provider>
  )
}
