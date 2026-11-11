import React, { useState } from 'react';
import { Card, CardHeader, CardBody } from '../../components/common/Card';
import { Button } from '../../components/common/Button';
import { Badge } from '../../components/common/Badge';
import { Settings, ShieldCheck, CheckCircle2, Clock } from 'lucide-react';

export const AcademicConfig: React.FC = () => {
  const [academicYear, setAcademicYear] = useState('2026-2027');
  const [statutoryDays, setStatutoryDays] = useState(220);
  const [curriculumHorizon, setCurriculumHorizon] = useState(180);
  const [reassessmentCycleWeeks, setReassessmentCycleWeeks] = useState(5);
  const [coreProtectionRatio, setCoreProtectionRatio] = useState(60);
  const [toast, setToast] = useState<string | null>(null);

  const handleSave = (e: React.FormEvent) => {
    e.preventDefault();
    setToast('Academic configuration settings saved successfully!');
    setTimeout(() => setToast(null), 4000);
  };

  return (
    <div className="space-y-6">
      {/* Toast Notification */}
      {toast && (
        <div className="fixed bottom-6 right-6 z-50 bg-navy-900 text-white px-4 py-3 rounded-xl shadow-modal border border-teal-500/40 text-xs flex items-center gap-2">
          <CheckCircle2 className="w-4 h-4 text-teal-400" />
          <span>{toast}</span>
        </div>
      )}

      {/* Header */}
      <div className="bg-white p-5 rounded-2xl border border-surface-border shadow-subtle flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-xl font-bold text-navy-900 tracking-tight">Academic Engine Configuration</h1>
          <p className="text-xs text-content-secondary mt-0.5">
            NEP 2020 Statutory Working Days, Recalibration Cycles, and Compacting Guardrails
          </p>
        </div>

        <Badge variant="teal" size="sm">
          Statewide Policy Controls
        </Badge>
      </div>

      <form onSubmit={handleSave} className="grid grid-cols-1 md:grid-cols-2 gap-6 text-xs">
        {/* Calendar and Instructional Days */}
        <Card>
          <CardHeader
            title="Instructional Calendar Baseline"
            subtitle="Statutory vs Effective Instructional Time"
            action={<Clock className="w-4 h-4 text-teal-600" />}
          />
          <CardBody className="space-y-4">
            <div>
              <label className="block font-semibold text-content-primary mb-1">
                Active Academic Year
              </label>
              <input
                type="text"
                value={academicYear}
                onChange={(e) => setAcademicYear(e.target.value)}
                className="w-full px-3 py-2 bg-white border border-surface-border rounded-lg"
              />
            </div>

            <div>
              <label className="block font-semibold text-content-primary mb-1">
                Statutory School Working Days (RTE Act / Board Norm)
              </label>
              <input
                type="number"
                value={statutoryDays}
                onChange={(e) => setStatutoryDays(Number(e.target.value))}
                className="w-full px-3 py-2 bg-white border border-surface-border rounded-lg"
              />
              <span className="text-[11px] text-content-muted mt-1 block">
                Official calendar baseline including administrative and sports events (typically 220 days).
              </span>
            </div>

            <div>
              <label className="block font-semibold text-content-primary mb-1">
                Micro-Curriculum Instruction Horizon
              </label>
              <input
                type="number"
                value={curriculumHorizon}
                onChange={(e) => setCurriculumHorizon(Number(e.target.value))}
                className="w-full px-3 py-2 bg-white border border-surface-border rounded-lg"
              />
              <span className="text-[11px] text-content-muted mt-1 block">
                Target classroom teaching periods per subject (180 days standard).
              </span>
            </div>
          </CardBody>
        </Card>

        {/* Time-Aware Pedagogical Thresholds */}
        <Card>
          <CardHeader
            title="Time-Aware Pedagogical Safeguards"
            subtitle="Competency Protection Ratios"
            action={<ShieldCheck className="w-4 h-4 text-teal-600" />}
          />
          <CardBody className="space-y-4">
            <div>
              <label className="block font-semibold text-content-primary mb-1">
                Reassessment Recalibration Frequency (Weeks)
              </label>
              <select
                value={reassessmentCycleWeeks}
                onChange={(e) => setReassessmentCycleWeeks(Number(e.target.value))}
                className="w-full px-3 py-2 bg-white border border-surface-border rounded-lg"
              >
                <option value={4}>Every 4 Weeks (Intensive)</option>
                <option value={5}>Every 5 Weeks (Standard Recommended)</option>
                <option value={6}>Every 6 Weeks (Relaxed)</option>
              </select>
            </div>

            <div>
              <label className="block font-semibold text-content-primary mb-1">
                Core Competencies Guaranteed Ratio: {coreProtectionRatio}%
              </label>
              <input
                type="range"
                min="50"
                max="80"
                step="5"
                value={coreProtectionRatio}
                onChange={(e) => setCoreProtectionRatio(Number(e.target.value))}
                className="w-full accent-teal-600 mt-2"
              />
              <span className="text-[11px] text-content-muted mt-1 block">
                Minimum syllabus proportion strictly reserved for live classroom teacher instruction during compaction.
              </span>
            </div>

            <div className="pt-4 border-t border-surface-border flex justify-end">
              <Button variant="teal" size="md" type="submit">
                Save Policy Configurations
              </Button>
            </div>
          </CardBody>
        </Card>
      </form>
    </div>
  );
};

