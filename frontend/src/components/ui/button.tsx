import { cn } from '@/lib/utils'
import type { ButtonHTMLAttributes } from 'react'

type Props = ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: 'primary' | 'secondary' | 'ghost' | 'danger'
  size?: 'sm' | 'md'
}

export function Button({ className, variant = 'primary', size = 'md', ...props }: Props) {
  return (
    <button
      className={cn(
        'inline-flex items-center justify-center gap-2 rounded-md font-medium transition disabled:cursor-not-allowed disabled:opacity-50',
        size === 'sm' ? 'h-8 px-3 text-sm' : 'h-10 px-4 text-sm',
        variant === 'primary' && 'bg-accent text-white hover:bg-[#185a4a]',
        variant === 'secondary' && 'border border-line bg-white text-ink hover:bg-paper',
        variant === 'ghost' && 'text-muted hover:bg-white hover:text-ink',
        variant === 'danger' && 'bg-red-700 text-white hover:bg-red-800',
        className,
      )}
      {...props}
    />
  )
}
