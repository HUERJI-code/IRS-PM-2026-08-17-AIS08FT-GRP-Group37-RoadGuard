import { errorMessage } from '../api/errors'

export function LoadingState() {
  return <p role="status">正在读取数据…</p>
}
export function EmptyState({
  message = '当前列表为空。',
}: {
  message?: string
}) {
  return <p role="status">{message}</p>
}
export function NoPlanState() {
  return <p role="status">尚未生成路线方案。空任务列表与没有方案是不同状态。</p>
}
export function ErrorState({ error }: { error: unknown }) {
  return <p role="alert">{errorMessage(error)}</p>
}
