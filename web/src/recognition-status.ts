// OPS-03 / AI-01: saved service status, never a connectivity or accuracy probe.
export type ServiceStatus = {
  name: string
  model: string
  kind: 'local' | 'external' | 'unconfigured'
  configured: boolean
  status: 'ready' | 'configured' | 'unavailable' | 'unconfigured'
  status_message: string
  endpoint_configured: boolean | null
  timeout_seconds: number | null
  cpu_threads: number | null
  automatic_fallback: false
  calibrated_confidence: false
}

export type ProviderStatus = ServiceStatus & {
  recent_requests: number
  recent_errors: number
  p95_latency_ms: number | null
  statistics_scope: 'current_provider_and_model'
  statistics_limit: 1000
}

export function providerLabel(name: string): string {
  switch (name) {
    case 'db1404-local':
      return '本地 DB1404 模型（CPU）'
    case 'volcengine-ark':
      return '火山引擎 Ark（外部服务）'
    case 'unconfigured':
      return '未启用'
    default:
      return '未知提供方'
  }
}

export function serviceStatusLabel(status: ServiceStatus['status']): string {
  switch (status) {
    case 'ready':
      return '本地模型已加载'
    case 'configured':
      return '已配置（未探测连接）'
    case 'unavailable':
      return '服务不可用'
    case 'unconfigured':
      return '未启用'
  }
}

export function serviceStatusType(status: ServiceStatus['status']) {
  if (status === 'ready') return 'success'
  if (status === 'configured') return 'info'
  return 'warning'
}

// Missing legacy fields must not imply successful local loading or reuse an Ark model.
export function recognitionStatus(value: Partial<ServiceStatus>): ServiceStatus {
  const name = value.name ?? 'unconfigured'
  const kind = name === 'db1404-local' ? 'local' : name === 'volcengine-ark' ? 'external' : 'unconfigured'
  const status =
    kind === 'unconfigured'
      ? 'unconfigured'
      : kind === 'local'
        ? value.status === 'ready'
          ? 'ready'
          : 'unavailable'
        : value.configured && value.status !== 'unavailable'
          ? 'configured'
          : 'unavailable'
  return {
    name,
    kind,
    model: kind === 'external' || (kind === 'local' && value.kind === 'local') ? (value.model ?? '') : '',
    configured: value.configured ?? false,
    status,
    status_message:
      value.status_message ||
      (kind === 'local'
        ? '未提供本地模型加载状态，请刷新或联系管理员确认。'
        : kind === 'external'
          ? status === 'configured'
            ? '外部服务配置完整，尚未探测连接。'
            : '外部服务配置不完整或暂不可用。'
          : '识别服务未启用，当前无法提供识别结果。'),
    endpoint_configured: kind === 'external' ? (value.endpoint_configured ?? null) : null,
    timeout_seconds: kind === 'unconfigured' ? null : (value.timeout_seconds ?? null),
    cpu_threads: kind === 'local' ? (value.cpu_threads ?? null) : null,
    automatic_fallback: false,
    calibrated_confidence: false,
  }
}
