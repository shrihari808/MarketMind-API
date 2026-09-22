import { clsx, type ClassValue } from 'clsx';
import { twMerge } from 'tailwind-merge';

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function formatCurrency(value?: number | null, currency: string = 'INR'): string {
  if (value === undefined || value === null || isNaN(value)) return '—';
  const curr = currency?.toUpperCase() || 'INR';
  const symbol = curr === 'INR' ? '₹' : curr === 'USD' ? '$' : `${curr} `;

  return `${symbol}${value.toLocaleString(undefined, {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}`;
}

export function formatPercent(value?: number | null): string {
  if (value === undefined || value === null || isNaN(value)) return '0.00%';
  const prefix = value > 0 ? '+' : '';
  return `${prefix}${value.toFixed(2)}%`;
}

export function formatCompactNumber(value?: number | null): string {
  if (value === undefined || value === null || isNaN(value)) return '—';
  return new Intl.NumberFormat('en', { notation: 'compact', compactDisplay: 'short' }).format(value);
}

export function getDomain(urlStr: string): string {
  try {
    const url = new URL(urlStr);
    return url.hostname.replace(/^www\./, '');
  } catch {
    return 'source';
  }
}
