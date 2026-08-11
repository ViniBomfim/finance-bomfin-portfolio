import { useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import { createPortal } from "react-dom";
import type { Period } from "../types";

type PeriodPickerProps = {
  periods: Period[];
  periodId: string;
  onChange: (id: string) => void;
  monthLabel: (mes: number, ano: number) => string;
  disabled?: boolean;
  className?: string;
  triggerClassName?: string;
  "aria-label"?: string;
  capitalizeLabel?: boolean;
};

const MONTH_SHORT = [
  "Jan",
  "Fev",
  "Mar",
  "Abr",
  "Mai",
  "Jun",
  "Jul",
  "Ago",
  "Set",
  "Out",
  "Nov",
  "Dez",
];

function capitalizePeriodLabel(label: string) {
  if (!label) return label;
  return label.charAt(0).toUpperCase() + label.slice(1);
}

export function PeriodPicker({
  periods,
  periodId,
  onChange,
  monthLabel,
  disabled,
  className = "",
  triggerClassName = "",
  "aria-label": ariaLabel = "Período financeiro",
  capitalizeLabel = false,
}: PeriodPickerProps) {
  const rootRef = useRef<HTMLDivElement>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const panelRef = useRef<HTMLDivElement>(null);
  const [open, setOpen] = useState(false);
  const [coords, setCoords] = useState<{ top: number; left: number; width: number } | null>(null);

  const current = useMemo(
    () => periods.find((p) => p.id === periodId) ?? null,
    [periods, periodId],
  );

  const years = useMemo(() => {
    const set = new Set(periods.map((p) => p.ano));
    return [...set].sort((a, b) => a - b);
  }, [periods]);

  const [viewYear, setViewYear] = useState(() => current?.ano ?? years[years.length - 1] ?? new Date().getFullYear());

  useEffect(() => {
    if (!open) {
      setCoords(null);
      return;
    }
    if (current) setViewYear(current.ano);
  }, [open, current]);

  const periodsByMonth = useMemo(() => {
    const map = new Map<number, Period>();
    for (const p of periods) {
      if (p.ano === viewYear) map.set(p.mes, p);
    }
    return map;
  }, [periods, viewYear]);

  const triggerText = current
    ? (() => {
        const label = monthLabel(current.mes, current.ano);
        const text = capitalizeLabel ? capitalizePeriodLabel(label) : label;
        return current.status === "closed" ? `${text} (fechado)` : text;
      })()
    : "Selecionar período";

  useLayoutEffect(() => {
    if (!open || !triggerRef.current) return;

    function place() {
      const trigger = triggerRef.current;
      const panel = panelRef.current;
      if (!trigger) return;
      const rect = trigger.getBoundingClientRect();
      const panelHeight = panel?.offsetHeight ?? 280;
      const panelWidth = Math.max(rect.width, 280);
      const gap = 8;
      const spaceBelow = window.innerHeight - rect.bottom;
      const openUp = spaceBelow < panelHeight + gap && rect.top > spaceBelow;
      const top = openUp ? rect.top - panelHeight - gap : rect.bottom + gap;
      let left = rect.left;
      if (left + panelWidth > window.innerWidth - 12) {
        left = Math.max(12, window.innerWidth - panelWidth - 12);
      }
      setCoords({ top: Math.max(8, top), left, width: panelWidth });
    }

    place();
    window.addEventListener("resize", place);
    window.addEventListener("scroll", place, true);
    return () => {
      window.removeEventListener("resize", place);
      window.removeEventListener("scroll", place, true);
    };
  }, [open, viewYear]);

  useEffect(() => {
    if (!open) return;

    function onPointerDown(event: MouseEvent) {
      const target = event.target as Node;
      if (rootRef.current?.contains(target) || panelRef.current?.contains(target)) return;
      setOpen(false);
    }

    function onKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") setOpen(false);
    }

    document.addEventListener("mousedown", onPointerDown);
    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("mousedown", onPointerDown);
      document.removeEventListener("keydown", onKeyDown);
    };
  }, [open]);

  function goYear(delta: number) {
    if (years.length === 0) return;
    const idx = years.indexOf(viewYear);
    const nextIdx = idx < 0 ? years.length - 1 : Math.min(years.length - 1, Math.max(0, idx + delta));
    setViewYear(years[nextIdx]);
  }

  const canPrevYear = years.length > 0 && viewYear > years[0];
  const canNextYear = years.length > 0 && viewYear < years[years.length - 1];

  return (
    <div className={`fm-period-picker ${className}`.trim()} ref={rootRef}>
      <button
        ref={triggerRef}
        type="button"
        className={`fm-period-picker__trigger ${triggerClassName}`.trim()}
        aria-label={ariaLabel}
        aria-haspopup="dialog"
        aria-expanded={open}
        disabled={disabled || periods.length === 0}
        onClick={() => setOpen((prev) => !prev)}
      >
        <span className="fm-period-picker__trigger-text">{triggerText}</span>
        <span className="fm-period-picker__chevron" aria-hidden="true">
          ▾
        </span>
      </button>

      {open &&
        createPortal(
          <div
            ref={panelRef}
            className={`fm-period-picker__panel${coords ? "" : " fm-period-picker__panel--measure"}`}
            role="dialog"
            aria-label="Selecionar período"
            style={
              coords
                ? { top: coords.top, left: coords.left, width: coords.width }
                : { top: 0, left: 0, visibility: "hidden" }
            }
          >
            <div className="fm-period-picker__header">
              <button
                type="button"
                className="fm-period-picker__nav"
                onClick={() => goYear(-1)}
                disabled={!canPrevYear}
                aria-label="Ano anterior"
              >
                ‹
              </button>
              <div className="fm-period-picker__year">{viewYear}</div>
              <button
                type="button"
                className="fm-period-picker__nav"
                onClick={() => goYear(1)}
                disabled={!canNextYear}
                aria-label="Próximo ano"
              >
                ›
              </button>
            </div>

            <div className="fm-period-picker__grid" role="listbox" aria-label={`Meses de ${viewYear}`}>
              {MONTH_SHORT.map((label, idx) => {
                const mes = idx + 1;
                const period = periodsByMonth.get(mes);
                const isSelected = period?.id === periodId;
                const isClosed = period?.status === "closed";
                const disabledMonth = !period;
                return (
                  <button
                    key={`${viewYear}-${mes}`}
                    type="button"
                    role="option"
                    aria-selected={isSelected}
                    disabled={disabledMonth}
                    className={[
                      "fm-period-picker__month",
                      isSelected ? "fm-period-picker__month--selected" : "",
                      isClosed ? "fm-period-picker__month--closed" : "",
                      disabledMonth ? "fm-period-picker__month--disabled" : "",
                    ]
                      .filter(Boolean)
                      .join(" ")}
                    onClick={() => {
                      if (!period) return;
                      onChange(period.id);
                      setOpen(false);
                    }}
                    title={
                      period
                        ? `${capitalizePeriodLabel(monthLabel(period.mes, period.ano))}${
                            isClosed ? " (fechado)" : ""
                          }`
                        : "Período indisponível"
                    }
                  >
                    <span className="fm-period-picker__month-label">{label}</span>
                    {isClosed && <span className="fm-period-picker__month-badge">Fechado</span>}
                  </button>
                );
              })}
            </div>
          </div>,
          document.body,
        )}
    </div>
  );
}
