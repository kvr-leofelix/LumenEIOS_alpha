import React, { useState } from 'react';
import { Navigate } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';
import { useData } from '../../context/DataContext';
import { hasPermission } from '../../lib/permissions';
import { AnswerSheetUpload } from '../../types';
import { Card, CardHeader, CardBody } from '../../components/common/Card';
import { Button } from '../../components/common/Button';
import { Badge } from '../../components/common/Badge';
import { FileText, PlusCircle } from 'lucide-react';

const SUBJECTS = ['Mathematics', 'Science'];

export const StudentHomework: React.FC = () => {
  const { currentUser } = useAuth();
  const { classes, sheetAssignments, answerSheetUploads, addSheetAssignment } = useData();
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [sheetId, setSheetId] = useState<string | null>(null);
  const [title, setTitle] = useState('');
  const [instructions, setInstructions] = useState('');
  const [subject, setSubject] = useState(SUBJECTS[0]);
  const [classId, setClassId] = useState('');
  const [dueDate, setDueDate] = useState('2026-11-20');
  const [giving, setGiving] = useState(false);

  if (!currentUser || !hasPermission(currentUser.role, 'REVIEW_STUDENT_SHEETS')) {
    return <Navigate to="/unauthorized" replace />;
  }

  const classIds = currentUser.assignedClassIds || [];
  const myClasses = classes.filter((item) => classIds.includes(item.id));
  const activeClassId = classId || myClasses[0]?.id || '';
  const assignments = sheetAssignments.filter((item) =>
    classIds.length === 0 ? item.schoolId === currentUser.schoolId : classIds.includes(item.classId)
  );
  const selected = assignments.find((item) => item.id === selectedId) || assignments[0] || null;
  const sheets = answerSheetUploads.filter((item) => item.assignmentId === selected?.id);
  const selectedSheet = sheets.find((item) => item.id === sheetId) || sheets[0] || null;

  const giveAssignment = (event: React.FormEvent) => {
    event.preventDefault();
    const classItem = myClasses.find((item) => item.id === activeClassId);
    if (!title.trim() || !classItem) return;
    addSheetAssignment({
      teacherId: currentUser.id,
      teacherName: currentUser.name,
      schoolId: currentUser.schoolId,
      classId: classItem.id,
      className: classItem.name,
      subject,
      title: title.trim(),
      instructions: instructions.trim() || 'Upload a photo of the handwritten answer sheet.',
      dueDate,
    });
    setTitle('');
    setInstructions('');
    setGiving(false);
    setSelectedId(null);
  };

  return (
    <div className="space-y-6">
      <div className="bg-white p-5 rounded-2xl border border-surface-border shadow-subtle flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div>
          <div className="flex items-center gap-2">
            <FileText className="w-5 h-5 text-teal-600" />
            <h1 className="text-xl font-bold text-navy-900">Student homework</h1>
            <Badge variant="teal" size="sm">Demo OCR</Badge>
          </div>
          <p className="text-sm text-content-secondary mt-2 max-w-2xl leading-relaxed">
            Give an assignment to a class. Students upload an answer sheet for that assignment, and the demo transcript appears here.
          </p>
        </div>
        <Button variant="teal" size="sm" onClick={() => setGiving((open) => !open)} icon={<PlusCircle className="w-4 h-4" />}>
          Give assignment
        </Button>
      </div>

      {giving && (
        <Card>
          <CardHeader title="New assignment" subtitle="Students in the chosen class can upload a sheet for this" />
          <CardBody>
            <form onSubmit={giveAssignment} className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <label className="text-sm font-semibold text-content-primary">
                Title
                <input
                  value={title}
                  onChange={(event) => setTitle(event.target.value)}
                  required
                  className="mt-1 block w-full rounded-lg border border-surface-border bg-white px-3 py-2 text-sm font-normal"
                  placeholder="Mensuration practice"
                />
              </label>
              <label className="text-sm font-semibold text-content-primary">
                Class
                <select
                  value={activeClassId}
                  onChange={(event) => setClassId(event.target.value)}
                  className="mt-1 block w-full rounded-lg border border-surface-border bg-white px-3 py-2 text-sm font-normal"
                >
                  {myClasses.map((item) => (
                    <option key={item.id} value={item.id}>{item.name}</option>
                  ))}
                </select>
              </label>
              <label className="text-sm font-semibold text-content-primary">
                Subject
                <select
                  value={subject}
                  onChange={(event) => setSubject(event.target.value)}
                  className="mt-1 block w-full rounded-lg border border-surface-border bg-white px-3 py-2 text-sm font-normal"
                >
                  {SUBJECTS.map((item) => (
                    <option key={item}>{item}</option>
                  ))}
                </select>
              </label>
              <label className="text-sm font-semibold text-content-primary">
                Due date
                <input
                  type="date"
                  value={dueDate}
                  onChange={(event) => setDueDate(event.target.value)}
                  required
                  className="mt-1 block w-full rounded-lg border border-surface-border bg-white px-3 py-2 text-sm font-normal"
                />
              </label>
              <label className="text-sm font-semibold text-content-primary md:col-span-2">
                Instructions
                <textarea
                  value={instructions}
                  onChange={(event) => setInstructions(event.target.value)}
                  rows={3}
                  className="mt-1 block w-full rounded-lg border border-surface-border bg-white px-3 py-2 text-sm font-normal"
                  placeholder="What should the student write on the sheet?"
                />
              </label>
              <div>
                <Button type="submit" variant="teal" disabled={!title.trim()}>Save assignment</Button>
              </div>
            </form>
          </CardBody>
        </Card>
      )}

      {assignments.length === 0 ? (
        <Card>
          <CardBody>
            <p className="text-sm text-content-secondary">No assignments yet. Give one, then students can upload their answer sheets.</p>
          </CardBody>
        </Card>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-[280px_1fr] gap-4">
          <Card>
            <CardHeader title="Assignments" subtitle={`${assignments.length} given`} />
            <CardBody className="space-y-2">
              {assignments.map((item) => {
                const count = answerSheetUploads.filter((sheet) => sheet.assignmentId === item.id).length;
                return (
                  <button
                    key={item.id}
                    type="button"
                    onClick={() => {
                      setSelectedId(item.id);
                      setSheetId(null);
                    }}
                    className={`w-full text-left rounded-xl border px-3 py-2 ${
                      selected?.id === item.id ? 'border-teal-500 bg-teal-50' : 'border-surface-border bg-white'
                    }`}
                  >
                    <span className="block text-sm font-semibold text-navy-900">{item.title}</span>
                    <span className="block text-xs text-content-secondary mt-0.5">{item.className} · {item.subject}</span>
                    <span className="block text-xs text-content-muted mt-0.5">Due {item.dueDate} · {count} sheet{count === 1 ? '' : 's'}</span>
                  </button>
                );
              })}
            </CardBody>
          </Card>

          {selected && (
            <div className="space-y-4">
              <Card>
                <CardHeader title={selected.title} subtitle={`${selected.className} · ${selected.subject} · Due ${selected.dueDate}`} />
                <CardBody>
                  <p className="text-sm text-content-primary leading-relaxed">{selected.instructions}</p>
                </CardBody>
              </Card>
              {sheets.length === 0 ? (
                <Card>
                  <CardBody>
                    <p className="text-sm text-content-secondary">No answer sheets for this assignment yet.</p>
                  </CardBody>
                </Card>
              ) : (
                <div className="space-y-3">
                  <div className="flex flex-wrap gap-2">
                    {sheets.map((sheet) => (
                      <button
                        key={sheet.id}
                        type="button"
                        onClick={() => setSheetId(sheet.id)}
                        className={`rounded-full border px-3 py-1.5 text-xs font-semibold ${
                          selectedSheet?.id === sheet.id ? 'border-teal-500 bg-teal-50 text-teal-900' : 'border-surface-border bg-white text-navy-900'
                        }`}
                      >
                        {sheet.studentName}
                      </button>
                    ))}
                  </div>
                  {selectedSheet && <SheetDetail upload={selectedSheet} />}
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
};

const SheetDetail: React.FC<{ upload: AnswerSheetUpload }> = ({ upload }) => (
  <Card>
    <CardHeader
      title={upload.studentName}
      subtitle={`${upload.fileName} · ${new Date(upload.uploadedAt).toLocaleString()}`}
    />
    <CardBody>
      <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
        <div>
          {upload.previewDataUrl ? (
            <img src={upload.previewDataUrl} alt={`Answer sheet from ${upload.studentName}`} className="w-full rounded-xl border border-surface-border bg-white" />
          ) : (
            <p className="text-sm text-content-secondary rounded-xl border border-surface-border p-4">
              {upload.fileName} has no stored image preview.
            </p>
          )}
        </div>
        <div className="space-y-2">
          <p className="text-xs font-semibold uppercase tracking-wide text-content-secondary">Extracted text</p>
          {upload.blocks.map((block, index) =>
            block.kind === 'equation' ? (
              <p key={index} className="rounded-lg bg-navy-900 text-teal-100 px-3 py-2 font-mono text-sm">
                {block.content}
              </p>
            ) : (
              <p key={index} className="text-sm text-content-primary leading-relaxed">
                {block.content}
              </p>
            ),
          )}
        </div>
      </div>
    </CardBody>
  </Card>
);
