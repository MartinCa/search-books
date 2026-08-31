---
name: frontend-conventions
description: House conventions for React frontends. Use whenever writing, reviewing, or scaffolding React, TypeScript, shadcn/ui, or Tailwind code in a personal project — including choosing a state library, adding a component, wiring an API call, or starting a new frontend. Also use when asked which stack or library to pick for a UI.
---

# Frontend conventions

These rules apply to every personal React project. They exist so that a dozen
small projects feel like one codebase, and so an agent picking up any of them
finds the same shapes in the same places.

**First: check for a local `DESIGN.md`.** If the project has one, it is
authoritative and its project-specific section overrides anything here. This
skill is the fallback and the summary; the file is the contract.

## The stack, decided

- TypeScript, `strict: true`. No `any`, no untyped API responses.
- React function components and hooks. No class components.
- Vite + TanStack Router by default (with `src/routeTree.gen.ts` committed as a
  vendored contract). Next.js only when SSR or SEO is a stated requirement —
  most of these projects are internal tools behind auth.
- shadcn/ui on Base UI primitives, pinned in `components.json`. Never mix bases.
- Tailwind with semantic theme tokens. Never a raw hex or `bg-blue-500`.
- TanStack Query for anything from a server. Zustand only for cross-cutting
  client state. `useState` for everything else.
- react-hook-form + zod for forms. TanStack Table for tables. date-fns for dates.
- lucide-react for icons, sonner for toasts.

Do not introduce a library outside this list without asking first.

## The rule that matters most

Most of what feels like global state is server state. Ask where the data comes
from before choosing a tool:

| Source                     | Tool                                                   |
| -------------------------- | ------------------------------------------------------ |
| An API                     | TanStack Query. Never copy results into another store. |
| One component              | `useState`                                             |
| Parent plus a child or two | Lift it, pass props                                    |
| No common ancestor         | Zustand, one store per concern, always with a selector |

React Context is for dependency injection, not for values that change often.

## shadcn components and generated files are vendored

Files in `src/components/ui/` are installed by the CLI and treated as
read-only. To change appearance, override theme CSS variables or target
`[data-slot="..."]`. To change behaviour, wrap the component in
`src/components/`. Hand-editing vendor files makes future `--overwrite` updates
a merge conflict.

Generated files (`src/routeTree.gen.ts`, `src/lib/api-types.ts`) are also
committed vendored contracts — never hand-edit them, always regenerate.
Committing `routeTree.gen.ts` ensures fresh clones have complete route types for
IDEs and type-aware linting without an upfront build.

Use `shadcn docs <component>` to get the current API rather than recalling
props. Use `--dry-run` or `--view` before writing files.

## Shared pieces come from the kit

Do not reimplement these; install them:

```sh
pnpm dlx shadcn@latest add MartinCa/frontend-kit/conventions   # DESIGN.md + AGENTS.md
pnpm dlx shadcn@latest add MartinCa/frontend-kit/api-client    # typed fetch + ApiError
pnpm dlx shadcn@latest add MartinCa/frontend-kit/query-setup   # QueryClient defaults
pnpm dlx shadcn@latest add MartinCa/frontend-kit/theme         # theme tokens
pnpm dlx shadcn@latest add MartinCa/frontend-kit/theme-provider # theme provider & dark mode support
```

`theme-provider` does nothing on its own — wrap the app in `<ThemeProvider>`
from `@/components/theme-provider` in `main.tsx`, or dark mode silently never
activates (the app renders light no matter the system preference, and
nothing errors to tell you why).

Lint, TypeScript, and Prettier config come from `@martinrun/frontend-config`.

## Talking to the backend

Backends vary (ASP.NET Core, FastAPI, Flask). The contract does not:

- OpenAPI spec is the source of truth; generate `src/lib/api-types.ts` from it.
  Never hand-write a response interface.
- Everything goes through `src/lib/api.ts`. No bare `fetch` in components.
- camelCase JSON, ISO 8601 timestamps with offset in UTC, decimals as strings,
  string enums, RFC 9457 `problem+json` errors.
- Same-origin `/api`, proxied by the dev server. No CORS config, no base URL in
  the bundle.

## Quality floor

Not optional, and not worth debating in review:

- Keyboard reachable with a visible focus ring.
- Real semantics. A `<div onClick>` is a defect.
- `prefers-reduced-motion` respected.
- Every async surface defines loading, empty, and error states.
- Error text says what happened and what to do next. It does not apologize.
- Button labels are verbs, consistent through a flow: "Publish" → "Published".
- Works at 375px wide.

## When unsure

Prefer less indirection. Prefer deleting an option to adding one. These are
hobby projects with one user; there is no backwards-compatibility burden.
