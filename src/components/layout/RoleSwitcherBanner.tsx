import React from 'react';
import { useNavigate } from 'react-router-dom';
import { demoMode, useAuth } from '../../context/AuthContext';
import { Role } from '../../types';
import { getDefaultDashboardPath } from '../../lib/permissions';
import { Sparkles, ArrowRight, Shield, GraduationCap, School, BookOpen, Users, Code } from 'lucide-react';

export const RoleSwitcherBanner: React.FC = () => {
  const { currentUser, loginAsRole } = useAuth();
  const navigate = useNavigate();
  const [switching, setSwitching] = React.useState(false);
  const [error, setError] = React.useState('');

  const roles: Array<{ role: Role; label: string; icon: React.ReactNode }> = [
    ...(currentUser?.demoRoot
      ? [{ role: 'developer' as const, label: 'Developer', icon: <Code className="w-3.5 h-3.5" /> }]
      : []),
    { role: 'admin', label: 'Admin', icon: <Shield className="w-3.5 h-3.5" /> },
    { role: 'principal', label: 'Principal', icon: <School className="w-3.5 h-3.5" /> },
    { role: 'teacher', label: 'Teacher', icon: <BookOpen className="w-3.5 h-3.5" /> },
    { role: 'student', label: 'Student', icon: <GraduationCap className="w-3.5 h-3.5" /> },
    { role: 'parent', label: 'Parent', icon: <Users className="w-3.5 h-3.5" /> },
  ];

  const handleRoleSelect = async (role: Role) => {
    setSwitching(true);
    setError('');
    try {
      const user = await loginAsRole(role);
      navigate(getDefaultDashboardPath(user.role));
    } catch {
      setError('Could not sign in to the demo account.');
    } finally {
      setSwitching(false);
    }
  };

  if (!demoMode && !currentUser?.demoRoot) return null;

  return (
    <div className="bg-navy-900 text-white px-4 py-2 text-xs flex flex-wrap items-center justify-between gap-2 border-b border-navy-800">
      <div className="flex items-center gap-2">
        <span className="flex items-center gap-1.5 font-semibold text-teal-400">
          <Sparkles className="w-3.5 h-3.5" />
          <span>{currentUser?.demoRoot ? 'Root access' : 'Interactive Stakeholder Prototype'}</span>
        </span>
        <span className="text-gray-400 hidden md:inline">• Active Persona:</span>
        <span className="bg-teal-500/20 text-teal-300 px-2 py-0.5 rounded font-mono font-medium hidden md:inline">
          {currentUser?.name} ({currentUser?.role})
        </span>
      </div>

      <div className="flex min-w-0 flex-wrap items-center gap-1.5">
        <span className="text-gray-400 text-[11px] hidden lg:inline mr-1">
          {currentUser?.demoRoot ? 'Open any role:' : 'Switch Persona:'}
        </span>
        {error && <span role="alert">{error}</span>}
        {roles.map((item) => {
          const isActive = currentUser?.role === item.role;
          return (
            <button
              key={item.role}
              disabled={switching}
              onClick={() => handleRoleSelect(item.role)}
              className={`inline-flex shrink-0 items-center gap-1.5 whitespace-nowrap px-2.5 py-1 rounded-md text-[11px] font-medium transition-all ${
                isActive
                  ? 'bg-teal-500 text-white shadow-sm ring-1 ring-teal-400'
                  : 'bg-navy-800 text-gray-300 hover:bg-navy-700 hover:text-white'
              }`}
            >
              {item.icon}
              <span>{item.label}</span>
            </button>
          );
        })}

        {currentUser?.role === 'principal' && (
          <button
            onClick={() => navigate('/teacher/time-aware')}
            className="inline-flex shrink-0 items-center gap-1 whitespace-nowrap text-[11px] text-amber-300 hover:text-amber-200 bg-amber-500/10 hover:bg-amber-500/20 px-2 py-1 rounded border border-amber-500/30 transition-colors"
            title="Direct link to signature Time-Aware Pedagogical Engine"
          >
            <span>Time-Aware Engine</span>
            <ArrowRight className="w-3 h-3" />
          </button>
        )}
      </div>
    </div>
  );
};

