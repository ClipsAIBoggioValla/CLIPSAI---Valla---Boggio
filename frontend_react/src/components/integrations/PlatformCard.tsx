import { ReactNode } from 'react'

interface PlatformCardProps {
  name: string
  icon: string
  iconWrapClass: string
  connected: boolean
  username: string | null
  description: string
  descriptionLong: string
  endpointHint: string
  loading: boolean
  onConnect: () => void
  connectLabel: string
  connectIcon: string
  connectClass: string
  children?: ReactNode
}

export default function PlatformCard(props: PlatformCardProps) {
  const {
    name, icon, iconWrapClass, connected, username, description, descriptionLong,
    endpointHint, loading, onConnect, connectLabel, connectIcon, connectClass,
  } = props
  return (
    <div className="card-spark">
      <div className="flex items-center gap-3 mb-3">
        <span className={iconWrapClass}><i className={icon} /></span>
        <div>
          <h3 className="font-bold text-[var(--text-primary)]">{name}</h3>
          {connected && username ? (
            <p className="text-xs text-emerald-300">@{username}</p>
          ) : (
            <p className="text-xs text-[var(--text-secondary)]">{description}</p>
          )}
        </div>
        {connected ? (
          <span className="ml-auto inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-bold bg-emerald-500/15 text-emerald-300 border border-emerald-500/20">
            <span className="h-1.5 w-1.5 rounded-full bg-emerald-400" /> Conectado
          </span>
        ) : (
          <span className="ml-auto inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-bold bg-white/5 text-[var(--text-secondary)] border border-[var(--border-subtle)]">No conectado</span>
        )}
      </div>
      <p className="text-sm text-[var(--text-secondary)] mb-4">{descriptionLong}</p>
      <button className={connectClass} disabled={loading} data-testid={`connect-${name.toLowerCase()}-btn`} onClick={onConnect}>
        {loading ? (
          <><span className="h-4 w-4 animate-spin rounded-full border-2 border-white/30 border-t-white" /> Conectando...</>
        ) : (
          <><i className={connectIcon} /> {connectLabel}</>
        )}
      </button>
      <p className="text-xs text-[var(--text-secondary)] mt-2 text-center">{endpointHint}</p>
      {props.children}
    </div>
  )
}
