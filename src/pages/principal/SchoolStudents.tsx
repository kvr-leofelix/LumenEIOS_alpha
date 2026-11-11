import React, { useState } from 'react';
import { Navigate } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';
import { useData } from '../../context/DataContext';
import { hasPermission } from '../../lib/permissions';
import { Card, CardBody } from '../../components/common/Card';
import { Button } from '../../components/common/Button';
import { Modal } from '../../components/common/Modal';
import { CheckCircle2, PlusCircle } from 'lucide-react';

export const SchoolStudents: React.FC = () => {
  const { currentUser, currentSchoolId } = useAuth();
  const { students, classes, schools, addStudent } = useData();

  const [isOpen, setIsOpen] = useState(false);
  const [name, setName] = useState('');
  const [rollNo, setRollNo] = useState('');
  const [gender, setGender] = useState<'M' | 'F' | 'Other'>('F');
  const [classId, setClassId] = useState('');
  const [toast, setToast] = useState<string | null>(null);

  if (!currentUser || !hasPermission(currentUser.role, 'ADD_STUDENT')) {
    return <Navigate to="/unauthorized" replace />;
  }

  const school = schools.find((item) => item.id === currentSchoolId) || schools[0];
  const schoolClasses = classes.filter((item) => item.schoolId === school?.id);
  const schoolStudents = students.filter((item) => item.schoolId === school?.id);

  const openForm = () => {
    setName('');
    setRollNo('');
    setGender('F');
    setClassId(schoolClasses[0]?.id || '');
    setIsOpen(true);
  };

  const handleSubmit = (event: React.FormEvent) => {
    event.preventDefault();
    if (!name.trim() || !classId || !school) return;
    addStudent({
      name,
      rollNo: Number(rollNo) || schoolStudents.length + 1,
      gender,
      classId,
      schoolId: school.id,
    });
    setIsOpen(false);
    const className = schoolClasses.find((item) => item.id === classId)?.name || 'the selected class';
    setToast(`${name.trim()} was added to ${className}.`);
    window.setTimeout(() => setToast(null), 4000);
  };

  return (
    <div className="space-y-6">
      {toast && (
        <div className="fixed bottom-6 right-6 z-50 bg-navy-900 text-white px-4 py-3 rounded-xl shadow-modal border border-teal-500/40 text-xs flex items-center gap-2">
          <CheckCircle2 className="w-4 h-4 text-teal-400" />
          <span>{toast}</span>
        </div>
      )}

      <div className="bg-white p-5 rounded-2xl border border-surface-border shadow-subtle flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-xl font-bold text-navy-900 tracking-tight">Students</h1>
          <p className="text-xs text-content-secondary mt-0.5">
            Add learners to {school?.name}. This option is available only for a school login.
          </p>
        </div>
        <Button variant="teal" onClick={openForm} icon={<PlusCircle className="w-4 h-4" />} disabled={schoolClasses.length === 0}>
          Add student
        </Button>
      </div>

      <Card>
        <CardBody className="p-0">
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="bg-surface-bg/80 text-content-secondary border-b border-surface-border">
                <tr>
                  <th className="py-3 px-4 font-semibold">Name</th>
                  <th className="py-3 px-4 font-semibold">Class</th>
                  <th className="py-3 px-4 font-semibold">Roll no.</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-surface-border bg-white">
                {schoolStudents.map((student) => (
                  <tr key={student.id}>
                    <td className="py-3 px-4 font-semibold text-navy-900">{student.name}</td>
                    <td className="py-3 px-4 text-content-secondary">{student.className}</td>
                    <td className="py-3 px-4 text-content-secondary">{student.rollNo}</td>
                  </tr>
                ))}
                {schoolStudents.length === 0 && (
                  <tr>
                    <td colSpan={3} className="py-8 px-4 text-center text-content-secondary">
                      No students yet. Add the first learner for this school.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </CardBody>
      </Card>

      <Modal isOpen={isOpen} onClose={() => setIsOpen(false)} title="Add student" subtitle={school?.name}>
        <form id="add-student-form" onSubmit={handleSubmit} className="space-y-4 text-sm">
          <div>
            <label className="block font-semibold text-content-primary mb-1" htmlFor="student-name">
              Student name
            </label>
            <input
              id="student-name"
              required
              value={name}
              onChange={(event) => setName(event.target.value)}
              className="w-full px-3 py-2 bg-white border border-surface-border rounded-lg"
              placeholder="Full name"
            />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block font-semibold text-content-primary mb-1" htmlFor="student-roll">
                Roll number
              </label>
              <input
                id="student-roll"
                type="number"
                min={1}
                required
                value={rollNo}
                onChange={(event) => setRollNo(event.target.value)}
                className="w-full px-3 py-2 bg-white border border-surface-border rounded-lg"
              />
            </div>
            <div>
              <label className="block font-semibold text-content-primary mb-1" htmlFor="student-gender">
                Gender
              </label>
              <select
                id="student-gender"
                value={gender}
                onChange={(event) => setGender(event.target.value as 'M' | 'F' | 'Other')}
                className="w-full px-3 py-2 bg-white border border-surface-border rounded-lg"
              >
                <option value="F">F</option>
                <option value="M">M</option>
                <option value="Other">Other</option>
              </select>
            </div>
          </div>
          <div>
            <label className="block font-semibold text-content-primary mb-1" htmlFor="student-class">
              Class
            </label>
            <select
              id="student-class"
              required
              value={classId}
              onChange={(event) => setClassId(event.target.value)}
              className="w-full px-3 py-2 bg-white border border-surface-border rounded-lg"
            >
              {schoolClasses.map((item) => (
                <option key={item.id} value={item.id}>
                  {item.name}
                </option>
              ))}
            </select>
          </div>
        </form>
        <div className="mt-5 flex justify-end gap-2">
          <Button type="button" variant="outline" onClick={() => setIsOpen(false)}>
            Cancel
          </Button>
          <Button type="submit" form="add-student-form" variant="teal">
            Save student
          </Button>
        </div>
      </Modal>
    </div>
  );
};
