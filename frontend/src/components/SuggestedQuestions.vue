<script setup lang="ts">
defineProps<{ questions: string[] }>()
const emit = defineEmits<{ pick: [question: string] }>()
</script>

<template>
  <section class="flex flex-col gap-3" aria-labelledby="suggestions-label">
    <p id="suggestions-label" class="text-xs leading-[18px] font-medium text-muted">
      Du kan for eksempel spørge om
    </p>
    <ul class="flex max-w-[560px] flex-wrap gap-x-2 gap-y-3">
      <li v-for="question in questions" :key="question">
        <button
          type="button"
          class="flex cursor-pointer items-start gap-2 rounded-lg bg-subtle px-3.5 py-2.5 text-left transition-colors hover:bg-line focus-visible:outline-2 focus-visible:outline-ink"
          @click="emit('pick', question)"
        >
          <span class="text-[13px] leading-5">{{ question }}</span>
          <span class="text-sm leading-[21px]" aria-hidden="true">↗</span>
        </button>
      </li>
    </ul>
  </section>
</template>
