import React from 'react';
import { useNavigate } from 'react-router-dom';
import { useData } from '../../context/DataContext';
import { useAuth } from '../../context/AuthContext';
import { calculateAverageCompetencies, calculateTimeAwarePacing } from '../../lib/calculations';
import { KPICard } from '../../components/common/KPICard';
import { Card, CardHeader, CardBody } from '../../components/common/Card';
import { Button } from '../../components/common/Button';
import { Badge } from '../../components/common/Badge';
import { CompetencyRadarChart } from '../../components/charts/CompetencyRadarChart';
import { ClassHeatmap } from '../../components/charts/ClassHeatmap';
import {
  Users,
  BookOpen,
  Clock,
  Sparkles,
  AlertTriangle,
  ScanLine,
  CheckCircle2,
  Calendar,
  ArrowRight,
  TrendingUp,
  FileCheck,
} from 'lucide-react';

export const TeacherDashboard: React.FC = () => {
  const { classes, students, curriculumDays, lostTeachingDays, assessments, homeworkRemediations } = useData();
  const { currentUser } = useAuth();
  const navigate = useNavigate();

  // Class 8-A context
  const targetClass = classes.find((c) => c.id === 'class-8a') || classes[0];
  const classStudents = students.filter((s) => s.classId === targetClass.id);
  const avgCompetencies = calculateAverageCompetencies(classStudents);

  const baselineComparison = {
    LU: 68,
    CU: 70,
    AU: 62,
    CT: 58,
    overall: 65,
  };

  const pacing = calculateTimeAwarePacing(curriculumDays, lostTeachingDays, 180, 104);

  return (
    <div className="space-y-6">
      {/* Teacher Welcome & Pacing Deficit Banner */}
      <div className="bg-white p-5 rounded-2xl border border-surface-border shadow-subtle flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-xl font-bold text-navy-900 tracking-tight">
              Namaste, {currentUser?.name || 'Vikram Sengupta'}
            </h1>
            <Badge variant="teal" size="sm">
              TGT Lead Educator
            </Badge>
          </div>
          <p className="text-xs text-content-secondary mt-1">
            Assigned: Class 8-A (32 students) & Class 9-B (28 students) • Sunrise Public Campus
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2.5">
          <Button
            variant="outline"
            size="sm"
            onClick={() => navigate('/upload')}
            icon={<ScanLine className="w-4 h-4 text-teal-600" />}
          >
            Upload Scanned Sheets
          </Button>
        </div>
      </div>

      {/* Pacing Alert Banner if behind */}
      {pacing.riskStatus === 'high' && (
        <div className="p-4 rounded-xl bg-gradient-to-r from-rose-50 to-amber-50 border border-rose-200 flex flex-col sm:flex-row sm:items-center justify-between gap-3 text-xs">
          <div className="flex items-start gap-3">
            <AlertTriangle className="w-5 h-5 text-rose-600 shrink-0 mt-0.5" />
            <div>
              <p className="font-bold text-rose-950">
                Instructional Pacing Alert: Calendar Deficit of {Math.abs(pacing.pacingBuffer)} Days
              </p>
              <p className="text-rose-800 mt-0.5 leading-relaxed">
                16 lost days (elections, extreme weather, health camp) have shortened remaining teaching periods. Core concept mastery is at risk if linear teaching continues.
              </p>
            </div>
          </div>
        </div>
      )}

      {/* KPI Cards Row */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <KPICard
          title="Assigned Students"
          value={classStudents.length}
          subtitle="Class 8-A Active Roster"
          icon={<Users className="w-5 h-5 text-navy-800" />}
          iconBg="bg-navy-50"
          onClick={() => navigate('/teacher/classes')}
        />
        <KPICard
          title="Class Baseline (NEP)"
          value={`${avgCompetencies.overall}%`}
          subtitle="+7% growth from Cycle 1 baseline"
          icon={<TrendingUp className="w-5 h-5 text-teal-600" />}
          iconBg="bg-teal-50"
          trend={{ value: '+7%', isPositive: true, label: 'vs Cycle 1' }}
        />
        <KPICard
          title="Instructional Days Left"
          value={`${pacing.remainingInstructionalDays}d`}
          subtitle={`${pacing.totalLostDays} days lost to official duties`}
          icon={<Clock className="w-5 h-5 text-amber-600" />}
          iconBg="bg-amber-50"
        />
        <KPICard
          title="Differentiated Remediations"
          value={homeworkRemediations.length}
          subtitle="Targeted LU/AU assignments"
          icon={<Sparkles className="w-5 h-5 text-emerald-600" />}
          iconBg="bg-emerald-50"
          onClick={() => navigate('/teacher/remediation')}
        />
      </div>

      {/* Middle Grid: Competency Radar & Quick Action Panels */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left (1 col): Class 8-A Competency Radar */}
        <Card>
          <CardHeader
            title="Competency Baseline Profile"
            subtitle="Comparing Class 8-A current vs Cycle 1 baseline"
            action={
              <Badge variant="teal" size="sm">
                4-Dimensional
              </Badge>
            }
          />
          <CardBody>
            <CompetencyRadarChart
              current={avgCompetencies}
              baseline={baselineComparison}
              benchmarkName="Cycle 1 Baseline"
              height={260}
            />
            <div className="mt-3 pt-3 border-t border-surface-border grid grid-cols-2 gap-2 text-xs text-center">
              <div className="p-2 bg-surface-bg rounded-lg">
                <span className="text-content-secondary text-[11px] block">Language (LU)</span>
                <span className="font-bold text-navy-800">{avgCompetencies.LU}%</span>
              </div>
              <div className="p-2 bg-surface-bg rounded-lg">
                <span className="text-content-secondary text-[11px] block">Concept (CU)</span>
                <span className="font-bold text-emerald-700">{avgCompetencies.CU}%</span>
              </div>
              <div className="p-2 bg-surface-bg rounded-lg">
                <span className="text-content-secondary text-[11px] block">Application (AU)</span>
                <span className="font-bold text-amber-700">{avgCompetencies.AU}%</span>
              </div>
              <div className="p-2 bg-surface-bg rounded-lg">
                <span className="text-content-secondary text-[11px] block">Critical Thinking (CT)</span>
                <span className="font-bold text-indigo-700">{avgCompetencies.CT}%</span>
              </div>
            </div>
          </CardBody>
        </Card>

        {/* Right (2 cols): 180-Day Curriculum Pacing & Quick Navigation */}
        <div className="lg:col-span-2 space-y-6">
          <Card>
            <CardHeader
              title="180-Day Daily Micro-Curriculum Progress"
              subtitle={`Currently at Day ${pacing.currentDay} of 180 • Chapter: Mensuration & Surface Areas`}
              action={
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => navigate('/teacher/curriculum-180')}
                  icon={<Calendar className="w-3.5 h-3.5" />}
                >
                  View 180-Day Timeline
                </Button>
              }
            />
            <CardBody className="space-y-4">
              <div className="p-3.5 bg-surface-bg rounded-xl border border-surface-border flex items-center justify-between text-xs">
                <div>
                  <span className="text-teal-700 font-bold block">Today's Lesson Plan (Day 104)</span>
                  <p className="text-content-primary font-medium mt-0.5">
                    Mensuration: Calculating Volumes of Composite Cylinders and Water Cisterns
                  </p>
                  <p className="text-content-secondary text-[11px] mt-0.5">
                    Modality: Visual • Bloom: Apply • Classification: Core Concept (Protected)
                  </p>
                </div>
                <Badge variant="success" size="sm">
                  Active
                </Badge>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 text-xs">
                <div className="p-3 rounded-lg border border-surface-border bg-white">
                  <span className="text-content-secondary text-[11px] block">Protected Core Topics</span>
                  <span className="font-bold text-lg text-teal-800">{pacing.coreConceptsRemaining} Remaining</span>
                </div>
                <div className="p-3 rounded-lg border border-surface-border bg-white">
                  <span className="text-content-secondary text-[11px] block">Supplementary Topics</span>
                  <span className="font-bold text-lg text-amber-800">{pacing.supplementaryTopicsRemaining} Remaining</span>
                </div>
                <div className="p-3 rounded-lg border border-surface-border bg-white">
                  <span className="text-content-secondary text-[11px] block">Pacing Status</span>
                  <span className="font-bold text-lg text-rose-700">{pacing.riskLabel}</span>
                </div>
              </div>
            </CardBody>
          </Card>

          {/* Quick Shortcuts */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div
              onClick={() => navigate('/teacher/assessments-beta')}
              className="p-4 bg-white rounded-xl border border-surface-border hover:border-teal-400 hover:shadow-card cursor-pointer transition-all flex items-center justify-between"
            >
              <div className="flex items-center gap-3">
                <div className="p-2.5 bg-teal-50 text-teal-600 rounded-lg">
                  <BookOpen className="w-5 h-5" />
                </div>
                <div>
                  <h4 className="font-semibold text-content-primary text-sm">AI Question Studio Beta</h4>
                  <p className="text-xs text-content-secondary">Generate questions from a chapter PDF</p>
                </div>
              </div>
              <ArrowRight className="w-4 h-4 text-content-muted" />
            </div>

            <div
              onClick={() => navigate('/upload')}
              className="p-4 bg-white rounded-xl border border-surface-border hover:border-teal-400 hover:shadow-card cursor-pointer transition-all flex items-center justify-between"
            >
              <div className="flex items-center gap-3">
                <div className="p-2.5 bg-indigo-50 text-indigo-600 rounded-lg">
                  <ScanLine className="w-5 h-5" />
                </div>
                <div>
                  <h4 className="font-semibold text-content-primary text-sm">Upload (OCR)</h4>
                  <p className="text-xs text-content-secondary">Verify offline handwritten answer sheets</p>
                </div>
              </div>
              <ArrowRight className="w-4 h-4 text-content-muted" />
            </div>
          </div>
        </div>
      </div>

      {/* Classroom Competency Heatmap */}
      <Card>
        <CardHeader
          title="Class 8-A Competency Heatmap Matrix"
          subtitle="Student-by-student mastery across Language (LU), Concept (CU), Application (AU), and Critical Thinking (CT)"
          action={
            <Button
              variant="outline"
              size="sm"
              onClick={() => navigate('/teacher/classes')}
              icon={<Users className="w-3.5 h-3.5" />}
            >
              Full Roster Detail
            </Button>
          }
        />
        <CardBody>
          <ClassHeatmap
            students={classStudents}
            onTriggerRemediation={(st) => {
              navigate('/teacher/remediation');
            }}
          />
        </CardBody>
      </Card>
    </div>
  );
};

