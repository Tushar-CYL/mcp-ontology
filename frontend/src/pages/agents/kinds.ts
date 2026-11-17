import { BookOpen, Lock, PenLine, Scale, Search, ShieldCheck, Sparkles, type LucideIcon } from 'lucide-react'
import type { OntoAgentKind } from '../../api/types'

/** One picture per way of answering. */
export const KIND_ICON: Record<OntoAgentKind, LucideIcon> = {
  guide: BookOpen,
  investigator: Search,
  metric: Scale,
  insight: Sparkles,
  trust: ShieldCheck,
  steward: PenLine,
  privacy: Lock,
}

/** What each kind does, in one line, for the form. */
export const KIND_HELP: Record<OntoAgentKind, string> = {
  guide: 'Explains what the data is and how things link. Never gives numbers.',
  investigator: 'Looks up one record by id or name and shows what it is linked to.',
  metric: 'Gives only certified numbers, with formula and owner. Refuses anything else.',
  insight: 'Answers any question from checked facts, using all four layers.',
  trust: 'Says whether a number or a field can be trusted, and why.',
  steward: 'Turns what you know into notes for a person to apply.',
  privacy: 'Finds where personal data is. Never shows a value.',
}
