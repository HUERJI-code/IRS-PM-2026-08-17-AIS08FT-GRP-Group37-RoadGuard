import { useEffect, useRef, useState, type FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import { useApi } from '../api/context'
import type { Model, UploadMetadata } from '../api/contracts'
import { ApiError, errorMessage } from '../api/errors'
import { validateImage, uploadMetadata } from './uploadValidation'

type Attempt = { file: File; metadata: UploadMetadata; key: string }

export default function UploadPage() {
  const { api, mode: source } = useApi()
  const navigate = useNavigate()
  const [mode, setMode] = useState<'real' | 'demo'>('real')
  const [file, setFile] = useState<File | null>(null)
  const [latitude, setLatitude] = useState('')
  const [longitude, setLongitude] = useState('')
  const [declared, setDeclared] = useState(false)
  const [scenario, setScenario] = useState('')
  const [catalogue, setCatalogue] =
    useState<Model<'DemoScenarioCatalogue'> | null>(null)
  const [catalogueError, setCatalogueError] = useState('')
  const [catalogueAttempt, setCatalogueAttempt] = useState(0)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [uncertain, setUncertain] = useState(false)
  const operation = useRef<Attempt | null>(null)
  const inFlight = useRef(false)
  const controller = useRef<AbortController | null>(null)
  const mounted = useRef(true)
  const locked = busy || uncertain

  useEffect(() => {
    mounted.current = true
    return () => {
      mounted.current = false
      controller.current?.abort()
    }
  }, [])
  useEffect(() => {
    if (!locked) return
    const warn = (event: BeforeUnloadEvent) => {
      event.preventDefault()
    }
    window.addEventListener('beforeunload', warn)
    return () => window.removeEventListener('beforeunload', warn)
  }, [locked])
  useEffect(() => {
    if (mode !== 'demo') return
    const abort = new AbortController()
    let active = true
    api
      .demoScenarios({ signal: abort.signal })
      .then((value) => {
        if (active) {
          setCatalogue(value)
          setCatalogueError('')
        }
      })
      .catch((err) => {
        if (active) setCatalogueError(errorMessage(err))
      })
    return () => {
      active = false
      abort.abort()
    }
  }, [api, mode, catalogueAttempt])

  async function submit(event: FormEvent) {
    event.preventDefault()
    if (inFlight.current || source !== 'live') return
    inFlight.current = true
    setBusy(true)
    setError('')
    try {
      if (!operation.current) {
        if (!file) throw new Error('Select a road photo.')
        const metadata = uploadMetadata(
          mode,
          latitude,
          longitude,
          declared,
          scenario,
        )
        await validateImage(file)
        if (!mounted.current) return
        operation.current = { file, metadata, key: crypto.randomUUID() }
      }
      const op = operation.current
      controller.current = new AbortController()
      const result = await api.upload(op.file, op.metadata, op.key, {
        signal: controller.current.signal,
        timeoutMs: 120_000,
      })
      if (!mounted.current) return
      setUncertain(false)
      // A successful upload is never repeated when the subsequent detail read fails.
      navigate(`/inspections/${result.inspection_id}`, {
        state: { upload: result },
      })
    } catch (err) {
      if (!mounted.current) return
      setError(
        err instanceof ApiError
          ? errorMessage(err)
          : err instanceof Error
            ? err.message
            : 'Upload failed.',
      )
      const unknown = err instanceof ApiError && err.outcomeUnknown
      setUncertain(unknown)
      if (!unknown) operation.current = null
    } finally {
      inFlight.current = false
      if (mounted.current) setBusy(false)
    }
  }

  return (
    <>
      <div className="page-heading">
        <p className="eyebrow">INSPECTION / 01</p>
        <h1>Upload and results</h1>
        <p className="description">
          Record the photo and its location. Detection results come from the server.
        </p>
      </div>
      {source !== 'live' && (
        <p role="status" className="notice">
          This is a read-only mock snapshot; uploads are disabled. Switch to“Live backend API”; For mock detection, select
          demo mode below.
        </p>
      )}
      <div className="upload-workspace">
      <form onSubmit={(event) => void submit(event)} className="upload-form">
        <fieldset disabled={locked || source !== 'live'}>
          <legend>1. Detection source and photo</legend>
          <label htmlFor="inspection-mode">Detection mode</label>
          <select
            id="inspection-mode"
            value={mode}
            onChange={(event) => {
              setMode(event.target.value as 'real' | 'demo')
              setScenario('')
            }}
          >
            <option value="real">Real image inference (experimental model)</option>
            <option value="demo">Mock detection (fixed synthetic result)</option>
          </select>
          <p className="field-note">
            Real inference follows current business rules. Mock detection does not analyse image contents but still saves an inspection record.
          </p>
          {mode === 'demo' && (
            <div>
              <label htmlFor="scenario">Mock detection scenario</label>
              <select
                id="scenario"
                value={scenario}
                onChange={(event) => setScenario(event.target.value)}
                disabled={!catalogue || !!catalogueError}
              >
                <option value="">Select a scenario</option>
                {catalogue?.scenarios.map((item) => (
                  <option key={item.scenario_id} value={item.scenario_id}>
                    {item.description}
                  </option>
                ))}
              </select>
              {!catalogue && !catalogueError && (
                <p role="status">Loading mock scenarios…</p>
              )}
              {catalogueError && (
                <>
                  <p role="alert">{catalogueError}</p>
                  <button
                    type="button"
                    onClick={() => setCatalogueAttempt((n) => n + 1)}
                  >
                    Retry loading scenarios
                  </button>
                </>
              )}
            </div>
          )}
          <div className="photo-picker">
          <span className="photo-symbol" aria-hidden="true">＋</span>
          <label htmlFor="photo">Road photo</label>
          <input
            id="photo"
            type="file"
            accept="image/jpeg,image/png"
            onChange={(event) => setFile(event.target.files?.[0] ?? null)}
          />
          <p className="field-note">
            One JPEG/PNG, up to 8 MiB and 20 MP. The server-corrected image orientation is displayed after upload.
          </p>
          {file && (
            <p>
              Selected: {file.name} · {(file.size / 1024 / 1024).toFixed(2)} MiB
            </p>
          )}
          </div>
        </fieldset>
        <fieldset disabled={locked || source !== 'live'}>
          <legend>2. Photo location and road declaration</legend>
          <div className="coordinate-fields">
            <div>
              <label htmlFor="latitude">Latitude (latitude)</label>
              <input
                id="latitude"
                inputMode="decimal"
                value={latitude}
                onChange={(event) => setLatitude(event.target.value)}
                placeholder="Enter photo latitude"
              />
            </div>
            <div>
              <label htmlFor="longitude">Longitude (longitude)</label>
              <input
                id="longitude"
                inputMode="decimal"
                value={longitude}
                onChange={(event) => setLongitude(event.target.value)}
                placeholder="Enter photo longitude"
              />
            </div>
          </div>
          <p className="field-note">
            Use WGS84 coordinates. Tasks are limited to Jurong East /
            West. The backend checks the frozen boundary. Enter the photo location using coordinates.
          </p>
          <label className="checkbox-label">
            <input
              type="checkbox"
              checked={declared}
              onChange={(event) => setDeclared(event.target.checked)}
            />
            I declare that this location is an eligible public motor road, excluding expressway mainlines/ramps and private or restricted roads.
          </label>
          <p className="field-note">This is a user declaration. The system has not verified road eligibility.</p>
        </fieldset>
        {error && (
          <p role="alert" className="notice">
            {error}
          </p>
        )}
        {uncertain && (
          <p className="notice">
            Stay here and retry the original request to obtain a definite outcome. The photo, location and request ID are retained. Do not upload again in another page. Leaving this page loses the selected local file.
          </p>
        )}
        <button
          className="button"
          type="submit"
          disabled={busy || source !== 'live'}
        >
          {busy
            ? 'Uploading and detecting…'
            : uncertain
              ? 'Retry original request'
              : 'Upload and detect'}
        </button>
        {busy && (
          <p role="status">
            Processing the photo; allow up to two minutes. Do not resubmit or change data sources.
          </p>
        )}
      </form>
      <aside className="upload-help">
        <p className="eyebrow">BEFORE SUBMISSION</p>
        <h2>One photo, one primary defect</h2>
        <p>Keep the defect and surrounding road surface visible. Avoid obstructions, blur and distant shots.</p>
        <ol className="help-checklist"><li><strong>Select a photo</strong><span>JPEG or PNG, up to 8 MiB.</span></li><li><strong>Enter the actual photo coordinates</strong><span>The service area covers Jurong East and West.</span></li><li><strong>Confirm road declaration</strong><span>Only public motor roads within the area are eligible.</span></li></ol>
        <div className="help-divider" />
        <h3>What happens after submission?</h3>
        <p>The backend returns one primary detection box and reports whether a task was created, review is needed or no damage was detected.</p>
        <p className="field-note">Real inference uses an experimental model; assess results alongside the photo. Mock mode uses fixed results without analysing the photo.</p>
      </aside>
      </div>
    </>
  )
}
