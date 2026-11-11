# LumenEIOS Frontend-to-Backend API Mapping

This document provides a comprehensive mapping between the existing React + Vite + TypeScript frontend routes, UI components, interactive workflows, and the corresponding backend FastAPI REST endpoints.

---

## 1. Authentication & Tenant Session Workflows

### 1.1 Login & Persona Switcher
- **Frontend Route**: `/login`, Topbar Persona Switcher, `RoleSwitcherBanner`
- **Frontend Component**: `src/pages/auth/LoginPage.tsx`, `src/context/AuthContext.tsx`
- **UI Trigger**: Form submit with email & password, or clicking any of the 5 demo persona cards (`admin`, `principal`, `teacher`, `student`, `parent`).
- **Backend API Endpoint**: `POST /api/v1/auth/login`
- **Request Schema**:
  ```json
  {
    "email": "teacher@lumeneios.demo",
    "password": "demo123"
  }
  ```
- **Response Schema**:
  ```json
  {
    "access_token": "string",
    "refresh_token": "string",
    "token_type": "bearer",
    "expires_in": 3600,
    "user": {
      "id": "uuid",
      "email": "string",
      "name": "string",
      "role": "admin | principal | teacher | student | parent",
      "school_id": "uuid",
      "designation": "string",
      "avatar": "string",
      "assigned_class_ids": ["uuid"],
      "assigned_subject_ids": ["uuid"],
      "linked_child_ids": ["uuid"]
    }
  }
  ```
- **Permissions**: Public (`AllowAny`)
- **Persistence Behavior**: Validates credentials against `users` table, verifies password hash, issues short-lived JWT and HTTP-only refresh cookie, logs `AUTH_LOGIN` audit event.

### 1.2 Current User & Authorized Memberships
- **Frontend Hook**: `useAuth()` in `src/context/AuthContext.tsx`
- **Backend API Endpoint**: `GET /api/v1/auth/me` and `GET /api/v1/auth/memberships`
- **Permissions**: Authenticated user (`Bearer <token>`)
- **Response Schema**: User entity and array of `SchoolMembership` entities.

### 1.3 School Context Switching
- **Frontend Trigger**: Topbar campus dropdown (`Sunrise Public School`, `Green Valley Academy`, etc.)
- **Backend API Endpoint**: `POST /api/v1/auth/switch-school`
- **Request Schema**:
  ```json
  {
    "school_id": "school-1"
  }
  ```
- **Response Schema**: Refreshed session token with authorized `active_school_id` claims.
- **Permissions**: Verified membership in target school or platform `admin`.

---

## 2. Schools, Users, & Campus Administration

### 2.1 Multi-School Network Directory
- **Frontend Route**: `/admin/schools`
- **Frontend Component**: `src/pages/admin/SchoolsManagement.tsx`
- **Backend API Endpoints**:
  - `GET /api/v1/schools` (Filters: `infrastructure_tier`, `search`, pagination)
  - `POST /api/v1/schools` (Create campus)
  - `GET /api/v1/schools/{school_id}` (Retrieve campus profile)
  - `PATCH /api/v1/schools/{school_id}` (Update campus profile)
  - `POST /api/v1/schools/{school_id}/archive` (Archive school)
- **Request Schema (`POST /schools`)**:
  ```json
  {
    "name": "Sunrise Public School",
    "location": "Indiranagar, Bengaluru",
    "state": "Karnataka",
    "infrastructure_tier": "high-tech | standard | low-tech",
    "principal_name": "Dr. Sunita Deshmukh",
    "student_count": 850,
    "teacher_count": 42,
    "class_count": 18,
    "description": "string",
    "official_working_days": 220
  }
  ```
- **Permissions**: Platform `admin` only.
- **Persistence Behavior**: Stored in `schools` table; triggers transaction and audit log.

### 2.2 Users & Role Management
- **Frontend Route**: `/admin/users`
- **Frontend Component**: `src/pages/admin/UsersManagement.tsx`
- **Backend API Endpoints**:
  - `GET /api/v1/users` (Filters: `role`, `school_id`, `search`)
  - `POST /api/v1/users` (Create user)
  - `PATCH /api/v1/users/{user_id}` (Update profile & roles)
- **Permissions**: Platform `admin` only.

### 2.3 Teacher Class Allocations
- **Frontend Route**: `/principal/teachers`
- **Frontend Component**: `src/pages/principal/TeacherAssignments.tsx`
- **UI Trigger**: "Reassign" button opening faculty reallocation modal.
- **Backend API Endpoint**: `POST /api/v1/classes/{class_id}/assignments`
- **Request Schema**:
  ```json
  {
    "teacher_id": "user-teacher-1",
    "is_lead_teacher": true
  }
  ```
- **Permissions**: `admin`, `principal` (scoped to their assigned school).
- **Persistence Behavior**: Inserts/updates `teacher_assignments` table; logs audit record.

---

## 3. Academic Calendar & Instructional Disruptions

### 3.1 Instructional Calendar & Disruption Logging
- **Frontend Route**: `/teacher/time-aware`
- **Frontend Component**: `src/pages/time-aware/TimeAwareEngine.tsx`
- **UI Trigger**: "Record Lost Teaching Days" modal.
- **Backend API Endpoints**:
  - `GET /api/v1/schools/{school_id}/calendar`
  - `POST /api/v1/schools/{school_id}/disruptions`
  - `DELETE /api/v1/disruptions/{disruption_id}`
  - `GET /api/v1/schools/{school_id}/instructional-availability`
- **Request Schema (`POST /disruptions`)**:
  ```json
  {
    "school_id": "school-1",
    "date": "2026-10-14",
    "reason": "Election Duties | Census Duties | Teacher Training | Health Drive | Extreme Weather | Local Festival | Administrative Work",
    "days_lost": 2.0,
    "notes": "State election officer presiding duties directive #SEC/2026/894"
  }
  ```
- **Permissions**: `admin`, `principal`, `teacher`.
- **Persistence Behavior**: Persists to `instructional_disruptions` table; re-evaluates school-wide available teaching periods and updates pacing deficits.

---

## 4. Time-Aware Pedagogical Engine & Curriculum Compacting

### 4.1 Time-Aware Pacing Calculation
- **Frontend Route**: `/teacher/time-aware`
- **Frontend Component**: `src/pages/time-aware/TimeAwareEngine.tsx`
- **UI Trigger**: Automatic on page load, or when disruption/compaction slider changes.
- **Backend API Endpoint**: `POST /api/v1/classes/{class_id}/time-aware/calculate`
- **Request Schema**:
  ```json
  {
    "core_ratio": 0.60,
    "current_day": 104,
    "total_official_days": 180
  }
  ```
- **Response Schema**:
  ```json
  {
    "total_official_days": 180,
    "current_day": 104,
    "total_lost_days": 16.0,
    "remaining_instructional_days": 60,
    "core_concepts_remaining": 68,
    "supplementary_topics_remaining": 36,
    "total_periods_needed_original": 104,
    "pacing_buffer": -4,
    "risk_status": "high",
    "risk_label": "High Pacing Risk (Deficit: 4 days)"
  }
  ```

### 4.2 Syllabus Compression Preview & Approval
- **Frontend Route**: `/teacher/time-aware` -> `CompressionPreviewModal.tsx`
- **UI Trigger**: "Preview Syllabus Compression" button -> "Accept Proposed Plan".
- **Backend API Endpoints**:
  - `POST /api/v1/classes/{class_id}/time-aware/compression-preview`
  - `POST /api/v1/curriculum-proposals/{proposal_id}/approve`
  - `POST /api/v1/curriculum-proposals/{proposal_id}/reject`
- **Approval Request Schema**:
  ```json
  {
    "proposal_id": "prop-123",
    "notes": "Approved 60/40 compacting strategy for Term 2"
  }
  ```
- **Permissions**: `teacher` (assigned to class), `principal`, `admin`.
- **Persistence Behavior**: Versioned curriculum update in transaction; updates lesson states to `compressed_to_homework` and `integrated`; guarantees 100% core competencies protected; records immutable audit event.

### 4.3 Cross-Curricular Synergy Detection
- **Frontend Component**: `src/pages/time-aware/TimeAwareEngine.tsx`
- **UI Trigger**: "Accept Proposal" or "Decline" on synergy cards.
- **Backend API Endpoints**:
  - `POST /api/v1/classes/{class_id}/curriculum/cross-curricular-proposals`
  - `POST /api/v1/cross-curricular-proposals/{proposal_id}/accept`
  - `POST /api/v1/cross-curricular-proposals/{proposal_id}/reject`
- **Permissions**: `teacher`, `principal`, `admin`.

---

## 5. Assessments, Question Bank, & Grading

### 5.1 Assessment Creation & Publishing
- **Frontend Route**: `/teacher/assessments-beta`
- **Frontend Component**: `src/pages/teacher/AssessmentBuilder.tsx`
- **UI Trigger**: Generate questions from a chapter PDF, then click **Assign the Assignment**.
- **Backend API Endpoints**:
  - `GET /api/v1/classes/{class_id}/assessments`
  - `POST /api/v1/classes/{class_id}/assessments`
  - `POST /api/v1/assessments/{assessment_id}/publish`
  - `GET /api/v1/assessments/question-bank`
  - `POST /api/v1/assessments/generate-questions-beta`
- **Request Schema (`POST /assessments`)**:
  ```json
  {
    "class_id": "class-8a",
    "subject_id": "sub-math",
    "title": "Cycle 3 Diagnostic: Mensuration & Spatial Reasoning",
    "cycle_number": 3,
    "duration_minutes": 45,
    "total_marks": 25,
    "questions": [
      {
        "text": "Calculate water cistern volume in m3 and liters...",
        "type": "practical",
        "marks": 4,
        "competency": "AU",
        "bloom_level": "Apply",
        "correct_answer": "Volume = 24 m3 = 24,000 Liters."
      }
    ],
    "competency_focus": ["AU", "CT", "LU"]
  }
  ```
- **Permissions**: `teacher`, `principal`, `admin`.

### 5.2 Student Assessment Submission & Quiz Lab
- **Frontend Route**: `/student/dashboard`
- **Frontend Component**: `src/pages/student/StudentDashboard.tsx` (Interactive Quiz Lab)
- **Backend API Endpoint**: `POST /api/v1/assessments/{assessment_id}/submissions`
- **Permissions**: `student` enrolled in the class.

---

## 6. Document Upload, Pluggable OCR, & Scan Review

### 6.1 Handwritten Assessment Scan Review (Low-Tech Workflow)
- **Frontend Route**: `/upload`
- **Frontend Component**: `src/pages/teacher/ScanReview.tsx`
- **UI Trigger**: File upload of answer script image/PDF -> OCR extraction review -> "Approve & Recalibrate Baseline".
- **Backend API Endpoints**:
  - `POST /api/v1/documents/upload` (Multipart form with file signature & MIME validation)
  - `GET /api/v1/documents/{document_id}` (Metadata, rendering pages, preview URLs)
  - `POST /api/v1/ocr/process` (Dispatches OCR job to active provider or simulator)
  - `GET /api/v1/ocr/{run_id}/results` (Page coordinates, bounding boxes, text, confidence)
  - `POST /api/v1/ocr/review/verify` (Teacher commits verified transcription & final marks)
- **Verification Request Schema**:
  ```json
  {
    "document_id": "doc-uuid",
    "student_id": "user-student-1",
    "assessment_id": "asm-2",
    "verified_items": [
      { "item_index": 1, "marks": 4, "text": "...", "feedback": "Accurate unit conversion" },
      { "item_index": 2, "marks": 2, "text": "...", "feedback": "Correct multiplicative inverse" }
    ],
    "teacher_notes": "Verified offline physical optical answer sheet."
  }
  ```
- **Permissions**: `teacher` (assigned to class), `admin`.
- **Persistence Behavior**: Saves original image to MinIO object storage; records verified marks in `assessment_submissions`; recalibrates student LU/CU/AU/CT snapshots; queues verified samples for the model fine-tuning dataset registry.

---

## 7. Competencies, Remediation, & Analytics

### 7.1 Student & Classroom Competency Analytics
- **Frontend Routes**: `/teacher/classes`, `/teacher/dashboard`, `/student/dashboard`, `/parent/dashboard`
- **Frontend Components**: `ClassHeatmap.tsx`, `CompetencyRadarChart.tsx`, `CompetencyBarChart.tsx`
- **Backend API Endpoints**:
  - `GET /api/v1/students/{student_id}/competencies`
  - `GET /api/v1/classes/{class_id}/competency-analytics`
  - `GET /api/v1/schools/{school_id}/competency-analytics`
  - `GET /api/v1/analytics/school-comparison`
- **Response Schema**:
  ```json
  {
    "LU": 78,
    "CU": 82,
    "AU": 70,
    "CT": 65,
    "overall": 74,
    "baseline": { "LU": 68, "CU": 72, "AU": 60, "CT": 54, "overall": 64 },
    "historical_trends": [...]
  }
  ```
- **Permissions**: Strict record-level access:
  - `student` can only access their own ID.
  - `parent` can only access their linked child IDs.
  - `teacher` can access only their assigned classes.
  - `principal` can access only their assigned school.

### 7.2 Differentiated Homework & Remediation
- **Frontend Route**: `/teacher/remediation`
- **Frontend Component**: `src/pages/teacher/RemediationManager.tsx`
- **Backend API Endpoints**:
  - `GET /api/v1/classes/{class_id}/homework`
  - `POST /api/v1/classes/{class_id}/homework`
  - `POST /api/v1/homework/{homework_id}/assign`
  - `POST /api/v1/homework/{homework_id}/submissions`
  - `GET /api/v1/students/{student_id}/remediation`
- **Permissions**: `teacher`, `student`, `parent`.

---

## 8. Notifications, Reports, & Audit Logging

### 8.1 Notifications & Announcements
- **Frontend Component**: `src/components/layout/Topbar.tsx`, Principal broadcast modal
- **Backend API Endpoints**:
  - `GET /api/v1/notifications`
  - `POST /api/v1/notifications/{notification_id}/read`
  - `POST /api/v1/announcements`
- **Permissions**: Role-based scoping.

### 8.2 Compliance Reports & Audit Events
- **Frontend Route**: `/principal/reports`, `/admin/audit-logs`
- **Backend API Endpoints**:
  - `POST /api/v1/reports/generate`
  - `GET /api/v1/reports/{report_id}/download`
  - `GET /api/v1/audit/events`
- **Permissions**: `admin`, `principal`.

---

## 9. UI Functionality Requiring Real Backend Support

The following existing UI elements previously relied on frontend simulation or in-memory state:
1. **Server-Side Authentication & Session Invalidation**: Frontend-only mock passwords and role switching are now backed by Argon2id password hashing, JWTs, and server-side authorization guards.
2. **True Record-Level Data Isolation**: Enforcing that parents can only see linked children (`user-student-1`, `student-ananya`) and students cannot tamper with marks or access classmates' files.
3. **Multi-Page Image & PDF Processing**: Secure multipart upload with MIME verification, page rendering, and S3-compatible private storage.
4. **OCR Extraction Pipeline & Human-in-the-Loop Review**: Pluggable OCR engine (TrOCR/PaddleOCR/Transformers/Mock) generating bounding boxes, extraction text, confidence scores, and capturing teacher corrections.
5. **Model Registry & Controlled Training Orchestration**: Dataset collection from verified scans, quality checks, CER/WER evaluation, model promotion, and rollbacks.
6. **Syllabus Compacting Database Transactions**: Versioned curriculum tables with atomic transitions ensuring that core learning outcomes can never be deleted.
7. **Neo4j Knowledge Graph Prerequisite Synchronization**: Dual-database sync mapping topic dependencies, learning outcomes, and cross-curricular synergy paths.

