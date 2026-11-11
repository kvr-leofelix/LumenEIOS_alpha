import React from 'react';
import type { ProcessStep } from '../../lib/apiClient';

export const ProcessProgress: React.FC<{ steps: ProcessStep[] }> = ({ steps }) => {
  if (!steps.length) return null;
  return (
    <div className="space-y-2 rounded-xl border border-surface-border bg-surface-bg p-3" aria-live="polite">
      {steps.map((item) => {
        const knownTotal = item.total > 0;
        const finished = knownTotal && item.done >= item.total;
        const width = knownTotal ? Math.min(100, Math.round((item.done / item.total) * 100)) : 0;
        return (
          <div key={item.step}>
            <div className="mb-1 flex items-center justify-between gap-3 text-xs">
              <span className="font-medium text-navy-900">{item.label}</span>
              {knownTotal && (
                <span className="shrink-0 text-content-secondary">
                  {item.done} / {item.total}
                </span>
              )}
            </div>
            {knownTotal && (
              <div
                className="h-1.5 overflow-hidden rounded-full bg-slate-200"
                role="progressbar"
                aria-valuenow={item.done}
                aria-valuemin={0}
                aria-valuemax={item.total}
                aria-label={item.label}
              >
                <div
                  className={`h-full rounded-full ${finished ? 'bg-teal-600' : 'bg-teal-500'}`}
                  style={{ width: `${width}%` }}
                />
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
};
