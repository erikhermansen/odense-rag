<!--
  Siden samler komponenterne. Al tilstand og alle API-kald ligger i useAsk,
  så komponenterne kun viser data og sender hændelser op.
-->
<script setup lang="ts">
import { computed, ref } from 'vue'
import AnswerSection from './components/AnswerSection.vue'
import AppFooter from './components/AppFooter.vue'
import AppHeader from './components/AppHeader.vue'
import QuestionForm from './components/QuestionForm.vue'
import RetrievalPanel from './components/RetrievalPanel.vue'
import SearchingState from './components/SearchingState.vue'
import SourceList from './components/SourceList.vue'
import SuggestedQuestions from './components/SuggestedQuestions.vue'
import { useAsk } from './composables/useAsk'
import { groupSources } from './lib/answer'

const EXAMPLES = [
  'Hvad koster et pas?',
  'Hvor hurtigt skal jeg melde flytning?',
  'Må jeg brænde haveaffald af?',
  'Kan vi blive gift på rådhuset den 28. november?',
]

const question = ref('')
const { state, ask, isLoading } = useAsk()

const sourcePages = computed(() =>
  state.value.status === 'done' ? groupSources(state.value.response.sources) : [],
)

function submit(text = question.value) {
  question.value = text
  void ask(text)
}
</script>

<template>
  <div class="flex min-h-dvh flex-col">
    <AppHeader />

    <main
      class="mx-auto flex w-full max-w-[792px] flex-1 flex-col gap-7 px-4 pb-16 transition-[padding] duration-300"
      :class="state.status === 'idle' ? 'pt-16 sm:pt-[164px]' : 'pt-8 sm:pt-[52px]'"
    >
      <div class="flex flex-col gap-3">
        <p class="text-[11px] leading-[17px] font-semibold tracking-[1.7px] text-muted">
          SPØRG DIN KOMMUNE
        </p>
        <h1 class="text-[32px] leading-10 font-medium tracking-[-1.4px] sm:text-[38px] sm:leading-[48px]">
          Spørg om Odense Kommune
        </h1>
        <p class="text-base leading-6 text-muted">
          Få et samlet svar med afsæt i kommunens egne oplysninger.
        </p>
      </div>

      <QuestionForm v-model="question" :loading="isLoading" @submit="submit()" />

      <!-- aria-live gør, at skærmlæsere læser nyt indhold op, når det kommer. -->
      <div aria-live="polite" class="flex flex-col gap-6">
        <SuggestedQuestions v-if="state.status === 'idle'" :questions="EXAMPLES" @pick="submit" />

        <SearchingState v-else-if="state.status === 'loading'" />

        <section v-else-if="state.status === 'error'" class="flex flex-col gap-4 pt-1.5" role="alert">
          <div class="h-px w-full bg-line" />
          <p class="text-[15px] leading-[23px] font-medium">{{ state.message }}</p>
        </section>

        <template v-else>
          <AnswerSection :response="state.response" :page-count="sourcePages.length" />
          <SourceList v-if="sourcePages.length" :key="state.question" :pages="sourcePages" />
          <RetrievalPanel :key="state.question" :response="state.response" />
        </template>
      </div>
    </main>

    <AppFooter />
  </div>
</template>
