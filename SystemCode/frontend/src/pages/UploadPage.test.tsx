import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { ApiContext, type ApiContextValue } from '../api/context'
import { createApiClient, type Transport } from '../api/client'
import { mockFixtures } from '../api/mock/transport'
import UploadPage from './UploadPage'
import InspectionPage from './InspectionPage'
import { uploadMetadata, validateImage } from './uploadValidation'

const records = mockFixtures.normal['/inspections'].items
const accepted = records.find((item) => item.status === 'accepted')!
const pending = records.find((item) => item.status === 'pending_review')!
const none = records.find((item) => item.status === 'no_detection')!
const reply = (value: unknown, status = 200) =>
  new Response(JSON.stringify(value), { status })
let transport: ReturnType<typeof vi.fn<Transport>>
let uploadCount: number
function mount(
  path = '/inspections/new',
  source: ApiContextValue['mode'] = 'live',
) {
  const value: ApiContextValue = {
    mode: source,
    setMode: vi.fn(),
    api: createApiClient(transport),
    imageUrl: (path) => path,
  }
  return render(
    <ApiContext.Provider value={value}>
      <MemoryRouter initialEntries={[path]}>
        <Routes>
          <Route path="/inspections/new" element={<UploadPage />} />
          <Route
            path="/inspections/:inspectionId"
            element={<InspectionPage />}
          />
        </Routes>
      </MemoryRouter>
    </ApiContext.Provider>,
  )
}
async function fill() {
  const user = userEvent.setup()
  await user.upload(
    screen.getByLabelText('道路照片'),
    new File(['image'], 'road.png', { type: 'image/png' }),
  )
  await user.type(screen.getByLabelText('纬度（latitude）'), '1.3405')
  await user.type(screen.getByLabelText('经度（longitude）'), '103.706')
  await user.click(screen.getByRole('checkbox'))
  return user
}
beforeEach(() => {
  uploadCount = 0
  vi.stubGlobal(
    'createImageBitmap',
    vi.fn().mockResolvedValue({ width: 640, height: 480, close: vi.fn() }),
  )
  transport = vi.fn<Transport>().mockImplementation(async (url, init) => {
    if (url === '/api/v1/inspections' && init.method === 'POST') {
      uploadCount++
      return reply(
        {
          inspection_id: accepted.inspection_id,
          status: 'accepted',
          detection: null,
          task_id: accepted.task_id,
        },
        201,
      )
    }
    const value = (mockFixtures.normal as Record<string, unknown>)[
      url.replace('/api/v1', '')
    ]
    return value
      ? reply(value)
      : reply({ code: 'not_found', message: 'not found' }, 404)
  })
})
afterEach(() => vi.unstubAllGlobals())

it('uploads once and displays server detail, single box and associated task', async () => {
  mount()
  const user = await fill()
  await user.click(screen.getByRole('button', { name: '上传并检测' }))
  expect(await screen.findByRole('heading', { name: '关联任务' })).toBeVisible()
  expect(screen.getByRole('img', { name: /唯一检测框/ })).toBeVisible()
  expect(screen.getByAltText('服务端归一化的巡检照片')).toHaveAttribute(
    'src',
    accepted.image_url,
  )
  expect(screen.getByText(/后续读取失败不会重新上传照片/)).toBeVisible()
  expect(uploadCount).toBe(1)
  const req = transport.mock.calls.find(
    ([, init]) => init.method === 'POST',
  )![1]
  expect(
    JSON.parse((req.body as FormData).get('metadata') as string),
  ).not.toHaveProperty('scenario_id')
})

it('reuses the original key and frozen input after a network-unknown upload outcome', async () => {
  const base = transport.getMockImplementation()!
  let first = true
  transport.mockImplementation(async (url, init) => {
    if (init.method === 'POST' && first) {
      first = false
      throw new TypeError('lost response')
    }
    return base(url, init)
  })
  mount()
  const user = await fill()
  await user.click(screen.getByRole('button', { name: '上传并检测' }))
  expect(
    await screen.findByRole('button', { name: '使用原请求重试' }),
  ).toBeEnabled()
  expect(screen.getByLabelText('纬度（latitude）')).toBeDisabled()
  await user.click(screen.getByRole('button', { name: '使用原请求重试' }))
  await screen.findByRole('heading', { name: '关联任务' })
  const uploads = transport.mock.calls.filter(
    ([, init]) => init.method === 'POST',
  )
  expect(uploads).toHaveLength(2)
  expect(uploads[0][1].headers).toEqual(uploads[1][1].headers)
  expect((uploads[0][1].body as FormData).get('metadata')).toEqual(
    (uploads[1][1].body as FormData).get('metadata'),
  )
})

it('retries only GET when detail reading fails after upload success', async () => {
  const base = transport.getMockImplementation()!
  let fail = true
  transport.mockImplementation(async (url, init) => {
    if (url.endsWith(accepted.inspection_id) && fail) {
      fail = false
      return reply(
        { code: 'database_unavailable', message: 'unavailable' },
        503,
      )
    }
    return base(url, init)
  })
  mount()
  const user = await fill()
  await user.click(screen.getByRole('button', { name: '上传并检测' }))
  await user.click(await screen.findByRole('button', { name: '重新读取详情' }))
  await screen.findByRole('heading', { name: '关联任务' })
  expect(uploadCount).toBe(1)
})

it('prevents a rapid duplicate submit while awaiting the upload', async () => {
  transport.mockImplementation(() => new Promise(() => {}))
  mount()
  await fill()
  const button = screen.getByRole('button', { name: '上传并检测' })
  fireEvent.submit(button.closest('form')!)
  fireEvent.submit(button.closest('form')!)
  await waitFor(() => expect(transport).toHaveBeenCalledTimes(1))
  expect(screen.getByRole('button', { name: '正在上传与检测…' })).toBeDisabled()
})

it('selects a backend demo case and sends it only in demo mode', async () => {
  mount()
  const user = await fill()
  await user.selectOptions(screen.getByLabelText('检测模式'), 'demo')
  await screen.findByRole('option', { name: /单个高置信度坑洞/ })
  await user.selectOptions(
    screen.getByLabelText('模拟检测案例'),
    'high_confidence',
  )
  await user.click(screen.getByRole('button', { name: '上传并检测' }))
  await screen.findByRole('heading', { name: '关联任务' })
  const req = transport.mock.calls.find(
    ([, init]) => init.method === 'POST',
  )![1]
  expect(
    JSON.parse((req.body as FormData).get('metadata') as string),
  ).toMatchObject({ mode: 'demo', scenario_id: 'high_confidence' })
})

it.each([
  [pending, '待人工审核'],
  [none, '未检测到损伤'],
])('renders %s without requesting a task', async (record, heading) => {
  mount('/inspections/' + record.inspection_id)
  expect(await screen.findByRole('heading', { name: heading })).toBeVisible()
  expect(
    transport.mock.calls.some(([url]) => url.startsWith('/api/v1/tasks/')),
  ).toBe(false)
  if (record.status === 'no_detection')
    expect(
      screen.queryByRole('img', { name: /唯一检测框/ }),
    ).not.toBeInTheDocument()
})

it('shows image failure while keeping inspection data visible', async () => {
  mount('/inspections/' + pending.inspection_id)
  const img = await screen.findByAltText('服务端归一化的巡检照片')
  fireEvent.error(img)
  expect(screen.getByRole('alert')).toHaveTextContent('图片读取失败')
  expect(screen.getByRole('heading', { name: '待人工审核' })).toBeVisible()
})

it('blocks submission in read-only mock mode', () => {
  mount('/inspections/new', 'normal')
  expect(screen.getByRole('button', { name: '上传并检测' })).toBeDisabled()
  expect(transport).not.toHaveBeenCalled()
})

it('validates image format, size, dimensions and decode errors', async () => {
  await expect(
    validateImage(new File(['x'], 'file.txt', { type: 'text/plain' })),
  ).rejects.toThrow('JPEG')
  await expect(
    validateImage(new File([], 'empty.png', { type: 'image/png' })),
  ).rejects.toThrow('不能为空')
  await expect(
    validateImage(
      new File([new Uint8Array(8 * 1024 * 1024 + 1)], 'large.png', {
        type: 'image/png',
      }),
    ),
  ).rejects.toThrow('8 MiB')
  vi.mocked(createImageBitmap).mockResolvedValueOnce({
    width: 5000,
    height: 5000,
    close: vi.fn(),
  } as unknown as ImageBitmap)
  await expect(
    validateImage(new File(['x'], 'large.png', { type: 'image/png' })),
  ).rejects.toThrow('20 MP')
  vi.mocked(createImageBitmap).mockRejectedValueOnce(new Error('decode'))
  await expect(
    validateImage(new File(['x'], 'broken.png', { type: 'image/png' })),
  ).rejects.toThrow('无法解码')
})

it('requires coordinates, declaration and a demo scenario, preserving real omission', () => {
  expect(() => uploadMetadata('real', '', '103.7', true, '')).toThrow('经度')
  expect(() => uploadMetadata('real', '100', '103.7', true, '')).toThrow('有效')
  expect(() => uploadMetadata('real', '1.34', '103.7', false, '')).toThrow(
    '公共',
  )
  expect(() => uploadMetadata('demo', '1.34', '103.7', true, '')).toThrow(
    '案例',
  )
  expect(
    uploadMetadata('real', '1.34', '103.7', true, 'ignored'),
  ).not.toHaveProperty('scenario_id')
})

it('renders a rejected inspection as a retained record without a task', async () => {
  transport.mockResolvedValue(reply({ ...pending, status: 'rejected' }))
  mount('/inspections/' + pending.inspection_id)
  expect(await screen.findByRole('heading', { name: '已驳回' })).toBeVisible()
  expect(
    screen.queryByRole('heading', { name: '关联任务' }),
  ).not.toBeInTheDocument()
})

it('retains the accepted inspection when fetching its associated task fails', async () => {
  const base = transport.getMockImplementation()!
  transport.mockImplementation(async (url, init) =>
    url.startsWith('/api/v1/tasks/')
      ? reply({ code: 'database_unavailable', message: 'unavailable' }, 503)
      : base(url, init),
  )
  mount('/inspections/' + accepted.inspection_id)
  expect(
    await screen.findByRole('heading', { name: '关联任务读取失败' }),
  ).toBeVisible()
  expect(screen.getByRole('heading', { name: '已接受' })).toBeVisible()
  expect(screen.getByRole('button', { name: '重新读取详情' })).toBeEnabled()
})

it('allows correction after a definite input rejection and creates a new request key', async () => {
  const base = transport.getMockImplementation()!
  let first = true
  transport.mockImplementation(async (url, init) => {
    if (init.method === 'POST' && first) {
      first = false
      return reply({ code: 'outside_service_area', message: 'outside' }, 422)
    }
    return base(url, init)
  })
  mount()
  const user = await fill()
  await user.click(screen.getByRole('button', { name: '上传并检测' }))
  expect(await screen.findByRole('alert')).toHaveTextContent('Jurong')
  expect(screen.getByLabelText('纬度（latitude）')).toBeEnabled()
  await user.clear(screen.getByLabelText('纬度（latitude）'))
  await user.type(screen.getByLabelText('纬度（latitude）'), '1.3406')
  await user.click(screen.getByRole('button', { name: '上传并检测' }))
  await screen.findByRole('heading', { name: '关联任务' })
  const uploads = transport.mock.calls.filter(
    ([, init]) => init.method === 'POST',
  )
  expect(uploads[0][1].headers).not.toEqual(uploads[1][1].headers)
})
