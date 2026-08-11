import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from "react";

export type ConfirmOptions = {
  title?: string;
  message: string;
  confirmLabel?: string;
  cancelLabel?: string;
  danger?: boolean;
};

export type AlertOptions = {
  title?: string;
  message: string;
  okLabel?: string;
};

type DialogState =
  | { kind: "confirm"; options: ConfirmOptions; resolve: (value: boolean) => void }
  | { kind: "alert"; options: AlertOptions; resolve: () => void }
  | null;

function normalizeConfirm(opts: ConfirmOptions | string): ConfirmOptions {
  return typeof opts === "string" ? { message: opts } : opts;
}

function normalizeAlert(opts: AlertOptions | string): AlertOptions {
  return typeof opts === "string" ? { message: opts } : opts;
}

const DialogContext = createContext<{
  confirm: (options: ConfirmOptions | string) => Promise<boolean>;
  alert: (options: AlertOptions | string) => Promise<void>;
} | null>(null);

export function DialogProvider({ children }: { children: ReactNode }) {
  const [dialog, setDialog] = useState<DialogState>(null);

  const confirm = useCallback((opts: ConfirmOptions | string) => {
    const options = normalizeConfirm(opts);
    return new Promise<boolean>((resolve) => {
      setDialog({ kind: "confirm", options, resolve });
    });
  }, []);

  const alert = useCallback((opts: AlertOptions | string) => {
    const options = normalizeAlert(opts);
    return new Promise<void>((resolve) => {
      setDialog({ kind: "alert", options, resolve });
    });
  }, []);

  useEffect(() => {
    if (!dialog) return;
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") {
        if (dialog.kind === "confirm") {
          dialog.resolve(false);
          setDialog(null);
        } else {
          dialog.resolve();
          setDialog(null);
        }
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [dialog]);

  function closeConfirm(ok: boolean) {
    if (dialog?.kind === "confirm") {
      dialog.resolve(ok);
      setDialog(null);
    }
  }

  function closeAlert() {
    if (dialog?.kind === "alert") {
      dialog.resolve();
      setDialog(null);
    }
  }

  const title =
    dialog?.kind === "confirm"
      ? (dialog.options.title ?? "Confirmar")
      : dialog?.kind === "alert"
        ? (dialog.options.title ?? "Aviso")
        : "";

  const message = dialog?.options.message ?? "";

  return (
    <DialogContext.Provider value={{ confirm, alert }}>
      {children}
      {dialog && (
        <div
          className="app-dialog-backdrop"
          role="presentation"
          onClick={() => (dialog.kind === "confirm" ? closeConfirm(false) : closeAlert())}
        >
          <div
            className="app-dialog"
            role="alertdialog"
            aria-modal="true"
            aria-labelledby="app-dialog-title"
            aria-describedby="app-dialog-desc"
            onClick={(e) => e.stopPropagation()}
          >
            <h2 id="app-dialog-title" className="app-dialog__title">
              {title}
            </h2>
            <p id="app-dialog-desc" className="app-dialog__message">
              {message}
            </p>
            <div className="app-dialog__actions">
              {dialog.kind === "confirm" && (
                <button
                  type="button"
                  className="btn btn-ghost app-dialog__btn"
                  onClick={() => closeConfirm(false)}
                >
                  {dialog.options.cancelLabel ?? "Cancelar"}
                </button>
              )}
              <button
                type="button"
                className={`btn app-dialog__btn${dialog.kind === "confirm" && dialog.options.danger ? " btn-danger" : ""}`}
                autoFocus
                onClick={() => (dialog.kind === "confirm" ? closeConfirm(true) : closeAlert())}
              >
                {dialog.kind === "confirm"
                  ? (dialog.options.confirmLabel ?? "Confirmar")
                  : (dialog.options.okLabel ?? "OK")}
              </button>
            </div>
          </div>
        </div>
      )}
    </DialogContext.Provider>
  );
}

export function useAppDialog() {
  const ctx = useContext(DialogContext);
  if (!ctx) {
    throw new Error("useAppDialog deve ser usado dentro de DialogProvider");
  }
  return ctx;
}
