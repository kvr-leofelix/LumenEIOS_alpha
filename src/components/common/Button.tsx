import React from 'react';
import { cn } from '../../lib/utils';

interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'secondary' | 'outline' | 'danger' | 'ghost' | 'teal';
  size?: 'sm' | 'md' | 'lg';
  icon?: React.ReactNode;
  loading?: boolean;
}

export const Button: React.FC<ButtonProps> = ({
  children,
  className,
  variant = 'primary',
  size = 'md',
  icon,
  loading = false,
  disabled,
  ...props
}) => {
  const baseStyles = 'inline-flex items-center justify-center font-medium rounded-lg transition-all duration-150 focus:outline-none focus:ring-2 focus:ring-offset-1 disabled:opacity-50 disabled:cursor-not-allowed select-none gap-2';

  const variants = {
    primary: 'bg-navy-800 text-white hover:bg-navy-900 active:bg-navy-950 focus:ring-navy-500 shadow-sm',
    teal: 'bg-teal-500 text-white hover:bg-teal-600 active:bg-teal-700 focus:ring-teal-400 shadow-sm',
    secondary: 'bg-surface-bg text-content-primary hover:bg-gray-200 border border-surface-border focus:ring-gray-300',
    outline: 'bg-white border border-surface-border text-content-primary hover:bg-gray-50 hover:border-gray-300 focus:ring-teal-400',
    danger: 'bg-red-600 text-white hover:bg-red-700 active:bg-red-800 focus:ring-red-400 shadow-sm',
    ghost: 'text-content-secondary hover:text-content-primary hover:bg-gray-100 focus:ring-gray-300',
  };

  const sizes = {
    sm: 'text-xs px-2.5 py-1.5',
    md: 'text-sm px-3.5 py-2',
    lg: 'text-base px-5 py-2.5',
  };

  return (
    <button
      className={cn(baseStyles, variants[variant], sizes[size], className)}
      disabled={disabled || loading}
      {...props}
    >
      {loading ? (
        <span className="w-4 h-4 border-2 border-current border-t-transparent rounded-full animate-spin" />
      ) : (
        icon && <span className="shrink-0">{icon}</span>
      )}
      <span>{children}</span>
    </button>
  );
};

