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
