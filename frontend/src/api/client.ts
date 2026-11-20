/**
 * Typet klient til odense-rag-API'et.
 *
 * Typerne i schema.d.ts genereres fra FastAPI's OpenAPI-skema (`pnpm gen:api`),
 * som igen genereres fra Pydantic-modellerne. Ændres et felt i Python, fejler
 * `pnpm typecheck` her, indtil frontenden er opdateret.
 */
import createClient from 'openapi-fetch'
import type { components, paths } from './schema'

export type AskResponse = components['schemas']['AskResponse']
export type Source = components['schemas']['Source']
export type RetrievedSource = components['schemas']['RetrievedSource']

export function createApiClient(
  fetchImpl: typeof fetch = globalThis.fetch,
  // Samme origin som siden: i udvikling proxier Vite til FastAPI, i drift serverer
  // FastAPI selv frontenden. URL'en skal være absolut, fordi Request i Node (tests) kræver det.
  baseUrl: string = window.location.origin,
) {
  return createClient<paths>({ baseUrl, fetch: fetchImpl })
}

export type ApiClient = ReturnType<typeof createApiClient>
