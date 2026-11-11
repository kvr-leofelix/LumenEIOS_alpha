import React, { useState } from 'react';
import { Navigate } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';
import { useData } from '../../context/DataContext';
import { hasPermission } from '../../lib/permissions';
import { buildDemoExtraction } from '../../lib/demoOcr';
import { AnswerSheetUpload } from '../../types';
import { Card, CardHeader, CardBody } from '../../components/common/Card';
import { Button } from '../../components/common/Button';
import { Badge } from '../../components/common/Badge';
import { ScanLine, Upload, CheckCircle2 } from 'lucide-react';

const ACCEPTED = '.jpg,.jpeg,.png,.webp,.pdf';

function readPreview(file: File): Promise<string | undefined> {
  if (!file.type.startsWith('image/')) return Promise.resolve(undefined);
  return new Promise((resolve) => {
    const img = new Image();
    const url = URL.createObjectURL(file);
    img.onload = () => {
      const max = 720;
      const scale = Math.min(1, max / Math.max(img.width, img.height));
      const canvas = document.createElement('canvas');
      canvas.width = Math.max(1, Math.round(img.width * scale));
      canvas.height = Math.max(1, Math.round(img.height * scale));
      const ctx = canvas.getContext('2d');
      if (!ctx) {
        URL.revokeObjectURL(url);
        resolve(undefined);
        return;
      }
      ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
      const data = canvas.toDataURL('image/jpeg', 0.62);
      URL.revokeObjectURL(url);
      resolve(data.length < 380000 ? data : undefined);
    };
    img.onerror = () => {
      URL.revokeObjectURL(url);
      resolve(undefined);
    };
    img.src = url;
  });
}

const Extraction: React.FC<{ upload: AnswerSheetUpload }> = ({ upload }) => (
  <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
    <div className="rounded-xl border border-surface-border bg-surface-bg p-3">
      <p className="text-xs font-semibold text-content-secondary mb-2">{upload.fileName}</p>
      {upload.previewDataUrl ? (
        <img src={upload.previewDataUrl} alt={`Uploaded sheet ${upload.fileName}`} className="w-full rounded-lg border border-surface-border bg-white" />
      ) : (
        <p className="text-sm text-content-secondary p-4">No image preview for this file. The demo transcript is still shown beside it.</p>
      )}
    </div>
    <div className="space-y-2">
      <div className="flex items-center gap-2">
        <Badge variant="teal" size="sm">Demo extraction</Badge>
        <span className="text-xs text-content-secondary">{upload.subject}</span>
      </div>
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
);

export const StudentAnswerSheets: React.FC = () => {
  const { currentUser } = useAuth();
  const { students, classes, answerSheetUploads, sheetAssignments, addAnswerSheetUpload } = useData();
  const [assignmentId, setAssignmentId] = useState('');
  const [file, setFile] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);
  const [latest, setLatest] = useState<AnswerSheetUpload | null>(null);
  const [error, setError] = useState<string | null>(null);

  if (!currentUser || !hasPermission(currentUser.role, 'SUBMIT_ASSIGNMENTS')) {
    return <Navigate to="/unauthorized" replace />;
  }

  const student =
    students.find((item) => item.id === currentUser.id) ||
    students.find((item) => item.name === currentUser.name);
  const classId = student?.classId || currentUser.assignedClassIds?.[0] || '';
  const className = student?.className || classes.find((item) => item.id === classId)?.name || 'Class';
  const mine = answerSheetUploads.filter((item) => item.studentId === currentUser.id);
  const assignments = sheetAssignments.filter((item) => item.classId === classId);
  const selected = assignments.find((item) => item.id === assignmentId) || assignments[0];

  const handleExtract = async () => {
    if (!file || !selected) return;
    if (file.size > 8 * 1024 * 1024) {
      setError('Choose a file smaller than 8 MB.');
      return;
    }
    setError(null);
    setBusy(true);
    const previewDataUrl = await readPreview(file);
    await new Promise((resolve) => setTimeout(resolve, 900));
    const saved = addAnswerSheetUpload({
      assignmentId: selected.id,
      assignmentTitle: selected.title,
      studentId: currentUser.id,
      studentName: student?.name || currentUser.name,
      classId,
      className,
      schoolId: student?.schoolId || currentUser.schoolId,
      subject: selected.subject,
      fileName: file.name,
      mimeType: file.type || 'application/octet-stream',
      previewDataUrl,
      blocks: buildDemoExtraction(student?.name || currentUser.name, className, selected.subject),
    });
    setLatest(saved);
    setFile(null);
    setBusy(false);
  };

  return (
    <div className="space-y-6">
      <div className="bg-white p-5 rounded-2xl border border-surface-border shadow-subtle">
        <div className="flex items-center gap-2">
          <ScanLine className="w-5 h-5 text-teal-600" />
          <h1 className="text-xl font-bold text-navy-900">Answer sheet OCR</h1>
          <Badge variant="teal" size="sm">Demo</Badge>
        </div>
        <p className="text-sm text-content-secondary mt-2 max-w-2xl leading-relaxed">
          Your teacher gives the assignment. Upload a photo or PDF of that answer sheet. This demo shows the text and equations a future OCR model would return. It does not read the file yet.
        </p>
      </div>

      <Card>
        <CardHeader title="Upload a sheet" subtitle={`${student?.name || currentUser.name} · ${className}`} />
        <CardBody className="space-y-4">
          {assignments.length === 0 ? (
            <p className="text-sm text-content-secondary">No assignment for your class yet. It will show up here after your teacher gives one.</p>
          ) : (
            <label className="block text-sm font-semibold text-content-primary">
              Assignment
              <select
                value={selected?.id || ''}
                onChange={(event) => setAssignmentId(event.target.value)}
                className="mt-1 block w-full max-w-lg rounded-lg border border-surface-border bg-white px-3 py-2 text-sm font-normal"
              >
                {assignments.map((item) => (
                  <option key={item.id} value={item.id}>
                    {item.title} · due {item.dueDate}
                  </option>
                ))}
              </select>
            </label>
          )}
          {selected && (
            <div className="rounded-xl border border-surface-border bg-surface-bg px-4 py-3">
              <p className="text-sm font-semibold text-navy-900">{selected.title}</p>
              <p className="text-xs text-content-secondary mt-1">{selected.subject} · {selected.teacherName} · Due {selected.dueDate}</p>
              <p className="text-sm text-content-primary mt-2 leading-relaxed">{selected.instructions}</p>
              {mine.some((item) => item.assignmentId === selected.id) && (
                <p className="text-xs text-emerald-700 font-semibold mt-2">You already sent a sheet for this assignment. A new upload is added beside it.</p>
              )}
            </div>
          )}
          <label className="flex flex-col items-center justify-center gap-2 rounded-2xl border border-dashed border-surface-border bg-surface-bg px-4 py-8 text-center cursor-pointer">
            <Upload className="w-6 h-6 text-teal-600" />
            <span className="text-sm font-semibold text-navy-900">{file ? file.name : 'Choose a JPG, PNG, WEBP, or PDF'}</span>
            <span className="text-xs text-content-secondary">The sheet stays in this browser for your teacher to open.</span>
            <input
              type="file"
              accept={ACCEPTED}
              className="hidden"
              onChange={(event) => {
                setFile(event.target.files?.[0] || null);
                setError(null);
              }}
            />
          </label>
          {error && <p className="text-sm text-rose-700">{error}</p>}
          <Button variant="teal" disabled={!file || busy || !selected} loading={busy} onClick={handleExtract} icon={<ScanLine className="w-4 h-4" />}>
            {busy ? 'Extracting…' : 'Extract text'}
          </Button>
        </CardBody>
      </Card>

      {latest && (
        <Card>
          <CardHeader
            title="Extracted text"
            subtitle="Sample transcript for this upload"
            action={<span className="text-xs text-emerald-700 font-semibold inline-flex items-center gap-1"><CheckCircle2 className="w-3.5 h-3.5" /> Ready for your teacher</span>}
          />
          <CardBody>
            <Extraction upload={latest} />
          </CardBody>
        </Card>
      )}

      <Card>
        <CardHeader title="Your uploads" subtitle="Sheets already sent from this browser" />
        <CardBody className="space-y-3">
          {mine.length === 0 && <p className="text-sm text-content-secondary">No answer sheets yet.</p>}
          {mine.map((upload) => (
            <button
              key={upload.id}
              type="button"
              onClick={() => setLatest(upload)}
              className="w-full text-left rounded-xl border border-surface-border px-4 py-3 hover:bg-surface-bg"
            >
              <span className="block text-sm font-semibold text-navy-900">{upload.assignmentTitle || upload.fileName}</span>
              <span className="block text-xs text-content-secondary mt-1">
                {upload.fileName} · {upload.subject} · {new Date(upload.uploadedAt).toLocaleString()}
              </span>
            </button>
          ))}
        </CardBody>
      </Card>
    </div>
  );
};
