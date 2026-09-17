import "@testing-library/jest-dom";

// jest-dom matcher *types* (toBeInTheDocument & co. under vitest 5) are
// augmented per-module in src/vitest.d.ts, not here — that file ships inside
// the src/ directory the Dockerfile copies, so the Docker build (`pnpm build`)
// gets the augmentation while this runtime setup file does not exist there.

// jsdom doesn't implement matchMedia; ThemeProvider (dark-mode detection) needs it whenever a
// test renders the app's root layout or anything wrapped in ThemeProvider.
if (typeof window !== "undefined" && !window.matchMedia) {
  window.matchMedia = (query: string) => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: () => {},
    removeListener: () => {},
    addEventListener: () => {},
    removeEventListener: () => {},
    dispatchEvent: () => false,
  });
}
