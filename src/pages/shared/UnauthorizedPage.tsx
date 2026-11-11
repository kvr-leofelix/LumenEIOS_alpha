import React from 'react';
import { useNavigate } from 'react-router-dom';
import { Button } from '../../components/common/Button';
import { useAuth } from '../../context/AuthContext';
import { getDefaultDashboardPath } from '../../lib/permissions';
import { ShieldAlert, ArrowLeft } from 'lucide-react';

export const UnauthorizedPage: React.FC = () => {
  const navigate = useNavigate();
  const { currentUser } = useAuth();
  const target = currentUser ? getDefaultDashboardPath(currentUser.role) : '/login';

  return (
    <div className="min-h-[70vh] flex flex-col items-center justify-center text-center p-6">
      <div className="w-16 h-16 rounded-2xl bg-rose-50 text-rose-600 flex items-center justify-center mb-4">
        <ShieldAlert className="w-8 h-8" />
      </div>
      <h1 className="text-2xl font-bold text-navy-900">Access Restricted</h1>
      <p className="text-xs text-content-secondary mt-1.5 max-w-sm">
        Your current persona ({currentUser?.role || 'Guest'}) does not hold administrative authorization for this workspace. Use the top persona switcher to change roles.
      </p>
      <div className="mt-5">
        <Button variant="primary" size="md" onClick={() => navigate(target)} icon={<ArrowLeft className="w-4 h-4" />}>
          Return to Authorized Dashboard
        </Button>
      </div>
    </div>
  );
};

