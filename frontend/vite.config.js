import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  test: {
    environment: 'jsdom',
    // jsdom only implements Storage APIs (localStorage) when it has an
    // origin to scope them to — without this, window.localStorage is
    // undefined rather than a working Storage instance.
    environmentOptions: { jsdom: { url: 'http://localhost:3000' } },
    setupFiles: './src/test/setup.js',
    globals: true,
  },
})
