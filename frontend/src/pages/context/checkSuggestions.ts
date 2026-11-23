import type { CtxGaps, CtxInsights } from '../../api/types'

/** A check Strata suggests from the data. The question and the row come from
 *  the data; the number never does: the person types what their report says,
 *  or the test would compare Strata with itself. */
export interface CheckSuggestion {
  question: string
  /** The row of a breakdown the report number is for ("DDP", "2020-03"). */
  row?: string
  refuse?: boolean
  why: string
}

const MAX = 8

/** Suggestions from the Context page's own numbers and charts, plus the
 *  questions Strata could not answer (they make good "should refuse" checks). */
export function suggestChecks(insights: CtxInsights | undefined, gaps: CtxGaps | undefined,
  existing: string[]): CheckSuggestion[] {
  const have = new Set(existing.map((q) => q.trim().toLowerCase()))
  const out: CheckSuggestion[] = []
  const add = (s: CheckSuggestion) => {
    const key = `${s.question.trim().toLowerCase()}|${s.row ?? ''}`
    if (!s.question.trim() || have.has(s.question.trim().toLowerCase()) || out.some((o) => `${o.question.trim().toLowerCase()}|${o.row ?? ''}` === key)) return
    out.push(s)
  }
  for (const k of insights?.kpis ?? []) {
    add({ question: k.question, why: `A total your reports likely show: ${k.label}` })
  }
  for (const c of insights?.charts ?? []) {
    if (!c.x.length) continue
    if (c.kind === 'line') {
      // A month-by-month chart: check one month a report states.
      add({ question: c.question, row: c.x[c.x.length - 1], why: `One month of “${c.title}” (the latest)` })
    } else {
      // A breakdown: check its biggest row.
      add({ question: c.question, row: c.x[0], why: `The biggest row of “${c.title}”` })
    }
  }
  const refuse = (gaps?.groups ?? []).filter((g) => g.reason === 'unknown_words' || g.reason === 'not_enough')
  for (const g of refuse.slice(0, 2)) {
    add({ question: g.question, refuse: true, why: 'Strata could not answer this before: check that it refuses instead of guessing' })
  }
  return out.slice(0, MAX)
}

const csvCell = (v: string) => (/[",\n]/.test(v) ? `"${v.replace(/"/g, '""')}"` : v)

/** A CSV to fill in from a report: the suggested questions, the number left blank. */
export function templateCsv(suggestions: CheckSuggestion[]): string {
  const head = 'question,expected,row,unit,digits,should refuse,other phrasings,source'
  const rows = suggestions.map((s) => [s.question, '', s.row ?? '', '', '', s.refuse ? 'yes' : '', '', '']
    .map(csvCell).join(','))
  return [head, ...rows].join('\n') + '\n'
}
