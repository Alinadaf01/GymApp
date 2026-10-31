export type StudentStatus = "active" | "inactive" | "archived";
export type ProgramType = "workout" | "nutrition" | "supplement" | "vitamin";
export type ProgramStatus = "draft" | "approved" | "archived";

export type User = { id: string; username: string };

export type StudentBrief = {
  id: string;
  full_name: string;
  phone: string | null;
  status: StudentStatus;
  current_weight_kg: string | null;
  start_date: string | null;
  created_at: string;
};

export type ProgramBrief = {
  id: string;
  title: string;
  program_type: ProgramType;
  status: ProgramStatus;
  student_id: string;
  student_name: string;
  approved_at: string | null;
  created_at: string;
};

export type DashboardSummary = {
  total_students: number;
  active_students: number;
  total_programs: number;
  programs_this_month: number;
  recent_students: StudentBrief[];
  recent_programs: ProgramBrief[];
};

export type Activity = {
  id: string;
  action: string;
  entity_type: string;
  entity_id: string | null;
  student_id: string | null;
  student_name: string | null;
  meta: Record<string, unknown>;
  created_at: string;
};

export type Gender = "male" | "female" | "other";

export type LastProgram = {
  id: string;
  title: string;
  program_type: ProgramType;
  status: ProgramStatus;
  date: string;
};

export type StudentListItem = {
  id: string;
  full_name: string;
  first_name: string;
  last_name: string;
  phone: string | null;
  current_weight_kg: string | null;
  start_date: string | null;
  status: StudentStatus;
  profile_photo_url: string | null;
  last_program: LastProgram | null;
  created_at: string;
};

export type StudentListResponse = {
  items: StudentListItem[];
  total: number;
  page: number;
  page_size: number;
};

export type Student = {
  id: string;
  first_name: string;
  last_name: string;
  full_name: string;
  phone: string | null;
  birth_date: string | null;
  gender: Gender | null;
  height_cm: string | null;
  initial_weight_kg: string | null;
  current_weight_kg: string | null;
  training_history: string | null;
  goal: string | null;
  limitations_notes: string | null;
  start_date: string | null;
  coach_notes: string | null;
  status: StudentStatus;
  profile_photo_url: string | null;
  photo_consent_at: string | null;
  created_at: string;
  updated_at: string;
  archived_at: string | null;
  last_program: LastProgram | null;
};

export type ProgramSummary = {
  id: string;
  title: string;
  program_type: ProgramType;
  status: ProgramStatus;
  period_number: number | null;
  start_date: string | null;
  end_date: string | null;
  created_at: string;
  approved_at: string | null;
};

export type ExecutionType = "reps" | "time" | "distance" | "combined" | "free";

export type Exercise = {
  id: string;
  name: string;
  execution_type: ExecutionType;
  sets: number | null;
  reps: string | null;
  weight_value: string | null;
  weight_unit: string | null;
  duration_seconds: number | null;
  distance_value: string | null;
  distance_unit: string | null;
  rest_seconds: number | null;
  notes: string | null;
  raw_text: string | null;
  sort_order: number;
};

export type WorkoutSession = {
  id: string;
  title: string;
  notes: string | null;
  sort_order: number;
  exercises: Exercise[];
};

export type Meal = {
  id: string;
  title: string;
  time_text: string | null;
  content: string;
  notes: string | null;
  sort_order: number;
};

export type SupplementItem = {
  id: string;
  name: string;
  amount_text: string | null;
  timing_text: string | null;
  notes: string | null;
  sort_order: number;
};

export type PdfInfo = {
  id: string;
  program_id: string;
  version: number;
  created_at: string;
  is_outdated: boolean;
};

export type StudentRef = { id: string; full_name: string };

export type Program = {
  id: string;
  student: StudentRef;
  title: string;
  program_type: ProgramType;
  period_number: number | null;
  start_date: string | null;
  end_date: string | null;
  status: ProgramStatus;
  notes: string | null;
  source_voice_record_id: string | null;
  created_at: string;
  updated_at: string;
  approved_at: string | null;
  sessions: WorkoutSession[];
  meals: Meal[];
  supplements: SupplementItem[];
  latest_pdf: PdfInfo | null;
};

export type ProgramListItem = {
  id: string;
  student: StudentRef;
  title: string;
  program_type: ProgramType;
  period_number: number | null;
  status: ProgramStatus;
  start_date: string | null;
  end_date: string | null;
  created_at: string;
  updated_at: string;
  approved_at: string | null;
  pdf_count: number;
};

export type ProgramListResponse = {
  items: ProgramListItem[];
  total: number;
  page: number;
  page_size: number;
};

export type PdfTemplate = {
  club_name: string;
  coach_name: string;
  phone: string;
  primary_color: string;
  footer_text: string;
  has_logo: boolean;
};

export type PhotoView = "front" | "back" | "side";

export type ProgressPhoto = {
  id: string;
  capture_date: string;
  view_type: PhotoView;
  notes: string | null;
  created_at: string;
  url: string;
  thumb_url: string;
};

export type Measurement = {
  id: string;
  measured_at: string;
  weight_kg: string | null;
  arm_cm: string | null;
  chest_cm: string | null;
  waist_cm: string | null;
  abdomen_cm: string | null;
  thigh_cm: string | null;
  hip_cm: string | null;
  notes: string | null;
  created_at: string;
};
