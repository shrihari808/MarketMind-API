import React from 'react';

interface CountryFlagProps {
  country: 'IN' | 'US' | string;
  className?: string;
  title?: string;
}

/**
 * High-definition, standalone vector SVG flags for reliable cross-platform rendering.
 * Resolves the Windows OS limitation where Unicode flag emojis (🇮🇳, 🇺🇸) render as two-letter text ('IN', 'US').
 */
export const CountryFlag: React.FC<CountryFlagProps> = ({
  country,
  className = 'w-5 h-3.5 inline-block',
  title,
}) => {
  const code = (country || '').toUpperCase();

  if (code === 'IN') {
    return (
      <svg
        viewBox="0 0 640 480"
        className={`inline-block shrink-0 rounded-[2px] shadow-xs border border-white/10 ${className}`}
        aria-label="Flag of India"
      >
        <title>{title || 'India'}</title>
        <rect width="640" height="160" fill="#FF9933" />
        <rect y="160" width="640" height="160" fill="#FFFFFF" />
        <rect y="320" width="640" height="160" fill="#138808" />
        <g transform="translate(320 240)">
          <circle r="60" fill="none" stroke="#000080" strokeWidth="8" />
          <circle r="12" fill="#000080" />
          {/* 24 spokes of Ashoka Chakra */}
          {Array.from({ length: 24 }).map((_, i) => (
            <line
              key={i}
              x1="0"
              y1="0"
              x2="0"
              y2="-58"
              stroke="#000080"
              strokeWidth="4"
              transform={`rotate(${i * 15})`}
            />
          ))}
        </g>
      </svg>
    );
  }

  if (code === 'US') {
    return (
      <svg
        viewBox="0 0 741 390"
        className={`inline-block shrink-0 rounded-[2px] shadow-xs border border-white/10 ${className}`}
        aria-label="Flag of United States"
      >
        <title>{title || 'United States'}</title>
        {/* 13 alternating red and white stripes */}
        <rect width="741" height="390" fill="#B22234" />
        {Array.from({ length: 6 }).map((_, i) => (
          <rect key={i} y={(2 * i + 1) * 30} width="741" height="30" fill="#FFFFFF" />
        ))}
        {/* Canton */}
        <rect width="296.4" height="210" fill="#3C3B6E" />
        {/* 50 Stars constellation */}
        <g fill="#FFFFFF">
          {[
            [24.7, 17.5], [74.1, 17.5], [123.5, 17.5], [172.9, 17.5], [222.3, 17.5], [271.7, 17.5],
            [49.4, 38.5], [98.8, 38.5], [148.2, 38.5], [197.6, 38.5], [247.0, 38.5],
            [24.7, 59.5], [74.1, 59.5], [123.5, 59.5], [172.9, 59.5], [222.3, 59.5], [271.7, 59.5],
            [49.4, 80.5], [98.8, 80.5], [148.2, 80.5], [197.6, 80.5], [247.0, 80.5],
            [24.7, 101.5], [74.1, 101.5], [123.5, 101.5], [172.9, 101.5], [222.3, 101.5], [271.7, 101.5],
            [49.4, 122.5], [98.8, 122.5], [148.2, 122.5], [197.6, 122.5], [247.0, 122.5],
            [24.7, 143.5], [74.1, 143.5], [123.5, 143.5], [172.9, 143.5], [222.3, 143.5], [271.7, 143.5],
            [49.4, 164.5], [98.8, 164.5], [148.2, 164.5], [197.6, 164.5], [247.0, 164.5],
            [24.7, 185.5], [74.1, 185.5], [123.5, 185.5], [172.9, 185.5], [222.3, 185.5], [271.7, 185.5],
          ].map(([cx, cy], idx) => (
            <polygon
              key={idx}
              points={`${cx},${cy - 7} ${cx + 2.1},${cy - 2.2} ${cx + 7.2},${cy - 2.2} ${cx + 3.1},${cy + 1.2} ${cx + 4.7},${cy + 6.3} ${cx},${cy + 3.2} ${cx - 4.7},${cy + 6.3} ${cx - 3.1},${cy + 1.2} ${cx - 7.2},${cy - 2.2} ${cx - 2.1},${cy - 2.2}`}
            />
          ))}
        </g>
      </svg>
    );
  }

  return <span className="font-mono text-xs">{code}</span>;
};
