import { statusLabel, statusTone } from '../utils/status'

interface Props { status: string }

export function StatusBadge({ status }: Props): JSX.Element {
  const tone = statusTone(status)
  return <span className={`status-badge status-badge--${tone}`}><span aria-hidden="true">●</span> {statusLabel(status)}</span>
}
