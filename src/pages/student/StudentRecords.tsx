import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { Card, CardBody, CardHeader } from '../../components/common/Card';
import { useAuth } from '../../context/AuthContext';
import { apiClient } from '../../lib/apiClient';
import { UnauthorizedPage } from '../shared/UnauthorizedPage';

type View = 'history' | 'profile';
type Profile = Awaited<ReturnType<typeof apiClient.student.profile>>;
type History = Awaited<ReturnType<typeof apiClient.ocr.history>>;

export function StudentRecords({ view }: { view: View }) {
  const { currentUser } = useAuth();
  if (currentUser?.role !== 'student') return <UnauthorizedPage />;
  return <RecordsPanel key={`${currentUser.id}:${currentUser.schoolId}:${view}`} view={view} email={currentUser.email} />;
}

function RecordsPanel({ view, email }: { view: View; email: string }) {
  const [profile, setProfile] = useState<Profile>();
  const [history, setHistory] = useState<History>();
  const [error, setError] = useState('');
  const isHistory = view === 'history';

  useEffect(() => {
    let active = true;
    const load = isHistory
      ? apiClient.ocr.history().then((rows) => { if (active) setHistory(rows); })
      : apiClient.student.profile().then((record) => { if (active) setProfile(record); });
    load.catch((err) => {
      if (active) setError(err instanceof Error ? err.message : 'Could not load your records.');
    });
    return () => { active = false; };
  }, [isHistory]);

  return (
    <Card>
      <CardHeader title={isHistory ? 'History' : 'Profile'} />
      <CardBody className="space-y-4 text-sm">
        {error && <p role="alert" className="text-rose-700">{error}</p>}
        {!error && !profile && !history && <p role="status">Loading…</p>}
        {profile && (
          <dl className="grid gap-4 sm:grid-cols-2">
            {[
              ['Name', profile.name],
              ['Student ID', profile.id],
              ['Login email', email],
              ['Roll number', profile.rollNo],
              ['Class', profile.className],
              ['Subjects', profile.subjectNames.join(', ') || 'No subjects recorded'],
              ['Parents / guardians', profile.parentNames.join(', ') || 'No parent accounts linked'],
            ].map(([label, value]) => (
              <div key={label} className="min-w-0 rounded-lg border border-surface-border p-3">
                <dt className="font-semibold">{label}</dt>
                <dd className="break-words text-content-secondary">{value}</dd>
              </div>
            ))}
          </dl>
        )}
        {history?.length === 0 && (
          <p>There are no saved extracts yet. <Link to="/upload" className="text-teal-700 underline">Upload a document</Link> to add one.</p>
        )}
        {history?.map((entry) => (
          <details key={entry.id} className="rounded-lg border border-surface-border p-3">
            <summary className="cursor-pointer font-semibold">
              {entry.file_name} · {new Date(entry.created_at).toLocaleString()} · {entry.pages_processed} page(s)
            </summary>
            {entry.assignment_title && <p className="mt-2 text-xs text-content-secondary">{entry.assignment_title}</p>}
            <p className="mt-3 whitespace-pre-wrap break-words">{entry.extracted_text || 'No text recognized.'}</p>
          </details>
        ))}
      </CardBody>
    </Card>
  );
}
