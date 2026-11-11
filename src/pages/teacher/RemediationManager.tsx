import React, { useState } from 'react';
import { useData } from '../../context/DataContext';
import { HomeworkRemediation, CompetencyKey } from '../../types';
import { Card, CardHeader, CardBody } from '../../components/common/Card';
import { Button } from '../../components/common/Button';
import { Badge } from '../../components/common/Badge';
import { Modal } from '../../components/common/Modal';
import {
  Sparkles,
  BookOpen,
  CheckCircle2,
  Calendar,
  User,
  PlusCircle,
  FileCheck,
} from 'lucide-react';

export const RemediationManager: React.FC = () => {
  const { homeworkRemediations, students, assignHomeworkRemediation } = useData();

  const [filterDim, setFilterDim] = useState<string>('all');
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [toast, setToast] = useState<string | null>(null);

  // New Remediation Form
  const [studentId, setStudentId] = useState(students[0]?.id || 'user-student-1');
  const [title, setTitle] = useState('');
  const [competencyTarget, setCompetencyTarget] = useState<CompetencyKey>('LU');
  const [reason, setReason] = useState('');
  const [description, setDescription] = useState('');
  const [dueDate, setDueDate] = useState('2026-10-20');

  const filtered = homeworkRemediations.filter((hw) => {
    return filterDim === 'all' || hw.competencyTarget === filterDim;
  });

  const handleCreateRemediation = (e: React.FormEvent) => {
    e.preventDefault();
    const st = students.find((s) => s.id === studentId);
    if (!st || !title.trim()) return;

    assignHomeworkRemediation({
      studentId: st.id,
      studentName: st.name,
      classId: st.classId,
      subjectId: 'sub-math',
      title,
      competencyTarget,
      reason: reason || `Targeted gap intervention in ${competencyTarget}.`,
      description: description || 'Complete the targeted mastery sheet.',
      dueDate,
      status: 'assigned',
    });

    setIsModalOpen(false);
    setTitle('');
    setToast(`Targeted remediation assigned to ${st.name}!`);
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
          <div className="flex items-center gap-2">
            <h1 className="text-xl font-bold text-navy-900 tracking-tight">
              Differentiated Remediation & Flipped Practice
            </h1>
            <Badge variant="teal" size="sm">
              NEP 2020 Personalized
            </Badge>
          </div>
          <p className="text-xs text-content-secondary mt-1">
            Deterministic diagnostic remediation: targeted homework addressing specific LU, CU, AU, or CT deficits
          </p>
        </div>

        <Button
          variant="teal"
          size="md"
          onClick={() => setIsModalOpen(true)}
          icon={<PlusCircle className="w-4 h-4" />}
        >
          Assign Remediation
        </Button>
      </div>

      {/* Filters and List */}
      <div className="flex items-center justify-between gap-4 bg-white p-3 rounded-xl border border-surface-border text-xs">
        <span className="font-semibold text-content-primary">Filter Dimension:</span>
        <div className="flex items-center gap-2 overflow-x-auto">
          {['all', 'LU', 'CU', 'AU', 'CT'].map((dim) => (
            <button
              key={dim}
              onClick={() => setFilterDim(dim)}
              className={`px-3 py-1.5 rounded-lg font-semibold transition-colors ${
                filterDim === dim
                  ? 'bg-navy-800 text-white'
                  : 'bg-surface-bg text-content-secondary hover:text-content-primary'
              }`}
            >
              {dim === 'all' ? 'All Dimensions' : `${dim} Gaps`}
            </button>
          ))}
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {filtered.map((hw) => (
          <Card key={hw.id} className="flex flex-col justify-between">
            <CardHeader
              title={hw.studentName}
              subtitle={`Due: ${hw.dueDate}`}
              action={
                <Badge
                  variant={
                    hw.competencyTarget === 'LU'
                      ? 'info'
                      : hw.competencyTarget === 'CU'
                      ? 'teal'
                      : hw.competencyTarget === 'AU'
                      ? 'warning'
                      : 'danger'
                  }
                  size="sm"
                >
                  {hw.competencyTarget} Focus
                </Badge>
              }
            />
            <CardBody className="space-y-3 text-xs">
              <div>
                <h4 className="font-bold text-navy-900 text-sm">{hw.title}</h4>
                <p className="text-[11px] text-content-muted mt-0.5">{hw.reason}</p>
              </div>

              <div className="p-3 bg-surface-bg rounded-lg border border-surface-border text-content-secondary leading-relaxed">
                {hw.description}
              </div>

              <div className="pt-2 border-t border-surface-border flex items-center justify-between text-[11px]">
                <span className="text-content-secondary">
                  Status:{' '}
                  <strong
                    className={`capitalize ${
                      hw.status === 'submitted'
                        ? 'text-teal-700'
                        : hw.status === 'reviewed'
                        ? 'text-emerald-700'
                        : 'text-amber-700'
                    }`}
                  >
                    {hw.status}
                  </strong>
                </span>
                {hw.score !== undefined && (
                  <span className="font-bold text-emerald-700">Score: {hw.score}%</span>
                )}
              </div>
            </CardBody>
          </Card>
        ))}
      </div>

      {/* Modal for Assigning New Remediation */}
      <Modal
        isOpen={isModalOpen}
        onClose={() => setIsModalOpen(false)}
        title="Assign Differentiated Remediation"
        subtitle="Select recipient student and tailor pedagogical focus"
        maxWidth="lg"
        footer={
          <div className="flex items-center justify-end gap-2.5 w-full">
            <Button variant="secondary" size="md" onClick={() => setIsModalOpen(false)}>
              Cancel
            </Button>
            <Button variant="teal" size="md" onClick={handleCreateRemediation}>
              Assign Remediation
            </Button>
          </div>
        }
      >
        <form onSubmit={handleCreateRemediation} className="space-y-4 text-xs">
          <div>
            <label className="block font-semibold text-content-primary mb-1">Target Student</label>
            <select
              value={studentId}
              onChange={(e) => setStudentId(e.target.value)}
              className="w-full px-3 py-2 bg-white border border-surface-border rounded-lg text-xs"
            >
              {students.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.name} (Roll #{s.rollNo} • Baseline: {s.competencies.overall}%)
                </option>
              ))}
            </select>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block font-semibold text-content-primary mb-1">Target Competency</label>
              <select
                value={competencyTarget}
                onChange={(e) => setCompetencyTarget(e.target.value as any)}
                className="w-full px-3 py-2 bg-white border border-surface-border rounded-lg text-xs"
              >
                <option value="LU">Language Understanding (LU)</option>
                <option value="CU">Concept Understanding (CU)</option>
                <option value="AU">Application Understanding (AU)</option>
                <option value="CT">Critical Thinking (CT)</option>
              </select>
            </div>
            <div>
              <label className="block font-semibold text-content-primary mb-1">Due Date</label>
              <input
                type="date"
                value={dueDate}
                onChange={(e) => setDueDate(e.target.value)}
                className="w-full px-3 py-2 bg-white border border-surface-border rounded-lg text-xs"
              />
            </div>
          </div>

          <div>
            <label className="block font-semibold text-content-primary mb-1">Activity Title</label>
            <input
              type="text"
              required
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="e.g. Word Problem Linguistic Scaffolding"
              className="w-full px-3 py-2 bg-white border border-surface-border rounded-lg text-xs"
            />
          </div>

          <div>
            <label className="block font-semibold text-content-primary mb-1">Diagnostic Rationale</label>
            <textarea
              rows={2}
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              placeholder="e.g. Scored 48% on Q3 word problem syntax interpretation."
              className="w-full px-3 py-2 bg-white border border-surface-border rounded-lg text-xs"
            />
          </div>

          <div>
            <label className="block font-semibold text-content-primary mb-1">Activity Description</label>
            <textarea
              rows={3}
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="e.g. Complete 5 scaffolded problems with bilingual vocabulary guides..."
              className="w-full px-3 py-2 bg-white border border-surface-border rounded-lg text-xs"
            />
          </div>
        </form>
      </Modal>
    </div>
  );
};

