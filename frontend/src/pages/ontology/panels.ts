import type { ReactNode } from 'react'
import {
  ConceptsPanel, DriftPanel, GovernPanel, IdentityPanel, IntakePanel, MappingPanel,
  ProfilePanel, PublishPanel, RulesPanel, StructurePanel, SurvivorshipPanel, type PanelProps,
} from './StepPanels'

/** One panel per journey step, keyed by the step id the API returns. */
export const PANELS: Record<string, (props: PanelProps) => ReactNode> = {
  intake: IntakePanel,
  profile: ProfilePanel,
  concepts: ConceptsPanel,
  mapping: MappingPanel,
  structure: StructurePanel,
  identity: IdentityPanel,
  survivorship: SurvivorshipPanel,
  rules: RulesPanel,
  govern: GovernPanel,
  publish: PublishPanel,
  drift: DriftPanel,
}
