<script setup lang="ts">
import { ref } from 'vue'
import type { SourcePage } from '../lib/answer'

defineProps<{ pages: SourcePage[] }>()

// Første kilde er udfoldet fra start, som i designet.
const open = ref(new Set([0]))

function toggle(index: number) {
  // Et nyt Set, så Vue opdager ændringen (som at kopiere state i React).
  const next = new Set(open.value)
  if (!next.delete(index)) next.add(index)
  open.value = next
}
</script>

<template>
  <section class="flex flex-col gap-2.5" aria-labelledby="sources-label">
    <p id="sources-label" class="text-xs leading-[18px] font-medium text-muted">Læs mere om</p>
    <div v-for="(page, i) in pages" :key="page.url" class="overflow-hidden rounded-[10px] bg-surface">
      <h3>
        <button
          type="button"
          class="flex w-full cursor-pointer items-center gap-4 px-[18px] py-3.5 text-left focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-ink"
          :aria-expanded="open.has(i)"
          :aria-controls="`source-${i}`"
          @click="toggle(i)"
        >
          <span class="shrink-0 rounded-[5px] bg-subtle px-[9px] py-[3px] text-xs leading-[18px] font-medium">
            {{ i + 1 }}
          </span>
          <span class="min-w-0 flex-1 text-[15px] leading-[23px] font-medium underline">
            {{ page.title }}
          </span>
          <span class="text-[21px] leading-8" aria-hidden="true">{{ open.has(i) ? '−' : '+' }}</span>
        </button>
      </h3>
      <div v-if="open.has(i)" :id="`source-${i}`" class="flex flex-col gap-2.5 pr-6 pb-[18px] pl-[62px]">
        <p v-for="quote in page.quotes" :key="quote" class="text-[15px] leading-6">{{ quote }}</p>
        <a
          :href="page.url"
          target="_blank"
          rel="noopener"
          class="w-fit text-[13px] leading-5 font-medium underline hover:text-muted"
        >
          Læs på odense.dk ↗
        </a>
      </div>
    </div>
  </section>
</template>
