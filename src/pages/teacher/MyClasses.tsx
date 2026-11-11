import React, { useState } from 'react';
import { useData } from '../../context/DataContext';
import { Student } from '../../types';
import { Card, CardHeader, CardBody } from '../../components/common/Card';
import { Button } from '../../components/common/Button';
import { Badge } from '../../components/common/Badge';
import { Modal } from '../../components/common/Modal';
import { ClassHeatmap } from '../../components/charts/ClassHeatmap';
import { CompetencyRadarChart } from '../../components/charts/CompetencyRadarChart';
import { CompetencyGroupBadges } from '../../components/common/CompetencyScoreBadge';
import { Users, GraduationCap, AlertCircle, Sparkles, BookOpen, Clock } from 'lucide-react';
import { recommendDifferentiatedHomework } from '../../lib/calculations';

export const MyClasses: React.FC = () => {
  const { classes, students, assignHomeworkRemediation } = useData();

  const [selectedClassId, setSelectedClassId] = useState('class-8a');
  const [selectedStudent, setSelectedStudent] = useState<Student | null>(null);
  const [isRemediationModalOpen, setIsRemediationModalOpen] = useState(false);
  const [notificationMsg, setNotificationMsg] = useState<string | null>(null);

  const activeClass = classes.find((c) => c.id === selectedClassId) || classes[0];
  const classStudents = students.filter((s) => s.classId === selectedClassId);

  const handleOpenRemediation = (student: Student) => {
    setSelectedStudent(student);
    setIsRemediationModalOpen(true);
  };

  const handleConfirmRemediation = () => {
    if (!selectedStudent) return;
    const rec = recommendDifferentiatedHomework(selectedStudent);
    assignHomeworkRemediation({
      studentId: selectedStudent.id,
      studentName: selectedStudent.name,
      classId: selectedStudent.classId,
      subjectId: 'sub-math',
      title: rec.title,
      competencyTarget: rec.competency,
      reason: rec.rationale,
      description: rec.description,
      dueDate: '2026-10-18',
      status: 'assigned',
    });

    setIsRemediationModalOpen(false);
    setNotificationMsg(`Differentiated homework successfully assigned to ${selectedStudent.name}!`);
    setTimeout(() => setNotificationMsg(null), 4000);
  };

  return (
    <div className="space-y-6">
      {/* Toast Notification */}
      {notificationMsg && (
        <div className="fixed bottom-6 right-6 z-50 bg-navy-900 text-white px-4 py-3 rounded-xl shadow-modal border border-teal-500/40 text-xs flex items-center gap-2">
          <Sparkles className="w-4 h-4 text-teal-400" />
          <span>{notificationMsg}</span>
        </div>
      )}

      {/* Header and Class Tabs */}
      <div className="bg-white p-5 rounded-2xl border border-surface-border shadow-subtle flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-xl font-bold text-navy-900 tracking-tight">Classroom Roster & Competency Matrix</h1>
          <p className="text-xs text-content-secondary mt-0.5">
            Individual student profiles and competency heatmaps aligned with NEP 2020 standards
          </p>
        </div>

        {/* Class Selector Tabs */}
        <div className="flex items-center gap-2 overflow-x-auto">
          {classes.slice(0, 3).map((cls) => (
            <button
              key={cls.id}
              onClick={() => setSelectedClassId(cls.id)}
              className={`px-3.5 py-1.5 rounded-lg text-xs font-semibold transition-all ${
                selectedClassId === cls.id
                  ? 'bg-navy-800 text-white shadow-sm'
                  : 'bg-surface-bg text-content-secondary hover:text-content-primary hover:bg-gray-200'
              }`}
            >
              {cls.name} ({cls.studentCount} Students)
            </button>
          ))}
        </div>
      </div>

      {/* Class Overview Summary Banner */}
      <div className="grid grid-cols-1 sm:grid-cols-4 gap-4">
        <div className="p-4 bg-white rounded-xl border border-surface-border">
          <span className="text-xs text-content-secondary font-medium uppercase">Active Section</span>
          <p className="text-lg font-bold text-navy-900 mt-1">{activeClass.name}</p>
          <span className="text-[11px] text-content-muted">Lead: {activeClass.classTeacherName}</span>
        </div>
        <div className="p-4 bg-white rounded-xl border border-surface-border">
          <span className="text-xs text-content-secondary font-medium uppercase">Total Enrolled</span>
          <p className="text-lg font-bold text-teal-700 mt-1">{classStudents.length} Students</p>
          <span className="text-[11px] text-teal-600 font-medium">100% Baselines Recorded</span>
        </div>
        <div className="p-4 bg-white rounded-xl border border-surface-border">
          <span className="text-xs text-content-secondary font-medium uppercase">Interventions Needed</span>
          <p className="text-lg font-bold text-rose-600 mt-1">
            {classStudents.filter((s) => s.needsSupport).length} Students
          </p>
          <span className="text-[11px] text-rose-600 font-medium">&lt;65% in LU or AU</span>
        </div>
        <div className="p-4 bg-white rounded-xl border border-surface-border">
          <span className="text-xs text-content-secondary font-medium uppercase">Average Attendance</span>
          <p className="text-lg font-bold text-navy-900 mt-1">
            {Math.round(
              classStudents.reduce((acc, s) => acc + s.attendancePct, 0) / (classStudents.length || 1)
            )}
            %
          </p>
          <span className="text-[11px] text-content-muted">Consistent tracking</span>
        </div>
      </div>

      {/* Interactive Class Heatmap Table */}
      <Card>
        <CardHeader
          title={`${activeClass.name} Competency Matrix`}
          subtitle="Click any student row to view diagnostic radar, baseline shifts, and assign tailored remediation"
        />
        <CardBody>
          <ClassHeatmap
            students={classStudents}
            onSelectStudent={(st) => setSelectedStudent(st)}
            onTriggerRemediation={(st) => handleOpenRemediation(st)}
          />
        </CardBody>
      </Card>

      {/* Detailed Student Diagnostic Modal */}
      {selectedStudent && (
        <Modal
          isOpen={!!selectedStudent}
          onClose={() => setSelectedStudent(null)}
          title={`Diagnostic Profile: ${selectedStudent.name}`}
          subtitle={`Roll #${selectedStudent.rollNo} • ${selectedStudent.className} • Modality: ${selectedStudent.learningModality}`}
          maxWidth="2xl"
          footer={
            <div className="flex items-center justify-between w-full">
              <div className="text-xs text-content-secondary">
                Attendance: <strong className="text-navy-900">{selectedStudent.attendancePct}%</strong>
              </div>
              <div className="flex items-center gap-2">
                <Button variant="secondary" size="sm" onClick={() => setSelectedStudent(null)}>
                  Close
                </Button>
                <Button
                  variant="teal"
                  size="sm"
                  onClick={() => {
                    handleOpenRemediation(selectedStudent);
                  }}
                  icon={<Sparkles className="w-3.5 h-3.5" />}
                >
                  Assign Remediation
                </Button>
              </div>
            </div>
          }
        >
          <div className="space-y-4">
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 items-center">
              <div>
                <h4 className="text-xs font-bold text-navy-900 uppercase tracking-wider mb-2">
                  Competency Growth vs Baseline
                </h4>
                <div className="space-y-2 text-xs">
                  <div className="p-2.5 bg-surface-bg rounded-lg border border-surface-border flex justify-between items-center">
                    <span>Language Understanding (LU)</span>
                    <span className="font-bold text-blue-700">{selectedStudent.competencies.LU}%</span>
                  </div>
                  <div className="p-2.5 bg-surface-bg rounded-lg border border-surface-border flex justify-between items-center">
                    <span>Concept Understanding (CU)</span>
                    <span className="font-bold text-emerald-700">{selectedStudent.competencies.CU}%</span>
                  </div>
                  <div className="p-2.5 bg-surface-bg rounded-lg border border-surface-border flex justify-between items-center">
                    <span>Application Understanding (AU)</span>
                    <span className="font-bold text-amber-700">{selectedStudent.competencies.AU}%</span>
                  </div>
                  <div className="p-2.5 bg-surface-bg rounded-lg border border-surface-border flex justify-between items-center">
                    <span>Critical Thinking (CT)</span>
                    <span className="font-bold text-indigo-700">{selectedStudent.competencies.CT}%</span>
                  </div>
                </div>
              </div>

              <div>
                <CompetencyRadarChart
                  current={selectedStudent.competencies}
                  baseline={selectedStudent.baselineCompetencies}
                  benchmarkName="Cycle 1 Baseline"
                  height={220}
                />
              </div>
            </div>

            {selectedStudent.needsSupport && (
              <div className="p-3 bg-rose-50 border border-rose-200 rounded-xl text-xs text-rose-900 flex items-start gap-2.5">
                <AlertCircle className="w-4 h-4 text-rose-600 shrink-0 mt-0.5" />
                <div>
                  <p className="font-bold">Intervention Recommended</p>
                  <p className="text-[11px] text-rose-800 mt-0.5 leading-relaxed">
                    Area of focus: {selectedStudent.supportArea || 'Identified learning gaps'}.
                  </p>
                </div>
              </div>
            )}
          </div>
        </Modal>
      )}

      {/* Differentiated Remediation Modal */}
      {selectedStudent && (
        <Modal
          isOpen={isRemediationModalOpen}
          onClose={() => setIsRemediationModalOpen(false)}
          title={`Generate Differentiated Remediation for ${selectedStudent.name}`}
          subtitle="Deterministic rule-based pedagogical homework recommendation"
          maxWidth="lg"
          footer={
            <div className="flex items-center justify-end gap-2.5 w-full">
              <Button variant="secondary" size="sm" onClick={() => setIsRemediationModalOpen(false)}>
                Cancel
              </Button>
              <Button variant="teal" size="sm" onClick={handleConfirmRemediation}>
                Confirm & Assign Task
              </Button>
            </div>
          }
        >
          {(() => {
            const rec = recommendDifferentiatedHomework(selectedStudent);
            return (
              <div className="space-y-4 text-xs">
                <div className="p-3.5 bg-teal-50 border border-teal-200 rounded-xl">
                  <div className="flex items-center gap-2 text-teal-900 font-bold">
                    <Sparkles className="w-4 h-4 text-teal-600" />
                    <span>Targeted Dimension: {rec.competency} ({rec.title})</span>
                  </div>
                  <p className="text-[11px] text-teal-800 mt-1 leading-relaxed">{rec.rationale}</p>
                </div>

                <div className="space-y-1">
                  <label className="font-semibold text-content-primary">Worksheet / Activity Description</label>
                  <p className="p-3 bg-surface-bg rounded-lg border border-surface-border text-content-secondary leading-relaxed">
                    {rec.description}
                  </p>
                </div>

                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="font-semibold text-content-primary">Due Date</label>
                    <input
                      type="date"
                      defaultValue="2026-10-18"
                      className="w-full mt-1 px-3 py-1.5 bg-white border border-surface-border rounded-lg text-xs"
                    />
                  </div>
                  <div>
                    <label className="font-semibold text-content-primary">Delivery Channel</label>
                    <select className="w-full mt-1 px-3 py-1.5 bg-white border border-surface-border rounded-lg text-xs">
                      <option>Digital Tablet Portal + Offline Printable Slip</option>
                      <option>Physical Printed Worksheet</option>
                    </select>
                  </div>
                </div>
              </div>
            );
          })()}
        </Modal>
      )}
    </div>
  );
};

