import { useState } from "react";

type PasswordFieldProps = {
  id: string;
  label: string;
  value: string;
  onChange: (value: string) => void;
  autoComplete?: string;
  required?: boolean;
  minLength?: number;
  disabled?: boolean;
  invalid?: boolean;
  errorId?: string;
  appearance?: "default" | "auth";
};

export function PasswordField({
  id,
  label,
  value,
  onChange,
  autoComplete = "current-password",
  required,
  minLength,
  disabled,
  invalid,
  errorId,
  appearance = "default",
}: PasswordFieldProps) {
  const [visible, setVisible] = useState(false);
  const isAuth = appearance === "auth";

  return (
    <div
      className={
        isAuth
          ? `auth-page__field${invalid ? " auth-page__field--error" : ""}`
          : `field${invalid ? " field--error" : ""}`
      }
    >
      <label className={isAuth ? "auth-page__field-lbl" : undefined} htmlFor={id}>
        {label}
      </label>
      <div className={isAuth ? "auth-page__field-wrap" : "password-field"}>
        <input
          id={id}
          className={isAuth ? "auth-page__field-input" : undefined}
          type={visible ? "text" : "password"}
          autoComplete={autoComplete}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          required={required}
          minLength={minLength}
          disabled={disabled}
          placeholder={isAuth ? "••••••••" : undefined}
          aria-invalid={invalid || undefined}
          aria-describedby={invalid && errorId ? errorId : undefined}
        />
        <button
          type="button"
          className={isAuth ? "auth-page__eye-btn" : "password-field__toggle"}
          onClick={() => setVisible((v) => !v)}
          aria-label={visible ? "Ocultar senha" : "Mostrar senha"}
          aria-pressed={visible}
          disabled={disabled}
          tabIndex={-1}
        >
          {visible ? (
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" aria-hidden>
              <path
                stroke="currentColor"
                strokeWidth="1.5"
                strokeLinecap="round"
                strokeLinejoin="round"
                d="M3.98 8.223A10.477 10.477 0 001.934 12C3.226 16.338 7.244 19.5 12 19.5c.993 0 1.953-.138 2.863-.395M6.228 6.228A10.45 10.45 0 0112 4.5c4.756 0 8.773 3.162 10.065 7.498a10.523 10.523 0 01-4.293 5.774M6.228 6.228L3 3m3.228 3.228l3.65 3.65m7.894 7.894L21 21m-3.228-3.228l-3.65-3.65m0 0a3 3 0 10-4.243-4.243m4.242 4.242L9.88 9.88"
              />
            </svg>
          ) : (
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" aria-hidden>
              <path
                stroke="currentColor"
                strokeWidth="1.5"
                strokeLinecap="round"
                strokeLinejoin="round"
                d="M2.036 12.322a1.012 1.012 0 010-.639C3.423 7.51 7.36 4.5 12 4.5c4.638 0 8.573 3.007 9.963 7.178.07.207.07.431 0 .639C20.577 16.49 16.64 19.5 12 19.5c-4.638 0-8.573-3.007-9.963-7.178z"
              />
              <path
                stroke="currentColor"
                strokeWidth="1.5"
                strokeLinecap="round"
                strokeLinejoin="round"
                d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"
              />
            </svg>
          )}
        </button>
      </div>
    </div>
  );
}
