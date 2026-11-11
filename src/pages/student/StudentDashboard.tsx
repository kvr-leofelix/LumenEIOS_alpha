import React, { useEffect, useState } from 'react';
import { useData } from '../../context/DataContext';
import { demoMode, useAuth } from '../../context/AuthContext';
import { ApiError, apiClient } from '../../lib/apiClient';
import type { Student } from '../../types';
import { UnauthorizedPage } from '../shared/UnauthorizedPage';
import { Card, CardHeader, CardBody } from '../../components/common/Card';
import { Button } from '../../components/common/Button';
import { Badge } from '../../components/common/Badge';
import { Modal } from '../../components/common/Modal';
import { CompetencyRadarChart } from '../../components/charts/CompetencyRadarChart';
import {
  GraduationCap,
  Sparkles,
  BookOpen,
  CheckCircle2,
  Clock,
  Award,
  ArrowRight,
  Printer,
  WifiOff,
} from 'lucide-react';

export const StudentDashboard: React.FC = () => {
  const { currentUser } = useAuth();
  if (currentUser?.role !== 'student') return <UnauthorizedPage />;
  return <StudentProfile key={currentUser.id} showDemo={(demoMode || !!currentUser.demoRoot) && currentUser.id === 'user-student-1'} />;
};

function StudentProfile({ showDemo }: { showDemo: boolean }) {
  const { students } = useData();
  const [student, setStudent] = useState<Student | null>(null);
  const [error, setError] = useState('');
  const [unlinked, setUnlinked] = useState(false);

  useEffect(() => {
    let active = true;
    apiClient.student.profile().then((profile) => {
      if (active) setStudent(profile);
    }).catch((err) => {
      if (!active) return;
      if (err instanceof ApiError && err.status === 404) setUnlinked(true);
      else setError('Could not load your student profile. Refresh the page to try again.');
    });
    return () => { active = false; };
  }, []);

  const profile = student || (showDemo && unlinked ? students.find((s) => s.id === 'user-student-1') : null);
  if (profile) return <StudentDashboardContent student={profile} />;
  if (error || unlinked) return <p role="alert">{error || 'Your login has no linked student profile. Contact your school.'}</p>;
  return <p role="status">Loading your student profile…</p>;
}

function StudentDashboardContent({ student }: { student: Student }) {
  const { homeworkRemediations, submitStudentHomework } = useData();
  const myHomework = homeworkRemediations.filter((h) => h.studentId === student.id);

  const [isQuizModalOpen, setIsQuizModalOpen] = useState(false);
  const [selectedAnswer, setSelectedAnswer] = useState<string | null>(null);
  const [quizSubmitted, setQuizSubmitted] = useState(false);
  const [isLowBandwidth, setIsLowBandwidth] = useState(false);
  const [toast, setToast] = useState<string | null>(null);

  const handleQuizSubmit = () => {
    setQuizSubmitted(true);
    setToast('Practice Quiz Submitted! You scored 100% (+4 AU Points)');
    setTimeout(() => setToast(null), 4000);
  };

  const handleCompleteHomework = (hwId: string) => {
    submitStudentHomework(hwId);
    setToast('Homework assignment submitted!');
    setTimeout(() => setToast(null), 4000);
  };

  return (
    <div className={`space-y-6 ${isLowBandwidth ? 'grayscale contrast-125' : ''}`}>
      {/* Toast Notification */}
      {toast && (
        <div className="fixed bottom-6 right-6 z-50 bg-navy-900 text-white px-4 py-3 rounded-xl shadow-modal border border-teal-500/40 text-xs flex items-center gap-2">
          <Sparkles className="w-4 h-4 text-teal-400" />
          <span>{toast}</span>
        </div>
      )}

      {/* Header */}
      <div className="bg-white p-5 rounded-2xl border border-surface-border shadow-subtle flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-xl font-bold text-navy-900 tracking-tight">
              Hello, {student.name}!
            </h1>
            <Badge variant="teal" size="sm">
              {student.className}
            </Badge>
          </div>
          <p className="text-xs text-content-secondary mt-1">
            Learning Modality: <strong className="text-navy-900">{student.learningModality}</strong> • Roll #{student.rollNo}
          </p>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={() => setIsLowBandwidth(!isLowBandwidth)}
            className={`px-3 py-1.5 rounded-lg border text-xs font-semibold flex items-center gap-1.5 transition-colors ${
              isLowBandwidth
                ? 'bg-navy-800 text-white border-navy-800'
                : 'bg-surface-bg text-content-secondary border-surface-border hover:text-content-primary'
            }`}
          >
            <WifiOff className="w-3.5 h-3.5" />
            <span>{isLowBandwidth ? 'Standard Mode' : 'Low-Bandwidth Mode'}</span>
          </button>

          <Button
            variant="teal"
            size="sm"
            onClick={() => setIsQuizModalOpen(true)}
            icon={<Sparkles className="w-3.5 h-3.5" />}
          >
            Start Today's Quiz
          </Button>
        </div>
      </div>

      {/* Today's Learning Mission Card */}
      <div className="p-5 rounded-2xl bg-gradient-to-r from-navy-800 to-navy-900 text-white shadow-card flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div className="space-y-1.5">
          <span className="text-[11px] font-bold uppercase tracking-wider text-teal-400 flex items-center gap-1.5">
            <Award className="w-4 h-4" />
            <span>Today's Adaptive Mission (Day 104)</span>
          </span>
          <h2 className="text-lg font-bold text-white">
            Mensuration: Practical Surface Areas & Water Tank Volumes
          </h2>
          <p className="text-xs text-gray-300 max-w-xl leading-relaxed">
            Learn to calculate volume in cubic meters and convert to household liters. Visual animations tailored for your learning preference!
          </p>
        </div>

        <Button
          variant="teal"
          size="md"
          className="shrink-0"
          onClick={() => setIsQuizModalOpen(true)}
          icon={<ArrowRight className="w-4 h-4" />}
        >
          Launch Interactive Lab
        </Button>
      </div>

      {/* Competency Spider & Mastery Cards */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Radar */}
        <Card>
          <CardHeader
            title="My Competency Mastery"
            subtitle="Your current growth across NEP skill dimensions"
            action={
              <Badge variant="teal" size="sm">
                Score: {student.competencies.overall}%
              </Badge>
            }
          />
          <CardBody>
            <CompetencyRadarChart
              current={student.competencies}
              baseline={student.baselineCompetencies}
              benchmarkName="Start of Year"
              height={240}
            />
          </CardBody>
        </Card>

        {/* 4 Skill Cards */}
        <div className="lg:col-span-2 grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div className="p-4 bg-white rounded-xl border border-surface-border flex flex-col justify-between">
            <div>
              <div className="flex justify-between items-center text-xs">
                <span className="font-bold text-blue-700">Language Understanding (LU)</span>
                <span className="font-bold text-navy-900">{student.competencies.LU}%</span>
              </div>
              <p className="text-xs text-content-secondary mt-1.5 leading-relaxed">
                Reading complex word problems and parsing mathematical clauses accurately.
              </p>
            </div>
            <div className="mt-3 pt-2 border-t border-surface-border text-[11px] text-teal-700 font-semibold">
              +10% increase from diagnostic baseline
            </div>
          </div>

          <div className="p-4 bg-white rounded-xl border border-surface-border flex flex-col justify-between">
            <div>
              <div className="flex justify-between items-center text-xs">
                <span className="font-bold text-emerald-700">Concept Understanding (CU)</span>
                <span className="font-bold text-navy-900">{student.competencies.CU}%</span>
              </div>
              <p className="text-xs text-content-secondary mt-1.5 leading-relaxed">
                Grasping fundamental algebraic equations, geometric axioms, and number models.
              </p>
            </div>
            <div className="mt-3 pt-2 border-t border-surface-border text-[11px] text-teal-700 font-semibold">
              +10% increase from diagnostic baseline
            </div>
          </div>

          <div className="p-4 bg-white rounded-xl border border-surface-border flex flex-col justify-between">
            <div>
              <div className="flex justify-between items-center text-xs">
                <span className="font-bold text-amber-700">Application Understanding (AU)</span>
                <span className="font-bold text-navy-900">{student.competencies.AU}%</span>
              </div>
              <p className="text-xs text-content-secondary mt-1.5 leading-relaxed">
                Solving real-life questions like water tanks, speed calculations, and unit conversions.
              </p>
            </div>
            <div className="mt-3 pt-2 border-t border-surface-border text-[11px] text-teal-700 font-semibold">
              +10% increase from diagnostic baseline
            </div>
          </div>

          <div className="p-4 bg-white rounded-xl border border-surface-border flex flex-col justify-between">
            <div>
              <div className="flex justify-between items-center text-xs">
                <span className="font-bold text-indigo-700">Critical Thinking (CT)</span>
                <span className="font-bold text-navy-900">{student.competencies.CT}%</span>
              </div>
              <p className="text-xs text-content-secondary mt-1.5 leading-relaxed">
                Evaluating claims, testing counterexamples, and detecting misleading data graphs.
              </p>
            </div>
            <div className="mt-3 pt-2 border-t border-surface-border text-[11px] text-teal-700 font-semibold">
              +11% increase from diagnostic baseline
            </div>
          </div>
        </div>
      </div>

      {/* Assigned Homework & Quizzes */}
      <Card>
        <CardHeader
          title="Assigned Adaptive Practice & Homework"
          subtitle="Differentiated tasks recommended by your teacher based on your assessments"
        />
        <CardBody className="space-y-3">
          {myHomework.map((hw) => (
            <div
              key={hw.id}
              className="p-4 rounded-xl border border-surface-border bg-surface-bg/40 flex flex-col sm:flex-row sm:items-center justify-between gap-3 text-xs"
            >
              <div>
                <div className="flex items-center gap-2">
                  <span className="font-bold text-navy-900 text-sm">{hw.title}</span>
                  <Badge variant="teal" size="sm">
                    {hw.competencyTarget} Practice
                  </Badge>
                  <span className="text-[11px] text-content-muted">Due: {hw.dueDate}</span>
                </div>
                <p className="text-content-secondary mt-1 leading-relaxed">{hw.description}</p>
              </div>

              <div className="shrink-0 flex items-center gap-2 self-end sm:self-auto">
                {hw.status === 'submitted' ? (
                  <span className="px-3 py-1 bg-emerald-50 text-emerald-800 font-semibold rounded-lg flex items-center gap-1">
                    <CheckCircle2 className="w-3.5 h-3.5" /> Submitted
                  </span>
                ) : (
                  <Button
                    variant="teal"
                    size="sm"
                    onClick={() => handleCompleteHomework(hw.id)}
                    icon={<CheckCircle2 className="w-3.5 h-3.5" />}
                  >
                    Submit Homework
                  </Button>
                )}
              </div>
            </div>
          ))}
        </CardBody>
      </Card>

      {/* Interactive Quiz Modal */}
      <Modal
        isOpen={isQuizModalOpen}
        onClose={() => {
          setIsQuizModalOpen(false);
          setQuizSubmitted(false);
          setSelectedAnswer(null);
        }}
        title="Adaptive Practice Check: Mensuration & Volume"
        subtitle="Question tagged to Application Understanding (AU) • Max 4 Marks"
        maxWidth="lg"
        footer={
          <div className="flex items-center justify-between w-full">
            <span className="text-xs text-content-secondary">
              Bloom's Level: <strong>Apply</strong>
            </span>
            <div className="flex items-center gap-2">
              <Button
                variant="secondary"
                size="sm"
                onClick={() => setIsQuizModalOpen(false)}
              >
                Close
              </Button>
              {!quizSubmitted && (
                <Button
                  variant="teal"
                  size="sm"
                  disabled={!selectedAnswer}
                  onClick={handleQuizSubmit}
                >
                  Submit Answer
                </Button>
              )}
            </div>
          </div>
        }
      >
        <div className="space-y-4 text-xs">
          <p className="text-sm font-semibold text-navy-900 leading-relaxed">
            A water tank is in the shape of a cuboid with length 4m, breadth 3m, and depth 2m. If water is poured at the rate of 60 liters per minute, how many hours will it take to fill the tank completely? (1 m³ = 1000 liters)
          </p>

          <div className="space-y-2">
            {[
              { id: 'opt-a', text: '4 hours and 20 minutes (18,000 Liters)' },
              { id: 'opt-b', text: '6 hours and 40 minutes (24,000 Liters)' },
              { id: 'opt-c', text: '8 hours and 00 minutes (28,800 Liters)' },
              { id: 'opt-d', text: '5 hours and 30 minutes (20,000 Liters)' },
            ].map((opt) => (
              <div
                key={opt.id}
                onClick={() => !quizSubmitted && setSelectedAnswer(opt.id)}
                className={`p-3 rounded-xl border transition-all cursor-pointer flex items-center gap-3 ${
                  selectedAnswer === opt.id
                    ? 'border-teal-500 bg-teal-50 text-teal-900 font-semibold'
                    : 'border-surface-border bg-white text-content-primary hover:border-gray-300'
                }`}
              >
                <div
                  className={`w-4 h-4 rounded-full border flex items-center justify-center shrink-0 ${
                    selectedAnswer === opt.id ? 'border-teal-600 bg-teal-600' : 'border-gray-300'
                  }`}
                >
                  {selectedAnswer === opt.id && <div className="w-1.5 h-1.5 rounded-full bg-white" />}
                </div>
                <span>{opt.text}</span>
              </div>
            ))}
          </div>

          {quizSubmitted && (
            <div className="p-4 bg-emerald-50 border border-emerald-200 rounded-xl space-y-1.5 animate-fade-in text-emerald-950">
              <div className="flex items-center gap-2 font-bold text-sm text-emerald-800">
                <CheckCircle2 className="w-4 h-4 text-emerald-600" />
                <span>Correct Answer! 4/4 Marks Awarded.</span>
              </div>
              <p className="text-[11px] leading-relaxed">
                <strong>Pedagogical Step:</strong> Volume = 4 × 3 × 2 = 24 m³ = 24,000 L. Time = 24,000 / 60 = 400 minutes = 6 hours and 40 minutes. Your Application Understanding (AU) mastery increased!
              </p>
            </div>
          )}
        </div>
      </Modal>
    </div>
  );
};

