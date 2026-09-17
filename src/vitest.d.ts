import type { TestingLibraryMatchers } from "@testing-library/jest-dom/matchers";

// --- jest-dom matcher types under vitest 5 ----------------------------------
// Vitest 5 inlined its expect package and changed the matcher interfaces: Assertion<T>
// became Assertion<R, T> (return type first), and the global jest.Matchers namespace that
// @testing-library/jest-dom's plain entry augments is no longer part of vitest's Assertion.
// jest-dom 7.0.1's own /vitest types still augment the v4 one-parameter Assertion<T>, which
// TypeScript silently drops (mismatched type parameters, suppressed by skipLibCheck) — so
// toBeInTheDocument & co. stopped type-checking. Augment the v5 shape here instead. Do NOT
// "fix" the runtime import in vitest.setup.ts to @testing-library/jest-dom/vitest: its stale
// augmentation would conflict with this block. Once jest-dom ships vitest 5 support, delete
// this file and switch the import to @testing-library/jest-dom/vitest.
//
// This file lives under src/ on purpose: the Dockerfile's frontend stage copies only src/
// (not vitest.setup.ts), and `pnpm build` type-checks the app with src present — so the
// augmentation must be part of src/ for the Docker build to see these methods.
declare module "vitest" {
  // `T` must stay in the signature (even though only `R` is used below) so this declaration
  // merges with vitest's own two-parameter `Assertion<R, T>` rather than shadowing it; the
  // no-empty-object-type/no-unused-vars disables below are consequences of that merge, not
  // things a member or a differently-shaped signature could satisfy.
  // `any` for the asymmetric-matcher parameter mirrors jest-dom's own vitest shim.
  // eslint-disable-next-line @typescript-eslint/no-explicit-any, @typescript-eslint/no-unused-vars, @typescript-eslint/no-empty-object-type
  interface Assertion<R, T> extends TestingLibraryMatchers<any, R> {}
  // eslint-disable-next-line @typescript-eslint/no-explicit-any, @typescript-eslint/no-empty-object-type
  interface AsymmetricMatchersContaining extends TestingLibraryMatchers<any, any> {}
}
