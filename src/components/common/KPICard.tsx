import React from 'react';
import { Card } from './Card';
import { cn } from '../../lib/utils';

interface KPICardProps {
  title: string;
  value: string | number;
  subtitle?: string;
  icon: React.ReactNode;
  iconBg?: string;
  trend?: {
    value: string;
    isPositive?: boolean;
    label?: string;
  };
  onClick?: () => void;
  className?: string;
}

export const KPICard: React.FC<KPICardProps> = ({
  title,
  value,
  subtitle,
  icon,
  iconBg = 'bg-teal-50 text-teal-600',
  trend,
  onClick,
  className,
}) => {
  return (
    <Card
      hoverable={!!onClick}
      onClick={onClick}
      className={cn('p-5 flex flex-col justify-between', className)}
    >
      <div className="flex items-start justify-between">
        <div>
          <p className="text-xs font-medium uppercase tracking-wider text-content-secondary">{title}</p>
          <p className="text-2xl font-bold text-content-primary mt-1.5 tracking-tight">{value}</p>
        </div>
        <div className={cn('p-2.5 rounded-xl shrink-0', iconBg)}>
          {icon}
        </div>
      </div>

      {(subtitle || trend) && (
        <div className="mt-3 pt-3 border-t border-surface-border flex items-center justify-between text-xs">
          {subtitle && <span className="text-content-secondary">{subtitle}</span>}
          {trend && (
            <span
              className={cn(
                'font-medium inline-flex items-center gap-1',
                trend.isPositive ? 'text-emerald-600' : 'text-rose-600'
              )}
            >
              {trend.value} <span className="text-content-muted font-normal">{trend.label}</span>
            </span>
          )}
        </div>
      )}
    </Card>
  );
};

