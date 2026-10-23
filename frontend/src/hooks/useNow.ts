import { useEffect, useState } from 'react'

export function useNow(clockNow: string | undefined): string {
  const [now, setNow] = useState(clockNow || new Date(0).toISOString())

  useEffect(() => {
    if (!clockNow) return
    const syncAt = Date.now()
    setNow(clockNow)
    const interval = window.setInterval(() => {
      const elapsedSeconds = (Date.now() - syncAt) / 1000
      setNow(new Date(new Date(clockNow).getTime() + elapsedSeconds * 1000).toISOString())
    }, 250)
    return () => window.clearInterval(interval)
  }, [clockNow])

  return now
}
