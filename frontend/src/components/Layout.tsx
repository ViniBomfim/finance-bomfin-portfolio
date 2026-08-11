import { useCallback, useEffect, useMemo, useRef, useState, type ChangeEvent } from "react";
import { Link, NavLink, Outlet, useLocation, useNavigate } from "react-router-dom";
import { api, setToken } from "../api";
import { useInactivityLogout } from "../hooks/useInactivityLogout";
import { clearSessionActivity } from "../lib/sessionActivity";
import { InactivityWarningDialog } from "./InactivityWarningDialog";
import { NotificationsPanel } from "./NotificationsPanel";
import { PeriodPicker } from "./PeriodPicker";
import { NavIconCard, NavIconExpense, NavIconHome, NavIconMetas, NavIconMore } from "./NavIcons";
import { useAppDialog } from "../context/DialogContext";
import { usePeriod } from "../context/PeriodContext";
import type { UserMe } from "../types";

type NavItemDef = {
  to: string;
  label: string;
  icon: string;
  end?: boolean;
  badge?: "default" | "green" | "amber";
  badgeKey?: "fixed" | "cards" | "goals";
};

const NAV_PRIMARY: NavItemDef[] = [
  { to: "/", label: "Dashboard", icon: "🏠", end: true },
  { to: "/gastos-fixos", label: "Gastos fixos", icon: "📌", badge: "amber", badgeKey: "fixed" },
  { to: "/cartoes", label: "Cartões", icon: "💳", badgeKey: "cards" },
  { to: "/metas", label: "Metas", icon: "🎯", badge: "green", badgeKey: "goals" },
];

const NAV_GESTAO: NavItemDef[] = [
  { to: "/devedores", label: "Devedores", icon: "💸" },
  { to: "/viagens", label: "Viagens", icon: "✈️" },
  { to: "/investimentos", label: "Investimentos", icon: "📈" },
  { to: "/categorias", label: "Categorias", icon: "🏷️" },
];

const PRIMARY_BOTTOM_ROUTES = ["/", "/cartoes", "/gastos-fixos", "/metas"];

const BOTTOM_NAV: { to: string; label: string; end?: boolean; more?: boolean }[] = [
  { to: "/", label: "Início", end: true },
  { to: "/cartoes", label: "Cartões" },
  { to: "/gastos-fixos", label: "Despesas fixas" },
  { to: "/metas", label: "Metas" },
  { to: "#more", label: "Mais", more: true },
];

const BOTTOM_ICONS = [NavIconHome, NavIconCard, NavIconExpense, NavIconMetas, NavIconMore];

const PAGE_TITLES: { match: (path: string) => boolean; title: string }[] = [
  { match: (p) => p === "/", title: "Dashboard" },
  { match: (p) => p.startsWith("/gastos-fixos"), title: "Gastos fixos" },
  { match: (p) => p.startsWith("/cartoes"), title: "Cartões" },
  { match: (p) => p.startsWith("/metas"), title: "Metas" },
  { match: (p) => p.startsWith("/devedores"), title: "Devedores" },
  { match: (p) => p.startsWith("/viagens"), title: "Viagens" },
  { match: (p) => p.startsWith("/investimentos"), title: "Investimentos" },
  { match: (p) => p.startsWith("/categorias"), title: "Categorias" },
  { match: (p) => p.startsWith("/admin"), title: "Administração" },
  { match: (p) => p.startsWith("/dashboard"), title: "Dashboard" },
];

function pageTitleFor(path: string): string {
  return PAGE_TITLES.find((x) => x.match(path))?.title ?? "BomFin";
}

function greetingForHour(h: number): string {
  if (h < 12) return "Bom dia";
  if (h < 18) return "Boa tarde";
  return "Boa noite";
}

function firstName(name: string): string {
  const part = name.trim().split(/\s+/)[0];
  return part || "usuário";
}

function userInitial(name: string): string {
  const n = name.trim();
  if (!n) return "?";
  return n.charAt(0).toUpperCase();
}

type ThemeMode = "light" | "dark";

const THEME_STORAGE_KEY = "bomfin-theme";

function readStoredTheme(): ThemeMode {
  if (typeof window === "undefined") return "dark";
  const raw = localStorage.getItem(THEME_STORAGE_KEY);
  return raw === "light" ? "light" : "dark";
}

function applyTheme(theme: ThemeMode): void {
  document.documentElement.dataset.theme = theme;
  localStorage.setItem(THEME_STORAGE_KEY, theme);
}

async function resizeImageFile(file: File, maxSize = 1024): Promise<File> {
  const bitmap = await createImageBitmap(file);
  const scale = Math.min(1, maxSize / Math.max(bitmap.width, bitmap.height));
  const w = Math.max(1, Math.round(bitmap.width * scale));
  const h = Math.max(1, Math.round(bitmap.height * scale));
  const canvas = document.createElement("canvas");
  canvas.width = w;
  canvas.height = h;
  const ctx = canvas.getContext("2d");
  if (!ctx) {
    bitmap.close();
    return file;
  }
  ctx.imageSmoothingEnabled = true;
  ctx.imageSmoothingQuality = "high";
  ctx.drawImage(bitmap, 0, 0, w, h);
  bitmap.close();
  const blob = await new Promise<Blob | null>((resolve) =>
    canvas.toBlob(resolve, "image/jpeg", 0.95),
  );
  if (!blob) return file;
  const base = file.name.replace(/\.[^.]+$/, "") || "avatar";
  return new File([blob], `${base}.jpg`, { type: "image/jpeg" });
}

export function Layout() {
  const [theme, setTheme] = useState<ThemeMode>(() => {
    const stored = readStoredTheme();
    if (typeof document !== "undefined") {
      document.documentElement.dataset.theme = stored;
    }
    return stored;
  });

  useEffect(() => {
    applyTheme(theme);
  }, [theme]);

  const {
    periods,
    periodId,
    setPeriodId,
    loading,
    error,
    ready,
    monthLabel,
    periodClosed,
    refreshPeriods,
  } = usePeriod();
  const { confirm, alert } = useAppDialog();
  const [periodActionLoading, setPeriodActionLoading] = useState(false);
  const [me, setMe] = useState<UserMe | null>(null);
  const [avatarUrl, setAvatarUrl] = useState<string | null>(null);
  const [avatarBusy, setAvatarBusy] = useState(false);
  const [avatarPreviewOpen, setAvatarPreviewOpen] = useState(false);
  const [navBadges, setNavBadges] = useState<{ fixed?: number; cards?: number; goals?: string }>({});
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [userMenuOpen, setUserMenuOpen] = useState<"sidebar" | "topbar" | null>(null);
  const [toast, setToast] = useState<{ msg: string; icon: string } | null>(null);
  const [notifOpen, setNotifOpen] = useState(false);
  const [notifUnread, setNotifUnread] = useState(0);
  const [inactivityEnabled, setInactivityEnabled] = useState(false);
  const [inactivityMinutes, setInactivityMinutes] = useState<number | null>(null);
  const location = useLocation();
  const navigate = useNavigate();
  const avatarInputRef = useRef<HTMLInputElement>(null);

  const handlePeriodChange = useCallback(
    (id: string) => {
      if (id === periodId) return;
      setPeriodId(id);
      setDrawerOpen(false);
      if (location.pathname !== "/") {
        navigate("/");
      }
    },
    [periodId, setPeriodId, location.pathname, navigate],
  );

  const [compactTopbar, setCompactTopbar] = useState(() =>
    typeof window !== "undefined" ? window.matchMedia("(max-width: 900px)").matches : false,
  );

  const isAdmin = !!me?.is_admin;
  const fullName = me?.name?.trim() || me?.username || "Usuário";
  const initial = userInitial(fullName);
  const pageTitle = pageTitleFor(location.pathname);

  const greeting = useMemo(() => {
    const g = greetingForHour(new Date().getHours());
    return `${g}, ${firstName(fullName)}`;
  }, [fullName]);

  const greetingDate = useMemo(() => {
    if (compactTopbar) {
      return new Date().toLocaleDateString("pt-BR", {
        weekday: "short",
        day: "numeric",
        month: "short",
      });
    }
    return new Date().toLocaleDateString("pt-BR", {
      weekday: "long",
      day: "numeric",
      month: "long",
      year: "numeric",
    });
  }, [compactTopbar]);

  useEffect(() => {
    const mq = window.matchMedia("(max-width: 900px)");
    const onChange = () => setCompactTopbar(mq.matches);
    onChange();
    mq.addEventListener("change", onChange);
    return () => mq.removeEventListener("change", onChange);
  }, []);

  const refreshSessionSettings = useCallback(async () => {
    try {
      const settings = await api.getSessionSettings();
      setInactivityEnabled(settings.inactivity_logout_enabled);
      setInactivityMinutes(settings.inactivity_logout_minutes);
    } catch {
      setInactivityEnabled(true);
      setInactivityMinutes(60);
    }
  }, []);

  useEffect(() => {
    void refreshSessionSettings();
  }, [refreshSessionSettings]);

  const { warningVisible, secondsRemaining, continueSession } = useInactivityLogout(
    inactivityEnabled,
    inactivityMinutes,
    refreshSessionSettings,
  );

  useEffect(() => {
    setDrawerOpen(false);
    setUserMenuOpen(null);
  }, [location.pathname]);

  useEffect(() => {
    document.body.classList.toggle("nav-drawer-open", drawerOpen);
    return () => document.body.classList.remove("nav-drawer-open");
  }, [drawerOpen]);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const user = await api.getMe();
        if (!cancelled) setMe(user);
      } catch {
        if (!cancelled) setMe(null);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    let cancelled = false;
    let pollTimer: ReturnType<typeof setInterval> | null = null;
    const lastGenerateAttemptRef = { current: 0 };
    const GENERATE_COOLDOWN_MS = 5 * 60 * 1000;

    const refreshUnread = async () => {
      try {
        const data = await api.listNotifications();
        if (!cancelled) setNotifUnread(data.total);
      } catch {
        /* ignore */
      }
    };

    const tick = async () => {
      const now = Date.now();
      if (now - lastGenerateAttemptRef.current >= GENERATE_COOLDOWN_MS) {
        lastGenerateAttemptRef.current = now;
        try {
          await api.generateNotifications();
        } catch {
          /* ignore */
        }
      }
      if (!cancelled) await refreshUnread();
    };

    void tick();
    pollTimer = setInterval(() => {
      void tick();
    }, 60_000);

    const onVisibility = () => {
      if (document.visibilityState === "visible") void tick();
    };
    document.addEventListener("visibilitychange", onVisibility);

    return () => {
      cancelled = true;
      if (pollTimer) clearInterval(pollTimer);
      document.removeEventListener("visibilitychange", onVisibility);
    };
  }, []);

  useEffect(() => {
    let revoked: string | null = null;
    let cancelled = false;
    if (!me?.has_avatar) {
      setAvatarUrl((prev) => {
        if (prev) URL.revokeObjectURL(prev);
        return null;
      });
      return;
    }
    (async () => {
      try {
        const blob = await api.fetchMyAvatarBlob();
        if (cancelled) return;
        const url = URL.createObjectURL(blob);
        revoked = url;
        setAvatarUrl((prev) => {
          if (prev) URL.revokeObjectURL(prev);
          return url;
        });
      } catch {
        if (!cancelled) {
          setAvatarUrl((prev) => {
            if (prev) URL.revokeObjectURL(prev);
            return null;
          });
        }
      }
    })();
    return () => {
      cancelled = true;
      if (revoked) URL.revokeObjectURL(revoked);
    };
  }, [me?.has_avatar, me?.updated_at]);

  useEffect(() => {
    if (!periodId || !ready) {
      setNavBadges({});
      return;
    }
    let cancelled = false;
    (async () => {
      try {
        const [summary, user] = await Promise.all([api.dashboardSummary(periodId), api.getMe()]);
        if (cancelled) return;
        setMe(user);
        const meUsage = summary.usage_by_person_cards.find((row) => row.pessoa_id === user.me_spender_id);
        const goals = summary.goal_progress;
        const goalsBadge =
          goals.length > 0
            ? `${Math.round(goals.reduce((acc, goal) => acc + goal.progress_percent, 0) / goals.length)}%`
            : undefined;
        setNavBadges({
          fixed: meUsage?.gastos_fixos.length ?? 0,
          cards: summary.card_totals.length,
          goals: goalsBadge,
        });
      } catch {
        if (!cancelled) setNavBadges({});
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [periodId, ready]);

  useEffect(() => {
    if (!userMenuOpen) return;
    function onDocClick(e: MouseEvent) {
      const target = e.target as Element | null;
      if (target?.closest?.("[data-user-menu]")) return;
      setUserMenuOpen(null);
    }
    document.addEventListener("mousedown", onDocClick);
    return () => document.removeEventListener("mousedown", onDocClick);
  }, [userMenuOpen]);

  useEffect(() => {
    if (!toast) return;
    const t = window.setTimeout(() => setToast(null), 2800);
    return () => window.clearTimeout(t);
  }, [toast]);

  function showToast(msg: string, icon = "🔔") {
    setToast({ msg, icon });
  }

  function toggleTheme() {
    setTheme((t) => (t === "dark" ? "light" : "dark"));
    setUserMenuOpen(null);
  }

  function toggleUserMenu(anchor: "sidebar" | "topbar") {
    setUserMenuOpen((v) => (v === anchor ? null : anchor));
  }

  async function handleAvatarFileChange(e: ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    e.target.value = "";
    if (!file) return;
    setAvatarBusy(true);
    setUserMenuOpen(null);
    try {
      const resized = await resizeImageFile(file);
      const updated = await api.uploadMyAvatar(resized);
      setMe(updated);
      showToast("Foto de perfil atualizada", "📷");
    } catch (err) {
      await alert(err instanceof Error ? err.message : "Não foi possível enviar a foto");
    } finally {
      setAvatarBusy(false);
    }
  }

  async function handleRemoveAvatar() {
    const ok = await confirm({
      title: "Remover foto",
      message: "Remover a foto de perfil?",
      confirmLabel: "Remover",
      danger: true,
    });
    if (!ok) return;
    setAvatarBusy(true);
    setUserMenuOpen(null);
    try {
      const updated = await api.deleteMyAvatar();
      setMe(updated);
      showToast("Foto removida", "📷");
    } catch (err) {
      await alert(err instanceof Error ? err.message : "Não foi possível remover a foto");
    } finally {
      setAvatarBusy(false);
    }
  }

  async function logout() {
    const ok = await confirm({
      title: "Sair",
      message: "Sair da conta?",
      confirmLabel: "Sair",
      danger: true,
    });
    if (!ok) return;
    setToken(null);
    clearSessionActivity();
    window.location.href = "/login";
  }

  async function handleClosePeriod() {
    if (!periodId) return;
    const ok = await confirm({
      title: "Fechar mês",
      message:
        "Fechar este mês? Não será possível alterar receitas, despesas, orçamentos e lançamentos até reabrir o período.",
      confirmLabel: "Fechar mês",
      danger: true,
    });
    if (!ok) return;
    setPeriodActionLoading(true);
    try {
      await api.closePeriod(periodId);
      await refreshPeriods();
    } catch (e) {
      await alert(e instanceof Error ? e.message : "Não foi possível fechar o período");
    } finally {
      setPeriodActionLoading(false);
    }
  }

  async function handleReopenPeriod() {
    if (!periodId) return;
    const ok = await confirm({
      title: "Reabrir mês",
      message: "Reabrir este mês para permitir alterações?",
      confirmLabel: "Reabrir",
    });
    if (!ok) return;
    setPeriodActionLoading(true);
    try {
      await api.reopenPeriod(periodId);
      await refreshPeriods();
    } catch (e) {
      await alert(e instanceof Error ? e.message : "Não foi possível reabrir o período");
    } finally {
      setPeriodActionLoading(false);
    }
  }

  function renderUserAvatar(className: string) {
    return (
      <div className={className} aria-hidden="true">
        {avatarUrl ? <img src={avatarUrl} alt="" /> : initial}
      </div>
    );
  }

  function openAvatarPreview() {
    setUserMenuOpen(null);
    setAvatarPreviewOpen(true);
  }

  function renderUserMenuItems() {
    return (
      <div className="user-dropdown" role="menu">
        <button
          type="button"
          className="user-dropdown-item"
          role="menuitem"
          onClick={openAvatarPreview}
        >
          Ver foto
        </button>
        {me?.has_avatar ? (
          <button
            type="button"
            className="user-dropdown-item"
            role="menuitem"
            disabled={avatarBusy}
            onClick={() => void handleRemoveAvatar()}
          >
            Remover foto
          </button>
        ) : (
          <button
            type="button"
            className="user-dropdown-item"
            role="menuitem"
            disabled={avatarBusy}
            onClick={() => avatarInputRef.current?.click()}
          >
            Colocar foto
          </button>
        )}
        <button
          type="button"
          className="user-dropdown-item"
          role="menuitem"
          onClick={toggleTheme}
        >
          {theme === "dark" ? "Tema claro" : "Tema escuro"}
        </button>
      </div>
    );
  }

  const sidebarNavCls = ({ isActive }: { isActive: boolean }) =>
    isActive ? "sb-nav-item active" : "sb-nav-item";

  const bottomNavCls = ({ isActive }: { isActive: boolean }) =>
    isActive ? "bottom-nav__link bottom-nav__link--active" : "bottom-nav__link";

  function navBadgeText(item: NavItemDef): string | null {
    if (!item.badgeKey) return null;
    if (item.badgeKey === "fixed") {
      const count = navBadges.fixed ?? 0;
      return count > 0 ? String(count) : null;
    }
    if (item.badgeKey === "cards") {
      const count = navBadges.cards ?? 0;
      return count > 0 ? String(count) : null;
    }
    return navBadges.goals ?? null;
  }

  function renderSidebarNavItem(item: NavItemDef) {
    const badgeText = navBadgeText(item);
    return (
      <NavLink key={item.to} to={item.to} end={item.end} className={sidebarNavCls}>
        <span className="sb-nav-icon" aria-hidden="true">
          {item.icon}
        </span>
        <span className="sb-nav-label">{item.label}</span>
        {badgeText && (
          <span className={`sb-nav-badge${item.badge ? ` sb-nav-badge--${item.badge}` : ""}`}>
            {badgeText}
          </span>
        )}
      </NavLink>
    );
  }

  const periodFooter = (
    <>
      {ready && (
        <div className="sb-period-block">
          <div className="sb-period-label">Período ativo</div>
          <div className="sb-period-value">
            <span
              className={`sb-period-dot${periodClosed ? " sb-period-dot--closed" : ""}`}
              aria-hidden="true"
            />
            <PeriodPicker
              periods={periods}
              periodId={periodId}
              onChange={handlePeriodChange}
              monthLabel={monthLabel}
              disabled={loading}
              aria-label="Período ativo"
              className="sb-period-picker"
              triggerClassName="sb-period-select"
            />
          </div>
        </div>
      )}
      <div className={`sb-footer-btns${ready && periodId ? "" : " sb-footer-btns--single"}`}>
        {ready && periodId && (
          periodClosed ? (
            <button
              type="button"
              className="sb-footer-btn sb-footer-btn--neutral"
              disabled={periodActionLoading}
              onClick={handleReopenPeriod}
            >
              ↺ Reabrir
            </button>
          ) : (
            <button
              type="button"
              className="sb-footer-btn sb-footer-btn--neutral"
              disabled={periodActionLoading}
              onClick={handleClosePeriod}
            >
              ⊠ Fechar mês
            </button>
          )
        )}
        <button type="button" className="sb-footer-btn sb-footer-btn--logout" onClick={logout}>
          → Sair
        </button>
      </div>
    </>
  );

  return (
    <div className="layout app-shell">
      <input
        ref={avatarInputRef}
        type="file"
        accept="image/jpeg,image/png,image/webp,image/*"
        hidden
        onChange={handleAvatarFileChange}
      />
      <aside className="side-board side-board--desktop" aria-label="Menu principal">
        <div className="sb-user-block" data-user-menu>
          <button
            type="button"
            className="sb-user-menu-btn"
            aria-label="Menu do perfil"
            aria-expanded={userMenuOpen === "sidebar"}
            aria-haspopup="menu"
            onClick={() => toggleUserMenu("sidebar")}
          >
            {renderUserAvatar("sb-user-av")}
            <span className="sb-user-name-row">
              <span className="sb-user-name">{fullName}</span>
              <span className={`sb-user-arrow${userMenuOpen === "sidebar" ? " sb-user-arrow--open" : ""}`} aria-hidden="true">
                ▾
              </span>
            </span>
          </button>
          {userMenuOpen === "sidebar" ? renderUserMenuItems() : null}
        </div>

        <nav className="sb-nav">
          <div className="sb-nav-group-label">Principal</div>
          {NAV_PRIMARY.map(renderSidebarNavItem)}

          <div className="sb-nav-group-label">Gestão</div>
          {NAV_GESTAO.map(renderSidebarNavItem)}
          {isAdmin && (
            <NavLink to="/admin/gestao" className={sidebarNavCls}>
              <span className="sb-nav-icon" aria-hidden="true">
                ⚙️
              </span>
              <span className="sb-nav-label">Administração</span>
            </NavLink>
          )}
        </nav>

        <div className="sb-footer">{periodFooter}</div>
      </aside>

      {drawerOpen && (
        <button
          type="button"
          className="nav-drawer-backdrop"
          aria-label="Fechar menu"
          onClick={() => setDrawerOpen(false)}
        />
      )}

      <aside
        className={`nav-drawer${drawerOpen ? " nav-drawer--open" : ""}`}
        aria-hidden={!drawerOpen}
        aria-label="Menu completo"
      >
        <div className="nav-drawer__header">
          <button
            type="button"
            className="nav-drawer__close"
            onClick={() => setDrawerOpen(false)}
            aria-label="Fechar"
          >
            ✕
          </button>
        </div>

        <nav className="nav-drawer__nav">
          <div className="sb-nav-group-label">Principal</div>
          {NAV_PRIMARY.map(renderSidebarNavItem)}

          <div className="sb-nav-group-label">Gestão</div>
          {NAV_GESTAO.map(renderSidebarNavItem)}
          {isAdmin && (
            <NavLink to="/admin/gestao" className={sidebarNavCls}>
              <span className="sb-nav-icon" aria-hidden="true">
                ⚙️
              </span>
              <span className="sb-nav-label">Administração</span>
            </NavLink>
          )}
        </nav>

        {ready && (
          <div className="nav-drawer__period">
            <div className="sb-period-label">Período ativo</div>
            <div className="nav-drawer__period-pill">
              <span
                className={`sb-period-dot${periodClosed ? " sb-period-dot--closed" : ""}`}
                aria-hidden="true"
              />
              <PeriodPicker
                periods={periods}
                periodId={periodId}
                onChange={handlePeriodChange}
                monthLabel={monthLabel}
                disabled={loading}
                aria-label="Período ativo"
                className="nav-drawer__period-picker"
                triggerClassName="nav-drawer__period-select"
              />
            </div>
          </div>
        )}

        <div className={`nav-drawer__footer sb-footer-btns${ready && periodId ? "" : " sb-footer-btns--single"}`}>
          {ready && periodId && (
            periodClosed ? (
              <button
                type="button"
                className="sb-footer-btn sb-footer-btn--neutral"
                disabled={periodActionLoading}
                onClick={handleReopenPeriod}
              >
                ↺ Reabrir
              </button>
            ) : (
              <button
                type="button"
                className="sb-footer-btn sb-footer-btn--neutral"
                disabled={periodActionLoading}
                onClick={handleClosePeriod}
              >
                ⊠ Fechar mês
              </button>
            )
          )}
          <button type="button" className="sb-footer-btn sb-footer-btn--logout" onClick={logout}>
            → Sair
          </button>
        </div>
      </aside>

      <section className="content-shell">
        <header className="topbar">
          <div className="topbar-accent" aria-hidden="true" />
          <div className="topbar-left">
            <div className="topbar-mobile-user" data-user-menu>
              <button
                type="button"
                className="topbar-mobile-user-btn"
                aria-label="Menu do perfil"
                aria-expanded={userMenuOpen === "topbar"}
                aria-haspopup="menu"
                onClick={() => toggleUserMenu("topbar")}
              >
                {renderUserAvatar("topbar-user-av topbar-mobile-avatar")}
              </button>
              {userMenuOpen === "topbar" ? renderUserMenuItems() : null}
            </div>
            <div className="topbar-greeting">
              <div className="topbar-greeting-main">{greeting}</div>
              <div className="topbar-greeting-sub">{greetingDate}</div>
            </div>
          </div>

          <div className="topbar-center-title">{pageTitle}</div>

          <div className="topbar-right">
            <button
              type="button"
              className="notif-btn"
              aria-label="Notificações"
              aria-expanded={notifOpen}
              onClick={() => setNotifOpen((v) => !v)}
            >
              <span aria-hidden="true">🔔</span>
              {notifUnread > 0 && (
                <span className="notif-badge">{notifUnread > 99 ? "99+" : notifUnread}</span>
              )}
            </button>
          </div>
        </header>

        {error && (
          <p className="error layout-banner" role="alert">
            {error}
          </p>
        )}
        {ready && periodClosed && (
          <p className="layout-banner period-closed-banner" role="status">
            Este mês está <strong>fechado</strong>. Alterações em receitas, despesas, orçamentos e cartão estão
            bloqueadas até você reabrir o período.
          </p>
        )}
        <main className="main-outlet">
          {loading && !ready ? (
            <p className="muted padded">Carregando períodos…</p>
          ) : (
            <Outlet />
          )}
        </main>
      </section>

      <nav className="bottom-nav" aria-label="Navegação rápida">
        <div className="bottom-nav__dock">
          {BOTTOM_NAV.map((item, idx) => {
            const Icon = BOTTOM_ICONS[idx];
            if (item.more) {
              const moreActive =
                drawerOpen ||
                !PRIMARY_BOTTOM_ROUTES.some((p) =>
                  p === "/" ? location.pathname === "/" : location.pathname.startsWith(p),
                );
              return (
                <button
                  key={item.label}
                  type="button"
                  className={`bottom-nav__link${moreActive ? " bottom-nav__link--active" : ""}`}
                  onClick={() => setDrawerOpen(true)}
                  aria-expanded={drawerOpen}
                  aria-label={item.label}
                >
                  <Icon />
                  <span>{item.label}</span>
                </button>
              );
            }
            return (
              <NavLink
                key={item.to}
                to={item.to}
                end={item.end}
                className={bottomNavCls}
                aria-label={item.label}
              >
                <Icon />
                <span>{item.label}</span>
              </NavLink>
            );
          })}
        </div>
      </nav>

      {toast && (
        <div className="shell-toast-wrap" aria-live="polite">
          <div className="shell-toast">
            <span aria-hidden="true">{toast.icon}</span>
            <span>{toast.msg}</span>
          </div>
        </div>
      )}

      {warningVisible && (
        <InactivityWarningDialog
          secondsRemaining={secondsRemaining}
          onContinue={continueSession}
        />
      )}

      <NotificationsPanel
        open={notifOpen}
        onClose={() => setNotifOpen(false)}
        unreadTotal={notifUnread}
        onUnreadChange={setNotifUnread}
      />

      {avatarPreviewOpen && (
        <div
          className="avatar-preview-overlay"
          role="dialog"
          aria-modal="true"
          aria-label="Foto de perfil"
          onClick={() => setAvatarPreviewOpen(false)}
        >
          <div
            className="avatar-preview-card"
            onClick={(e) => e.stopPropagation()}
          >
            <button
              type="button"
              className="avatar-preview-close"
              aria-label="Fechar"
              onClick={() => setAvatarPreviewOpen(false)}
            >
              ✕
            </button>
            <div className="avatar-preview-media">
              {avatarUrl ? (
                <img src={avatarUrl} alt={fullName} />
              ) : (
                <span className="avatar-preview-initial" aria-hidden="true">
                  {initial}
                </span>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
