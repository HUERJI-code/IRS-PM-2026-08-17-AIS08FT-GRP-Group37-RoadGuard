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
    <section aria-label="Inspection image and detection box">
      {mode !== 'live' && (
        <p className="notice">Mock placeholder, not a road photo; the box comes from a synthetic example.</p>
      )}
      <div
        className="detection-image"
        style={{
          aspectRatio: `${inspection.image_width} / ${inspection.image_height}`,
        }}
      >
        <img
          src={url}
          alt="Server-normalised inspection photo"
          onError={() => setFailed(true)}
          onLoad={() => setFailed(false)}
        />
        {!failed && detection && (
          <svg
            viewBox={`0 0 ${inspection.image_width} ${inspection.image_height}`}
            preserveAspectRatio="none"
            role="img"
            aria-label={`Single detection box: ${detection.label}`}
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
        <p role="alert">The image could not load. The detection record remains available. Refresh the details to retry.</p>
      )}
      {detection && (
        <div className="detection-caption"><div><span>Primary detection result</span><strong>{labelName}</strong><small>{detection.label}</small></div><div><span>Model confidence</span><strong>{(detection.confidence * 100).toFixed(1)}%</strong><small>Not an accuracy guarantee</small></div></div>
      )}
    </section>
  )
}
