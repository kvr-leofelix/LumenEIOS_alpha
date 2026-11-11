import React, { useCallback, useEffect, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { Card } from '../../components/common/Card';
import { Button } from '../../components/common/Button';
import { apiClient, ApiError, SubscriptionRow } from '../../lib/apiClient';
import { CheckCircle2, ExternalLink, AlertTriangle } from 'lucide-react';

const OPEN_STATUSES = ['APPROVAL_PENDING', 'APPROVED', 'ACTIVE', 'SUSPENDED'];

const STATUS_LABELS: Record<string, string> = {
  APPROVAL_PENDING: 'Waiting for approval on PayPal',
  APPROVED: 'Approved, starting soon',
  ACTIVE: 'Active',
  SUSPENDED: 'Suspended, payment needed',
  CANCELLED: 'Cancelled',
  EXPIRED: 'Expired',
};

const KIND_TITLES: Record<SubscriptionRow['kind'], string> = {
  base: 'School plan',
  seats: 'Teacher seats',
};

const KIND_PRICES: Record<SubscriptionRow['kind'], string> = {
  base: '$20 per month for the school',
  seats: '$5 per month per teacher',
};

const RESULT_NOTICES: Record<string, string> = {
  return: 'Thanks. Once PayPal confirms each approval, the status below will update. This can take a short moment.',
  cancel: 'Checkout was cancelled. Nothing was charged. You can start again whenever you are ready.',
};

export const SchoolSubscription: React.FC = () => {
  const [searchParams, setSearchParams] = useSearchParams();
  const [rows, setRows] = useState<SubscriptionRow[]>([]);
  const [approveLinks, setApproveLinks] = useState<string[]>([]);
  const [teacherCount, setTeacherCount] = useState(1);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const result = searchParams.get('result');
  const requestedSeats = Number(searchParams.get('teacherSeats'));

  useEffect(() => {
    if (Number.isInteger(requestedSeats) && requestedSeats >= 1 && requestedSeats <= 500) {
      setTeacherCount(requestedSeats);
    }
  }, [requestedSeats]);

  const loadStatus = useCallback(async () => {
    setError(null);
    try {
      setRows(await apiClient.subscriptions.status());
    } catch (err: any) {
      setError(err instanceof ApiError ? err.message : 'Could not load your subscription.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadStatus();
  }, [loadStatus]);

  useEffect(() => {
    if (result && RESULT_NOTICES[result]) {
      setNotice(RESULT_NOTICES[result]);
      // Clear the query string so a refresh does not show the notice again.
      setSearchParams({}, { replace: true });
    }
  }, [result, setSearchParams]);

  const base = rows.find((r) => r.kind === 'base');
  const seats = rows.find((r) => r.kind === 'seats');
  const hasOpenSubscription = rows.some((r) => OPEN_STATUSES.includes(r.status));
  const seatsActive = seats?.status === 'ACTIVE';

  const runAction = async (action: () => Promise<void>) => {
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      await action();
    } catch (err: any) {
      setError(err instanceof ApiError ? err.message : 'Something went wrong. Please try again.');
    } finally {
      setBusy(false);
    }
  };

  const handleStart = () =>
    runAction(async () => {
      const res = await apiClient.subscriptions.start(teacherCount);
      setRows(res.subscriptions);
      setApproveLinks(res.approve_links);
      setNotice('Your subscriptions are created. Approve each one on PayPal below.');
    });

  const handleChangeSeats = () =>
    runAction(async () => {
      await apiClient.subscriptions.changeSeats(teacherCount);
      await loadStatus();
      setNotice(`Teacher seats updated to ${teacherCount}.`);
    });

  const openApproval = (link: string) => {
    window.open(link, '_blank', 'noopener,noreferrer');
  };

  const invalidCount = !Number.isInteger(teacherCount) || teacherCount < 1 || teacherCount > 500;

  return (
    <div className="space-y-6">
      <div className="bg-white p-5 rounded-2xl border border-surface-border shadow-subtle">
        <h1 className="text-xl font-bold text-navy-900 tracking-tight">School subscription</h1>
        <p className="mt-1 text-sm text-content-secondary">
          Pay for the school plan and for each teacher seat through PayPal. You approve each subscription on PayPal.
        </p>
      </div>

      {notice && (
        <div role="status" className="flex items-start gap-2 rounded-xl border border-teal-500/40 bg-teal-50 p-4 text-sm text-navy-900">
          <CheckCircle2 className="w-4 h-4 mt-0.5 text-teal-600 shrink-0" />
          <span>{notice}</span>
        </div>
      )}
      {error && (
        <div role="alert" className="flex items-start gap-2 rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-800">
          <AlertTriangle className="w-4 h-4 mt-0.5 shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {loading ? (
        <p role="status" className="text-sm text-content-secondary">Loading subscription…</p>
      ) : (
        <div className="grid gap-4 md:grid-cols-2">
          {(['base', 'seats'] as const).map((kind) => {
            const row = kind === 'base' ? base : seats;
            return (
              <Card key={kind} className="p-5">
                <h2 className="text-base font-semibold text-navy-900">{KIND_TITLES[kind]}</h2>
                <p className="mt-1 text-xs text-content-secondary">{KIND_PRICES[kind]}</p>
                <div className="mt-4 space-y-1 text-sm">
                  <p>
                    <span className="text-content-secondary">Status: </span>
                    <span className="font-medium">{row ? STATUS_LABELS[row.status] ?? row.status : 'Not started'}</span>
                  </p>
                  {row && (
                    <p>
                      <span className="text-content-secondary">Quantity: </span>
                      <span className="font-medium">{row.quantity}</span>
                    </p>
                  )}
                </div>
              </Card>
            );
          })}
        </div>
      )}

      {!loading && !hasOpenSubscription && (
        <Card className="p-5 space-y-4">
          <div>
            <h2 className="text-base font-semibold text-navy-900">Start subscription</h2>
            <p className="mt-1 text-sm text-content-secondary">
              Enter how many teachers the school has. You will be charged $5 per teacher each month, plus $20 for the school.
            </p>
          </div>
          <div className="flex flex-col sm:flex-row sm:items-end gap-3">
            <label className="flex flex-col text-sm">
              <span className="mb-1 text-content-secondary">Number of teachers</span>
              <input
                type="number"
                min={1}
                max={500}
                value={teacherCount}
                onChange={(e) => setTeacherCount(Number(e.target.value))}
                className="w-40 rounded-lg border border-surface-border px-3 py-2 text-sm"
              />
            </label>
            <Button variant="teal" onClick={handleStart} loading={busy} disabled={invalidCount || busy}>
              Start subscription
            </Button>
          </div>
          {invalidCount && <p className="text-xs text-red-700">Enter a number from 1 to 500.</p>}
        </Card>
      )}

      {approveLinks.length > 0 && (
        <Card className="p-5 space-y-3">
          <h2 className="text-base font-semibold text-navy-900">Approve on PayPal</h2>
          <p className="text-sm text-content-secondary">Approve each subscription. Each opens in a new tab.</p>
          <div className="flex flex-wrap gap-3">
            {approveLinks.map((link, index) => (
              <Button key={link} variant="outline" onClick={() => openApproval(link)} icon={<ExternalLink className="w-4 h-4" />}>
                Approve {index === 0 ? 'school plan' : 'teacher seats'}
              </Button>
            ))}
          </div>
        </Card>
      )}

      {!loading && seatsActive && (
        <Card className="p-5 space-y-4">
          <div>
            <h2 className="text-base font-semibold text-navy-900">Change teacher seats</h2>
            <p className="mt-1 text-sm text-content-secondary">
              Update the number of teachers. PayPal prorates the change on your next bill.
            </p>
          </div>
          <div className="flex flex-col sm:flex-row sm:items-end gap-3">
            <label className="flex flex-col text-sm">
              <span className="mb-1 text-content-secondary">Number of teachers</span>
              <input
                type="number"
                min={1}
                max={500}
                value={teacherCount}
                onChange={(e) => setTeacherCount(Number(e.target.value))}
                className="w-40 rounded-lg border border-surface-border px-3 py-2 text-sm"
              />
            </label>
            <Button variant="primary" onClick={handleChangeSeats} loading={busy} disabled={invalidCount || busy}>
              Update seats
            </Button>
          </div>
          {invalidCount && <p className="text-xs text-red-700">Enter a number from 1 to 500.</p>}
        </Card>
      )}
    </div>
  );
};
