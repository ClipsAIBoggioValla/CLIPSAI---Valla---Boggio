type Props = {
  name?: string | null
  email?: string | null
  avatarUrl?: string | null
  size?: number
  className?: string
}

function getInitials(name?: string | null, email?: string | null): string {
  const src = (name && name.trim()) ? name.trim() : (email ?? '')
  if (!src) return 'U'
  if (name && name.trim()) {
    const parts = name.trim().split(/\s+/).filter(Boolean)
    if (parts.length >= 2) return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase()
    return parts[0].slice(0, 2).toUpperCase()
  }
  return src.slice(0, 2).toUpperCase()
}

import { useState } from 'react'

export default function Avatar({ name, email, avatarUrl, size = 32, className = '' }: Props) {
  const [imgError, setImgError] = useState(false)
  const px = `${size}px`
  const hasAvatar = typeof avatarUrl === 'string' && avatarUrl.trim() !== '' && /^https?:\/\//.test(avatarUrl.trim()) && !imgError
  if (hasAvatar) {
    return (
      <img
        src={avatarUrl!.trim()}
        alt={name ?? email ?? 'avatar'}
        className={`rounded-full object-cover shrink-0 ${className}`}
        style={{ width: px, height: px }}
        onError={() => setImgError(true)}
      />
    )
  }
  const initials = getInitials(name, email)
  return (
    <span
      className={`inline-flex items-center justify-center rounded-full font-extrabold shrink-0 bg-gradient-to-tr from-emerald-500 to-[#B4F105] text-[#080C14] shadow-[0_0_16px_rgba(180,241,5,0.35)] ${className}`}
      style={{ width: px, height: px, fontSize: size * 0.38, border: '1px solid rgba(180,241,5,0.3)' }}
      aria-label={name ?? email ?? 'avatar'}
    >
      {initials}
    </span>
  )
}
