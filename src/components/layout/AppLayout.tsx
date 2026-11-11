import React, { useState } from 'react';
import { Outlet, useLocation } from 'react-router-dom';
import { Topbar } from './Topbar';
import { Sidebar } from './Sidebar';
import { RoleSwitcherBanner } from './RoleSwitcherBanner';
import { Menu, X } from 'lucide-react';
import { useAuth } from '../../context/AuthContext';
import { AssistantPanel } from './AssistantPanel';

export const AppLayout: React.FC = () => {
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const location = useLocation();
  const { currentUser, currentSchoolId } = useAuth();

  // Close mobile menu on route change
  React.useEffect(() => {
    setMobileMenuOpen(false);
  }, [location.pathname]);

  return (
    <div className="min-h-screen bg-surface-bg flex flex-col font-sans">
      {/* 1. Global Stakeholder Role Switcher Banner */}
      <RoleSwitcherBanner />

      {/* 2. Topbar Navigation */}
      <Topbar />

      {/* Mobile Drawer Toggle (visible only on small screens) */}
      <div className="md:hidden bg-navy-800 text-white px-4 py-2 flex items-center justify-between border-b border-navy-700">
        <span className="text-xs font-semibold">LumenEIOS Menu</span>
        <button
          onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
          aria-label={mobileMenuOpen ? 'Close navigation menu' : 'Open navigation menu'}
          aria-expanded={mobileMenuOpen}
          className="p-1 rounded bg-navy-700 text-gray-200"
        >
          {mobileMenuOpen ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
        </button>
      </div>

      {/* Main App Container */}
      <div className="flex-1 flex">
        {/* Persistent Desktop Sidebar */}
        <Sidebar />

        {/* Mobile Slideout Sidebar */}
        {mobileMenuOpen && (
          <div className="md:hidden fixed inset-0 z-40 flex">
            <div
              className="fixed inset-0 bg-navy-950/60 backdrop-blur-sm"
              onClick={() => setMobileMenuOpen(false)}
            />
            <div className="relative z-50 w-64 bg-navy-800 h-full flex flex-col shadow-xl">
              <Sidebar mobile />
            </div>
          </div>
        )}

        {/* Dynamic Route Viewport */}
        <main className="min-w-0 flex-1 p-4 sm:p-6 lg:p-8 max-w-7xl mx-auto w-full overflow-x-hidden">
          <Outlet />
        </main>
      </div>
      {currentUser && ['admin', 'teacher', 'principal', 'student', 'parent'].includes(currentUser.role) && (
        <AssistantPanel key={JSON.stringify([currentUser.id, currentUser.role, currentSchoolId])} role={currentUser.role} />
      )}
    </div>
  );
};

