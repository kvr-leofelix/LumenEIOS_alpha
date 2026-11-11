import React from 'react';
import { PacingMetrics } from '../../lib/calculations';
import { cn } from '../../lib/utils';
import { AlertTriangle, CheckCircle2, Clock, CalendarDays } from 'lucide-react';

interface PacingProgressChartProps {
  metrics: PacingMetrics;
}

export const PacingProgressChart: React.FC<PacingProgressChartProps> = ({ metrics }) => {
  const {
    totalOfficialDays,
    currentDay,
    totalLostDays,
    remainingInstructionalDays,
    coreConceptsRemaining,
    supplementaryTopicsRemaining,
    pacingBuffer,
    riskStatus,
  } = metrics;

  const completedPct = Math.round((currentDay / totalOfficialDays) * 100);
  const lostPct = Math.round((totalLostDays / totalOfficialDays) * 100);
  const remainingPct = Math.max(0, 100 - completedPct - lostPct);

  return (
    <div className="space-y-5">
      {/* Risk Alert Header */}
      <div
        className={cn(
          'p-4 rounded-xl border flex items-start gap-3.5',
          riskStatus === 'high'
            ? 'bg-rose-50 border-rose-200 text-rose-900'
            : riskStatus === 'medium'
            ? 'bg-amber-50 border-amber-200 text-amber-900'
            : 'bg-emerald-50 border-emerald-200 text-emerald-900'
        )}
      >
        {riskStatus === 'high' ? (
          <AlertTriangle className="w-5 h-5 text-rose-600 shrink-0 mt-0.5" />
        ) : riskStatus === 'medium' ? (
          <Clock className="w-5 h-5 text-amber-600 shrink-0 mt-0.5" />
        ) : (
          <CheckCircle2 className="w-5 h-5 text-emerald-600 shrink-0 mt-0.5" />
        )}
        <div className="text-sm">
          <p className="font-semibold">
            {riskStatus === 'high'
              ? `Deficit Alert: Behind by ${Math.abs(pacingBuffer)} Teaching Periods`
              : riskStatus === 'medium'
              ? `Pacing Warning: Slim Buffer (${pacingBuffer} days)`
              : 'Pacing Healthy: Safe Buffer Available'}
          </p>
          <p className="text-xs opacity-90 mt-0.5 leading-relaxed">
            {riskStatus === 'high'
              ? `Unplanned disruptions (${totalLostDays} days lost) have compressed remaining calendar. Textbook-first teaching risks sacrificing foundational mastery.`
              : 'Class instructional pace currently aligns with NEP 2020 competency milestones.'}
          </p>
        </div>
      </div>

      {/* Visual Instructional Calendar Bar */}
      <div>
        <div className="flex justify-between items-center text-xs font-medium text-content-secondary mb-2">
          <span>Instructional Calendar Horizon ({totalOfficialDays} Total Days)</span>
          <span>Day {currentDay} of {totalOfficialDays}</span>
        </div>

        <div className="h-6 w-full bg-gray-200 rounded-lg overflow-hidden flex shadow-inner">
          <div
            style={{ width: `${completedPct}%` }}
            className="bg-navy-800 flex items-center justify-center text-[10px] text-white font-medium"
            title={`Completed Instruction: ${currentDay} days`}
          >
            {completedPct > 10 && `${currentDay}d Taught`}
          </div>
          <div
            style={{ width: `${lostPct}%` }}
            className="bg-rose-500 flex items-center justify-center text-[10px] text-white font-medium animate-pulse"
            title={`Lost Instructional Days: ${totalLostDays} days`}
          >
            {lostPct > 5 && `-${totalLostDays}d Lost`}
          </div>
          <div
            style={{ width: `${remainingPct}%` }}
            className="bg-teal-500 flex items-center justify-center text-[10px] text-white font-medium"
            title={`Actual Teaching Days Left: ${remainingInstructionalDays} days`}
          >
            {remainingPct > 10 && `${remainingInstructionalDays}d Left`}
          </div>
        </div>

        {/* Legend */}
        <div className="flex flex-wrap items-center gap-4 mt-2.5 text-xs text-content-secondary">
          <div className="flex items-center gap-1.5">
            <span className="w-3 h-3 rounded bg-navy-800" />
            <span>Completed ({currentDay}d)</span>
          </div>
          <div className="flex items-center gap-1.5">
            <span className="w-3 h-3 rounded bg-rose-500" />
            <span>Lost Teaching Days ({totalLostDays}d)</span>
          </div>
          <div className="flex items-center gap-1.5">
            <span className="w-3 h-3 rounded bg-teal-500" />
            <span>Available Teaching Days ({remainingInstructionalDays}d)</span>
          </div>
        </div>
      </div>

      {/* Syllabus Demand Breakdown Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
        <div className="p-3 bg-surface-bg rounded-xl border border-surface-border">
          <p className="text-[11px] font-medium text-content-secondary uppercase">Available Teaching Days</p>
          <p className="text-xl font-bold text-navy-800 mt-1">{remainingInstructionalDays} Days</p>
          <p className="text-[11px] text-content-muted mt-0.5">Net calendar periods</p>
        </div>
        <div className="p-3 bg-surface-bg rounded-xl border border-surface-border">
          <p className="text-[11px] font-medium text-content-secondary uppercase">Protected Core Concepts</p>
          <p className="text-xl font-bold text-teal-700 mt-1">{coreConceptsRemaining} Topics</p>
          <p className="text-[11px] text-teal-600 font-medium mt-0.5">100% Protected (NEP 2020)</p>
        </div>
        <div className="p-3 bg-surface-bg rounded-xl border border-surface-border">
          <p className="text-[11px] font-medium text-content-secondary uppercase">Supplementary Content</p>
          <p className="text-xl font-bold text-amber-700 mt-1">{supplementaryTopicsRemaining} Topics</p>
          <p className="text-[11px] text-amber-600 font-medium mt-0.5">Eligible for Flipped Compacting</p>
        </div>
      </div>
    </div>
  );
};

