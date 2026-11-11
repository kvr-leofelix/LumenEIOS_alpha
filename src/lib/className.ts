export type ParsedClassName =
  | { ok: true; grade: number; section: string; display: string; identity: string }
  | { ok: false; error: string };

const FORMAT_HELP =
  'Use a grade and one letter, such as 8A, or a grade and a section name, such as 8 Name1.';

/** Identity used to catch the same class under either naming style, including older "Class 8-A" labels. */
export function classIdentity(name: string): string {
  const trimmed = name.trim().replace(/^class\s+/i, '');
  const letter = trimmed.match(/^(\d{1,2})\s*-?\s*([A-Za-z])$/);
  if (letter) {
    const grade = Number(letter[1]);
    if (grade >= 1 && grade <= 12) return `${grade}:${letter[2].toUpperCase()}`;
  }
  const named = trimmed.match(/^(\d{1,2})\s+([A-Za-z][A-Za-z0-9]*)$/);
  if (named) {
    const grade = Number(named[1]);
    if (grade >= 1 && grade <= 12) return `${grade}:${named[2].toLowerCase()}`;
  }
  return trimmed.toLowerCase();
}

export function parseClassName(raw: string): ParsedClassName {
  const text = raw.trim().replace(/\s+/g, ' ');
  if (!text) return { ok: false, error: 'Enter a class name.' };

  const letter = text.match(/^(\d{1,2})([A-Za-z])$/);
  if (letter) {
    const grade = Number(letter[1]);
    if (grade < 1 || grade > 12) return { ok: false, error: 'Grade must be from 1 to 12.' };
    const section = letter[2].toUpperCase();
    return { ok: true, grade, section, display: `${grade}${section}`, identity: `${grade}:${section}` };
  }

  const named = text.match(/^(\d{1,2}) ([A-Za-z][A-Za-z0-9]*)$/);
  if (named) {
    const grade = Number(named[1]);
    if (grade < 1 || grade > 12) return { ok: false, error: 'Grade must be from 1 to 12.' };
    const section = named[2];
    return { ok: true, grade, section, display: `${grade} ${section}`, identity: `${grade}:${section.toLowerCase()}` };
  }

  return { ok: false, error: `That name is not a supported class format. ${FORMAT_HELP}` };
}

export const CLASS_NAME_HELP = FORMAT_HELP;
