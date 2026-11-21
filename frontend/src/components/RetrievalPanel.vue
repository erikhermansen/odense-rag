<script setup lang="ts">
import { computed, ref } from 'vue'
import type { AskResponse, RetrievedSource } from '../api/client'
import { formatMeta, sectionLabel } from '../lib/answer'

const props = defineProps<{ response: AskResponse }>()
const open = ref(false)

interface RetrievedPage {
  url: string
  title: string
  chunks: RetrievedSource[]
}

// Retrieval giver hele sider (small-to-big), så tekststykkerne grupperes pr. side.
const pages = computed(() => {
  const byUrl = new Map<string, RetrievedPage>()
  for (const chunk of props.response.retrieved) {
    const page = byUrl.get(chunk.url) ?? { url: chunk.url, title: chunk.title, chunks: [] }
    page.chunks.push(chunk)
    byUrl.set(chunk.url, page)
  }
  return [...byUrl.values()]
})
</script>

<template>
  <section class="flex flex-col">
    <div class="h-px w-full bg-line" />
    <button
      type="button"
      class="flex w-full cursor-pointer items-center gap-3 py-[18px] text-left focus-visible:outline-2 focus-visible:outline-ink"
      :aria-expanded="open"
      aria-controls="retrieval-details"
      @click="open = !open"
    >
      <span class="w-[11px] text-[21px] leading-8" aria-hidden="true">{{ open ? '⌄' : '›' }}</span>
      <span class="min-w-0 flex-1 text-sm leading-[21px] font-medium">Sådan fandt jeg svaret</span>
      <span class="text-xs leading-[18px] text-muted">{{ pages.length === 1 ? '1 side' : `${pages.length} sider` }} søgt</span>
    </button>
    <div v-if="open" id="retrieval-details" class="flex flex-col gap-4 pb-4 pl-[26px]">
      <p class="text-[13px] leading-[21px] text-muted">
        Søgningen kombinerer betydning (embeddings) og ord (dansk fuldtekst). De bedste sider
        sendes til sprogmodellen. Fremhævede afsnit er citeret i svaret.
      </p>
      <div v-for="(page, i) in pages" :key="page.url" class="flex flex-col gap-[5px]">
        <a
          :href="page.url"
          target="_blank"
          rel="noopener"
          class="w-fit text-sm leading-[21px] font-medium underline hover:text-muted"
        >
          {{ i + 1 }}. {{ page.title }} ↗
        </a>
        <ul class="flex flex-col gap-1 text-[13px] leading-[21px]">
          <li
            v-for="chunk in page.chunks"
            :key="chunk.chunk_id"
            class="flex justify-between gap-4"
            :class="chunk.cited ? 'text-ink' : 'text-muted'"
          >
            <span class="min-w-0">
              {{ sectionLabel(chunk.section) }}
              <span v-if="chunk.cited" class="font-medium">· citeret</span>
            </span>
            <span class="shrink-0 tabular-nums" :title="'Cosinus-lighed med spørgsmålet'">
              {{ chunk.score.toFixed(2).replace('.', ',') }}
            </span>
          </li>
        </ul>
      </div>
      <p class="text-[11px] leading-[17px] text-muted">
        odense.dk · {{ response.retrieved.length }} tekststykker · {{ formatMeta(response) }}
      </p>
    </div>
    <div class="h-px w-full bg-line" />
  </section>
</template>
