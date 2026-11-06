export function KpiSkeleton() {
  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
      {Array.from({ length: 4 }).map((_, i) => (
        <div key={i} className="rounded-2xl bg-[#121824] border border-[rgba(255,255,255,0.08)] p-5 animate-pulse">
          <div className="h-3 bg-[rgba(255,255,255,0.06)] rounded w-1/2 mb-4" />
          <div className="h-8 bg-[rgba(255,255,255,0.06)] rounded w-1/3 mb-2" />
          <div className="h-3 bg-[rgba(255,255,255,0.04)] rounded w-2/3" />
        </div>
      ))}
    </div>
  )
}
