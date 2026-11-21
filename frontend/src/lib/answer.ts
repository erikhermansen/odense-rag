/**
 * Rene funktioner, der former API-svaret til det, designet viser.
 * Holdt ude af komponenterne, så de kan testes uden at rendere noget.
 */
import type { AskResponse, Source } from '../api/client'

/** Designet viser første sætning som overskrift og resten som brødtekst. */
export function splitAnswer(answer: string): { headline: string; body: string } {
  const text = answer.trim()
  // Første punktum, spørgsmålstegn eller udråbstegn efterfulgt af mellemrum.
  // Tal som "28. november" springes over, fordi punktummet skal følge et bogstav.
  const match = /^(.+?\p{L}[.!?])\s+(.+)$/su.exec(text)
  if (!match) return { headline: text, body: '' }
  return { headline: match[1], body: match[2] }
}

export interface SourcePage {
  url: string
  title: string
  quotes: string[]
}

/** Samler citater fra samme side, så hver side kun vises én gang. */
export function groupSources(sources: Source[]): SourcePage[] {
  const pages = new Map<string, SourcePage>()
  for (const source of sources) {
    const page = pages.get(source.url) ?? { url: source.url, title: source.title, quotes: [] }
    if (!page.quotes.includes(source.quote)) page.quotes.push(source.quote)
    pages.set(source.url, page)
  }
  return [...pages.values()]
}

export function pluralKilder(n: number): string {
  return n === 1 ? '1 kilde' : `${n} kilder`
}

export function formatMeta(response: AskResponse): string {
  const seconds = (response.latency_ms / 1000).toFixed(1).replace('.', ',')
  const tokens = response.input_tokens + response.output_tokens
  return `${response.model} · ${seconds} s · ${tokens.toLocaleString('da-DK')} tokens`
}

/** Afsnit er en overskriftssti ("Side > Afsnit > Underafsnit"). Første led er sidens egen overskrift. */
export function sectionLabel(section: string): string {
  const parts = section.split(' > ')
  return parts.length > 1 ? parts.slice(1).join(' › ') : section
}
