import { apiUrl } from "@/lib/api";
import { cn } from "@/lib/utils";

const SIZES = { sm: "size-9 text-sm", md: "size-12 text-base", lg: "size-20 text-2xl" } as const;

/**
 * Profile photo from the authenticated API (session cookie is sent with the request).
 * next/image is not used: its optimizer fetches server-side without the coach's cookie.
 */
export function StudentAvatar({
  name,
  photoUrl,
  size = "sm",
  className,
}: {
  name: string;
  photoUrl: string | null;
  size?: keyof typeof SIZES;
  className?: string;
}) {
  const initial = name.trim().charAt(0) || "؟";
  return (
    <span
      className={cn(
        "relative inline-flex shrink-0 items-center justify-center overflow-hidden rounded-full bg-accent font-semibold text-accent-foreground",
        SIZES[size],
        className,
      )}
    >
      {photoUrl ? (
        // eslint-disable-next-line @next/next/no-img-element
        <img src={apiUrl(photoUrl)} alt={`تصویر ${name}`} className="size-full object-cover" loading="lazy" />
      ) : (
        <span aria-hidden>{initial}</span>
      )}
    </span>
  );
}
