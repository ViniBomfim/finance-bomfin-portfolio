import { useEffect, useRef } from "react";

const DEFAULT_SIZE = 300;
const SPEED = 0.004;
const DEFAULT_SRC = "/bomfin-logo.png";

type AuthLogoShineProps = {
  className?: string;
  /** Canvas and draw size in CSS pixels (internal resolution). */
  size?: number;
  /** Logo image used as destination-in mask. */
  src?: string;
  /** When set, animation only runs while this media query matches. */
  activeMedia?: string;
};

export function AuthLogoShine({
  className,
  size = DEFAULT_SIZE,
  src = DEFAULT_SRC,
  activeMedia,
}: AuthLogoShineProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const motionQuery = window.matchMedia("(prefers-reduced-motion: reduce)");
    const activeQuery = activeMedia ? window.matchMedia(activeMedia) : null;

    let rafId = 0;
    let cancelled = false;
    let phase = 0;
    let logoReady = false;
    let running = false;

    const logoImg = new Image();
    logoImg.src = src;

    const stop = () => {
      running = false;
      cancelAnimationFrame(rafId);
      rafId = 0;
      ctx.clearRect(0, 0, size, size);
    };

    const draw = () => {
      if (cancelled || !running) return;

      ctx.clearRect(0, 0, size, size);

      const cx = (phase % 1.0) * (size * 1.6) - size * 0.3;
      const stripW = size * 0.45;

      const grad = ctx.createLinearGradient(cx - stripW / 2, 0, cx + stripW / 2, 0);
      grad.addColorStop(0, "rgba(255,255,255,0)");
      grad.addColorStop(0.3, "rgba(255,255,255,0.06)");
      grad.addColorStop(0.48, "rgba(255,255,255,0.72)");
      grad.addColorStop(0.5, "rgba(220,235,255,0.9)");
      grad.addColorStop(0.52, "rgba(255,255,255,0.72)");
      grad.addColorStop(0.7, "rgba(255,255,255,0.06)");
      grad.addColorStop(1, "rgba(255,255,255,0)");

      ctx.save();
      ctx.transform(1, 0, -0.28, 1, 0, 0);
      ctx.fillStyle = grad;
      ctx.fillRect(cx - stripW / 2 - 40, -20, stripW + 80, size + 40);
      ctx.restore();

      ctx.globalCompositeOperation = "destination-in";
      ctx.drawImage(logoImg, 0, 0, size, size);
      ctx.globalCompositeOperation = "source-over";

      phase += SPEED;
      if (phase % 1.0 > 0.52) {
        phase += SPEED * 0.05;
      }

      rafId = requestAnimationFrame(draw);
    };

    const sync = () => {
      const mediaOk = activeQuery ? activeQuery.matches : true;
      const shouldRun = mediaOk && !motionQuery.matches && logoReady;
      if (shouldRun && !running) {
        running = true;
        draw();
      } else if (!shouldRun && running) {
        stop();
      }
    };

    logoImg.onload = () => {
      if (cancelled) return;
      logoReady = true;
      sync();
    };
    if (logoImg.complete && logoImg.naturalWidth > 0) {
      logoReady = true;
      sync();
    }

    const onChange = () => sync();
    motionQuery.addEventListener("change", onChange);
    activeQuery?.addEventListener("change", onChange);

    return () => {
      cancelled = true;
      stop();
      motionQuery.removeEventListener("change", onChange);
      activeQuery?.removeEventListener("change", onChange);
    };
  }, [activeMedia, size, src]);

  return (
    <canvas
      ref={canvasRef}
      className={className}
      width={size}
      height={size}
      aria-hidden="true"
    />
  );
}
