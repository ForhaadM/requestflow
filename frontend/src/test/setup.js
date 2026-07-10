import '@testing-library/jest-dom/vitest'

// This Node/vitest/jsdom combination leaves both `localStorage` and
// `window.localStorage` undefined in the test environment (Node's own
// experimental `localStorage` global requires an unset --localstorage-file
// flag, and it isn't overridden by jsdom's implementation here) — real
// browsers are unaffected, this is purely a test-tooling gap. Polyfill a
// minimal Storage-compatible implementation so app code that calls
// `localStorage.getItem/setItem/removeItem` (AuthContext.jsx) works under
// test the same way it does in a real browser.
class MemoryStorage {
  #store = new Map()
  getItem(key) {
    return this.#store.has(key) ? this.#store.get(key) : null
  }
  setItem(key, value) {
    this.#store.set(key, String(value))
  }
  removeItem(key) {
    this.#store.delete(key)
  }
  clear() {
    this.#store.clear()
  }
}

if (typeof globalThis.localStorage?.getItem !== 'function') {
  Object.defineProperty(globalThis, 'localStorage', {
    value: new MemoryStorage(),
    configurable: true,
    writable: true,
  })
}
