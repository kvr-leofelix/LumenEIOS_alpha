import React, { useState } from 'react';
import { Modal } from '../../components/common/Modal';
import { Button } from '../../components/common/Button';
import { Badge } from '../../components/common/Badge';
import { CompressionPlanProposal } from '../../lib/calculations';
import {
  CheckCircle2,
  Clock,
  ArrowRight,
  ShieldCheck,
  AlertTriangle,
  Sparkles,
  BookOpen,
  FileCheck,
} from 'lucide-react';

interface CompressionPreviewModalProps {
  isOpen: boolean;
  onClose: () => void;
  proposal: CompressionPlanProposal;
  onAcceptPlan: () => void;
}

export const CompressionPreviewModal: React.FC<CompressionPreviewModalProps> = ({
  isOpen,
  onClose,
  proposal,
  onAcceptPlan,
}) => {
  const [activeTab, setActiveTab] = useState<'comparison' | 'topics' | 'tradeoffs'>('comparison');
  const [isApplying, setIsApplying] = useState(false);

  const handleConfirm = () => {
    setIsApplying(true);
    setTimeout(() => {
      onAcceptPlan();
      setIsApplying(false);
      onClose();
    }, 600);
  };

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title="Syllabus Compacting Plan: 60/40 Time-Aware Strategy"
      subtitle="Previewing revised instructional pacing schedule under calendar disruptions"
      maxWidth="3xl"
      footer={
        <div className="flex items-center justify-between w-full">
          <div className="text-xs text-content-secondary flex items-center gap-1.5">
            <ShieldCheck className="w-4 h-4 text-teal-600" />
            <span>NEP 2020: 100% Core Competencies strictly preserved</span>
          </div>
          <div className="flex items-center gap-2.5">
            <Button variant="secondary" size="md" onClick={onClose}>
              Cancel / Reject
            </Button>
            <Button
              variant="teal"
              size="md"
              loading={isApplying}
              onClick={handleConfirm}
              icon={<CheckCircle2 className="w-4 h-4" />}
            >
              Accept Proposed Plan
            </Button>
          </div>
        </div>
      }
    >
      {/* Tab Navigation */}
      <div className="flex items-center border-b border-surface-border mb-5 gap-4 text-xs font-semibold">
        <button
          onClick={() => setActiveTab('comparison')}
          className={`pb-2.5 border-b-2 transition-colors ${
            activeTab === 'comparison'
              ? 'border-teal-600 text-teal-700'
              : 'border-transparent text-content-secondary hover:text-content-primary'
          }`}
        >
          Pacing Comparison & Metrics
        </button>
        <button
          onClick={() => setActiveTab('topics')}
          className={`pb-2.5 border-b-2 transition-colors ${
            activeTab === 'topics'
              ? 'border-teal-600 text-teal-700'
              : 'border-transparent text-content-secondary hover:text-content-primary'
          }`}
        >
          Reassigned & Integrated Topics ({proposal.topicsReassignedCount + proposal.topicsIntegratedCount})
        </button>
        <button
          onClick={() => setActiveTab('tradeoffs')}
          className={`pb-2.5 border-b-2 transition-colors ${
            activeTab === 'tradeoffs'
              ? 'border-teal-600 text-teal-700'
              : 'border-transparent text-content-secondary hover:text-content-primary'
          }`}
        >
          Pedagogical Risk & Trade-offs
        </button>
      </div>

      {activeTab === 'comparison' && (
        <div className="space-y-5">
          {/* Before vs After Metric Cards */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            {/* Original Plan */}
            <div className="p-4 rounded-xl border border-rose-200 bg-rose-50/40">
              <div className="flex items-center justify-between">
                <span className="text-xs font-bold text-rose-700 uppercase tracking-wider">
                  Current Schedule (Deficit)
                </span>
                <Badge variant="danger" size="sm">
                  Pacing Deficit
                </Badge>
              </div>
              <p className="text-3xl font-extrabold text-navy-900 mt-2">
                {proposal.originalDurationDays} <span className="text-sm font-normal text-content-secondary">Periods Needed</span>
              </p>
              <p className="text-xs text-rose-700 mt-1">
                Linear textbook coverage exceeds actual available teaching days by {proposal.daysSaved - 4} days.
              </p>
            </div>

            {/* Revised Compacted Plan */}
            <div className="p-4 rounded-xl border border-teal-200 bg-teal-50/50">
              <div className="flex items-center justify-between">
                <span className="text-xs font-bold text-teal-800 uppercase tracking-wider">
                  Proposed Compacted Plan
                </span>
                <Badge variant="teal" size="sm">
                  Buffer Restored
                </Badge>
              </div>
              <p className="text-3xl font-extrabold text-teal-800 mt-2">
                {proposal.revisedDurationDays} <span className="text-sm font-normal text-teal-700">Classroom Periods</span>
              </p>
              <p className="text-xs text-teal-700 mt-1 font-medium">
                Recovers <span className="font-bold">{proposal.daysSaved} instructional periods</span> via flipped learning and cross-curricular synthesis.
              </p>
            </div>
          </div>

          {/* Core Protection Guarantee Banner */}
          <div className="p-4 rounded-xl bg-navy-800 text-white flex items-start gap-3">
            <Sparkles className="w-5 h-5 text-teal-400 shrink-0 mt-0.5" />
            <div className="text-xs">
              <p className="font-semibold text-white text-sm">Protected Core Competencies Guarantee</p>
              <p className="text-gray-300 mt-0.5 leading-relaxed">
                All {proposal.preservedCoreCount} foundational core concept periods remain scheduled for live teacher instruction. Only secondary exploratory topics are transitioned to guided flipped inquiry.
              </p>
            </div>
          </div>

          {/* Key Adjustments Summary List */}
          <div className="space-y-2">
            <h4 className="text-xs font-bold text-content-primary uppercase tracking-wider">
              Summary of Adjustments
            </h4>
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-2.5 text-xs">
              <div className="p-3 bg-surface-bg rounded-lg border border-surface-border">
                <span className="font-semibold text-content-primary block">
                  {proposal.topicsReassignedCount} Topics Flipped
                </span>
                <span className="text-content-secondary text-[11px]">
                  Assigned as scaffolded home reading & parent-guided worksheets.
                </span>
              </div>
              <div className="p-3 bg-surface-bg rounded-lg border border-surface-border">
                <span className="font-semibold text-content-primary block">
                  {proposal.topicsIntegratedCount} Projects Merged
                </span>
                <span className="text-content-secondary text-[11px]">
                  Shared with Science and Social Studies double periods.
                </span>
              </div>
              <div className="p-3 bg-surface-bg rounded-lg border border-surface-border">
                <span className="font-semibold text-teal-700 block">
                  +{proposal.daysSaved} Days Recovered
                </span>
                <span className="text-content-secondary text-[11px]">
                  Restores safe revision buffer before board exams.
                </span>
              </div>
            </div>
          </div>
        </div>
      )}

      {activeTab === 'topics' && (
        <div className="space-y-4">
          <p className="text-xs text-content-secondary leading-relaxed">
            The following supplementary lessons will be modified from full teacher lectures to flipped learning modules or integrated cross-curricular units:
          </p>
          <div className="space-y-2 max-h-80 overflow-y-auto pr-1">
            {proposal.reassignedTopics.map((topic) => (
              <div
                key={topic.id}
                className="p-3 bg-surface-bg rounded-lg border border-surface-border flex items-start justify-between gap-3 text-xs"
              >
                <div>
                  <div className="flex items-center gap-2">
                    <span className="font-semibold text-navy-800">Day {topic.dayNumber}: {topic.topic}</span>
                    <Badge variant="warning" size="sm">Flipped Homework</Badge>
                  </div>
                  <p className="text-content-secondary mt-1 text-[11px] leading-relaxed">
                    Objective: {topic.objective}
                  </p>
                </div>
                <span className="shrink-0 text-[11px] font-mono text-content-muted">
                  {topic.estimatedDurationMins} min saved
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {activeTab === 'tradeoffs' && (
        <div className="space-y-4 text-xs">
          <div>
            <h4 className="font-semibold text-content-primary mb-2 flex items-center gap-1.5">
              <CheckCircle2 className="w-4 h-4 text-teal-600" />
              <span>Pedagogical Safeguards</span>
            </h4>
            <ul className="space-y-1.5 list-disc list-inside text-content-secondary pl-1">
              {proposal.tradeOffAnalysis.map((item, idx) => (
                <li key={idx} className="leading-relaxed">
                  {item}
                </li>
              ))}
            </ul>
          </div>

          <div className="pt-3 border-t border-surface-border">
            <h4 className="font-semibold text-amber-900 mb-2 flex items-center gap-1.5">
              <AlertTriangle className="w-4 h-4 text-amber-600" />
              <span>Mandatory Remediation Prerequisites</span>
            </h4>
            <ul className="space-y-1.5 list-disc list-inside text-amber-800 pl-1">
              {proposal.remediationRequirements.map((item, idx) => (
                <li key={idx} className="leading-relaxed">
                  {item}
                </li>
              ))}
            </ul>
          </div>
        </div>
      )}
    </Modal>
  );
};

