<script setup lang="ts">
import { MAX_LENGTH } from '../composables/useAsk'

// defineModel giver v-model på komponenten (som value + onChange-props i React).
const question = defineModel<string>({ required: true })
defineProps<{ loading: boolean }>()
const emit = defineEmits<{ submit: [] }>()
</script>

<template>
  <form class="flex flex-col gap-2.5" @submit.prevent="emit('submit')">
    <label for="question" class="text-[13px] leading-5 font-semibold">Dit spørgsmål</label>
    <div
      class="flex h-[68px] items-center gap-4 rounded-xl border bg-surface pr-2 pl-5 transition-colors focus-within:border-ink"
      :class="question ? 'border-line' : 'border-outline'"
    >
      <input
        id="question"
        v-model="question"
        :maxlength="MAX_LENGTH"
        :readonly="loading"
        autocomplete="off"
        placeholder="Hvad vil du gerne vide?"
        class="min-w-0 flex-1 bg-transparent text-base leading-6 outline-none placeholder:text-muted"
      />
      <button
        type="submit"
        :disabled="loading"
        class="flex shrink-0 cursor-pointer items-center gap-2.5 rounded-lg px-5 py-3 whitespace-nowrap transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ink disabled:cursor-default"
        :class="loading ? 'bg-subtle text-ink' : 'bg-ink text-white hover:bg-black'"
      >
        <span class="text-sm leading-[21px] font-medium">{{ loading ? 'Søger…' : 'Spørg' }}</span>
        <span class="text-[19px] leading-[29px]" aria-hidden="true">{{ loading ? '···' : '↑' }}</span>
      </button>
    </div>
  </form>
</template>
