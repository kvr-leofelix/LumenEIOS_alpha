import React, { useState } from 'react';
import { useData } from '../../context/DataContext';
import { useAuth } from '../../context/AuthContext';
import { Card, CardHeader, CardBody } from '../../components/common/Card';
import { Button } from '../../components/common/Button';
import { Badge } from '../../components/common/Badge';
import { CompetencyRadarChart } from '../../components/charts/CompetencyRadarChart';
import {
  Users,
  GraduationCap,
  HeartHandshake,
  CheckCircle2,
  Calendar,
  Download,
  BookOpen,
  Sparkles,
  TrendingUp,
} from 'lucide-react';

export const ParentDashboard: React.FC = () => {
  const { students } = useData();
  const { currentUser } = useAuth();

  // Meera Patel's linked children: Aarav Patel & Ananya Patel
  const linkedChildren = students.filter(
    (s) => s.id === 'user-student-1' || s.id === 'student-ananya'
  );

  const [selectedChildId, setSelectedChildId] = useState(linkedChildren[0]?.id || 'user-student-1');
  const [toast, setToast] = useState<string | null>(null);

  const activeChild = linkedChildren.find((c) => c.id === selectedChildId) || linkedChildren[0];

  const handlePrintReport = () => {
    setToast(`Generating official NEP 2020 Progress Transcript for ${activeChild.name}...`);
    setTimeout(() => {
      window.print();
      setToast(null);
    }, 800);
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

      {/* Header and Child Switcher */}
      <div className="bg-white p-5 rounded-2xl border border-surface-border shadow-subtle flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-xl font-bold text-navy-900 tracking-tight">
              Parent Portal • Family Learning Progress
            </h1>
            <Badge variant="teal" size="sm">
              NEP Holistic Card
            </Badge>
          </div>
          <p className="text-xs text-content-secondary mt-1">
            Guardian: <strong className="text-navy-900">{currentUser?.name || 'Meera Patel'}</strong> • Sunrise Public Campus
          </p>
        </div>

        {/* Linked Children Toggle */}
        <div className="flex items-center gap-2">
          <span className="text-xs font-semibold text-content-secondary">Viewing Child:</span>
          {linkedChildren.map((ch) => (
            <button
              key={ch.id}
              onClick={() => setSelectedChildId(ch.id)}
              className={`px-3.5 py-1.5 rounded-lg text-xs font-semibold transition-all ${
                selectedChildId === ch.id
                  ? 'bg-navy-800 text-white shadow-sm'
                  : 'bg-surface-bg text-content-secondary hover:text-content-primary'
              }`}
            >
              {ch.name} ({ch.className})
            </button>
          ))}
        </div>
      </div>

      {/* Reassuring Child Growth Banner */}
      <div className="p-5 rounded-2xl bg-gradient-to-r from-teal-50 via-white to-surface-bg border border-teal-200/80 shadow-subtle flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div className="space-y-1">
          <span className="text-[11px] font-bold uppercase tracking-wider text-teal-800 flex items-center gap-1.5">
            <Sparkles className="w-4 h-4 text-teal-600" />
            <span>Academic Well-Being Summary</span>
          </span>
          <h2 className="text-lg font-bold text-navy-900">
            {activeChild.name} is making steady, confident progress in Grade 8
          </h2>
          <p className="text-xs text-content-secondary max-w-2xl leading-relaxed">
            Attendance is strong at <strong className="text-navy-900">{activeChild.attendancePct}%</strong>. In Mathematics, foundational concepts are well-understood. Practical word-problem practice is currently reinforced with engaging home activities.
          </p>
        </div>

        <Button
          variant="outline"
          size="sm"
          className="shrink-0"
          onClick={handlePrintReport}
          icon={<Download className="w-3.5 h-3.5 text-teal-700" />}
        >
          Download Holistic Card
        </Button>
      </div>

      {/* Plain Language Competencies & Radar */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Radar */}
        <Card>
          <CardHeader
            title="Skill Mastery Growth"
            subtitle={`${activeChild.name}'s four learning dimensions`}
          />
          <CardBody>
            <CompetencyRadarChart
              current={activeChild.competencies}
              baseline={activeChild.baselineCompetencies}
              benchmarkName="Term Baseline"
              height={240}
            />
            <div className="mt-3 text-center text-xs font-semibold text-teal-800">
              Composite Baseline: {activeChild.competencies.overall}%
            </div>
          </CardBody>
        </Card>

        {/* Plain Language Explanations */}
        <div className="lg:col-span-2 space-y-3">
          <h3 className="text-xs font-bold text-navy-900 uppercase tracking-wider">
            Competencies in Plain Language
          </h3>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3.5 text-xs">
            <div className="p-4 bg-white rounded-xl border border-surface-border space-y-1">
              <span className="font-bold text-blue-700 flex items-center justify-between">
                <span>1. Language Understanding (LU)</span>
                <span>{activeChild.competencies.LU}%</span>
              </span>
              <p className="text-content-secondary text-[11px] leading-relaxed">
                How well {activeChild.name} reads and understands technical terms and instructions in math and science questions.
              </p>
            </div>

            <div className="p-4 bg-white rounded-xl border border-surface-border space-y-1">
              <span className="font-bold text-emerald-700 flex items-center justify-between">
                <span>2. Concept Understanding (CU)</span>
                <span>{activeChild.competencies.CU}%</span>
              </span>
              <p className="text-content-secondary text-[11px] leading-relaxed">
                Grasp of the underlying core principles and formulas without relying on rote memorization.
              </p>
            </div>

            <div className="p-4 bg-white rounded-xl border border-surface-border space-y-1">
              <span className="font-bold text-amber-700 flex items-center justify-between">
                <span>3. Application in Real Life (AU)</span>
                <span>{activeChild.competencies.AU}%</span>
              </span>
              <p className="text-content-secondary text-[11px] leading-relaxed">
                Applying knowledge to solve practical scenarios (e.g. estimating volumes, cooking ratios, household budgeting).
              </p>
            </div>

            <div className="p-4 bg-white rounded-xl border border-surface-border space-y-1">
              <span className="font-bold text-indigo-700 flex items-center justify-between">
                <span>4. Critical Thinking (CT)</span>
                <span>{activeChild.competencies.CT}%</span>
              </span>
              <p className="text-content-secondary text-[11px] leading-relaxed">
                Ability to evaluate logical claims, question assumptions, and interpret charts thoughtfully.
              </p>
            </div>
          </div>
        </div>
      </div>

      {/* Teacher Remarks and Home Learning Suggestions */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Remarks */}
        <Card>
          <CardHeader
            title="Educator Observations & Feedback"
            subtitle="From TGT Lead: Vikram Sengupta"
          />
          <CardBody className="space-y-3 text-xs leading-relaxed text-content-secondary">
            <p className="p-3.5 bg-surface-bg rounded-xl border border-surface-border italic">
              "{activeChild.name} actively participates in class discussions and shows strong logical reasoning. In recent geometry assignments, step-by-step written justifications were clear and accurate. Continue encouraging daily reading to build speed in multi-part word problems."
            </p>
            <div className="flex items-center justify-between text-[11px] text-content-muted">
              <span>Verified: Cycle 2 Mid-Term Review</span>
              <span>Updated 3 days ago</span>
            </div>
          </CardBody>
        </Card>

        {/* Home Learning Suggestions */}
        <Card>
          <CardHeader
            title="Suggested Supportive Home Activities"
            subtitle="Simple, positive family activities to build everyday confidence"
          />
          <CardBody className="space-y-2.5 text-xs text-content-secondary">
            <div className="p-2.5 bg-teal-50/50 rounded-lg border border-teal-200/60 flex items-start gap-2">
              <CheckCircle2 className="w-4 h-4 text-teal-600 shrink-0 mt-0.5" />
              <span>
                <strong>Kitchen Mensuration:</strong> Involve {activeChild.name} when baking or cooking to measure volumes using liters and milliliters.
              </span>
            </div>

            <div className="p-2.5 bg-teal-50/50 rounded-lg border border-teal-200/60 flex items-start gap-2">
              <CheckCircle2 className="w-4 h-4 text-teal-600 shrink-0 mt-0.5" />
              <span>
                <strong>News Graph Discussion:</strong> Look at rainfall or temperature charts in the newspaper together and ask what trends they notice.
              </span>
            </div>

            <div className="p-2.5 bg-teal-50/50 rounded-lg border border-teal-200/60 flex items-start gap-2">
              <CheckCircle2 className="w-4 h-4 text-teal-600 shrink-0 mt-0.5" />
              <span>
                <strong>Positive Encouragement:</strong> Praise effort and reasoning rather than just quick answers to foster a growth mindset.
              </span>
            </div>
          </CardBody>
        </Card>
      </div>
    </div>
  );
};

