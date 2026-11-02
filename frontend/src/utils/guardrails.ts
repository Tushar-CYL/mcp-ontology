/**
 * Turn a natural-language safeguard into an instruction the agent can follow.
 *
 * The rule is deliberately small: keep an imperative that already starts with
 * one, otherwise prepend "Always". The point is that the text lands in the
 * guardrail list looking like an instruction, not like a note.
 */
const IMPERATIVE_START =
  /^(never|always|do not|don't|must|only|avoid|ensure|use|prefer|escalate|refuse|cite|keep|treat|answer|include|exclude|ask|leave|state|say|label|show|mention|decline)\b/i

export function toGuardrailInstruction(text: string): string {
  const cleaned = text
    .replace(/^[\s\-*•\u2022]+/, '')
    .replace(/\s+/g, ' ')
    .trim()

  if (!cleaned) return ''

  const sentence = IMPERATIVE_START.test(cleaned)
    ? cleaned
    : `Always ${cleaned.charAt(0).toLowerCase()}${cleaned.slice(1)}`

  const capitalised = sentence.charAt(0).toUpperCase() + sentence.slice(1)
  return /[.!?]$/.test(capitalised) ? capitalised : `${capitalised}.`
}
