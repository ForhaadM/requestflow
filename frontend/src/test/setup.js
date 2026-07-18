import '@testing-library/jest-dom/vitest'

// App code (AuthContext.jsx) stores the token in `sessionStorage`, which
// jsdom implements natively given the `environmentOptions.jsdom.url` set in
// vite.config.js — no polyfill needed here (unlike `localStorage`, which
// Node's own experimental global shadows in this environment).
