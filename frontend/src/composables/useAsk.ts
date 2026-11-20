/**
 * Tilstand for ét spørgsmål ad gangen.
 *
 * Tilstanden er en discriminated union, så en komponent kun kan læse `response`,
 * når status er 'done', og kun `message`, når status er 'error'.
 */
import { computed, ref } from 'vue'
import { createApiClient, type ApiClient, type AskResponse } from '../api/client'

export const MIN_LENGTH = 3
export const MAX_LENGTH = 500

export type AskState =
  | { status: 'idle' }
  | { status: 'loading'; question: string }
  | { status: 'done'; question: string; response: AskResponse }
  | { status: 'error'; question: string; message: string }

function errorMessage(status: number): string {
  if (status === 422) return `Spørgsmålet skal være mellem ${MIN_LENGTH} og ${MAX_LENGTH} tegn.`
  if (status === 503) return 'Tjenesten er ikke klar lige nu. Prøv igen om lidt.'
  return 'Der skete en fejl. Prøv igen.'
}

export function useAsk(client: ApiClient = createApiClient()) {
  const state = ref<AskState>({ status: 'idle' })
  let controller: AbortController | null = null

  async function ask(rawQuestion: string): Promise<void> {
    const question = rawQuestion.trim()
    if (question.length < MIN_LENGTH || question.length > MAX_LENGTH) {
      state.value = { status: 'error', question, message: errorMessage(422) }
      return
    }

    // Et nyt spørgsmål annullerer et igangværende, så et sent svar ikke overskriver et nyere.
    controller?.abort()
    const current = new AbortController()
    controller = current
    state.value = { status: 'loading', question }

    try {
      const { data, response } = await client.POST('/ask', {
        body: { question },
        signal: current.signal,
      })
      if (current.signal.aborted) return
      state.value = data
        ? { status: 'done', question, response: data }
        : { status: 'error', question, message: errorMessage(response.status) }
    } catch (error) {
      if (current.signal.aborted) return
      state.value = {
        status: 'error',
        question,
        message: 'Kunne ikke få forbindelse til serveren.',
      }
      console.error(error)
    }
  }

  function reset(): void {
    controller?.abort()
    state.value = { status: 'idle' }
  }

  return {
    state,
    ask,
    reset,
    isLoading: computed(() => state.value.status === 'loading'),
  }
}
