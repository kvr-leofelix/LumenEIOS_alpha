import React, { useEffect, useMemo, useState } from 'react';
import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import { useAuth } from '../../context/AuthContext';
import { useData } from '../../context/DataContext';
import { CompetencyScores, Student, AssessmentResult } from '../../types';
import { LineChart as LineChartIcon } from 'lucide-react';
import { Card, CardHeader, CardBody } from '../common/Card';
import { Button } from '../common/Button';
import { Modal } from '../common/Modal';

function scoreClass(value: number): string {
  if (value >= 85) return 'bg-emerald-600 text-white';
  if (value >= 70) return 'bg-emerald-100 text-emerald-900';
  if (value >= 55) return 'bg-amber-100 text-amber-900';
  if (value >= 40) return 'bg-orange-100 text-orange-900';
  return 'bg-rose-600 text-white';
}

function Score({ value }: { value: number }) {
  return (
    <span className={`inline-flex min-w-[2.25rem] justify-center rounded-md px-1.5 py-0.5 text-xs font-bold ${scoreClass(value)}`}>
      {value}
    </span>
  );
}

function ScoreLegend() {
  const bands = [
    ['85–100', 'Very good', 'bg-emerald-600'],
    ['70–84', 'Good', 'bg-emerald-300'],
    ['55–69', 'Fair', 'bg-amber-300'],
    ['40–54', 'Weak', 'bg-orange-300'],
    ['0–39', 'Very low', 'bg-rose-600'],
  ];
  return (
    <div className="flex flex-wrap gap-3 text-xs text-content-secondary">
      {bands.map(([range, label, color]) => (
        <span key={range} className="inline-flex items-center gap-1.5">
          <span className={`h-3 w-3 rounded-sm ${color}`} />
          {label} ({range})
        </span>
      ))}
    </div>
  );
}

function averageScores(rows: CompetencyScores[]): CompetencyScores | null {
  if (rows.length === 0) return null;
  const total = rows.reduce(
    (sum, row) => ({
      LU: sum.LU + row.LU,
      CU: sum.CU + row.CU,
      AU: sum.AU + row.AU,
      CT: sum.CT + row.CT,
      overall: sum.overall + row.overall,
    }),
    { LU: 0, CU: 0, AU: 0, CT: 0, overall: 0 }
  );
  return {
    LU: Math.round(total.LU / rows.length),
    CU: Math.round(total.CU / rows.length),
    AU: Math.round(total.AU / rows.length),
    CT: Math.round(total.CT / rows.length),
    overall: Math.round(total.overall / rows.length),
  };
}

const CURRENT_YEAR = 2026;

function admissionYear(student: Student): number {
  if (student.joinedYear) return student.joinedYear;
  if (student.rollNo <= 16) return 2024;
  if (student.rollNo <= 28) return 2025;
  return CURRENT_YEAR;
}

function clampScore(value: number): number {
  return Math.max(0, Math.min(100, Math.round(value)));
}

const SCHOOL_MONTHS = ['Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec', 'Jan', 'Feb', 'Mar'];

function scaleScores(scores: CompetencyScores, factor: number): CompetencyScores {
  return {
    LU: scores.LU * factor,
    CU: scores.CU * factor,
    AU: scores.AU * factor,
    CT: scores.CT * factor,
    overall: scores.overall * factor,
  };
}

function yearPoints(student: Student, year: number, results: AssessmentResult[]) {
  const months = year >= CURRENT_YEAR ? SCHOOL_MONTHS.slice(0, 8) : SCHOOL_MONTHS;
  const yearsBack = Math.max(0, CURRENT_YEAR - year);
  const start = year >= CURRENT_YEAR
    ? student.baselineCompetencies
    : scaleScores(student.baselineCompetencies, 1 - yearsBack * 0.09 - 0.1);
  const end = year >= CURRENT_YEAR
    ? student.competencies
    : scaleScores(student.baselineCompetencies, 1 - yearsBack * 0.09);
  const recorded = year >= CURRENT_YEAR ? results.find((item) => item.studentId === student.id) : undefined;

  return months.map((label, index) => {
    const progress = months.length === 1 ? 1 : index / (months.length - 1);
    const wave = Math.sin((index + 1) * 1.2) * 1.4;
    const mix = (from: number, to: number, wobble: number) => clampScore(from + (to - from) * progress + wobble);
    const point = {
      label,
      LU: mix(start.LU, end.LU, wave),
      CU: mix(start.CU, end.CU, -wave * 0.6),
      AU: mix(start.AU, end.AU, wave * 0.4),
      CT: mix(start.CT, end.CT, -wave * 0.3),
      overall: mix(start.overall, end.overall, 0),
    };
    if (recorded && label === 'Sep') {
      return { label, ...recorded.scores };
    }
    return point;
  });
}

function ScoreTable({
  rows,
  empty,
  onSelect,
  selectedId,
}: {
  rows: Array<{ id: string; name: string; detail: string; scores: CompetencyScores | null }>;
  empty: string;
  onSelect?: (id: string) => void;
  selectedId?: string | null;
}) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-left text-sm">
        <thead className="bg-surface-bg/80 text-content-secondary border-b border-surface-border">
          <tr>
            <th className="py-3 px-4 font-semibold">{onSelect ? 'Name (click to view)' : 'Name'}</th>
            <th className="py-3 px-4 font-semibold">LU</th>
            <th className="py-3 px-4 font-semibold">CU</th>
            <th className="py-3 px-4 font-semibold">AU</th>
            <th className="py-3 px-4 font-semibold">CT</th>
            <th className="py-3 px-4 font-semibold">Overall</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-surface-border bg-white">
          {rows.map((row) => (
            <tr key={row.id} className={selectedId === row.id ? 'bg-teal-50' : undefined}>
              <td className="py-3 px-4">
                {onSelect ? (
                  <button
                    type="button"
                    onClick={() => onSelect(row.id)}
                    className="group flex w-full items-center justify-between gap-3 rounded-lg px-2 py-1.5 -mx-2 text-left hover:bg-teal-50 focus-visible:outline focus-visible:outline-2 focus-visible:outline-teal-600"
                  >
                    <span>
                      <span className="block font-semibold text-teal-800 underline decoration-2 underline-offset-2 group-hover:text-teal-950">
                        {row.name}
                      </span>
                      <span className="mt-0.5 block text-xs font-normal text-content-secondary no-underline">{row.detail}</span>
                    </span>
                    <span className="shrink-0 rounded-full bg-teal-600 px-2.5 py-1 text-[11px] font-bold text-white">
                      View
                    </span>
                  </button>
                ) : (
                  <>
                    <div className="font-semibold text-navy-900">{row.name}</div>
                    <div className="text-xs text-content-secondary mt-0.5">{row.detail}</div>
                  </>
                )}
              </td>
              {row.scores ? (
                <>
                  <td className="py-3 px-4"><Score value={row.scores.LU} /></td>
                  <td className="py-3 px-4"><Score value={row.scores.CU} /></td>
                  <td className="py-3 px-4"><Score value={row.scores.AU} /></td>
                  <td className="py-3 px-4"><Score value={row.scores.CT} /></td>
                  <td className="py-3 px-4"><Score value={row.scores.overall} /></td>
                </>
              ) : (
                <td colSpan={5} className="py-3 px-4 text-content-secondary">No class scores yet</td>
              )}
            </tr>
          ))}
          {rows.length === 0 && (
            <tr>
              <td colSpan={6} className="py-8 px-4 text-center text-content-secondary">{empty}</td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  );
}

interface SchoolPerformanceProps {
  schoolId: string;
  onBack?: () => void;
}

export const SchoolPerformance: React.FC<SchoolPerformanceProps> = ({ schoolId, onBack }) => {
  const { schools, classes, students, addedTeachers, assessmentResults } = useData();
  const { availableUsers } = useAuth();
  const [selectedStudentId, setSelectedStudentId] = useState<string | null>(null);
  const [chartYear, setChartYear] = useState(CURRENT_YEAR);

  useEffect(() => {
    setSelectedStudentId(null);
    setChartYear(CURRENT_YEAR);
  }, [schoolId]);

  const school = schools.find((item) => item.id === schoolId) || null;
  const schoolClasses = classes.filter((item) => item.schoolId === schoolId);
  const schoolStudents = students.filter((item) => item.schoolId === schoolId);
  const teachers = useMemo(() => {
    const seen = new Set<string>();
    return [...availableUsers.filter((user) => user.role === 'teacher'), ...addedTeachers].filter((user) => {
      if (seen.has(user.id)) return false;
      seen.add(user.id);
      return true;
    });
  }, [availableUsers, addedTeachers]);
  const schoolTeachers = teachers.filter(
    (teacher) => teacher.schoolId === schoolId || schoolClasses.some((item) => item.classTeacherId === teacher.id)
  );

  if (!school) {
    return (
      <Card>
        <CardBody className="p-6 text-sm text-content-secondary">This school is not available.</CardBody>
      </Card>
    );
  }

  const student = schoolStudents.find((item) => item.id === selectedStudentId) || null;
  const joined = student ? admissionYear(student) : CURRENT_YEAR;
  const years = student ? Array.from({ length: CURRENT_YEAR - joined + 1 }, (_, index) => CURRENT_YEAR - index) : [];
  const points = student ? yearPoints(student, chartYear, assessmentResults) : [];

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between gap-3">
        <div>
          <h2 className="text-lg font-bold text-navy-900">{school.name}</h2>
          <p className="text-sm text-content-secondary mt-1">
            {onBack
              ? 'Teachers, students, and benchmark scores for this school.'
              : 'Teachers, students, and benchmark scores for your school.'}
          </p>
        </div>
        {onBack && (
          <Button variant="secondary" size="sm" onClick={onBack}>
            Back to schools
          </Button>
        )}
      </div>
      <div className="flex items-start gap-3 rounded-xl border-2 border-teal-600 bg-teal-50 px-4 py-3 text-sm text-navy-900">
        <LineChartIcon className="mt-0.5 h-5 w-5 shrink-0 text-teal-700" />
        <p>
          <span className="font-bold">Click a student’s name</span> to open a monthly performance graph.
          Use the year menu in that window for earlier years at this school.
        </p>
      </div>
      <ScoreLegend />
      <Card>
        <CardHeader title="Teachers" subtitle="A teacher’s scores are the average of the students in the classes they lead." />
        <CardBody className="p-0">
          <ScoreTable
            rows={schoolTeachers.map((teacher) => {
              const led = schoolClasses.filter((item) => item.classTeacherId === teacher.id);
              const roster = schoolStudents.filter((student) => led.some((item) => item.id === student.classId));
              return {
                id: teacher.id,
                name: teacher.name,
                detail: led.map((item) => item.name).join(', ') || teacher.designation || 'Teacher',
                scores: averageScores(roster.map((student) => student.competencies)),
              };
            })}
            empty="No teachers are listed for this school."
          />
        </CardBody>
      </Card>
      <Card>
        <CardHeader
          title="Students"
          subtitle="Click a name to open that student’s monthly graph. Scores are Language (LU), Concept (CU), Application (AU), and Critical Thinking (CT)."
        />
        <CardBody className="p-0">
          <ScoreTable
            selectedId={selectedStudentId}
            onSelect={(id) => {
              setSelectedStudentId(id);
              setChartYear(CURRENT_YEAR);
            }}
            rows={schoolStudents.map((student) => ({
              id: student.id,
              name: student.name,
              detail: `${student.className} · ${
                schoolClasses.find((item) => item.id === student.classId)?.classTeacherName || 'Unassigned'
              }`,
              scores: student.competencies,
            }))}
            empty="No students are listed for this school."
          />
        </CardBody>
      </Card>
      {student && (
        <Modal
          isOpen
          onClose={() => setSelectedStudentId(null)}
          maxWidth="3xl"
          title={`${student.name} · ${chartYear}–${String(chartYear + 1).slice(2)}`}
          subtitle={`Monthly scores at ${school.name}. ${
            joined < CURRENT_YEAR ? `Enrolled since ${joined}.` : `Enrolled in ${joined}.`
          }`}
        >
          <label className="mb-4 flex items-center gap-3 text-sm font-semibold text-navy-900">
            Year
            <select
              value={chartYear}
              onChange={(event) => setChartYear(Number(event.target.value))}
              className="px-3 py-2 bg-white border border-surface-border rounded-lg font-semibold"
            >
              {years.map((year) => (
                <option key={year} value={year}>
                  {year}–{String(year + 1).slice(2)}
                </option>
              ))}
            </select>
          </label>
          <div className="h-80">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={points} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="label" interval={0} tick={{ fontSize: 12 }} />
                <YAxis domain={[0, 100]} tick={{ fontSize: 12 }} />
                <Tooltip />
                <Legend />
                <Line type="monotone" dataKey="LU" name="Language" stroke="#3B82F6" strokeWidth={2} dot />
                <Line type="monotone" dataKey="CU" name="Concept" stroke="#10B981" strokeWidth={2} dot />
                <Line type="monotone" dataKey="AU" name="Application" stroke="#F59E0B" strokeWidth={2} dot />
                <Line type="monotone" dataKey="CT" name="Critical Thinking" stroke="#8B5CF6" strokeWidth={2} dot />
                <Line type="monotone" dataKey="overall" name="Overall" stroke="#142A43" strokeWidth={2} dot />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </Modal>
      )}
    </div>
  );
};


