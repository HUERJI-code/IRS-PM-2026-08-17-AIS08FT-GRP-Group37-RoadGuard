import { Link } from 'react-router-dom'
import { canOpen, useAuth } from '../auth/context'

const steps = [
  { path: '/inspections/new', title: '上传巡检', text: '提交道路照片、Jurong 拍摄坐标和道路声明。', icon: '01' },
  { path: '/reviews', title: '处理待审', text: '低置信度先核对照片；确认或纠正后才进入任务。', icon: '02' },
  { path: '/tasks', title: '管理任务', text: '核对维修任务；已完成或取消的任务退出新规划。', icon: '03' },
  { path: '/routes', title: '安排四队', text: '确认队伍可用状态，主动生成 GA 与 Greedy 方案。', icon: '04' },
  { path: '/comparison', title: '比较方案', text: '在同一次重算结果中，比较任务覆盖与维修安排。', icon: '05' },
]

const guidance: Record<string, { title: string; text: string }> = {
  '/inspections/new': { title: '从一张道路照片开始', text: '真实主框置信度达到 60% 时自动建任务；低于阈值进入人工审核，无检测则不建任务。结果以后端为准。' },
  '/reviews': { title: '先看照片，再作出审核决定', text: '从队列选择一条记录。确认或纠正会创建任务；驳回会保留巡检记录，不创建任务。' },
  '/tasks': { title: '这里管理要做什么，四队路线决定怎么安排', text: '选中任务查看详情和修改状态。新增或修改任务后，请前往四队路线核对并重新规划。' },
  '/routes': { title: '先确认队伍，再生成本次安排', text: '检查活动任务和四支工程队，点击重算生成两种算法的方案。任务或队伍变化后需要主动重算。' },
  '/comparison': { title: '先看任务覆盖，再比较时间', text: '从四队路线完成一次重算后进入本页，才能确认两个方案来自同一轮。未分配任务也要一起评估。' },
}

export default function WorkflowGuide({ path }: { path: string }) {
  const role = useAuth()?.session?.user.role ?? 'dispatcher'
  const current = guidance[path]
  if (!current) return null
  return (
    <aside className="workflow-guide" aria-label="当前步骤指引">
      <div className="guide-context"><span className="guide-symbol" aria-hidden="true">↗</span><div><strong>{current.title}</strong><p>{current.text}</p></div></div>
      <details className="workflow-guide-details">
        <summary>查看完整流程</summary>
        <ol className="workflow-steps">
          {steps.map((step) => <li key={step.path} className={path === step.path ? 'current' : undefined}><span>{step.icon}</span><div>{canOpen(role, step.path) ? <Link to={step.path}>{step.title}</Link> : <strong>{step.title}</strong>}<p>{step.text}</p></div></li>)}
        </ol>
        <p className="guide-footnote">自动接受的巡检可直接进入任务，无需逐条人工审核。60% 是分流阈值，不是准确率保证；维修时长和队伍约束依据项目配置。</p>
      </details>
    </aside>
  )
}
