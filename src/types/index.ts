export type Role = 'developer' | 'admin' | 'principal' | 'teacher' | 'student' | 'parent';

export type InfrastructureTier = 'high-tech' | 'standard' | 'low-tech';

export type VARKModality = 'Visual' | 'Auditory' | 'Reading/Writing' | 'Kinesthetic';

export type BloomLevel = 'Remember' | 'Understand' | 'Apply' | 'Analyze' | 'Evaluate' | 'Create';

export type CompetencyKey = 'LU' | 'CU' | 'AU' | 'CT';

export interface CompetencyScores {
  LU: number; // Language Understanding
  CU: number; // Concept Understanding
  AU: number; // Application Understanding
  CT: number; // Critical Thinking
  overall: number;
}

export interface User {
  demoRoot?: boolean;
  id: string;
  email: string;
  name: string;
  role: Role;
  schoolId: string;
  avatar?: string;
  assignedClassIds?: string[];
  assignedSubjectIds?: string[];
  linkedChildIds?: string[];
  designation?: string;
}

export interface School {
  id: string;
  name: string;
  location: string;
  state: string;
  infrastructureTier: InfrastructureTier;
  academicYear: string;
  principalId: string;
  principalName: string;
  studentCount: number;
  teacherCount: number;
  classCount: number;
  pacingRisk: 'low' | 'medium' | 'high';
  description: string;
  officialWorkingDays: number;
}

export interface ClassSection {
  id: string;
  schoolId: string;
  grade: number;
  section: string;
  name: string;
  classTeacherId: string;
  classTeacherName: string;
  studentCount: number;
  subjectIds: string[];
}

export interface Subject {
  id: string;
  name: string;
  code: string;
  grade: number;
  iconName: string;
}

export interface Student {
  id: string;
  schoolId: string;
  classId: string;
  className: string;
  name: string;
  rollNo: number;
  gender: 'M' | 'F' | 'Other';
  attendancePct: number;
  competencies: CompetencyScores;
  baselineCompetencies: CompetencyScores;
  learningModality: VARKModality;
  parentId: string;
  homeworkCompletionRate: number;
  needsSupport: boolean;
  supportArea?: string;
  joinedYear?: number;
}

export interface Question {
  id: string;
  assessmentId?: string;
  subjectId?: string;
  text: string;
  type: 'mcq' | 'short' | 'descriptive' | 'practical';
  options?: string[];
  correctAnswer?: string;
  markingRubric?: string;
  marks: number;
  competency: CompetencyKey;
  bloomLevel: BloomLevel;
  sourceDocumentIds?: string[];
  sourceDocumentNames?: string[];
  isAiGenerated?: boolean;
}

export interface SourceDocument {
  id: string;
  schoolId: string;
  subjectId?: string;
  uploadedBy: string;
  fileName: string;
  mimeType: string;
  fileSize: number;
  pageCount: number;
  docType: string;
  status: string;
  extractedTextPreview?: string;
  createdAt?: string;
}

export interface BulkDocumentUploadItem {
  fileName: string;
  fileSize: number;
  mimeType: string;
  status: 'uploaded' | 'duplicate' | 'failed';
  documentId?: string;
  pageCount: number;
  errorMessage?: string;
  extractedTextPreview?: string;
}

export interface BulkDocumentUploadResponse {
  totalSelected: number;
  uploadedCount: number;
  duplicateCount: number;
  failedCount: number;
  items: BulkDocumentUploadItem[];
}

export interface BatchQuestionEvaluation {
  question_id: string;
  question_index: number;
  question_text: string;
  type: 'mcq' | 'short' | 'descriptive' | 'practical';
  student_answer: string;
  expected_answer?: string | null;
  rubric?: string | null;
  awarded_marks: number;
  max_marks: number;
  confidence: number;
  competency: CompetencyKey;
  feedback: string;
  flagged_for_review: boolean;
}

export type BatchItemStageStatus =
  | 'queued'
  | 'uploading'
  | 'uploaded'
  | 'extracting_ocr'
  | 'identifying_student'
  | 'evaluating_answers'
  | 'calculating_marks'
  | 'completed'
  | 'requires_review'
  | 'failed'
  | 'cancelled';

export interface GradingBatchItem {
  id: string;
  batchId: string;
  documentId?: string | null;
  fileName: string;
  fileSize: number;
  mimeType: string;
  pageCount: number;
  pageRange?: string | null;
  status: BatchItemStageStatus;
  stageProgress: number;
  errorMessage?: string | null;
  retryCount: number;
  studentId?: string | null;
  studentName?: string | null;
  studentConfidence: number;
  ocrConfidence: number;
  extractedText?: string | null;
  questionEvaluations: BatchQuestionEvaluation[];
  marksObtained: number;
  maxMarks: number;
  percentage: number;
  grade: string;
  competencyScores: Record<string, number>;
  requiresReview: boolean;
  reviewReasons: string[];
  teacherApproved: boolean;
  approvedById?: string | null;
  approvedAt?: string | null;
}

export interface GradingBatch {
  id: string;
  schoolId: string;
  classId: string;
  className?: string | null;
  subjectId: string;
  subjectName?: string | null;
  assessmentId: string;
  assessmentTitle?: string | null;
  createdById: string;
  uploadMode: 'single' | 'bulk';
  status: 'configuring' | 'queued' | 'processing' | 'completed' | 'completed_with_warnings' | 'failed' | 'cancelled';
  totalFiles: number;
  validFiles: number;
  invalidOrDuplicateFiles: number;
  completedFiles: number;
  reviewRequiredFiles: number;
  failedFiles: number;
  splitMultiPdf: boolean;
  concurrencyLimit: number;
  createdAt?: string | null;
  completedAt?: string | null;
  items: GradingBatchItem[];
}

export interface Assessment {
  id: string;
  schoolId: string;
  classId: string;
  subjectId: string;
  title: string;
  cycleNumber: number; // 1 to 4 (every 4-6 weeks)
  date: string;
  durationMinutes: number;
  totalMarks: number;
  questions: Question[];
  status: 'draft' | 'scheduled' | 'graded';
  competencyFocus: CompetencyKey[];
}

export interface AssessmentResult {
  id: string;
  assessmentId: string;
  studentId: string;
  studentName: string;
  marksObtained: number;
  totalMarks: number;
  percentage: number;
  scores: CompetencyScores;
  feedback?: string;
  submissionDate: string;
  isScanned?: boolean;
}

export interface CurriculumDay {
  id: string;
  dayNumber: number; // 1 to 180
  classId: string;
  subjectId: string;
  topic: string;
  objective: string;
  teachingProcess: string;
  measurableOutcome: string;
  estimatedDurationMins: number;
  varkModality: VARKModality;
  bloomLevel: BloomLevel;
  classification: 'core' | 'supplementary';
  status: 'completed' | 'in-progress' | 'pending' | 'compressed_to_homework' | 'integrated';
  prerequisites?: string[];
}

export interface LostTeachingDay {
  id: string;
  schoolId: string;
  date: string;
  reason: 'Election Duties' | 'Census Duties' | 'Teacher Training' | 'Health Drive' | 'Extreme Weather' | 'Local Festival' | 'Administrative Work';
  daysLost: number;
  recordedBy: string;
  notes?: string;
}

export interface CrossCurricularProposal {
  id: string;
  title: string;
  subjectIds: string[];
  subjectNames: string[];
  targetDayNumbers: number[];
  learningObjectives: string[];
  activity: string;
  varkModality: VARKModality;
  bloomLevel: BloomLevel;
  estimatedDurationHours: number;
  timeSavedHours: number;
  status: 'pending' | 'accepted' | 'rejected';
}

export interface ExtractedBlock {
  kind: 'text' | 'equation';
  content: string;
}

export interface SheetAssignment {
  id: string;
  teacherId: string;
  teacherName: string;
  schoolId: string;
  classId: string;
  className: string;
  subject: string;
  title: string;
  instructions: string;
  dueDate: string;
  createdAt: string;
}

export interface AnswerSheetUpload {
  id: string;
  assignmentId: string;
  assignmentTitle: string;
  studentId: string;
  studentName: string;
  classId: string;
  className: string;
  schoolId: string;
  subject: string;
  fileName: string;
  mimeType: string;
  previewDataUrl?: string;
  uploadedAt: string;
  blocks: ExtractedBlock[];
}

export interface HomeworkRemediation {
  id: string;
  studentId: string;
  studentName: string;
  classId: string;
  subjectId: string;
  title: string;
  competencyTarget: CompetencyKey;
  reason: string;
  description: string;
  dueDate: string;
  status: 'assigned' | 'submitted' | 'reviewed';
  score?: number;
}

export interface AuditLog {
  id: string;
  timestamp: string;
  userId: string;
  userName: string;
  action: string;
  details: string;
  category: 'curriculum' | 'assessment' | 'user' | 'system';
}

export interface NotificationItem {
  id: string;
  userId: string;
  title: string;
  message: string;
  type: 'info' | 'warning' | 'success' | 'alert';
  read: boolean;
  createdAt: string;
  link?: string;
}

