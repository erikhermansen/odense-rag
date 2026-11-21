/// <reference types="vitest/config" />
import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import tailwindcss from '@tailwindcss/vite'

// API_URL kan pege på en anden backend, fx en mock under udvikling af frontend.
const apiUrl = process.env.API_URL ?? 'http://localhost:8000'

export default defineConfig({
  plugins: [vue(), tailwindcss()],
  server: {
    // I udvikling sendes API-kald videre til FastAPI (uv run uvicorn odense_rag.api:app).
    proxy: {
      '/ask': apiUrl,
      '/health': apiUrl,
    },
  },
  test: {
    environment: 'jsdom',
  },
})
