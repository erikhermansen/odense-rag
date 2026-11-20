/// <reference types="vitest/config" />
import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  server: {
    // I udvikling sendes API-kald videre til FastAPI (uv run uvicorn odense_rag.api:app).
    proxy: {
      '/ask': 'http://localhost:8000',
      '/health': 'http://localhost:8000',
    },
  },
  test: {
    environment: 'jsdom',
  },
})
