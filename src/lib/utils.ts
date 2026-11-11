import { type ClassValue, clsx } from 'clsx';
import { twMerge } from 'tailwind-merge';

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function formatPercent(value: number): string {
  return `${Math.round(value)}%`;
}

export function getCompetencyColor(score: number): {
  bg: string;
  text: string;
  border: string;
  badge: string;
} {
  if (score >= 80) {
    return {
      bg: 'bg-emerald-50',
      text: 'text-emerald-700',
      border: 'border-emerald-200',
      badge: 'bg-emerald-100 text-emerald-800',
    };
  } else if (score >= 65) {
    return {
      bg: 'bg-blue-50',
      text: 'text-blue-700',
      border: 'border-blue-200',
      badge: 'bg-blue-100 text-blue-800',
    };
  } else if (score >= 50) {
    return {
      bg: 'bg-amber-50',
      text: 'text-amber-700',
      border: 'border-amber-200',
      badge: 'bg-amber-100 text-amber-800',
    };
  } else {
    return {
      bg: 'bg-rose-50',
      text: 'text-rose-700',
      border: 'border-rose-200',
      badge: 'bg-rose-100 text-rose-800',
    };
  }
}

export function getTierBadge(tier: string) {
  switch (tier) {
    case 'high-tech':
      return {
        label: 'High-Tech Private',
        color: 'bg-teal-50 text-teal-700 border-teal-200',
      };
    case 'standard':
      return {
        label: 'Standard Blended',
        color: 'bg-blue-50 text-blue-700 border-blue-200',
      };
    case 'low-tech':
      return {
        label: 'Low-Tech / Rural Gov',
        color: 'bg-amber-50 text-amber-800 border-amber-200',
      };
    default:
      return {
        label: tier,
        color: 'bg-gray-50 text-gray-700 border-gray-200',
      };
  }
}

