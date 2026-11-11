import React, { useState } from 'react';
import { Navigate } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';
import { useData } from '../../context/DataContext';
import { hasPermission } from '../../lib/permissions';
import { ApiError, apiClient } from '../../lib/apiClient';
import { Card, CardBody } from '../../components/common/Card';
import { Button } from '../../components/common/Button';
import { Modal } from '../../components/common/Modal';
import { CheckCircle2, PlusCircle } from 'lucide-react';

export const SchoolTeachers: React.FC = () => {
  const { currentUser, currentSchoolId, availableUsers } = useAuth();
  const { schools, addedTeachers, addTeacher } = useData();
  const [isOpen, setIsOpen] = useState(false);
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [designation, setDesignation] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [toast, setToast] = useState<string | null>(null);

  if (!currentUser || !hasPermission(currentUser.role, 'ADD_TEACHER')) {
    return <Navigate to="/unauthorized" replace />;
  }

  const school = schools.find((item) => item.id === currentSchoolId) || schools[0];
  const schoolId = school?.id || currentSchoolId;
  const seeded = availableUsers.filter((user) => user.role === 'teacher' && user.schoolId === schoolId);
  const created = addedTeachers.filter((user) => user.schoolId === schoolId);
  const teachers = [...created, ...seeded];

  const openForm = () => {
    setName('');
    setEmail('');
    setDesignation('');
    setError(null);
    setIsOpen(true);
  };

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!school) return;
    setSaving(true);
    setError(null);
    try {
      await apiClient.teachers.create({
        name,
        email,
        designation,
        schoolId: school.id,
      });
    } catch (err) {
      if (err instanceof ApiError && (err.status === 400 || err.status === 404 || err.status === 409)) {
        setError(err.message);
        setSaving(false);
        return;
      }
    }
    const saved = addTeacher({
      name,
      email,
      designation,
      schoolId: school.id,
      existingEmails: availableUsers.map((user) => user.email),
    });
    setSaving(false);
    if (!saved.ok) {
      setError(saved.error);
      return;
    }
    setIsOpen(false);
    setToast(`${saved.teacher.name} was added as a teacher.`);
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
          <h1 className="text-xl font-bold text-navy-900 tracking-tight">Teachers</h1>
          <p className="text-xs text-content-secondary mt-0.5">
            Add a teacher to {school?.name}. Existing staff and login personas stay unchanged.
          </p>
        </div>
        <Button variant="teal" onClick={openForm} icon={<PlusCircle className="w-4 h-4" />}>
          Add teacher
        </Button>
      </div>

      <Card>
        <CardBody className="p-0">
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="bg-surface-bg/80 text-content-secondary border-b border-surface-border">
                <tr>
                  <th className="py-3 px-4 font-semibold">Name</th>
                  <th className="py-3 px-4 font-semibold">Email</th>
                  <th className="py-3 px-4 font-semibold">Designation</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-surface-border bg-white">
                {teachers.map((teacher) => (
                  <tr key={teacher.id}>
                    <td className="py-3 px-4 font-semibold text-navy-900">{teacher.name}</td>
                    <td className="py-3 px-4 text-content-secondary">{teacher.email}</td>
                    <td className="py-3 px-4 text-content-secondary">{teacher.designation || 'Teacher'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </CardBody>
      </Card>

      <Modal
        isOpen={isOpen}
        onClose={() => setIsOpen(false)}
        title="Add teacher"
        subtitle="Name and email are required. The new teacher is not added to the demo login list."
        maxWidth="md"
        footer={
          <div className="flex items-center justify-end gap-2.5 w-full">
            <Button variant="secondary" size="sm" onClick={() => setIsOpen(false)}>Cancel</Button>
            <Button variant="teal" size="sm" onClick={handleSubmit} loading={saving}>Save teacher</Button>
          </div>
        }
      >
        <form onSubmit={handleSubmit} className="space-y-3 text-sm">
          <label className="block font-semibold text-content-primary">
            Name
            <input
              value={name}
              onChange={(event) => setName(event.target.value)}
              className="mt-1 w-full px-3 py-2 bg-white border border-surface-border rounded-lg font-normal"
            />
          </label>
          <label className="block font-semibold text-content-primary">
            Email
            <input
              type="email"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              className="mt-1 w-full px-3 py-2 bg-white border border-surface-border rounded-lg font-normal"
            />
          </label>
          <label className="block font-semibold text-content-primary">
            Designation
            <input
              value={designation}
              onChange={(event) => setDesignation(event.target.value)}
              placeholder="Teacher"
              className="mt-1 w-full px-3 py-2 bg-white border border-surface-border rounded-lg font-normal"
            />
          </label>
          {error && <p className="text-sm font-semibold text-rose-700">{error}</p>}
        </form>
      </Modal>
    </div>
  );
};
