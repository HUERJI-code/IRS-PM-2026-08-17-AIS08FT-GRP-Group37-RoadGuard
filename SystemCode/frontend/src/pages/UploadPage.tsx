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
        if (!file) throw new Error('请选择一张道路照片。')
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
            : '上传失败。',
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
        <p className="eyebrow">巡检 / 01</p>
        <h1>上传与结果</h1>
        <p className="description">
          记录照片与拍摄位置，检测结果以服务端返回为准。
        </p>
      </div>
      {source !== 'live' && (
        <p role="status" className="notice">
          当前为只读模拟快照，不能上传。请切换到“实时后端接口”；模拟检测请在下方选择
          demo 模式。
        </p>
      )}
      <div className="upload-workspace">
      <form onSubmit={(event) => void submit(event)} className="upload-form">
        <fieldset disabled={locked || source !== 'live'}>
          <legend>1. 检测来源与照片</legend>
          <label htmlFor="inspection-mode">检测模式</label>
          <select
            id="inspection-mode"
            value={mode}
            onChange={(event) => {
              setMode(event.target.value as 'real' | 'demo')
              setScenario('')
            }}
          >
            <option value="real">真实图片推理（实验模型）</option>
            <option value="demo">模拟检测（固定合成结果）</option>
          </select>
          <p className="field-note">
            真实推理按当前业务规则处理；模拟检测不分析图片内容，也会保存巡检记录。
          </p>
          {mode === 'demo' && (
            <div>
              <label htmlFor="scenario">模拟检测案例</label>
              <select
                id="scenario"
                value={scenario}
                onChange={(event) => setScenario(event.target.value)}
                disabled={!catalogue || !!catalogueError}
              >
                <option value="">请选择案例</option>
                {catalogue?.scenarios.map((item) => (
                  <option key={item.scenario_id} value={item.scenario_id}>
                    {item.description}
                  </option>
                ))}
              </select>
              {!catalogue && !catalogueError && (
                <p role="status">正在读取模拟案例…</p>
              )}
              {catalogueError && (
                <>
                  <p role="alert">{catalogueError}</p>
                  <button
                    type="button"
                    onClick={() => setCatalogueAttempt((n) => n + 1)}
                  >
                    重试读取案例
                  </button>
                </>
              )}
            </div>
          )}
          <div className="photo-picker">
          <span className="photo-symbol" aria-hidden="true">＋</span>
          <label htmlFor="photo">道路照片</label>
          <input
            id="photo"
            type="file"
            accept="image/jpeg,image/png"
            onChange={(event) => setFile(event.target.files?.[0] ?? null)}
          />
          <p className="field-note">
            一张 JPEG/PNG，最多 8 MiB、20 MP。上传后展示后端校正方向的图片。
          </p>
          {file && (
            <p>
              已选：{file.name} · {(file.size / 1024 / 1024).toFixed(2)} MiB
            </p>
          )}
          </div>
        </fieldset>
        <fieldset disabled={locked || source !== 'live'}>
          <legend>2. 拍摄位置与道路声明</legend>
          <div className="coordinate-fields">
            <div>
              <label htmlFor="latitude">纬度（latitude）</label>
              <input
                id="latitude"
                inputMode="decimal"
                value={latitude}
                onChange={(event) => setLatitude(event.target.value)}
                placeholder="填写拍摄纬度"
              />
            </div>
            <div>
              <label htmlFor="longitude">经度（longitude）</label>
              <input
                id="longitude"
                inputMode="decimal"
                value={longitude}
                onChange={(event) => setLongitude(event.target.value)}
                placeholder="填写拍摄经度"
              />
            </div>
          </div>
          <p className="field-note">
            使用 WGS84 坐标。任务限 Jurong East /
            West；后端校验冻结边界。请填写照片拍摄位置，当前使用坐标输入。
          </p>
          <label className="checkbox-label">
            <input
              type="checkbox"
              checked={declared}
              onChange={(event) => setDeclared(event.target.checked)}
            />
            我声明此位置属于允许的公共机动车道路，不是高速公路主线/匝道或私有、受限道路。
          </label>
          <p className="field-note">这是用户声明，不代表系统已核验道路权限。</p>
        </fieldset>
        {error && (
          <p role="alert" className="notice">
            {error}
          </p>
        )}
        {uncertain && (
          <p className="notice">
            请留在此页，使用原请求重试以取得确定结果。原图片、位置与请求标识已保留；不要另开页面重复上传。离开页面后无法恢复所选本地文件。
          </p>
        )}
        <button
          className="button"
          type="submit"
          disabled={busy || source !== 'live'}
        >
          {busy
            ? '正在上传与检测…'
            : uncertain
              ? '使用原请求重试'
              : '上传并检测'}
        </button>
        {busy && (
          <p role="status">
            正在处理照片，最多等待两分钟。请勿重复提交或切换数据来源。
          </p>
        )}
      </form>
      <aside className="upload-help">
        <p className="eyebrow">提交前准备</p>
        <h2>一张照片，一处主要损伤</h2>
        <p>拍摄时让损伤和周边路面都清晰可见，避免遮挡、模糊或距离过远。</p>
        <ol className="help-checklist"><li><strong>选择照片</strong><span>JPEG 或 PNG，最大 8 MiB。</span></li><li><strong>填写实际拍摄坐标</strong><span>服务范围为 Jurong East 与 West。</span></li><li><strong>确认道路声明</strong><span>仅允许范围内的公共机动车道路。</span></li></ol>
        <div className="help-divider" />
        <h3>提交后会发生什么？</h3>
        <p>后端返回一个主要检测框，并告知是已创建任务、需要审核，还是没有检测到损伤。</p>
        <p className="field-note">真实推理使用实验模型，检测结果仍需结合照片判断。模拟模式使用固定结果，不分析照片。</p>
      </aside>
      </div>
    </>
  )
}
