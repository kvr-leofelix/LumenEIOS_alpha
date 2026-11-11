import React, { useState } from 'react';

const SIZES = [
  { id: 'default', label: 'A', title: 'Default text size', className: 'text-[11px]' },
  { id: 'large', label: 'A', title: 'Large text', className: 'text-sm' },
  { id: 'larger', label: 'A', title: 'Larger text', className: 'text-base' },
] as const;

export type FontSizeId = (typeof SIZES)[number]['id'];

const STORAGE_KEY = 'lumeneios_font_size';

export function readFontSize(): FontSizeId {
  try {
    const saved = localStorage.getItem(STORAGE_KEY);
    if (saved === 'large' || saved === 'larger') return saved;
  } catch {
    /* ignore */
  }
  return 'default';
}

export function applyFontSize(size: FontSizeId) {
  if (size === 'default') {
    delete document.documentElement.dataset.font;
  } else {
    document.documentElement.dataset.font = size;
  }
}

applyFontSize(readFontSize());

export const FontSizeControl: React.FC = () => {
  const [size, setSize] = useState<FontSizeId>(readFontSize);

  const choose = (next: FontSizeId) => {
    applyFontSize(next);
    try {
      if (next === 'default') localStorage.removeItem(STORAGE_KEY);
      else localStorage.setItem(STORAGE_KEY, next);
    } catch {
      /* ignore */
    }
    setSize(next);
  };

  return (
    <div
      className="flex items-center rounded-lg border border-surface-border overflow-hidden"
      role="group"
      aria-label="Text size"
    >
      {SIZES.map((item) => {
        const selected = size === item.id;
        return (
          <button
            key={item.id}
            type="button"
            title={item.title}
            aria-pressed={selected}
            onClick={() => choose(item.id)}
            className={`px-2 py-1 font-semibold leading-none transition-colors ${item.className} ${
              selected
                ? 'bg-navy-800 text-white'
                : 'bg-white text-content-secondary hover:bg-surface-bg'
            }`}
          >
            {item.label}
          </button>
        );
      })}
    </div>
  );
};
