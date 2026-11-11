import React from 'react';
import { cn } from '../../lib/utils';

interface CardProps extends React.HTMLAttributes<HTMLDivElement> {
  children: React.ReactNode;
  className?: string;
  hoverable?: boolean;
}

export const Card: React.FC<CardProps> = ({ children, className, hoverable, ...props }) => {
  return (
    <div
      className={cn(
        'bg-surface-card border border-surface-border rounded-xl shadow-subtle transition-shadow duration-200 overflow-hidden',
        hoverable && 'hover:shadow-card hover:border-surface-borderHover cursor-pointer',
        className
      )}
      {...props}
    >
      {children}
    </div>
  );
};

export const CardHeader: React.FC<{
  title: React.ReactNode;
  subtitle?: React.ReactNode;
  action?: React.ReactNode;
  className?: string;
}> = ({ title, subtitle, action, className }) => {
  return (
    <div className={cn('px-5 py-4 border-b border-surface-border flex items-center justify-between gap-4', className)}>
      <div>
        <h3 className="font-semibold text-content-primary text-base leading-snug">{title}</h3>
        {subtitle && <p className="text-xs text-content-secondary mt-0.5">{subtitle}</p>}
      </div>
      {action && <div className="shrink-0">{action}</div>}
    </div>
  );
};

export const CardBody: React.FC<{ children: React.ReactNode; className?: string }> = ({
  children,
  className,
}) => {
  return <div className={cn('p-5', className)}>{children}</div>;
};

