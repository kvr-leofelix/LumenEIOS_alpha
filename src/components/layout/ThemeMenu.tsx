import React, { useEffect, useRef, useState } from 'react';
import { Check, Palette } from 'lucide-react';
import { THEMES, useTheme } from '../../context/ThemeContext';
import { cn } from '../../lib/utils';

export const ThemeMenu: React.FC<{ className?: string }> = ({ className }) => {
  const { theme, setTheme } = useTheme();
  const [open, setOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);
  const active = THEMES.find((item) => item.id === theme) ?? THEMES[0];

  useEffect(() => {
    if (!open) return;

    const onPointerDown = (event: MouseEvent) => {
      if (!rootRef.current?.contains(event.target as Node)) {
        setOpen(false);
      }
    };
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') setOpen(false);
    };

    document.addEventListener('mousedown', onPointerDown);
    document.addEventListener('keydown', onKeyDown);
    return () => {
      document.removeEventListener('mousedown', onPointerDown);
      document.removeEventListener('keydown', onKeyDown);
    };
  }, [open]);

  return (
    <div ref={rootRef} className={cn('relative', className)}>
      <button
        type="button"
        onClick={() => setOpen((value) => !value)}
        className="flex items-center gap-1.5 px-2.5 py-1.5 text-xs font-medium text-content-secondary hover:text-navy-800 hover:bg-surface-bg border border-surface-border rounded-lg transition-colors"
        title="Change theme"
        aria-haspopup="menu"
        aria-expanded={open}
      >
        <Palette className="w-3.5 h-3.5 text-content-muted" />
        <span className="hidden sm:inline">Theme</span>
        <span className="flex items-center -space-x-1" aria-hidden>
          {active.swatches.map((color) => (
            <span
              key={color}
              className="w-2.5 h-2.5 rounded-full border border-white/80"
              style={{ backgroundColor: color }}
            />
          ))}
        </span>
      </button>

      {open && (
        <div
          role="menu"
          className="absolute right-0 mt-1.5 w-64 bg-white rounded-xl shadow-modal border border-surface-border py-2 z-50 animate-fade-in"
        >
          <div className="px-3.5 py-1.5 text-[11px] font-semibold text-content-secondary uppercase tracking-wider">
            Appearance
          </div>
          {THEMES.map((item) => {
            const selected = item.id === theme;
            return (
              <button
                key={item.id}
                type="button"
                role="menuitemradio"
                aria-checked={selected}
                onClick={() => {
                  setTheme(item.id);
                  setOpen(false);
                }}
                className={cn(
                  'w-full px-3.5 py-2 text-left text-xs hover:bg-surface-bg flex items-center gap-3 transition-colors',
                  selected ? 'bg-teal-50/60 text-teal-800' : 'text-content-primary'
                )}
              >
                <span className="flex items-center -space-x-1 shrink-0" aria-hidden>
                  {item.swatches.map((color) => (
                    <span
                      key={color}
                      className="w-4 h-4 rounded-full border border-surface-border"
                      style={{ backgroundColor: color }}
                    />
                  ))}
                </span>
                <span className="min-w-0 flex-1">
                  <span className="block font-semibold">{item.label}</span>
                  <span className="block text-[10px] text-content-secondary">{item.hint}</span>
                </span>
                {selected && <Check className="w-4 h-4 text-teal-600 shrink-0" />}
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
};
