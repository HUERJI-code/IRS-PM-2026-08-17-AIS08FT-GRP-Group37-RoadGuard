import { Link } from 'react-router-dom'

type Props = {
  number: string
  title: string
  description: string
  areas: readonly string[]
  next: { path: string; label: string }
}

export default function WorkspacePage({
  number,
  title,
  description,
  areas,
  next,
}: Props) {
  return (
    <>
      <div className="page-heading">
        <p className="eyebrow">WORKSPACE / {number}</p>
        <h1>{title}</h1>
        <p className="description">{description}</p>
      </div>
      <section className="workspace-panel" aria-labelledby="workspace-status">
        <div className="panel-top">
          <span className="badge">In development</span>
          <span>Assistant service is not connected</span>
        </div>
        <div className="empty-state">
          <div className="placeholder-symbol" aria-hidden="true">
            ＋
          </div>
          <h2 id="workspace-status">Route assistant is not available yet</h2>
          <p>Inspection, review, task and four-crew route workspaces are available. This page does not yet support questions or crew changes.</p>
        </div>
        <div className="planned-areas" aria-label="Planned features">
          {areas.map((area, index) => (
            <div key={area}>
              <span>0{index + 1}</span>
              <p>{area}</p>
            </div>
          ))}
        </div>
      </section>
      <section className="workflow-note">
        <div>
          <p className="eyebrow">WORKFLOW</p>
          <h2>Continue in the available workspaces</h2>
          <p>Start an inspection with a road photo. Navigation does not trigger uploads, reviews or replanning.</p>
        </div>
        <Link className="button" to={next.path}>
          {next.label}
          <span aria-hidden="true"> →</span>
        </Link>
      </section>
    </>
  )
}
