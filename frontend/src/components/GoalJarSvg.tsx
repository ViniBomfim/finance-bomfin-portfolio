type GoalJarVariant = "short" | "medium" | "long" | "overdue";

type GoalJarSvgProps = {
  progress: number;
  id: string;
  variant?: GoalJarVariant;
};

const JAR_TOP = 22;
const JAR_BOTTOM = 76;
const JAR_HEIGHT = JAR_BOTTOM - JAR_TOP;

const LIQUID: Record<GoalJarVariant, { top: string; bottom: string; wave: string }> = {
  short: { top: "#34d399", bottom: "#16a34a", wave: "#34d399" },
  medium: { top: "#fbbf24", bottom: "#d97706", wave: "#fbbf24" },
  long: { top: "#a78bfa", bottom: "#7c3aed", wave: "#a78bfa" },
  overdue: { top: "#f87171", bottom: "#dc2626", wave: "#f87171" },
};

export function GoalJarSvg({ progress, id, variant = "short" }: GoalJarSvgProps) {
  const clipId = `jar-clip-${id}`;
  const gradId = `liquid-grad-${id}`;
  const shineId = `shine-${id}`;
  const pct = Math.max(0, Math.min(100, progress));
  const fillHeight = (pct / 100) * JAR_HEIGHT;
  const fillY = JAR_BOTTOM - fillHeight;
  const colors = LIQUID[variant];
  const waveY = fillY;
  const showLiquid = pct > 0;
  const showNotes = pct >= 12;

  return (
    <svg width="62" height="80" viewBox="0 0 62 80" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
      <defs>
        <clipPath id={clipId}>
          <path d="M10 22 Q10 18 14 18 L48 18 Q52 18 52 22 L52 68 Q52 76 44 76 L18 76 Q10 76 10 68 Z" />
        </clipPath>
        <linearGradient id={gradId} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={colors.top} />
          <stop offset="100%" stopColor={colors.bottom} />
        </linearGradient>
        <linearGradient id={shineId} x1="0" y1="0" x2="1" y2="0">
          <stop offset="0%" stopColor="white" stopOpacity="0.08" />
          <stop offset="40%" stopColor="white" stopOpacity="0.18" />
          <stop offset="100%" stopColor="white" stopOpacity="0.02" />
        </linearGradient>
      </defs>

      <rect x="8" y="10" width="46" height="10" rx="5" fill="var(--surface2)" stroke="var(--border2)" strokeWidth="1" />
      <rect x="13" y="12" width="36" height="6" rx="3" fill="var(--chrome-2)" />

      <path
        d="M10 22 Q10 18 14 18 L48 18 Q52 18 52 22 L52 68 Q52 76 44 76 L18 76 Q10 76 10 68 Z"
        fill="var(--surface)"
        stroke="var(--border2)"
        strokeWidth="1.5"
      />

      {showLiquid && (
        <g clipPath={`url(#${clipId})`}>
          <rect
            className="gp-jar-fill"
            x="10"
            y={fillY}
            width="42"
            height={fillHeight}
            fill={`url(#${gradId})`}
          />
          {fillHeight >= 4 && (
            <path
              className="gp-jar-wave"
              d={`M10 ${waveY} Q21 ${waveY - 4} 31 ${waveY} Q41 ${waveY + 4} 52 ${waveY} L52 ${waveY + 3} Q41 ${waveY + 7} 31 ${waveY + 3} Q21 ${waveY - 1} 10 ${waveY + 3} Z`}
              fill={colors.wave}
              opacity="0.6"
            />
          )}
          <rect x="10" y="22" width="42" height="54" fill={`url(#${shineId})`} />
          <circle cx="22" cy="60" r="2" fill="white" opacity="0.15">
            <animate attributeName="cy" values="68;50;68" dur="3s" repeatCount="indefinite" />
            <animate attributeName="opacity" values="0;0.2;0" dur="3s" repeatCount="indefinite" />
          </circle>
          <circle cx="38" cy="65" r="1.5" fill="white" opacity="0.12">
            <animate attributeName="cy" values="72;54;72" dur="2.5s" begin="1s" repeatCount="indefinite" />
            <animate attributeName="opacity" values="0;0.18;0" dur="2.5s" begin="1s" repeatCount="indefinite" />
          </circle>
        </g>
      )}

      <path d="M15 24 L15 68" stroke="rgba(255,255,255,0.06)" strokeWidth="3" strokeLinecap="round" />

      {showNotes && (
        <g clipPath={`url(#${clipId})`}>
          <g transform="translate(31,53) rotate(-8)">
            <rect x="-11" y="-6" width="22" height="12" rx="2" fill="#16a34a" stroke="#15803d" strokeWidth="0.8" />
            <rect x="-9" y="-4" width="18" height="8" rx="1" fill="none" stroke="#bbf7d0" strokeWidth="0.5" opacity="0.4" />
            <circle cx="0" cy="0" r="3" fill="#15803d" opacity="0.5" />
            <text x="0" y="1" textAnchor="middle" dominantBaseline="middle" fontSize="3.5" fill="#bbf7d0" fontFamily="monospace" opacity="0.9">
              $
            </text>
            <animateTransform
              attributeName="transform"
              type="translate"
              additive="sum"
              values="0,0; 0,-2; 0,0"
              dur="3s"
              repeatCount="indefinite"
              calcMode="spline"
              keySplines="0.4 0 0.6 1; 0.4 0 0.6 1"
            />
          </g>
          <g transform="translate(20,60) rotate(12)">
            <rect x="-9" y="-5" width="18" height="10" rx="2" fill="#15803d" stroke="#166534" strokeWidth="0.8" />
            <rect x="-7" y="-3" width="14" height="6" rx="1" fill="none" stroke="#bbf7d0" strokeWidth="0.5" opacity="0.35" />
            <circle cx="0" cy="0" r="2.5" fill="#166534" opacity="0.5" />
            <text x="0" y="1" textAnchor="middle" dominantBaseline="middle" fontSize="3" fill="#bbf7d0" fontFamily="monospace" opacity="0.9">
              $
            </text>
            <animateTransform
              attributeName="transform"
              type="translate"
              additive="sum"
              values="0,0; 0,-1.5; 0,0"
              dur="4s"
              begin="0.8s"
              repeatCount="indefinite"
              calcMode="spline"
              keySplines="0.4 0 0.6 1; 0.4 0 0.6 1"
            />
          </g>
          <g transform="translate(42,57) rotate(-5)">
            <rect x="-8" y="-5" width="16" height="9" rx="2" fill="#1a7a3c" stroke="#15803d" strokeWidth="0.8" />
            <rect x="-6" y="-3" width="12" height="5" rx="1" fill="none" stroke="#bbf7d0" strokeWidth="0.5" opacity="0.3" />
            <circle cx="0" cy="0" r="2" fill="#166534" opacity="0.4" />
            <text x="0" y="0.8" textAnchor="middle" dominantBaseline="middle" fontSize="2.8" fill="#bbf7d0" fontFamily="monospace" opacity="0.8">
              $
            </text>
            <animateTransform
              attributeName="transform"
              type="translate"
              additive="sum"
              values="0,0; 0,-2.5; 0,0"
              dur="3.5s"
              begin="1.5s"
              repeatCount="indefinite"
              calcMode="spline"
              keySplines="0.4 0 0.6 1; 0.4 0 0.6 1"
            />
          </g>
          <rect x="10" y="22" width="42" height="54" fill={`url(#${shineId})`} pointerEvents="none" />
        </g>
      )}
    </svg>
  );
}
