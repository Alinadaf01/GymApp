import { Archive, CircleCheck, FilePen } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { programStatusLabel } from "@/lib/labels";
import type { ProgramStatus } from "@/lib/types";

export function ProgramStatusBadge({ status }: { status: ProgramStatus }) {
  const Icon = status === "approved" ? CircleCheck : status === "draft" ? FilePen : Archive;
  return (
    <Badge variant={status === "approved" ? "success" : status === "draft" ? "default" : "muted"}>
      <Icon aria-hidden />
      {programStatusLabel[status]}
    </Badge>
  );
}
