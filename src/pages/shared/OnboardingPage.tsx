import React, { useEffect, useState } from 'react';
import { Button } from '../../components/common/Button';
import { Card, CardBody, CardHeader } from '../../components/common/Card';
import { useAuth } from '../../context/AuthContext';
import { ApiError, apiClient } from '../../lib/apiClient';
import { UnauthorizedPage } from './UnauthorizedPage';

const roles = { Student: 'teacher', Teacher: 'principal', School: 'admin' } as const;
const inputClass = 'mt-1 block w-full rounded-lg border border-surface-border bg-white px-3 py-2 text-sm';

function Field({ label, ...props }: React.InputHTMLAttributes<HTMLInputElement> & { label: string }) {
  return (
    <label className="block text-sm font-medium text-navy-900">
      {label}
      <input {...props} className={inputClass} />
    </label>
  );
}

export function OnboardingPage({ kind }: { kind: keyof typeof roles }) {
  const { currentUser } = useAuth();
  const allowed = currentUser?.role === roles[kind] || currentUser?.role === 'developer';
  const schoolId = currentUser?.schoolId;
  const [classes, setClasses] = useState<Array<{ id: string; name: string }>>([]);
  const [isLoadingClasses, setIsLoadingClasses] = useState(false);
  const [classError, setClassError] = useState('');
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState('');
  const [saved, setSaved] = useState('');
  const today = new Date();
  const maxBirthDate = [today.getFullYear(), today.getMonth() + 1, today.getDate()]
    .map((part) => String(part).padStart(2, '0')).join('-');

  useEffect(() => {
    if (!allowed || kind !== 'Student') return;
    setClasses([]);
    setClassError('');
    if (!schoolId) {
      setClassError('Your account needs an active school before you can add students.');
      return;
    }
    let active = true;
    setIsLoadingClasses(true);
    apiClient.onboarding.classes(schoolId)
      .then((sections) => {
        if (!active) return;
        setClasses(sections);
        if (!sections.length) setClassError('Your school needs a class section before you can add students.');
      })
      .catch(() => { if (active) setClassError('Could not load class sections. Refresh the page to try again.'); })
      .finally(() => { if (active) setIsLoadingClasses(false); });
    return () => { active = false; };
  }, [allowed, kind, schoolId]);

  if (!allowed) return <UnauthorizedPage />;

  const handleSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (isSaving) return;
    const form = event.currentTarget;
    const data = new FormData(form);
    const field = (name: string) => String(data.get(name) ?? '').trim();
    const account = {
      name: field('name'),
      email: field('email'),
      password: String(data.get('password') ?? ''),
      phone: field('phone') || undefined,
      address: field('address') || undefined,
      date_of_birth: field('date_of_birth') || undefined,
    };
    setIsSaving(true);
    setError('');
    setSaved('');
    try {
      if (kind === 'Student') {
        const user = await apiClient.onboarding.addStudent({
          ...account, class_id: field('class_id'), roll_no: Number(field('roll_no')), gender: field('gender'),
        });
        setSaved(`${user.name} was added to the class. Sign-in email: ${user.email}.`);
      } else if (kind === 'Teacher') {
        const user = await apiClient.onboarding.addTeacher({ ...account, designation: field('designation') || undefined });
        setSaved(`${user.name} was added to your school. Sign-in email: ${user.email}.`);
      } else {
        const school = await apiClient.onboarding.addSchool({
          name: field('school_name'), location: field('location'), state: field('state'),
          infrastructure_tier: field('infrastructure_tier'), academic_year: field('academic_year'),
          official_working_days: Number(field('official_working_days')), principal: account,
        });
        setSaved(`${school.name} was added. The principal can sign in with ${account.email}.`);
      }
      form.reset();
    } catch (err) {
      const detail = err instanceof ApiError ? err.data?.detail : undefined;
      const validation = Array.isArray(detail) ? detail.map((item) => item.msg).join(' ') : undefined;
      setError(typeof detail === 'string' ? detail : validation || 'Could not save. Check the backend connection and try again.');
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <Card className="mx-auto max-w-3xl">
      <CardHeader title={`Add ${kind}`} subtitle={
        kind === 'School' ? 'Register a school and create its principal’s login.' : 'Create a profile and login for your school.'
      } />
      <CardBody>
        <form onSubmit={handleSubmit} className="space-y-5">
          <fieldset disabled={isSaving} className="space-y-5">
            {kind === 'School' && (
              <div className="grid gap-4 sm:grid-cols-2">
                <Field label="School name" name="school_name" required maxLength={255} />
                <Field label="School address / location" name="location" required maxLength={255} />
                <Field label="State" name="state" required maxLength={100} />
                <label className="text-sm font-medium text-navy-900">
                  Infrastructure tier
                  <select name="infrastructure_tier" className={inputClass} defaultValue="standard">
                    <option value="high-tech">High-tech</option>
                    <option value="standard">Standard</option>
                    <option value="low-tech">Low-tech</option>
                  </select>
                </label>
                <Field label="Academic year" name="academic_year" required maxLength={50} placeholder="2026-2027" />
                <Field label="Official working days" name="official_working_days" type="number" min={1} max={366} defaultValue={220} required />
              </div>
            )}

            <fieldset className="grid gap-4 sm:grid-cols-2">
              <legend className="mb-2 font-semibold text-navy-900">{kind === 'School' ? 'Principal account' : `${kind} account`}</legend>
              <Field label="Full name" name="name" required maxLength={255} autoComplete="off" />
              <Field label="Email (used for sign-in)" name="email" type="email" required maxLength={255} autoComplete="off" />
              <Field label="Password (at least 8 characters)" name="password" type="password" required minLength={8} maxLength={72} autoComplete="new-password" />
              <Field label="Phone number" name="phone" type="tel" maxLength={40} />
              <Field label="Address" name="address" maxLength={1000} />
              <Field label="Date of birth" name="date_of_birth" type="date" max={maxBirthDate} />
              {kind === 'Teacher' && <Field label="Designation" name="designation" maxLength={255} />}
              {kind === 'Student' && (
                <>
                  <label className="text-sm font-medium text-navy-900">
                    Class section
                    <select name="class_id" defaultValue="" required className={inputClass} disabled={!classes.length}>
                      <option value="">{isLoadingClasses ? 'Loading classes…' : 'Select a class'}</option>
                      {classes.map((section) => <option key={section.id} value={section.id}>{section.name}</option>)}
                    </select>
                  </label>
                  <Field label="Roll number" name="roll_no" type="number" min={1} max={2147483647} required />
                  <label className="text-sm font-medium text-navy-900">
                    Gender
                    <select name="gender" className={inputClass} defaultValue="Other">
                      <option value="Other">Other / unspecified</option>
                      <option value="F">Female</option>
                      <option value="M">Male</option>
                    </select>
                  </label>
                </>
              )}
            </fieldset>
          </fieldset>
          {(classError || error) && <p role="alert" className="text-sm text-rose-700">{error || classError}</p>}
          {saved && <p role="status" className="text-sm text-teal-700">{saved}</p>}
          <Button type="submit" variant="teal" loading={isSaving} disabled={kind === 'Student' && !classes.length}>
            Add {kind}
          </Button>
        </form>
      </CardBody>
    </Card>
  );
}
