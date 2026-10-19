import { Link } from 'react-router-dom'
import { canOpen, useAuth } from '../auth/context'

const steps = [
  { path: '/inspections/new', title: 'Upload inspection', text: 'Submit a road photo, its Jurong coordinates and a road declaration.', icon: '01' },
  { path: '/reviews', title: 'Review pending', text: 'Check low-confidence photos first; confirm or correct them before task creation.', icon: '02' },
  { path: '/tasks', title: 'Manage tasks', text: 'Check repair tasks. Completed or cancelled tasks are excluded from new plans.', icon: '03' },
  { path: '/routes', title: 'Assign four crews', text: 'Check crew availability and explicitly generate GA and Greedy plans.', icon: '04' },
  { path: '/comparison', title: 'Compare plans', text: 'Compare task coverage and repair schedules from the same recalculation.', icon: '05' },
]

const guidance: Record<string, { title: string; text: string }> = {
  '/inspections/new': { title: 'Start with a road photo', text: 'A real primary detection at 60% confidence or above creates a task automatically. Lower confidence requires review; no detection creates no task. The backend result is authoritative.' },
  '/reviews': { title: 'Check the photo before deciding', text: 'Select a queue record. Confirming or correcting creates a task; rejection retains the inspection without creating a task.' },
  '/tasks': { title: 'Manage the work here; schedule it in four-crew routes', text: 'Select a task to view details or update its status. After adding or changing tasks, check and recalculate the four-crew routes.' },
  '/routes': { title: 'Check crews before generating the schedule', text: 'Check active tasks and all four crews, then recalculate both algorithms. Recalculate explicitly after tasks or crews change.' },
  '/comparison': { title: 'Check task coverage before comparing time', text: 'Enter this page after a recalculation in four-crew routes to verify that both plans belong to the same run. Include unassigned tasks in your assessment.' },
}

export default function WorkflowGuide({ path }: { path: string }) {
  const role = useAuth()?.session?.user.role ?? 'dispatcher'
  const current = guidance[path]
  if (!current) return null
  return (
    <aside className="workflow-guide" aria-label="Current step guide">
      <div className="guide-context"><span className="guide-symbol" aria-hidden="true">↗</span><div><strong>{current.title}</strong><p>{current.text}</p></div></div>
      <details className="workflow-guide-details">
        <summary>View the full workflow</summary>
        <ol className="workflow-steps">
          {steps.map((step) => <li key={step.path} className={path === step.path ? 'current' : undefined}><span>{step.icon}</span><div>{canOpen(role, step.path) ? <Link to={step.path}>{step.title}</Link> : <strong>{step.title}</strong>}<p>{step.text}</p></div></li>)}
        </ol>
        <p className="guide-footnote">Automatically accepted inspections enter the task queue without individual review. The 60% gate is not an accuracy guarantee. Repair durations and crew constraints follow project configuration.</p>
      </details>
    </aside>
  )
}
