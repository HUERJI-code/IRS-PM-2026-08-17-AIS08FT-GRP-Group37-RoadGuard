import { useState } from 'react'
import { useApi } from '../api/context'
import type { Model } from '../api/contracts'
import { ErrorState } from './RequestState'
import labels from '../../../model/label_schema.json'

export default function InspectionImage({
  inspection,
}: {
  inspection: Model<'InspectionResponse'>
}) {
  const { imageUrl, mode } = useApi()
  const [failed, setFailed] = useState(false)
  let url: string
  try {
    url = imageUrl(inspection.image_url)
  } catch (error) {
    return <ErrorState error={error} />
  }
  const detection = inspection.detections[0]
  const labelName = labels.classes.find((item) => item.label_key === detection?.label)?.display_name_zh ?? detection?.label
  return (
    <section aria-label="巡检图片与检测框">
      {mode !== 'live' && (
        <p className="notice">模拟占位图，非道路照片；框来自合成样例。</p>
      )}
      <div
        className="detection-image"
        style={{
          aspectRatio: `${inspection.image_width} / ${inspection.image_height}`,
        }}
      >
        <img
          src={url}
          alt="服务端归一化的巡检照片"
          onError={() => setFailed(true)}
          onLoad={() => setFailed(false)}
        />
        {!failed && detection && (
          <svg
            viewBox={`0 0 ${inspection.image_width} ${inspection.image_height}`}
            preserveAspectRatio="none"
            role="img"
            aria-label={`唯一检测框：${detection.label}`}
          >
            <rect
              x={detection.bbox_xyxy[0]}
              y={detection.bbox_xyxy[1]}
              width={detection.bbox_xyxy[2] - detection.bbox_xyxy[0]}
              height={detection.bbox_xyxy[3] - detection.bbox_xyxy[1]}
              fill="none"
              stroke="#ffb300"
              strokeWidth="3"
              vectorEffect="non-scaling-stroke"
            />
          </svg>
        )}
      </div>
      {failed && (
        <p role="alert">图片读取失败，检测记录仍可查看。可刷新详情重试。</p>
      )}
      {detection && (
        <div className="detection-caption"><div><span>主要检测结果</span><strong>{labelName}</strong><small>{detection.label}</small></div><div><span>模型置信度</span><strong>{(detection.confidence * 100).toFixed(1)}%</strong><small>不代表准确率保证</small></div></div>
      )}
    </section>
  )
}
