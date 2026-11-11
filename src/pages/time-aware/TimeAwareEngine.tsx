import React, { useState } from 'react';
import { useData } from '../../context/DataContext';
import { useAuth } from '../../context/AuthContext';
import { calculateTimeAwarePacing, generateSyllabusCompressionPlan } from '../../lib/calculations';
import { PacingProgressChart } from '../../components/charts/PacingProgressChart';
import { CompressionPreviewModal } from './CompressionPreviewModal';
import { UnauthorizedPage } from '../shared/UnauthorizedPage';
import { Card, CardHeader, CardBody } from '../../components/common/Card';
import { Button } from '../../components/common/Button';
import { Badge } from '../../components/common/Badge';
import { Modal } from '../../components/common/Modal';
import {
  Clock,
  Calendar,
  AlertTriangle,
  PlusCircle,
  Sparkles,
  Layers,
  ArrowRight,
  Sliders,
  CheckCircle2,
  XCircle,
  FileText,
  ShieldCheck,
  RefreshCw,
} from 'lucide-react';

export const TimeAwareEngine: React.FC = () => {
  const {
    curriculumDays,
    lostTeachingDays,
    crossCurricularProposals,
    recordLostTeachingDay,
    applySyllabusCompression,
    acceptCrossCurricularProposal,
    rejectCrossCurricularProposal,
  } = useData();
  const { currentUser } = useAuth();

  // Selected Class & Subject context
  const [selectedClass] = useState('class-8a');
  const [selectedSubject] = useState('sub-math');

  // Configurable Core / Supplementary ratio (default 60 / 40)
  const [coreRatio, setCoreRatio] = useState(60);

  // Modals state
  const [isRecordModalOpen, setIsRecordModalOpen] = useState(false);
  const [isCompressionModalOpen, setIsCompressionModalOpen] = useState(false);
  const [toastMessage, setToastMessage] = useState<string | null>(null);

  // New Lost Day Form
  const [lostDate, setLostDate] = useState(new Date().toISOString().substring(0, 10));
  const [lostReason, setLostReason] = useState<
    'Election Duties' | 'Census Duties' | 'Teacher Training' | 'Health Drive' | 'Extreme Weather' | 'Local Festival' | 'Administrative Work'
  >('Election Duties');
  const [lostDaysCount, setLostDaysCount] = useState(2);
  const [lostNotes, setLostNotes] = useState('');

  // Calculate live pacing metrics
  const pacingMetrics = calculateTimeAwarePacing(curriculumDays, lostTeachingDays, 180, 104);
  const compressionProposal = generateSyllabusCompressionPlan(curriculumDays, pacingMetrics.totalLostDays);

  const handleRecordLostDay = (e: React.FormEvent) => {
    e.preventDefault();
    recordLostTeachingDay({
      schoolId: 'school-1',
      date: lostDate,
      reason: lostReason,
      daysLost: Number(lostDaysCount),
      recordedBy: currentUser?.name || 'Vikram Sengupta',
      notes: lostNotes || `Recorded disruption for ${lostReason}`,
    });
    setIsRecordModalOpen(false);
    setLostNotes('');
    showToast(`Recorded ${lostDaysCount} lost teaching days. Pacing buffer updated.`);
  };

  const handleAcceptPlan = () => {
    applySyllabusCompression(compressionProposal);
    showToast(`Syllabus Compacting Plan applied! ${compressionProposal.daysSaved} days recovered.`);
  };

  const showToast = (msg: string) => {
    setToastMessage(msg);
    setTimeout(() => setToastMessage(null), 4000);
  };

  const pendingProposals = crossCurricularProposals.filter((p) => p.status === 'pending');
  const acceptedProposals = crossCurricularProposals.filter((p) => p.status === 'accepted');

  if (currentUser?.role !== 'principal') {
    return <UnauthorizedPage />;
  }

  return (
    <div className="space-y-6">
      {/* Toast Notification */}
      {toastMessage && (
        <div className="fixed bottom-6 right-6 z-50 bg-navy-900 text-white px-4 py-3 rounded-xl shadow-modal border border-teal-500/40 flex items-center gap-2.5 text-xs animate-bounce">
          <CheckCircle2 className="w-4 h-4 text-teal-400 shrink-0" />
          <span>{toastMessage}</span>
        </div>
      )}

      {/* Top Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 bg-white p-5 rounded-2xl border border-surface-border shadow-subtle">
        <div>
          <div className="flex items-center gap-2.5">
            <div className="p-2 bg-amber-500/10 text-amber-600 rounded-lg">
              <Clock className="w-5 h-5" />
            </div>
            <div>
              <h1 className="text-xl font-bold text-navy-900 tracking-tight">
                Time-Aware Pedagogical Engine
              </h1>
              <p className="text-xs text-content-secondary mt-0.5">
                NEP 2020 Dynamic Curriculum Compacting • Protecting Core Concept Mastery Against Calendar Disruptions
              </p>
            </div>
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-2.5">
          <Button
            variant="outline"
            size="md"
            onClick={() => setIsRecordModalOpen(true)}
            icon={<PlusCircle className="w-4 h-4 text-rose-600" />}
          >
            Record Lost Teaching Days
          </Button>

          <Button
            variant="teal"
            size="md"
            onClick={() => setIsCompressionModalOpen(true)}
            icon={<Sparkles className="w-4 h-4" />}
          >
            Preview Syllabus Compression
          </Button>
        </div>
      </div>

      {/* Signature Metric Bar & Calendar Horizon */}
      <Card>
        <CardHeader
          title="Instructional Time Budget & Calendar Horizon"
          subtitle="Real available instructional contact hours vs statutory syllabus requirements"
          action={
            <div className="flex items-center gap-2">
              <span className="text-xs text-content-secondary">Target Grade:</span>
              <span className="text-xs font-semibold text-navy-800 bg-surface-bg px-2.5 py-1 rounded-md border border-surface-border">
                Class 8-A • Mathematics
              </span>
            </div>
          }
        />
        <CardBody>
          <PacingProgressChart metrics={pacingMetrics} />
        </CardBody>
      </Card>

      {/* Middle Row: Lost Teaching Days Log & 60/40 Strategy Setting */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left (2 cols): Lost Teaching Days Breakdown */}
        <Card className="lg:col-span-2">
          <CardHeader
            title="Calendar Disruptions Log"
            subtitle={`Total ${pacingMetrics.totalLostDays} instructional days lost to non-academic public duties`}
            action={
              <Button
                variant="outline"
                size="sm"
                onClick={() => setIsRecordModalOpen(true)}
                icon={<PlusCircle className="w-3.5 h-3.5" />}
              >
                Log Disruption
              </Button>
            }
          />
          <CardBody className="p-0">
            <div className="divide-y divide-surface-border max-h-72 overflow-y-auto">
              {lostTeachingDays.map((item) => (
                <div
                  key={item.id}
                  className="p-3.5 hover:bg-surface-bg/50 transition-colors flex items-start justify-between gap-3 text-xs"
                >
                  <div className="flex items-start gap-2.5">
                    <span className="p-1.5 bg-rose-50 text-rose-700 rounded-md border border-rose-200 shrink-0 font-bold font-mono">
                      -{item.daysLost}d
                    </span>
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="font-semibold text-content-primary">{item.reason}</span>
                        <span className="text-[10px] text-content-muted">{item.date}</span>
                      </div>
                      <p className="text-content-secondary text-[11px] mt-0.5 leading-relaxed">
                        {item.notes}
                      </p>
                      <p className="text-[10px] text-content-muted mt-1">
                        Reported by: {item.recordedBy}
                      </p>
                    </div>
                  </div>
                  <Badge variant="danger" size="sm" className="shrink-0">
                    Lost Contact Hours
                  </Badge>
                </div>
              ))}
            </div>
          </CardBody>
        </Card>

        {/* Right (1 col): Configurable 60/40 Strategy Panel */}
        <Card>
          <CardHeader
            title="Curriculum Compacting Config"
            subtitle="Illustrative 60/40 Core vs Supplementary Ratio"
            action={<Sliders className="w-4 h-4 text-teal-600" />}
          />
          <CardBody className="space-y-4">
            <div>
              <div className="flex justify-between items-center text-xs font-semibold mb-1.5">
                <span className="text-teal-700">Protected Core: {coreRatio}%</span>
                <span className="text-amber-700">Flipped Supp: {100 - coreRatio}%</span>
              </div>
              <input
                type="range"
                min="50"
                max="80"
                step="5"
                value={coreRatio}
                onChange={(e) => setCoreRatio(Number(e.target.value))}
                className="w-full accent-teal-600 cursor-pointer"
              />
              <div className="flex justify-between text-[10px] text-content-muted mt-1">
                <span>50% (High Agility)</span>
                <span>60% (NEP Default)</span>
                <span>80% (Strict Contact)</span>
              </div>
            </div>

            <div className="p-3 bg-surface-bg rounded-xl border border-surface-border text-xs space-y-2">
              <div className="flex items-start gap-2 text-content-primary font-medium">
                <ShieldCheck className="w-4 h-4 text-teal-600 shrink-0 mt-0.5" />
                <span>Pedagogical Safeguard Rule</span>
              </div>
              <p className="text-[11px] text-content-secondary leading-relaxed">
                Core competencies represent non-negotiable foundational learning objectives. They are never discarded. When schedule deficits emerge, supplementary material is reassigned to guided flipped homework with parent verification rubrics.
              </p>
            </div>

            <Button
              variant="outline"
              size="sm"
              className="w-full"
              onClick={() => setIsCompressionModalOpen(true)}
              icon={<Sparkles className="w-3.5 h-3.5 text-teal-600" />}
            >
              Simulate Pacing with {coreRatio}/{100 - coreRatio} Strategy
            </Button>
          </CardBody>
        </Card>
      </div>

      {/* Cross-Curricular Integration Opportunities */}
      <Card>
        <CardHeader
          title="Cross-Curricular Synergy Detection"
          subtitle="Automated identification of multi-subject learning objectives to recover instructional periods"
          action={
            <Badge variant="teal" size="sm">
              {acceptedProposals.length} Applied • {pendingProposals.length} Pending
            </Badge>
          }
        />
        <CardBody className="space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {crossCurricularProposals.map((prop) => (
              <div
                key={prop.id}
                className={`p-4 rounded-xl border transition-all text-xs flex flex-col justify-between ${
                  prop.status === 'accepted'
                    ? 'bg-teal-50/40 border-teal-200'
                    : prop.status === 'rejected'
                    ? 'bg-gray-50 border-gray-200 opacity-60'
                    : 'bg-white border-surface-border hover:border-teal-300'
                }`}
              >
                <div>
                  <div className="flex items-start justify-between gap-2">
                    <h4 className="font-bold text-navy-900 text-sm">{prop.title}</h4>
                    <span className="font-mono text-teal-800 bg-teal-100/80 px-2 py-0.5 rounded font-bold shrink-0">
                      +{prop.timeSavedHours}h Saved
                    </span>
                  </div>

                  {/* Subject Badges */}
                  <div className="flex flex-wrap items-center gap-1.5 my-2">
                    {prop.subjectNames.map((s) => (
                      <Badge key={s} variant="outline" size="sm">
                        {s}
                      </Badge>
                    ))}
                    <Badge variant="teal" size="sm">
                      {prop.varkModality}
                    </Badge>
                    <Badge variant="info" size="sm">
                      Bloom: {prop.bloomLevel}
                    </Badge>
                  </div>

                  <p className="text-content-secondary text-[11px] leading-relaxed mb-3">
                    {prop.activity}
                  </p>

                  <div className="bg-surface-bg/80 p-2.5 rounded-lg border border-surface-border space-y-1">
                    <p className="text-[10px] font-semibold text-content-primary uppercase">Preserved Objectives:</p>
                    <ul className="list-disc list-inside text-[11px] text-content-secondary space-y-0.5">
                      {prop.learningObjectives.map((obj, i) => (
                        <li key={i} className="line-clamp-1">
                          {obj}
                        </li>
                      ))}
                    </ul>
                  </div>
                </div>

                <div className="mt-4 pt-3 border-t border-surface-border flex items-center justify-between">
                  <span className="text-[11px] font-medium text-content-secondary">
                    Status:{' '}
                    <span
                      className={`font-semibold capitalize ${
                        prop.status === 'accepted'
                          ? 'text-teal-700'
                          : prop.status === 'rejected'
                          ? 'text-gray-500'
                          : 'text-amber-700'
                      }`}
                    >
                      {prop.status}
                    </span>
                  </span>

                  {prop.status === 'pending' && (
                    <div className="flex items-center gap-2">
                      <button
                        onClick={() => rejectCrossCurricularProposal(prop.id)}
                        className="p-1.5 text-content-secondary hover:text-rose-600 hover:bg-rose-50 rounded-lg transition-colors"
                        title="Decline proposal"
                      >
                        <XCircle className="w-4 h-4" />
                      </button>
                      <button
                        onClick={() => {
                          acceptCrossCurricularProposal(prop.id);
                          showToast(`Merged "${prop.title}" — saved ${prop.timeSavedHours} hours!`);
                        }}
                        className="px-3 py-1 bg-teal-500 hover:bg-teal-600 text-white rounded-lg text-xs font-semibold flex items-center gap-1 transition-colors shadow-xs"
                      >
                        <CheckCircle2 className="w-3.5 h-3.5" />
                        <span>Accept Proposal</span>
                      </button>
                    </div>
                  )}

                  {prop.status === 'accepted' && (
                    <span className="text-teal-700 font-semibold flex items-center gap-1">
                      <CheckCircle2 className="w-4 h-4" /> Integrated
                    </span>
                  )}
                </div>
              </div>
            ))}
          </div>
        </CardBody>
      </Card>

      {/* Recalibration & Reassessment Cycles (Every 4-6 Weeks) */}
      <Card>
        <CardHeader
          title="Periodic Reassessment & Recalibration Horizon"
          subtitle="Tracking competency baseline progress every 4-6 weeks to iteratively adjust curriculum pacing"
          action={
            <div className="flex items-center gap-1.5 text-xs text-teal-700 font-semibold">
              <RefreshCw className="w-3.5 h-3.5" />
              <span>Adaptive Recalibration</span>
            </div>
          }
        />
        <CardBody>
          <div className="grid grid-cols-1 sm:grid-cols-4 gap-4 text-xs">
            {/* Cycle 1 */}
            <div className="p-3.5 rounded-xl border border-surface-border bg-surface-bg/50">
              <div className="flex items-center justify-between">
                <span className="font-bold text-navy-800">Cycle 1 Baseline</span>
                <Badge variant="success" size="sm">Completed</Badge>
              </div>
              <p className="text-[11px] text-content-muted mt-0.5">July 28, 2026</p>
              <div className="mt-2.5 pt-2 border-t border-surface-border space-y-1">
                <div className="flex justify-between">
                  <span>Class Baseline:</span>
                  <span className="font-bold text-navy-800">62%</span>
                </div>
                <div className="text-[10px] text-content-secondary">Diagnostic baseline established across LU, CU, AU, CT.</div>
              </div>
            </div>

            {/* Cycle 2 */}
            <div className="p-3.5 rounded-xl border border-surface-border bg-surface-bg/50">
              <div className="flex items-center justify-between">
                <span className="font-bold text-navy-800">Cycle 2 Mid-Term</span>
                <Badge variant="success" size="sm">Graded</Badge>
              </div>
              <p className="text-[11px] text-content-muted mt-0.5">Sept 18, 2026</p>
              <div className="mt-2.5 pt-2 border-t border-surface-border space-y-1">
                <div className="flex justify-between">
                  <span>New Baseline:</span>
                  <span className="font-bold text-teal-700">72% (+10%)</span>
                </div>
                <div className="text-[10px] text-content-secondary">Application (AU) and Concept (CU) demonstrated marked improvement.</div>
              </div>
            </div>

            {/* Cycle 3 */}
            <div className="p-3.5 rounded-xl border-2 border-teal-500 bg-teal-50/30">
              <div className="flex items-center justify-between">
                <span className="font-bold text-teal-900">Cycle 3 Pacing Check</span>
                <Badge variant="teal" size="sm">Scheduled</Badge>
              </div>
              <p className="text-[11px] text-teal-700 font-medium mt-0.5">Oct 24, 2026 (In 12 days)</p>
              <div className="mt-2.5 pt-2 border-t border-teal-200 space-y-1">
                <div className="flex justify-between text-teal-900">
                  <span>Focus Areas:</span>
                  <span className="font-semibold">AU & CT</span>
                </div>
                <div className="text-[10px] text-teal-800">Mensuration and data interpretation exit tickets.</div>
              </div>
            </div>

            {/* Cycle 4 */}
            <div className="p-3.5 rounded-xl border border-surface-border bg-surface-bg/30 opacity-70">
              <div className="flex items-center justify-between">
                <span className="font-bold text-content-primary">Cycle 4 Summative</span>
                <Badge variant="outline" size="sm">Upcoming</Badge>
              </div>
              <p className="text-[11px] text-content-muted mt-0.5">Dec 15, 2026</p>
              <div className="mt-2.5 pt-2 border-t border-surface-border space-y-1">
                <div className="flex justify-between">
                  <span>Target Mastery:</span>
                  <span className="font-bold">85%+</span>
                </div>
                <div className="text-[10px] text-content-secondary">Comprehensive end-of-term competency certification.</div>
              </div>
            </div>
          </div>
        </CardBody>
      </Card>

      {/* Record Lost Teaching Days Modal */}
      <Modal
        isOpen={isRecordModalOpen}
        onClose={() => setIsRecordModalOpen(false)}
        title="Record Lost Instructional Teaching Days"
        subtitle="Log calendar disruptions so the Time-Aware Engine can protect core competency pacing"
        maxWidth="md"
        footer={
          <div className="flex items-center justify-end gap-2.5 w-full">
            <Button variant="secondary" size="md" onClick={() => setIsRecordModalOpen(false)}>
              Cancel
            </Button>
            <Button variant="danger" size="md" onClick={handleRecordLostDay}>
              Deduct & Recalculate Buffer
            </Button>
          </div>
        }
      >
        <form onSubmit={handleRecordLostDay} className="space-y-4 text-xs">
          <div>
            <label className="block font-semibold text-content-primary mb-1">
              Date of Disruption
            </label>
            <input
              type="date"
              value={lostDate}
              onChange={(e) => setLostDate(e.target.value)}
              required
              className="w-full px-3 py-2 bg-surface-bg/60 border border-surface-border rounded-lg text-sm text-content-primary focus:outline-none focus:border-teal-500"
            />
          </div>

          <div>
            <label className="block font-semibold text-content-primary mb-1">
              Reason / Duty Mandate
            </label>
            <select
              value={lostReason}
              onChange={(e) => setLostReason(e.target.value as any)}
              className="w-full px-3 py-2 bg-surface-bg/60 border border-surface-border rounded-lg text-sm text-content-primary focus:outline-none focus:border-teal-500"
            >
              <option value="Election Duties">Election Duties (Polling setup & polling officer training)</option>
              <option value="Census Duties">Census & Household Verification Drive</option>
              <option value="Teacher Training">Mandatory State Board Pedagogy Training</option>
              <option value="Health Drive">District Health & Immunization Camp</option>
              <option value="Extreme Weather">Extreme Weather (Heatwave / Monsoon Floods Closure)</option>
              <option value="Local Festival">Local Festival / Regional Holiday</option>
              <option value="Administrative Work">Administrative / Examination Inspection Duty</option>
            </select>
          </div>

          <div>
            <label className="block font-semibold text-content-primary mb-1">
              Number of Instructional Days Lost
            </label>
            <input
              type="number"
              min="1"
              max="15"
              value={lostDaysCount}
              onChange={(e) => setLostDaysCount(Number(e.target.value))}
              required
              className="w-full px-3 py-2 bg-surface-bg/60 border border-surface-border rounded-lg text-sm text-content-primary focus:outline-none focus:border-teal-500"
            />
          </div>

          <div>
            <label className="block font-semibold text-content-primary mb-1">
              Official Directive / Reference Notes
            </label>
            <textarea
              rows={3}
              value={lostNotes}
              onChange={(e) => setLostNotes(e.target.value)}
              placeholder="e.g. State Election Commission circular #SEC/2026/894. All senior teachers deployed."
              className="w-full px-3 py-2 bg-surface-bg/60 border border-surface-border rounded-lg text-xs text-content-primary focus:outline-none focus:border-teal-500"
            />
          </div>

          <div className="p-3 bg-rose-50 border border-rose-200 rounded-lg text-[11px] text-rose-800 leading-relaxed">
            <strong>Time-Aware Engine Notice:</strong> Deducting instructional contact days will update the live pacing deficit. LumenEIOS will automatically suggest cross-curricular project options to maintain mastery without cutting core competencies.
          </div>
        </form>
      </Modal>

      {/* Syllabus Compression Preview Modal */}
      <CompressionPreviewModal
        isOpen={isCompressionModalOpen}
        onClose={() => setIsCompressionModalOpen(false)}
        proposal={compressionProposal}
        onAcceptPlan={handleAcceptPlan}
      />
    </div>
  );
};

