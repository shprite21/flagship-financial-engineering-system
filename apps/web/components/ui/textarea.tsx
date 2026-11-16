import type { ComponentProps } from 'react';

export function Textarea({ className = '', ...props }: ComponentProps<'textarea'>) {
  return <textarea className={`min-h-24 w-full rounded-md border border-input bg-transparent px-3 py-2 text-sm outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:opacity-50 ${className}`} {...props} />;
}
