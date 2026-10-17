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
          <span className="badge">页面准备中</span>
          <span>业务页面待接入</span>
        </div>
        <div className="empty-state">
          <div className="placeholder-symbol" aria-hidden="true">
            ＋
          </div>
          <h2 id="workspace-status">工作区已建立，业务功能尚未接入</h2>
          <p>本工作区的业务界面尚未接入。可使用上方数据来源检查接口状态。</p>
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
          <h2>查看下一工作区</h2>
          <p>目前可浏览页面结构；导航不会触发上传、审核或重新规划。</p>
        </div>
        <Link className="button" to={next.path}>
          {next.label}
          <span aria-hidden="true"> →</span>
        </Link>
      </section>
    </>
  )
}
