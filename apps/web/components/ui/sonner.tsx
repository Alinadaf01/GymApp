"use client";

import { Toaster as Sonner, type ToasterProps } from "sonner";

function Toaster(props: ToasterProps) {
  return (
    <Sonner
      dir="rtl"
      position="top-center"
      richColors
      toastOptions={{ style: { fontFamily: "var(--font-sans)" } }}
      {...props}
    />
  );
}

export { Toaster };
