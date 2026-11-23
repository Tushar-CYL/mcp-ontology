import { BadgeCheck, CircleHelp, GitBranch, TriangleAlert, UserCheck, Diamond } from 'lucide-react'

/**
 * The one honest mark used on every layer. A fact is shown with exactly one of
 * these, the same shape and colour everywhere, so a reader learns the language
 * once and reads all four pages. The mark never relies on colour alone: it
 * always carries a word and an icon.
 */
export type Proof = 'proved' | 'guess' | 'rule' | 'disagrees' | 'person' | 'company'

export const PROOF: Record<Proof, { icon: typeof BadgeCheck; word: string; help: string }> = {
  proved: { icon: BadgeCheck, word: 'Proved', help: 'Checked on the data and it agrees' },
  guess: { icon: CircleHelp, word: 'AI guess', help: 'The AI suggested this; not checked yet' },
  rule: { icon: GitBranch, word: 'Rule', help: 'Worked out by a business rule' },
  disagrees: { icon: TriangleAlert, word: 'Data disagrees', help: 'Checked on the data and it does not agree' },
  person: { icon: UserCheck, word: 'Approved', help: 'A person approved this' },
  company: { icon: Diamond, word: 'Company meaning', help: "Your company's meaning differs from the usual one" },
}

export const PROOF_ORDER: Proof[] = ['proved', 'guess', 'rule', 'disagrees', 'person', 'company']

export function proofWord(kind: Proof): string {
  return PROOF[kind].word
}
