export * from 'frontend_common/components/clip-library/helpers'

const PUBLISH_STATUS_LABELS: Record<string, string> = {
  PUBLISHING: 'Publicando',
  PUBLISHED: 'Publicado',
  FAILED: 'No se pudo publicar',
}

export function publishStatusLabel(status: string): string {
  return PUBLISH_STATUS_LABELS[status] ?? 'Actualizando'
}
