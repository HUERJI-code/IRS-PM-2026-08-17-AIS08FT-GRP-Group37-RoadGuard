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
        <p className="eyebrow">工作区 / {number}</p>
        <h1>{title}</h1>
        <p className="description">{description}</p>
      </div>
      <section className="workspace-panel" aria-labelledby="workspace-status">
        <div className="panel-top">
          <span className="badge">开发中</span>
          <span>助手服务尚未接入</span>
        </div>
        <div className="empty-state">
          <div className="placeholder-symbol" aria-hidden="true">
            ＋
          </div>
          <h2 id="workspace-status">路线助手尚未开放</h2>
          <p>当前可以使用巡检、审核、任务与四队路线；此页面暂不提供问答或队伍调整。</p>
        </div>
        <div className="planned-areas" aria-label="后续功能区域">
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
          <p className="eyebrow">流程衔接</p>
          <h2>继续使用已接入的工作区</h2>
          <p>从道路照片开始完成巡检。页面导航不会触发上传、审核或重新规划。</p>
        </div>
        <Link className="button" to={next.path}>
          {next.label}
          <span aria-hidden="true"> →</span>
        </Link>
      </section>
    </>
  )
}
