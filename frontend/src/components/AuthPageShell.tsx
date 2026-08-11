import type { ReactNode } from "react";
import { AppLogo } from "./AppLogo";
import { AuthLogoShine } from "./AuthLogoShine";

type AuthPageShellProps = {
  title: string;
  eyebrow?: string;
  subtitle?: string;
  children: ReactNode;
  footer?: ReactNode;
};

export function AuthPageShell({ title, eyebrow, subtitle, children, footer }: AuthPageShellProps) {
  return (
    <div className="auth-page">
      <div className="auth-page__orb auth-page__orb--1" aria-hidden="true" />
      <div className="auth-page__orb auth-page__orb--2" aria-hidden="true" />
      <div className="auth-page__grid" aria-hidden="true" />

      <aside className="auth-page__brand" aria-label="BomFin">
        <div className="auth-page__logo-wrap">
          <AppLogo className="auth-page__brand-logo" />
          <AuthLogoShine className="auth-page__shine-canvas" activeMedia="(min-width: 900px)" />
        </div>
      </aside>

      <div className="auth-page__right">
        <div className="auth-page__form-card">
          <div className="auth-page__logo-area">
            <div className="auth-page__logo-wrap auth-page__logo-wrap--mobile">
              <AppLogo className="auth-page__mobile-logo" />
              <AuthLogoShine className="auth-page__shine-canvas" activeMedia="(max-width: 899px)" />
            </div>
          </div>
          <div className="auth-page__logo-sep" aria-hidden="true" />
          {eyebrow ? <div className="auth-page__eyebrow">{eyebrow}</div> : null}
          <h1 className="auth-page__title">{title}</h1>
          {subtitle ? <p className="auth-page__subtitle">{subtitle}</p> : null}
          {children}
          {footer}
        </div>
      </div>
    </div>
  );
}
