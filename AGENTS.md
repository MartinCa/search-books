# AGENTS.md

## Before writing any UI code

Read `DESIGN.md` in this repository in full. It is binding. If a rule there
conflicts with a habit, a tutorial, or a suggestion from a model, the file wins.

`DESIGN.md` is distributed from `MartinCa/frontend-kit` and is **not edited here**.
To change a convention, change it upstream and reinstall:

```sh
pnpm dlx shadcn@latest add MartinCa/frontend-kit/conventions --overwrite
```

The project-specific section at the bottom of `DESIGN.md` is the exception — that
part is owned by this repo.

## Mandatory verification before opening PRs

Git hooks (`lefthook`) format and lint on `git commit`, but agents often work
where hooks are not initialized (ephemeral cloud VMs, web/mobile sessions, Docker
containers). Before creating commits and opening a pull request, you **MUST**
run all verification commands explicitly (script names here differ from the
frontend-kit standard; these match this repo's `package.json` and CI):

1. `pnpm lint:ci` — ESLint with `--max-warnings 0`.
2. `pnpm format:check` — Prettier verification (`prettier --check .`).
3. `pnpm build` — full type-check (`tsc -b`) plus the vite build.
4. `uv run ruff check . && uv run ruff format --check .` — backend lint and format.
5. `uv run pytest` — backend test suite.

There is no frontend test suite; the type-check in `pnpm build` covers the frontend.

Fix any reported violations or warnings rather than disabling rules or skipping checks.

## Git hooks

Local hooks are installed automatically by `pnpm install` (the `prepare` script runs `lefthook install` — idempotent, safe to re-run).

Hooks come from the shared `MartinCa/lefthook-configs` fragments pinned at `v2.0.0` in `lefthook.yml`. `remotes:` configs merge _over_ `lefthook.yml`. The fragments are native to this repo's tooling (pnpm on the frontend, uv/ruff on the backend), and since `v2.0.0` every language fragment names its commands with a language suffix (`lint-ts`/`format-ts`, `lint-python`/`format-python`), so `langs/ts.yml` and `langs/python.yml` compose natively — there is no `lefthook-local.yml` here.

- **pre-commit** — ESLint `--fix` + Prettier `--write` on staged TS/TSX (Prettier on JSON/CSS/MD), Ruff `check --fix` + `format` on staged Python, re-staging fixed files; `lefthook-shared.yml` secret-scans the staged diff with `betterleaks` (blocks the commit on a leak) and audits staged `.github/workflows/*` files with `zizmor` (blocks on a finding).
- **commit-msg** — `commit-msg.yml` enforces Conventional Commits, e.g. `feat: ...`, `fix(api): ...`.

These hooks are the **only** enforcement of the lint/format autofixes, the secret scan, and Conventional-Commits checks. CI runs `pnpm lint:ci` (ESLint with `--max-warnings 0`), `pnpm format:check`, `pnpm build`, `uv run ruff check`, `ruff format --check`, and `uv run pytest` as blocking gates, and uploads a zizmor SARIF report to code scanning — a non-blocking SARIF upload, not a merge gate. CI does not run the autofixes, `betterleaks`, or commit-msg validation itself. Do not bypass the hooks.

Two hook tools must be on `PATH`: `betterleaks` (secret scan, install per its project README) and `zizmor` (workflow audit, install from zizmor.sh). If a tool is missing, `LEFTHOOK=0 git commit` skips the hooks entirely — a pragmatic escape hatch for restricted setups, not a way to dodge the gates.

## Shortcuts

- `shadcn info` — what is installed, which base, where the docs are.
- `shadcn docs <component>` — current API for a primitive. Use this instead of
  recalling props from memory; the Base UI and Radix APIs differ.
- `shadcn add <name> --dry-run` / `--view` — inspect before writing files.

## Dependency versions

Install packages with the package manager (`pnpm add <pkg>`, no version pin) and
let it resolve the current release; `pnpm add` writes a range and Renovate keeps
it current. Do not hand-write a version into `package.json` from memory — training
data lags, and a remembered version is routinely a major or two behind. If a
specific version genuinely matters (a peer dependency constraint, a known-bad
release), say so and name the reason in the commit.

## House rules that are linted

`pnpm lint` enforces the mechanical parts of `DESIGN.md` — strict TypeScript, no
deep relative imports, no direct primitive imports outside `components/ui/`, no
inline `style` props, no Zustand fetches, TanStack Query best practices; the rules
themselves live in `DESIGN.md`. A few are warnings rather than errors, so CI runs
with `--max-warnings 0`: a warning is a thing to fix, not a pass. Fix the code
rather than disabling the rule; if a rule is genuinely wrong, change it upstream
in `@martinrun/frontend-config`.

## Do not

- Add a state, data-fetching, or UI library. The stack is decided in `DESIGN.md`.
- Hand-edit `src/components/ui/**` or generated files (`src/lib/api-types.ts`,
  `src/routeTree.gen.ts` where present). All are vendored.
- Refactor files unrelated to the task in hand.
- Write a response interface by hand. Regenerate from the OpenAPI spec.
