import { Construction } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";

export function ComingSoon({ phase }: { phase: number }) {
  return (
    <Card>
      <CardContent className="flex flex-col items-center gap-3 py-10 text-center text-muted-foreground">
        <Construction className="size-8" aria-hidden />
        <p>این بخش در فاز {new Intl.NumberFormat("fa-IR").format(phase)} ساخته می‌شود.</p>
      </CardContent>
    </Card>
  );
}
