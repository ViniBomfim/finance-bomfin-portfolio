import { useEffect, useId, useLayoutEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";

type DatePickerProps = {
  id?: string;
  value: string;
  onChange: (isoDate: string) => void;
  required?: boolean;
  className?: string;
  inputClassName?: string;
  "aria-label"?: string;
  allowClear?: boolean;
};

const WEEKDAYS = ["Dom", "Seg", "Ter", "Qua", "Qui", "Sex", "Sáb"];
const MONTHS = [
  "Janeiro",
  "Fevereiro",
  "Março",
  "Abril",
  "Maio",
  "Junho",
  "Julho",
  "Agosto",
  "Setembro",
  "Outubro",
  "Novembro",
  "Dezembro",
];

function parseIso(iso: string): Date | null {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(iso)) return null;
  const [y, m, d] = iso.split("-").map(Number);
  const date = new Date(y, m - 1, d);
  if (date.getFullYear() !== y || date.getMonth() !== m - 1 || date.getDate() !== d) return null;
  return date;
}

function toIso(date: Date): string {
  const y = date.getFullYear();
  const m = String(date.getMonth() + 1).padStart(2, "0");
  const d = String(date.getDate()).padStart(2, "0");
  return `${y}-${m}-${d}`;
}

function formatDisplay(iso: string): string {
  const date = parseIso(iso);
  if (!date) return "Selecionar data";
  return date.toLocaleDateString("pt-BR");
}

function sameDay(a: Date, b: Date): boolean {
  return a.getFullYear() === b.getFullYear() && a.getMonth() === b.getMonth() && a.getDate() === b.getDate();
}

function buildCalendarDays(viewYear: number, viewMonth: number): Date[] {
  const first = new Date(viewYear, viewMonth, 1);
  const startPad = first.getDay();
  const daysInMonth = new Date(viewYear, viewMonth + 1, 0).getDate();
  const cells: Date[] = [];
  for (let i = startPad - 1; i >= 0; i--) {
    cells.push(new Date(viewYear, viewMonth, -i));
  }
  for (let day = 1; day <= daysInMonth; day++) {
    cells.push(new Date(viewYear, viewMonth, day));
  }
  while (cells.length % 7 !== 0 || cells.length < 42) {
    const last = cells[cells.length - 1];
    cells.push(new Date(last.getFullYear(), last.getMonth(), last.getDate() + 1));
  }
  return cells;
}

export function DatePicker({
  id,
  value,
  onChange,
  required,
  className = "",
  inputClassName = "",
  "aria-label": ariaLabel,
  allowClear = false,
}: DatePickerProps) {
  const autoId = useId();
  const triggerId = id ?? autoId;
  const panelId = `${triggerId}-panel`;
  const rootRef = useRef<HTMLDivElement>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const panelRef = useRef<HTMLDivElement>(null);
  const [open, setOpen] = useState(false);
  const [coords, setCoords] = useState<{ top: number; left: number; width: number } | null>(null);

  const selected = parseIso(value);
  const today = new Date();
  const initialView = selected ?? today;
  const [viewYear, setViewYear] = useState(initialView.getFullYear());
  const [viewMonth, setViewMonth] = useState(initialView.getMonth());

  useEffect(() => {
    if (!open) {
      setCoords(null);
      return;
    }
    const base = parseIso(value) ?? new Date();
    setViewYear(base.getFullYear());
    setViewMonth(base.getMonth());
  }, [open, value]);

  useLayoutEffect(() => {
    if (!open || !triggerRef.current) return;

    function place() {
      const trigger = triggerRef.current;
      const panel = panelRef.current;
      if (!trigger) return;
      const rect = trigger.getBoundingClientRect();
      const panelHeight = panel?.offsetHeight ?? 320;
      const panelWidth = Math.max(rect.width, 288);
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
  }, [open, viewMonth, viewYear]);

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

  function shiftMonth(delta: number) {
    const next = new Date(viewYear, viewMonth + delta, 1);
    setViewYear(next.getFullYear());
    setViewMonth(next.getMonth());
  }

  function pick(date: Date) {
    onChange(toIso(date));
    setOpen(false);
  }

  const days = buildCalendarDays(viewYear, viewMonth);

  return (
    <div className={`fm-datepicker ${className}`.trim()} ref={rootRef}>
      <input
        type="text"
        className="fm-datepicker__sr"
        value={value}
        required={required}
        readOnly
        tabIndex={-1}
        aria-hidden="true"
      />
      <button
        ref={triggerRef}
        id={triggerId}
        type="button"
        className={`fm-datepicker__trigger ${inputClassName}`.trim()}
        aria-label={ariaLabel ?? "Selecionar data"}
        aria-haspopup="dialog"
        aria-expanded={open}
        aria-controls={open ? panelId : undefined}
        onClick={() => setOpen((prev) => !prev)}
      >
        <span className={`fm-datepicker__value${selected ? "" : " fm-datepicker__value--empty"}`}>
          {formatDisplay(value)}
        </span>
        <span className="fm-datepicker__icon" aria-hidden="true">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none">
            <path
              d="M8 2v3M16 2v3M3.5 9h17M5 5h14a2 2 0 012 2v13a2 2 0 01-2 2H5a2 2 0 01-2-2V7a2 2 0 012-2z"
              stroke="currentColor"
              strokeWidth="1.6"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>
        </span>
      </button>

      {open &&
        createPortal(
          <div
            ref={panelRef}
            id={panelId}
            className={`fm-datepicker__panel${coords ? "" : " fm-datepicker__panel--measure"}`}
            role="dialog"
            aria-label="Calendário"
            style={
              coords
                ? { top: coords.top, left: coords.left, width: coords.width }
                : { top: 0, left: 0, visibility: "hidden" }
            }
          >
            <div className="fm-datepicker__header">
              <button
                type="button"
                className="fm-datepicker__nav"
                onClick={() => shiftMonth(-1)}
                aria-label="Mês anterior"
              >
                ‹
              </button>
              <div className="fm-datepicker__month">
                {MONTHS[viewMonth]} {viewYear}
              </div>
              <button
                type="button"
                className="fm-datepicker__nav"
                onClick={() => shiftMonth(1)}
                aria-label="Próximo mês"
              >
                ›
              </button>
            </div>

            <div className="fm-datepicker__weekdays" aria-hidden="true">
              {WEEKDAYS.map((day) => (
                <span key={day}>{day}</span>
              ))}
            </div>

            <div className="fm-datepicker__grid" role="grid">
              {days.map((date) => {
                const inMonth = date.getMonth() === viewMonth;
                const isSelected = selected ? sameDay(date, selected) : false;
                const isToday = sameDay(date, today);
                return (
                  <button
                    key={toIso(date)}
                    type="button"
                    role="gridcell"
                    className={[
                      "fm-datepicker__day",
                      inMonth ? "" : "fm-datepicker__day--muted",
                      isSelected ? "fm-datepicker__day--selected" : "",
                      isToday ? "fm-datepicker__day--today" : "",
                    ]
                      .filter(Boolean)
                      .join(" ")}
                    onClick={() => pick(date)}
                  >
                    {date.getDate()}
                  </button>
                );
              })}
            </div>

            <div className="fm-datepicker__footer">
              {allowClear ? (
                <button
                  type="button"
                  className="fm-datepicker__link"
                  onClick={() => {
                    onChange("");
                    setOpen(false);
                  }}
                >
                  Limpar
                </button>
              ) : (
                <span />
              )}
              <button
                type="button"
                className="fm-datepicker__link fm-datepicker__link--accent"
                onClick={() => pick(new Date())}
              >
                Hoje
              </button>
            </div>
          </div>,
          document.body,
        )}
    </div>
  );
}
