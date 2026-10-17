import Ajv2020 from 'ajv/dist/2020'
import addFormats from 'ajv-formats'
import spec from './generated/openapi.json'
import type { components } from './generated/schema'
import { ApiError } from './errors'

export type Schemas = components['schemas']
export type Model<K extends keyof Schemas> = Schemas[K]
export type UploadMetadata = {
  latitude: number
  longitude: number
  road_type: 'public_motor_road'
} & (
  { mode: 'real'; scenario_id?: never } | { mode: 'demo'; scenario_id: string }
)

// Validate the same JSON Schema exported by FastAPI, without coercing strings,
// inserting defaults or dropping unknown fields. Domain rules remain server-owned.
const validator = new Ajv2020({ strict: false, allErrors: false })
addFormats(validator)
validator.addSchema({ $id: 'roadguard', components: spec.components })

export function parseModel<K extends keyof Schemas>(
  name: K,
  value: unknown,
): Model<K> {
  const validate = validator.getSchema(`roadguard#/components/schemas/${name}`)
  if (!validate || !validate(value)) {
    throw new ApiError(
      'contract_mismatch',
      '服务返回格式不符合当前接口约定。',
      0,
      'contract',
    )
  }
  return value as Model<K>
}
