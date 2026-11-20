<!--
  Funktionelt skelet: hele kæden virker, men der er ingen visuel stil.
  Erstat det med dine egne komponenter. Logikken ligger i useAsk og kan genbruges uændret.
-->
<script setup lang="ts">
import { ref } from 'vue'
import { MAX_LENGTH, useAsk } from './composables/useAsk'

const EXAMPLES = [
  'Hvad koster et pas?',
  'Hvor hurtigt skal jeg melde flytning?',
  'Må jeg brænde haveaffald af?',
  'Kan vi blive gift på rådhuset den 28. november?',
]

const question = ref('')
const { state, ask, isLoading } = useAsk()

function submit(text = question.value) {
  question.value = text
  void ask(text)
}
</script>

<template>
  <main>
    <h1>Spørg om Odense Kommune</h1>

    <form @submit.prevent="submit()">
      <label for="question">Dit spørgsmål</label>
      <input
        id="question"
        v-model="question"
        :maxlength="MAX_LENGTH"
        autocomplete="off"
        placeholder="Fx: Hvad koster et pas?"
      />
      <button type="submit" :disabled="isLoading">Spørg</button>
    </form>

    <ul aria-label="Eksempler på spørgsmål">
      <li v-for="example in EXAMPLES" :key="example">
        <button type="button" :disabled="isLoading" @click="submit(example)">{{ example }}</button>
      </li>
    </ul>

    <!-- aria-live gør, at skærmlæsere læser svaret op, når det kommer. -->
    <section aria-live="polite">
      <p v-if="state.status === 'loading'">Finder svar …</p>

      <p v-else-if="state.status === 'error'" role="alert">{{ state.message }}</p>

      <article v-else-if="state.status === 'done'">
        <p v-if="state.response.kind === 'unknown'"><strong>Det kan jeg ikke svare på.</strong></p>
        <p>{{ state.response.answer }}</p>

        <ol v-if="state.response.sources.length">
          <li v-for="source in state.response.sources" :key="source.chunk_id">
            <a :href="source.url" target="_blank" rel="noopener">{{ source.section }}</a>
            <blockquote>{{ source.quote }}</blockquote>
          </li>
        </ol>

        <details>
          <summary>Sådan fandt jeg svaret</summary>
          <ol>
            <li v-for="chunk in state.response.retrieved" :key="chunk.chunk_id">
              {{ chunk.score.toFixed(2) }} · {{ chunk.section }}
              <span v-if="chunk.cited">(citeret)</span>
            </li>
          </ol>
        </details>

        <small>
          {{ state.response.model }} · {{ (state.response.latency_ms / 1000).toFixed(1) }} s ·
          {{ state.response.input_tokens + state.response.output_tokens }} tokens
        </small>
      </article>
    </section>
  </main>
</template>
