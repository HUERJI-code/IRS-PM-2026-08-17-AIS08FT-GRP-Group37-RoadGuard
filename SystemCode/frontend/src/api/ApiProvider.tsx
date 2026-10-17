import { useMemo, useState, type ReactNode } from 'react'
import { createApiClient, resolveImageUrl } from './client'
import { ApiContext, type DataMode } from './context'
import { createMockTransport } from './mock/transport'

export default function ApiProvider({ children }: { children: ReactNode }) {
  const [mode, setMode] = useState<DataMode>('live')
  const value = useMemo(
    () => ({
      mode,
      setMode,
      api:
        mode === 'live'
          ? createApiClient()
          : createApiClient(createMockTransport(mode)),
      imageUrl: (path: string) => {
        const checked = resolveImageUrl(path)
        return mode === 'live' ? checked : '/mock/inspection.png'
      },
    }),
    [mode],
  )
  // Switching source remounts consumers, aborting requests and removing old data.
  return (
    <ApiContext.Provider value={value}>
      <div key={mode}>{children}</div>
    </ApiContext.Provider>
  )
}
