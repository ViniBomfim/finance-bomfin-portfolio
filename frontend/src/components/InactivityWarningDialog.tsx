type InactivityWarningDialogProps = {
  secondsRemaining: number;
  onContinue: () => void;
};

export function InactivityWarningDialog({
  secondsRemaining,
  onContinue,
}: InactivityWarningDialogProps) {
  return (
    <div className="app-dialog-backdrop" role="presentation">
      <div
        className="app-dialog"
        role="alertdialog"
        aria-modal="true"
        aria-labelledby="inactivity-dialog-title"
        aria-describedby="inactivity-dialog-desc"
      >
        <h2 id="inactivity-dialog-title" className="app-dialog__title">
          Sessão prestes a expirar
        </h2>
        <p id="inactivity-dialog-desc" className="app-dialog__message">
          Você será desconectado em{" "}
          <strong aria-live="assertive" aria-atomic="true">
            {secondsRemaining}s
          </strong>{" "}
          por inatividade.
        </p>
        <div className="app-dialog__actions">
          <button
            type="button"
            className="btn app-dialog__btn"
            autoFocus
            onClick={onContinue}
          >
            Continuar sessão
          </button>
        </div>
      </div>
    </div>
  );
}
