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
