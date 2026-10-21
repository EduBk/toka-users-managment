const VIEWBOX = '0 0 32 32';

interface BrandMarkProps {
  inverse?: boolean;
  size?: number;
}

export function BrandMark({ inverse = false, size = 32 }: BrandMarkProps) {
  return (
    <svg
      className={inverse ? 'brandmark brandmark--inverse' : 'brandmark'}
      width={size}
      height={size}
      viewBox={VIEWBOX}
      aria-hidden="true"
      focusable="false"
    >
      <path className="brandmark__portal" d="M5 28V15a11 11 0 0 1 22 0v13Z" />
      <rect className="brandmark__cut" x="9.6" y="9" width="12.8" height="3.4" rx="1.7" />
      <rect className="brandmark__cut" x="14.7" y="9" width="2.6" height="19" rx="1.3" />
      <rect className="brandmark__threshold" x="5" y="29.6" width="22" height="2.4" rx="1.2" />
    </svg>
  );
}

interface BrandProps extends BrandMarkProps {
  withWordmark?: boolean;
}

export function Brand({ inverse = false, size = 32, withWordmark = true }: BrandProps) {
  return (
    <span className={inverse ? 'brand brand--inverse' : 'brand'}>
      <BrandMark inverse={inverse} size={size} />
      {withWordmark && <span className="brand__word">Toka</span>}
    </span>
  );
}
