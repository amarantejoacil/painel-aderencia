import { cn } from '@/lib/utils'
import type { InputHTMLAttributes } from 'react'

export function Input({ className, ...props }: InputHTMLAttributes<HTMLInputElement>) {
  return (
    <input
      className={cn(
        'h-10 w-full rounded-md border border-line bg-white px-3 text-sm text-ink outline-none focus:border-accent',
        className,
      )}
      {...props}
    />
  )
}
