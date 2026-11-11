import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';
import { useData } from '../../context/DataContext';
import { apiClient } from '../../lib/apiClient';
import type { School } from '../../types';
import {
  Bell,
  Search,
  Building2,
  ChevronDown,
  LogOut,
  RotateCcw,
  User as UserIcon,
  CheckCircle,
  ExternalLink,
  ShieldAlert,
} from 'lucide-react';
import { Badge } from '../common/Badge';
import { ThemeMenu } from './ThemeMenu';
import { FontSizeControl } from './FontSizeControl';

export const Topbar: React.FC = () => {
  const { currentUser, currentSchoolId, switchSchool, logout } = useAuth();
  const { schools, notifications, markNotificationAsRead, resetDemoData } = useData();
  const navigate = useNavigate();

  const [showSchoolMenu, setShowSchoolMenu] = useState(false);
  const [showNotifMenu, setShowNotifMenu] = useState(false);
  const [showUserMenu, setShowUserMenu] = useState(false);

  const localSchool = schools.find((s) => s.id === currentSchoolId);
  const [loadedSchool, setLoadedSchool] = useState<Pick<School, 'id' | 'name' | 'state' | 'infrastructureTier'>>();
  const currentSchool = localSchool || (loadedSchool?.id === currentSchoolId ? loadedSchool : undefined);

  useEffect(() => {
    if (localSchool) return;
    let active = true;
    apiClient.schools.getById(currentSchoolId).then((school) => {
      if (active) setLoadedSchool({
        id: school.id,
        name: school.name,
        state: school.state,
        infrastructureTier: school.infrastructure_tier,
      });
    }).catch(() => {});
    return () => { active = false; };
  }, [currentSchoolId, localSchool]);
  const userNotifications = notifications.filter(
    (n) => !currentUser || n.userId === currentUser.id || n.userId === 'user-active'
  );
  const unreadCount = userNotifications.filter((n) => !n.read).length;

  const handleResetData = () => {
    if (window.confirm('Reset all demo data back to initial baseline? All custom edits will be restored.')) {
      resetDemoData();
      window.location.reload();
    }
  };

  return (
    <header className="h-16 bg-white border-b border-surface-border sticky top-0 z-30 flex items-center justify-between px-4 sm:px-6 shadow-subtle">
      {/* Left: Current School Switcher */}
      <div className="flex items-center gap-3">
        <div className="relative">
          <button
            onClick={() => setShowSchoolMenu(!showSchoolMenu)}
            className="flex items-center gap-2.5 px-3 py-1.5 rounded-lg border border-surface-border hover:bg-surface-bg transition-colors text-left text-sm"
          >
            <div className="w-7 h-7 rounded-md bg-navy-800 text-white flex items-center justify-center font-bold text-xs shrink-0">
              <Building2 className="w-4 h-4" />
            </div>
            <div className="hidden sm:block">
              <div className="flex items-center gap-1.5">
                <span className="font-semibold text-content-primary leading-tight line-clamp-1 max-w-[190px]">
                  {currentSchool?.name || 'Active campus'}
                </span>
                <ChevronDown className="w-3.5 h-3.5 text-content-secondary" />
              </div>
              <span className="text-[11px] text-content-secondary">
                {currentSchool && `${currentSchool.state} • ${currentSchool.infrastructureTier}`}
              </span>
            </div>
          </button>

          {showSchoolMenu && (
            <div className="absolute left-0 mt-1.5 w-72 bg-white rounded-xl shadow-modal border border-surface-border py-2 z-50 animate-fade-in">
              <div className="px-3.5 py-1.5 text-[11px] font-semibold text-content-secondary uppercase tracking-wider">
                Select Active Campus Context
              </div>
              <div className="max-h-60 overflow-y-auto">
                {schools.map((sch) => (
                  <button
                    key={sch.id}
                    onClick={async () => {
                      try {
                        await switchSchool(sch.id);
                      } catch {
                        window.alert('Could not switch to that school.');
                      }
                      setShowSchoolMenu(false);
                    }}
                    className={`w-full px-3.5 py-2 text-left text-xs hover:bg-surface-bg flex items-center justify-between transition-colors ${
                      sch.id === currentSchoolId ? 'bg-teal-50/60 font-semibold text-teal-800' : 'text-content-primary'
                    }`}
                  >
                    <div>
                      <div className="font-medium">{sch.name}</div>
                      <div className="text-[10px] text-content-secondary">
                        {sch.location} ({sch.infrastructureTier})
                      </div>
                    </div>
                    {sch.id === currentSchoolId && (
                      <CheckCircle className="w-4 h-4 text-teal-600 shrink-0" />
                    )}
                  </button>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* NEP 2020 Compliance Indicator */}
        <Badge variant="teal" size="sm" className="hidden lg:inline-flex">
          NEP 2020 Pedagogical Engine
        </Badge>
      </div>

      {/* Right Controls: Notifications, Reset Demo Data, User Profile */}
      <div className="flex items-center gap-2.5">
        <FontSizeControl />
        <ThemeMenu />

        {/* Reset Demo Data Pill */}
        <button
          onClick={handleResetData}
          title="Reset LocalStorage demo data to clean baseline"
          aria-label="Reset Demo Data"
          className="flex shrink-0 items-center gap-1.5 px-2.5 py-1.5 text-xs font-medium text-content-secondary hover:text-navy-800 hover:bg-surface-bg border border-surface-border rounded-lg transition-colors"
        >
          <RotateCcw className="w-3.5 h-3.5 text-content-muted" />
          <span className="hidden lg:inline">Reset Demo Data</span>
        </button>

        {/* Notifications Dropdown */}
        <div className="relative">
          <button
            onClick={() => setShowNotifMenu(!showNotifMenu)}
            className="p-2 text-content-secondary hover:text-content-primary hover:bg-surface-bg rounded-lg relative transition-colors"
            title="System & Pedagogical Notifications"
          >
            <Bell className="w-5 h-5" />
            {unreadCount > 0 && (
              <span className="absolute top-1 right-1 w-4 h-4 bg-rose-500 text-white rounded-full text-[10px] font-bold flex items-center justify-center">
                {unreadCount}
              </span>
            )}
          </button>

          {showNotifMenu && (
            <div className="absolute right-0 mt-1.5 w-80 sm:w-96 bg-white rounded-xl shadow-modal border border-surface-border py-2 z-50 animate-fade-in">
              <div className="px-4 py-2 border-b border-surface-border flex items-center justify-between">
                <span className="font-semibold text-sm text-content-primary">Notifications</span>
                <span className="text-xs text-content-secondary">{unreadCount} unread</span>
              </div>
              <div className="max-h-72 overflow-y-auto divide-y divide-surface-border">
                {userNotifications.length === 0 ? (
                  <div className="p-4 text-center text-xs text-content-secondary">
                    No active notifications
                  </div>
                ) : (
                  userNotifications.map((notif) => (
                    <div
                      key={notif.id}
                      onClick={() => {
                        markNotificationAsRead(notif.id);
                        if (notif.link) {
                          navigate(notif.link);
                          setShowNotifMenu(false);
                        }
                      }}
                      className={`p-3 text-xs cursor-pointer hover:bg-surface-bg transition-colors ${
                        !notif.read ? 'bg-teal-50/30' : ''
                      }`}
                    >
                      <div className="flex items-start justify-between gap-2">
                        <span className="font-semibold text-content-primary">{notif.title}</span>
                        <span className="text-[10px] text-content-muted shrink-0">{notif.createdAt}</span>
                      </div>
                      <p className="text-content-secondary mt-1 text-[11px] leading-relaxed">
                        {notif.message}
                      </p>
                    </div>
                  ))
                )}
              </div>
            </div>
          )}
        </div>

        {/* User Profile Menu */}
        <div className="relative">
          <button
            onClick={() => setShowUserMenu(!showUserMenu)}
            className="flex items-center gap-2 pl-2 pr-1.5 py-1 rounded-lg hover:bg-surface-bg border border-transparent hover:border-surface-border transition-colors"
          >
            <div className="w-8 h-8 rounded-full bg-navy-800 text-white flex items-center justify-center text-xs font-bold overflow-hidden border border-navy-700">
              {currentUser?.avatar ? (
                <img src={currentUser.avatar} alt={currentUser.name} className="w-full h-full object-cover" />
              ) : (
                <UserIcon className="w-4 h-4" />
              )}
            </div>
            <div className="hidden sm:block text-left">
              <div className="text-xs font-semibold text-content-primary leading-tight">
                {currentUser?.name}
              </div>
              <div className="text-[10px] text-teal-600 font-medium capitalize">
                {currentUser?.role}
              </div>
            </div>
            <ChevronDown className="w-3.5 h-3.5 text-content-secondary" />
          </button>

          {showUserMenu && (
            <div className="absolute right-0 mt-1.5 w-56 bg-white rounded-xl shadow-modal border border-surface-border py-1.5 z-50 animate-fade-in">
              <div className="px-3.5 py-2 border-b border-surface-border">
                <p className="text-xs font-semibold text-content-primary">{currentUser?.name}</p>
                <p className="text-[11px] text-content-secondary truncate">{currentUser?.email}</p>
                <div className="mt-1.5">
                  <Badge variant="teal" size="sm">
                    Role: {currentUser?.role}
                  </Badge>
                </div>
              </div>

              <div className="p-1">
                <button
                  onClick={() => {
                    setShowUserMenu(false);
                    navigate('/login');
                  }}
                  className="w-full px-3 py-1.5 text-xs text-content-secondary hover:text-content-primary hover:bg-surface-bg rounded-lg text-left flex items-center gap-2 transition-colors"
                >
                  <UserIcon className="w-3.5 h-3.5" />
                  <span>Switch Demo Persona</span>
                </button>

                <button
                  onClick={() => {
                    setShowUserMenu(false);
                    logout();
                    navigate('/login');
                  }}
                  className="w-full px-3 py-1.5 text-xs text-rose-600 hover:bg-rose-50 rounded-lg text-left flex items-center gap-2 transition-colors"
                >
                  <LogOut className="w-3.5 h-3.5" />
                  <span>Log Out</span>
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </header>
  );
};

