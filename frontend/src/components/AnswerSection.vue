<script setup lang="ts">
import { computed } from 'vue'
import type { AskResponse } from '../api/client'
import { pluralKilder, splitAnswer } from '../lib/answer'

const props = defineProps<{ response: AskResponse; pageCount: number }>()

const parts = computed(() =>
  props.response.kind === 'unknown'
    ? { headline: 'Det kan jeg ikke svare på.', body: props.response.answer }
    : splitAnswer(props.response.answer),
)
</script>

<template>
  <section class="flex flex-col gap-4 pt-1.5" aria-labelledby="answer-label">
    <div class="h-px w-full bg-line" />
    <div class="flex items-center justify-between pt-2 text-muted">
      <h2 id="answer-label" class="text-[11px] leading-[17px] font-semibold tracking-[1.4px]">
        DIT SVAR
      </h2>
      <p class="text-xs leading-[18px]">
        {{ pageCount ? `Baseret på ${pluralKilder(pageCount)}` : 'Ingen kilder' }}
      </p>
    </div>
    <p class="text-2xl leading-8 font-medium">{{ parts.headline }}</p>
    <p v-if="parts.body" class="text-[17px] leading-7">{{ parts.body }}</p>
  </section>
</template>
