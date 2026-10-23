import { useState } from 'react'
import { createBatch } from '../api'
import type { Donor, ItemType } from '../types'

interface BatchFormProps {
  donors: Donor[]
  refresh: () => Promise<void>
}

const itemTypes: ItemType[] = ['cooked_meal', 'raw_ration_kit', 'infant_formula', 'short_life_medicine']

function label(value: string): string {
  return value.replace(/_/g, ' ').replace(/\b\w/g, (letter) => letter.toUpperCase())
}

function notify(message: string, tone: 'success' | 'error'): void {
  window.dispatchEvent(new CustomEvent('freshrelay:toast', { detail: { message, tone } }))
}

export function BatchForm({ donors, refresh }: BatchFormProps): JSX.Element {
  const [donorId, setDonorId] = useState(donors[0]?.id || '')
  const [itemType, setItemType] = useState<ItemType>('cooked_meal')
  const [totalQty, setTotalQty] = useState('')
  const [expiresInMinutes, setExpiresInMinutes] = useState('')
  const [errors, setErrors] = useState<Record<string, string>>({})
  const [submitting, setSubmitting] = useState(false)

  const submit = async (event: React.FormEvent<HTMLFormElement>): Promise<void> => {
    event.preventDefault()
    const nextErrors: Record<string, string> = {}
    const quantity = Number(totalQty)
    const expiry = Number(expiresInMinutes)
    if (!donorId) nextErrors.donorId = 'Select a donor.'
    if (!Number.isInteger(quantity) || quantity <= 0) nextErrors.totalQty = 'Enter a whole quantity above zero.'
    if (!Number.isInteger(expiry) || expiry <= 0) nextErrors.expiresInMinutes = 'Enter minutes above zero.'
    setErrors(nextErrors)
    if (Object.keys(nextErrors).length > 0) return

    setSubmitting(true)
    try {
      await createBatch({ donorId, itemType, totalQty: quantity, expiresInMinutes: expiry })
      await refresh()
      notify('Batch created successfully.', 'success')
      setTotalQty('')
      setExpiresInMinutes('')
    } catch (error) {
      notify(error instanceof Error ? error.message : 'Batch creation failed.', 'error')
    } finally {
      setSubmitting(false)
    }
  }

  return <form className="batch-form" onSubmit={(event) => void submit(event)}>
    <div className="batch-form__heading"><div><p className="eyebrow">NEW ALLOCATION</p><h3>Create batch</h3></div></div>
    <label>Donor
      <select value={donorId} onChange={(event) => setDonorId(event.target.value)} aria-invalid={Boolean(errors.donorId)}>
        <option value="">Select donor</option>
        {donors.map((donor) => <option value={donor.id} key={donor.id}>{donor.name}</option>)}
      </select>
      {errors.donorId && <small className="field-error">{errors.donorId}</small>}
    </label>
    <label>Item type
      <select value={itemType} onChange={(event) => setItemType(event.target.value as ItemType)}>
        {itemTypes.map((type) => <option value={type} key={type}>{label(type)}</option>)}
      </select>
    </label>
    <div className="form-row">
      <label>Quantity
        <input type="number" min="1" step="1" value={totalQty} onChange={(event) => setTotalQty(event.target.value)} placeholder="180" aria-invalid={Boolean(errors.totalQty)} />
        {errors.totalQty && <small className="field-error">{errors.totalQty}</small>}
      </label>
      <label>Expires in
        <div className="input-suffix"><input type="number" min="1" step="1" value={expiresInMinutes} onChange={(event) => setExpiresInMinutes(event.target.value)} placeholder="75" aria-invalid={Boolean(errors.expiresInMinutes)} /><span>min</span></div>
        {errors.expiresInMinutes && <small className="field-error">{errors.expiresInMinutes}</small>}
      </label>
    </div>
    <button className="button button--primary" type="submit" disabled={submitting}>{submitting ? 'Creating…' : 'Create batch'}</button>
  </form>
}
