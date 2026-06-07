// Reusable styled confirm dialog. Renders nothing unless `open`.
export default function ConfirmModal({
  open,
  title = 'Are you sure?',
  message,
  confirmLabel = 'Confirm',
  cancelLabel = 'Cancel',
  danger = false,
  onConfirm,
  onCancel,
}) {
  if (!open) return null
  return (
    <div className="modal-backdrop" onClick={onCancel}>
      <div className="modal confirm-modal" onClick={(e) => e.stopPropagation()}>
        <h3 className="confirm-title">{title}</h3>
        {message && <p className="confirm-msg">{message}</p>}
        <div className="confirm-actions">
          <button className="btn-cancel" onClick={onCancel}>{cancelLabel}</button>
          <button className={`submit${danger ? ' danger' : ''}`} onClick={onConfirm}>{confirmLabel}</button>
        </div>
      </div>
    </div>
  )
}
