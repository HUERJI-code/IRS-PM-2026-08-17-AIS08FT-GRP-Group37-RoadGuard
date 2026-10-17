import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, expect, it, vi } from 'vitest'
import App from '../App'

afterEach(() => vi.unstubAllGlobals())
it('switches explicitly between live, normal, empty and failed sources without network fallback', async () => {
  const network = vi.fn().mockResolvedValue(
    new Response(
      JSON.stringify({
        status: 'ok',
        database: 'ok',
        api_version: 'v1',
        input_revision: 5,
      }),
    ),
  )
  vi.stubGlobal('fetch', network)
  const user = userEvent.setup()
  render(
    <MemoryRouter>
      <App />
    </MemoryRouter>,
  )
  await screen.findByText(/已连接 · 输入版本 5/)
  await user.selectOptions(
    screen.getByRole('combobox', { name: '数据来源' }),
    'normal',
  )
  expect(await screen.findByText(/模拟连接状态/)).toBeVisible()
  expect(screen.getByText(/固定只读快照/)).toBeVisible()
  await user.click(screen.getByText('检查数据接入'))
  await user.click(screen.getByRole('button', { name: '读取当前来源' }))
  expect(await screen.findByText(/活动任务：1/)).toBeVisible()
  await user.selectOptions(
    screen.getByRole('combobox', { name: '数据来源' }),
    'empty',
  )
  expect(screen.queryByText(/活动任务：1/)).not.toBeInTheDocument()
  await user.click(screen.getByText('检查数据接入'))
  await user.click(screen.getByRole('button', { name: '读取当前来源' }))
  expect(await screen.findByText('当前列表为空。')).toBeVisible()
  expect(screen.getByText(/空任务列表与没有方案是不同状态/)).toBeVisible()
  await user.selectOptions(
    screen.getByRole('combobox', { name: '数据来源' }),
    'failure',
  )
  await user.click(screen.getByText('检查数据接入'))
  await user.click(screen.getByRole('button', { name: '读取当前来源' }))
  expect(
    await within(screen.getByRole('region', { name: '数据来源' })).findByRole(
      'alert',
    ),
  ).toHaveTextContent('数据库暂不可用')
  expect(network).toHaveBeenCalledTimes(2)
})
