type AppLogoProps = {
  className?: string;
};

export function AppLogo({ className }: AppLogoProps) {
  return (
    <img
      src="/bomfin-logo.png"
      alt="BomFin — Planejamento Financeiro"
      width={360}
      height={360}
      className={className}
    />
  );
}
