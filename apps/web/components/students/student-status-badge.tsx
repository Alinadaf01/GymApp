import { Archive, CircleCheck, CirclePause } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { studentStatusLabel } from "@/lib/labels";
import type { StudentStatus } from "@/lib/types";

/** Icon + text, so status is not conveyed by color alone. */
export function StudentStatusBadge({ status }: { status: StudentStatus }) {
  const Icon = status === "active" ? CircleCheck : status === "inactive" ? CirclePause : Archive;
  const variant = status === "active" ? "success" : "muted";
  return (
    <Badge variant={variant}>
      <Icon aria-hidden />
      {studentStatusLabel[status]}
    </Badge>
  );
}
