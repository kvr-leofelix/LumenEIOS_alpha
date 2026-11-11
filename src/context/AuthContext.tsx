import React, { createContext, useContext, useState, useEffect } from 'react';
import { User, Role } from '../types';
import { initialUsers } from '../data/seedData';
import { apiClient } from '../lib/apiClient';

export const demoMode = (import.meta as any).env?.VITE_DEMO_MODE === 'true';

interface AuthContextType {
  currentUser: User | null;
  currentSchoolId: string;
  isRestoringSession: boolean;
  login: (email: string, password: string) => Promise<User>;
  loginAsRole: (role: Role) => Promise<User>;
  logout: () => void;
  switchSchool: (schoolId: string) => Promise<void>;
  availableUsers: User[];
  isAuthenticated: boolean;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

function toUser(user: Awaited<ReturnType<typeof apiClient.auth.me>>): User {
  return { ...user, schoolId: user.school_id || '', demoRoot: user.demo_root === true };
}

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [currentUser, setCurrentUser] = useState<User | null>(null);
  const [isRestoringSession, setIsRestoringSession] = useState(
    () => !!localStorage.getItem('lumeneios_token')
  );
  const currentSchoolId = currentUser?.schoolId || 'school-1';

  const acceptUser = (user: User) => {
    localStorage.setItem('lumeneios_current_school', user.schoolId || 'school-1');
    setCurrentUser(user);
  };

  useEffect(() => {
    localStorage.removeItem('lumeneios_auth_user');
    if (!localStorage.getItem('lumeneios_token')) return;
    let active = true;
    apiClient.auth.me()
      .then((user) => { if (active) acceptUser(toUser(user)); })
      .catch(() => { if (active) localStorage.removeItem('lumeneios_token'); })
      .finally(() => { if (active) setIsRestoringSession(false); });
    return () => { active = false; };
  }, []);

  const login = async (email: string, password: string) => {
    const response = await apiClient.auth.login(email.trim(), password);
    const user = toUser(response.user);
    acceptUser(user);
    return user;
  };

  const loginAsRole = async (role: Role) => {
    if (currentUser?.demoRoot) {
      const user = toUser(await apiClient.auth.switchDemoRole(role));
      acceptUser(user);
      return user;
    }
    const user = initialUsers.find((candidate) => candidate.role === role);
    if (!demoMode || !user) throw new Error('Demo sign-in is disabled.');
    return login(user.email, 'demo123');
  };

  const logout = () => {
    void apiClient.auth.logout();
    localStorage.removeItem('lumeneios_current_school');
    setCurrentUser(null);
  };

  const switchSchool = async (schoolId: string) => {
    const response = await apiClient.auth.switchSchool(schoolId);
    acceptUser(toUser(response.user));
  };

  return (
    <AuthContext.Provider value={{
      currentUser, currentSchoolId, isRestoringSession, login, loginAsRole, logout,
      switchSchool, availableUsers: initialUsers, isAuthenticated: !!currentUser,
    }}>
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) throw new Error('useAuth must be used within an AuthProvider');
  return context;
};
