import React, { useRef, useState } from 'react';
import { cn } from '../../lib/utils';

export const HoverTip: React.FC<{
  label: string;
  children: React.ReactNode;
  className?: string;
}> = ({ label, children, className }) => {
  const anchor = useRef<HTMLSpanElement>(null);
  const [open, setOpen] = useState(false);
  const [pos, setPos] = useState({ top: 0, left: 0 });

  const show = () => {
    const rect = anchor.current?.getBoundingClientRect();
    if (!rect) return;
    const width = 240;
    const left = Math.min(Math.max(12, rect.left), window.innerWidth - width - 12);
    const below = rect.bottom + 8;
    const top = below + 72 > window.innerHeight ? Math.max(12, rect.top - 76) : below;
    setPos({ top, left });
    setOpen(true);
  };

  return (
    <span
      ref={anchor}
      className={cn('inline-flex', className)}
      onMouseEnter={show}
      onMouseLeave={() => setOpen(false)}
      onFocusCapture={show}
      onBlurCapture={() => setOpen(false)}
    >
      {children}
      {open && (
        <span
          role="tooltip"
          style={{ top: pos.top, left: pos.left }}
          className="fixed z-[80] w-60 rounded-lg bg-navy-900 px-3 py-2 text-left text-xs font-medium leading-relaxed text-white shadow-modal"
        >
          {label}
        </span>
      )}
    </span>
  );
};
