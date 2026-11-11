import { ExtractedBlock } from '../types';

/**
 * Stand-in transcript for the answer-sheet demo.
 * A real OCR model is not connected; the same lesson text is returned so the review screens can be tried.
 */
export function buildDemoExtraction(studentName: string, className: string, subject: string): ExtractedBlock[] {
  const useVolumeSheet = subject !== 'Science';
  if (useVolumeSheet) {
    return [
      { kind: 'text', content: `Name: ${studentName}` },
      { kind: 'text', content: `Class: ${className}    Subject: Mathematics    Topic: Mensuration` },
      { kind: 'text', content: 'Q1. A water tank is a cuboid. Length = 4 m, breadth = 3 m, depth = 2 m. Water flows in at 60 litres per minute. How long does the tank take to fill?' },
      { kind: 'equation', content: 'V = l × b × h = 4 × 3 × 2 = 24 m³' },
      { kind: 'equation', content: '24 m³ = 24 × 1000 = 24000 L' },
      { kind: 'equation', content: 't = 24000 ÷ 60 = 400 min = 6 h 40 min' },
      { kind: 'text', content: 'Answer: 6 hours 40 minutes.' },
      { kind: 'text', content: 'Q2. A cube has side 5 cm. Find its surface area.' },
      { kind: 'equation', content: 'SA = 6a² = 6 × 5² = 6 × 25 = 150 cm²' },
    ];
  }
  return [
    { kind: 'text', content: `Name: ${studentName}` },
    { kind: 'text', content: `Class: ${className}    Subject: Mathematics    Topic: Algebraic identities` },
    { kind: 'text', content: 'Q1. Expand (x + 3)(x + 5).' },
    { kind: 'equation', content: '(x + 3)(x + 5) = x² + 5x + 3x + 15' },
    { kind: 'equation', content: '= x² + 8x + 15' },
    { kind: 'text', content: 'Q2. If a + b = 9 and ab = 20, find a² + b².' },
    { kind: 'equation', content: 'a² + b² = (a + b)² − 2ab' },
    { kind: 'equation', content: '= 9² − 2 × 20 = 81 − 40 = 41' },
  ];
}
