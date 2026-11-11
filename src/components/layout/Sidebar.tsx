import React from 'react';
import { NavLink, useLocation } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';
import {
  LayoutDashboard,
  Building2,
  Users,
  BookOpen,
  Calendar,
  Clock,
  ScanLine,
  FileSpreadsheet,
  CreditCard,
  ShieldCheck,
  GraduationCap,
  Sparkles,
  BarChart3,
  Award,
  HeartHandshake,
  Settings,
  PlusCircle,
  History,
  UserRound,
} from 'lucide-react';
import { cn } from '../../lib/utils';

export const Sidebar: React.FC<{ mobile?: boolean }> = ({ mobile = false }) => {
  const { currentUser } = useAuth();
  const location = useLocation();
  const role = currentUser?.role || 'admin';

  interface NavItem {
    label: string;
    path: string;
    icon: React.ReactNode;
    badge?: string;
    highlight?: boolean;
  }

  const uploadItem: NavItem = {
    label: 'Upload',
    path: '/upload',
    icon: <ScanLine className="w-4 h-4" />,
    badge: 'OCR',
  };
  const uploadBetaItem: NavItem = {
    label: 'Upload Beta',
    path: '/upload-beta',
    icon: <ScanLine className="w-4 h-4" />,
  };

  const questionStudioBetaItem: NavItem = {
    label: 'AI Question Studio Beta',
    path: '/teacher/assessments-beta',
    icon: <Sparkles className="w-4 h-4" />,
  };

  const getNavItems = (): NavItem[] => {
    switch (role) {
      case 'developer':
      case 'admin':
        return [
          { label: 'Platform Overview', path: '/admin/dashboard', icon: <LayoutDashboard className="w-4 h-4" /> },
          { label: 'Schools Directory', path: '/admin/schools', icon: <Building2 className="w-4 h-4" /> },
          { label: 'Add School', path: '/admin/schools/add', icon: <PlusCircle className="w-4 h-4" /> },
          { label: 'Users & Roles', path: '/admin/users', icon: <Users className="w-4 h-4" /> },
          { label: 'Academic Config', path: '/admin/academic-config', icon: <Settings className="w-4 h-4" /> },
          { label: 'Audit & Security', path: '/admin/audit-logs', icon: <ShieldCheck className="w-4 h-4" /> },
        ];

      case 'principal':
        return [
          { label: 'Campus Dashboard', path: '/principal/dashboard', icon: <LayoutDashboard className="w-4 h-4" /> },
          { label: 'Teacher Assignments', path: '/principal/teachers', icon: <Users className="w-4 h-4" /> },
          { label: 'Add Teacher', path: '/principal/teachers/add', icon: <PlusCircle className="w-4 h-4" /> },
          { label: 'Teachers', path: '/principal/staff', icon: <BookOpen className="w-4 h-4" /> },
          { label: 'Students', path: '/principal/students', icon: <GraduationCap className="w-4 h-4" /> },
          { label: 'School Performance', path: '/principal/performance', icon: <BarChart3 className="w-4 h-4" /> },
          { label: 'Classes & Roster', path: '/teacher/classes', icon: <GraduationCap className="w-4 h-4" /> },
          { label: 'Curriculum Oversight', path: '/principal/curriculum', icon: <BookOpen className="w-4 h-4" /> },
          {
            label: 'Time-Aware Engine',
            path: '/teacher/time-aware',
            icon: <Clock className="w-4 h-4" />,
            highlight: true,
            badge: 'Pacing',
          },
          { label: 'Compliance Reports', path: '/principal/reports', icon: <FileSpreadsheet className="w-4 h-4" /> },
          { label: 'Subscription', path: '/principal/subscription', icon: <CreditCard className="w-4 h-4" /> },
        ];

      case 'teacher':
        return [
          { label: 'Teacher Dashboard', path: '/teacher/dashboard', icon: <LayoutDashboard className="w-4 h-4" /> },
          { label: 'My Classes & Heatmap', path: '/teacher/classes', icon: <Users className="w-4 h-4" /> },
          { label: 'Add Student', path: '/teacher/students/add', icon: <PlusCircle className="w-4 h-4" /> },
          { label: '180-Day Curriculum', path: '/teacher/curriculum-180', icon: <Calendar className="w-4 h-4" /> },
          questionStudioBetaItem,
          { label: 'Differentiated Homework', path: '/teacher/remediation', icon: <Sparkles className="w-4 h-4" /> },
          { label: 'Student Homework', path: '/teacher/student-homework', icon: <FileSpreadsheet className="w-4 h-4" />, badge: 'Demo' },
          uploadItem,
          uploadBetaItem,
        ];

      case 'student':
        return [
          { label: 'My Learning Mission', path: '/student/dashboard', icon: <LayoutDashboard className="w-4 h-4" /> },
          { label: 'Answer Sheet OCR', path: '/student/answer-sheets', icon: <ScanLine className="w-4 h-4" />, badge: 'Demo' },
          { label: 'Adaptive Practice', path: '/student/dashboard', icon: <Sparkles className="w-4 h-4" /> },
          { label: 'My Achievements', path: '/student/dashboard', icon: <Award className="w-4 h-4" /> },
          uploadItem,
          uploadBetaItem,
          { label: 'History', path: '/student/history', icon: <History className="w-4 h-4" /> },
          { label: 'Profile', path: '/student/profile', icon: <UserRound className="w-4 h-4" /> },
        ];

      case 'parent':
        return [
          { label: 'Family Progress', path: '/parent/dashboard', icon: <LayoutDashboard className="w-4 h-4" /> },
          { label: 'Competency Growth', path: '/parent/dashboard', icon: <BarChart3 className="w-4 h-4" /> },
          { label: 'Home Learning Guide', path: '/parent/dashboard', icon: <HeartHandshake className="w-4 h-4" /> },
        ];

      default:
        return [];
    }
  };

  const navItems = getNavItems();

  return (
    <aside className={cn(
      'w-64 bg-navy-800 text-white shrink-0 flex-col border-r border-navy-700',
      mobile ? 'flex h-full' : 'hidden md:flex min-h-[calc(100vh-4rem)]'
    )}>
      {/* Brand Header */}
      <div className="p-5 border-b border-navy-700/60 flex items-center gap-3">
        <div className="w-9 h-9 rounded-xl bg-teal-500 text-navy-950 flex items-center justify-center font-black text-lg shadow-sm">
          L
        </div>
        <div>
          <h1 className="font-bold text-base tracking-tight text-white leading-none">
            Lumen<span className="text-teal-400">EIOS</span>
          </h1>
          <p className="text-[11px] text-gray-400 mt-1 font-medium">Adaptive EdTech NEP 2020</p>
        </div>
      </div>

      {/* Role Pill Banner */}
      <div className="px-5 py-3 bg-navy-900/60 border-b border-navy-700/40">
        <div className="flex items-center justify-between text-xs">
          <span className="text-gray-400">Workspace:</span>
          <span className="capitalize font-semibold text-teal-400 bg-teal-500/10 px-2 py-0.5 rounded border border-teal-500/20">
            {role} Portal
          </span>
        </div>
      </div>

      {/* Navigation List */}
      <nav className="flex-1 p-3.5 space-y-1 overflow-y-auto">
        {navItems.map((item) => {
          const isActive = location.pathname === item.path;
          return (
            <NavLink
              key={item.label}
              to={item.path}
              end
              className={cn(
                'flex items-center justify-between px-3.5 py-2.5 rounded-lg text-xs font-medium transition-colors group',
                isActive
                  ? 'bg-teal-500 text-white shadow-sm'
                  : item.highlight
                  ? 'text-amber-300 hover:bg-navy-700 hover:text-white bg-amber-500/10'
                  : 'text-gray-300 hover:bg-navy-700 hover:text-white'
              )}
            >
              <div className="flex items-center gap-3">
                <span className={cn('shrink-0', isActive ? 'text-white' : 'text-gray-400 group-hover:text-white')}>
                  {item.icon}
                </span>
                <span>{item.label}</span>
              </div>
              {item.badge && (
                <span
                  className={cn(
                    'text-[10px] px-1.5 py-0.5 rounded font-semibold',
                    isActive
                      ? 'bg-white/20 text-white'
                      : item.highlight
                      ? 'bg-amber-400 text-navy-950'
                      : 'bg-navy-700 text-gray-300'
                  )}
                >
                  {item.badge}
                </span>
              )}
            </NavLink>
          );
        })}
      </nav>

      {/* Footer Info Box */}
      <div className="p-4 m-3 rounded-xl bg-navy-900/80 border border-navy-700 text-xs">
        <p className="font-semibold text-teal-300">Pedagogical Guardrail</p>
        <p className="text-[11px] text-gray-400 mt-1 leading-relaxed">
          Protects 60% Core Competencies when calendar disruptions occur.
        </p>
      </div>
    </aside>
  );
};

