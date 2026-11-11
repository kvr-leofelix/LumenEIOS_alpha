import { Role } from '../types';

export const PERMISSIONS = {
  MANAGE_SCHOOLS: ['admin'],
  MANAGE_USERS: ['admin'],
  VIEW_GLOBAL_ANALYTICS: ['admin'],
  AUDIT_LOGS: ['admin'],
  ASSIGN_TEACHERS: ['admin', 'principal'],
  REVIEW_LESSON_PLANS: ['admin', 'principal'],
  VIEW_SCHOOL_METRICS: ['admin', 'principal'],
  SEND_ANNOUNCEMENTS: ['admin', 'principal', 'teacher'],
  MANAGE_CLASSES: ['admin', 'principal', 'teacher'],
  CREATE_ASSESSMENT: ['admin', 'principal', 'teacher'],
  GRADE_ASSESSMENT: ['teacher'],
  RECORD_LOST_DAYS: ['admin', 'principal', 'teacher'],
  PREVIEW_COMPRESSION: ['admin', 'principal', 'teacher'],
  APPROVE_COMPRESSION: ['admin', 'principal', 'teacher'],
  ASSIGN_REMEDIATION: ['teacher'],
  SUBMIT_ASSIGNMENTS: ['student'],
  REVIEW_STUDENT_SHEETS: ['teacher'],
  VIEW_CHILD_PROGRESS: ['parent'],
  ADD_STUDENT: ['principal'],
  ADD_TEACHER: ['principal'],
} as const;

export function hasPermission(role: Role, permission: keyof typeof PERMISSIONS): boolean {
  if (role === 'developer') return true;
  const allowedRoles = PERMISSIONS[permission] as readonly string[];
  return allowedRoles.includes(role);
}

export function getDefaultDashboardPath(role: Role): string {
  switch (role) {
    case 'developer':
    case 'admin':
      return '/admin/dashboard';
    case 'principal':
      return '/principal/dashboard';
    case 'teacher':
      return '/teacher/dashboard';
    case 'student':
      return '/student/dashboard';
    case 'parent':
      return '/parent/dashboard';
    default:
      return '/login';
  }
}

