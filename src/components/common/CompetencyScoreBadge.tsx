import React from 'react';
import { CompetencyKey } from '../../types';
import { cn, getCompetencyColor } from '../../lib/utils';

interface CompetencyScoreBadgeProps {
  type: CompetencyKey | 'overall';
  score: number;
  showLabel?: boolean;
  size?: 'sm' | 'md' | 'lg';
  className?: string;
}

const labels: Record<string, { short: string; full: string }> = {
  LU: { short: 'LU', full: 'Language Understanding' },
  CU: { short: 'CU', full: 'Concept Understanding' },
  AU: { short: 'AU', full: 'Application Understanding' },
  CT: { short: 'CT', full: 'Critical Thinking' },
  overall: { short: 'Avg', full: 'Composite Competency Baseline' },
};

export const CompetencyScoreBadge: React.FC<CompetencyScoreBadgeProps> = ({
  type,
  score,
  showLabel = true,
  size = 'md',
  className,
}) => {
  const color = getCompetencyColor(score);
  const info = labels[type] || { short: type, full: type };

  const sizeClasses = {
    sm: 'text-[11px] px-2 py-0.5',
    md: 'text-xs px-2.5 py-1',
    lg: 'text-sm px-3.5 py-1.5 font-semibold',
  };

  return (
    <div
      title={`${info.full}: ${score}%`}
      className={cn(
        'inline-flex items-center gap-1.5 rounded-lg border font-medium',
        color.bg,
        color.text,
        color.border,
        sizeClasses[size],
        className
      )}
    >
      {showLabel && <span className="opacity-75 font-semibold">{info.short}:</span>}
      <span className="font-bold">{score}%</span>
    </div>
  );
};

export const CompetencyGroupBadges: React.FC<{
  scores: { LU: number; CU: number; AU: number; CT: number; overall?: number };
  size?: 'sm' | 'md';
  includeOverall?: boolean;
}> = ({ scores, size = 'sm', includeOverall = false }) => {
  return (
    <div className="flex flex-wrap items-center gap-1.5">
      <CompetencyScoreBadge type="LU" score={scores.LU} size={size} />
      <CompetencyScoreBadge type="CU" score={scores.CU} size={size} />
      <CompetencyScoreBadge type="AU" score={scores.AU} size={size} />
      <CompetencyScoreBadge type="CT" score={scores.CT} size={size} />
      {includeOverall && scores.overall !== undefined && (
        <CompetencyScoreBadge type="overall" score={scores.overall} size={size} />
      )}
    </div>
  );
};

