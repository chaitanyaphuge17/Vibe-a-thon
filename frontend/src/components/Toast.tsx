import { useEffect, useState } from 'react'

interface ToastState { message: string; tone: 'info' | 'success' | 'warning' | 'error' }

export function Toast(): JSX.Element | null {
  const [toast, setToast] = useState<ToastState | null>(null)

  useEffect(() => {
    const onToast = (event: Event) => {
      const detail = (event as CustomEvent<ToastState>).detail
      setToast(detail)
      window.setTimeout(() => setToast(null), 3200)
    }
    window.addEventListener('freshrelay:toast', onToast)
    return () => window.removeEventListener('freshrelay:toast', onToast)
  }, [])

  return toast ? <div className={`toast toast--${toast.tone}`} role="status">{toast.message}</div> : null
}
