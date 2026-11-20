import { describe, expect, it, vi } from 'vitest'
import { createApiClient, type AskResponse } from '../api/client'
import { useAsk } from './useAsk'

const ANSWER: AskResponse = {
  kind: 'answer',
  answer: 'Det koster 150 kr.',
  sources: [],
  retrieved: [],
  model: 'test',
  latency_ms: 1,
  input_tokens: 1,
  output_tokens: 1,
}

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

function setup(fetchImpl: typeof fetch) {
  return useAsk(createApiClient(fetchImpl))
}

describe('useAsk', () => {
  it('går fra loading til done med svaret', async () => {
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(jsonResponse(ANSWER))
    const { state, ask } = setup(fetchMock)

    const pending = ask('  Hvad koster et legitimationskort?  ')
    expect(state.value).toEqual({ status: 'loading', question: 'Hvad koster et legitimationskort?' })
    await pending

    expect(state.value).toEqual({
      status: 'done',
      question: 'Hvad koster et legitimationskort?',
      response: ANSWER,
    })
  })

  it('afviser for korte spørgsmål uden at kalde API’et', async () => {
    const fetchMock = vi.fn<typeof fetch>()
    const { state, ask } = setup(fetchMock)

    await ask('hi')

    expect(fetchMock).not.toHaveBeenCalled()
    expect(state.value.status).toBe('error')
  })

  it('viser en forståelig besked ved 503', async () => {
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(jsonResponse({ detail: 'x' }, 503))
    const { state, ask } = setup(fetchMock)

    await ask('Hvad koster et pas?')

    expect(state.value).toMatchObject({ status: 'error', message: expect.stringContaining('ikke klar') })
  })

  it('lader et nyere spørgsmål vinde over et langsommere ældre', async () => {
    let resolveFirst: (r: Response) => void = () => {}
    const fetchMock = vi
      .fn<typeof fetch>()
      .mockImplementationOnce(() => new Promise((resolve) => (resolveFirst = resolve)))
      .mockResolvedValueOnce(jsonResponse({ ...ANSWER, answer: 'Nyeste svar' }))
    const { state, ask } = setup(fetchMock)

    const first = ask('Første spørgsmål')
    await ask('Andet spørgsmål')
    resolveFirst(jsonResponse({ ...ANSWER, answer: 'Gammelt svar' }))
    await first

    expect(state.value).toMatchObject({ status: 'done', question: 'Andet spørgsmål' })
  })
})
