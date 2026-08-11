import { useEffect, useRef, useState, type ReactNode } from "react";

type ChartBoxProps = {
  height?: number;
  className?: string;
  children: (size: { width: number; height: number }) => ReactNode;
};

export function ChartBox({ height = 180, className = "", children }: ChartBoxProps) {
  const ref = useRef<HTMLDivElement>(null);
  const [size, setSize] = useState({ width: 0, height });

  useEffect(() => {
    const el = ref.current;
    if (!el) return;

    const update = () => {
      const width = Math.floor(el.getBoundingClientRect().width);
      if (width > 0) setSize({ width, height });
    };

    update();
    const ro = new ResizeObserver(() => update());
    ro.observe(el);
    return () => ro.disconnect();
  }, [height]);

  return (
    <div
      ref={ref}
      className={`chart-box${className ? ` ${className}` : ""}`}
      style={{ minHeight: height }}
    >
      {size.width > 0 ? children(size) : null}
    </div>
  );
}
