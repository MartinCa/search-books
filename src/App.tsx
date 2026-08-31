import { useState, type FormEvent } from "react";
import { useQuery } from "@tanstack/react-query";
import { ExternalLink, Search as SearchIcon } from "lucide-react";
import type { components } from "@/lib/api-types";
import { api } from "@/lib/api";
import { SourceColumn } from "@/components/SourceColumn";
import { ThemeToggle } from "@/components/theme-toggle";
import { Button, buttonVariants } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils";

type SearchResponse = components["schemas"]["SearchResponse"];

function getInitialQuery(): string {
  if (typeof window === "undefined") return "";
  const params = new URLSearchParams(window.location.search);
  return params.get("q")?.trim() ?? "";
}

export function App() {
  const [queryInput, setQueryInput] = useState(getInitialQuery);
  const [activeQuery, setActiveQuery] = useState(getInitialQuery);

  const { data, error, isLoading, isFetching } = useQuery<SearchResponse>({
    queryKey: ["search", activeQuery],
    queryFn: () => api.get<SearchResponse>("/search", { query: { q: activeQuery } }),
    enabled: activeQuery.length > 0,
  });

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const trimmed = queryInput.trim();
    if (!trimmed) return;

    const url = new URL(window.location.href);
    url.searchParams.set("q", trimmed);
    window.history.replaceState(null, "", url);

    setActiveQuery(trimmed);
  }

  const sources = data?.sources ?? [];
  const shelfmarkUrl = data?.shelfmark_url;

  return (
    <div className="bg-background text-foreground flex min-h-screen flex-col">
      <header className="border-border border-b px-4 py-4 sm:px-6">
        <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-4">
          <div className="flex items-center gap-2">
            <span className="text-2xl" aria-hidden="true">
              📚
            </span>
            <h1 className="text-xl font-bold tracking-tight">search-books</h1>
          </div>

          <div className="flex items-center gap-2">
            <ThemeToggle />
          </div>

          <form
            onSubmit={handleSubmit}
            role="search"
            className="flex w-full flex-wrap items-center gap-2 pt-2 sm:pt-0"
          >
            <div className="relative min-w-[260px] flex-1">
              <Input
                id="query"
                type="search"
                value={queryInput}
                onChange={(e) => setQueryInput(e.target.value)}
                placeholder="Title, author, series…"
                autoComplete="off"
                autoFocus
                required
                className="w-full pl-9"
              />
              <SearchIcon className="text-muted-foreground pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2" />
            </div>

            <Button type="submit" disabled={isLoading || isFetching}>
              {isLoading || isFetching ? "Searching…" : "Search"}
            </Button>

            {shelfmarkUrl && (
              <a
                href={shelfmarkUrl}
                target="_blank"
                rel="noopener noreferrer"
                className={cn(
                  buttonVariants({ variant: "outline" }),
                  "text-primary gap-1.5 font-semibold",
                )}
              >
                <span>Search in Shelfmark</span>
                <ExternalLink className="size-4" />
              </a>
            )}
          </form>
        </div>
      </header>

      <main className="mx-auto flex w-full max-w-7xl flex-1 flex-col p-4 sm:p-6">
        {error ? (
          <div className="border-destructive/50 bg-destructive/10 text-destructive rounded-lg border p-4 text-center text-sm">
            {error instanceof Error ? error.message : "An unexpected error occurred."}
          </div>
        ) : null}

        {isLoading ? (
          <div className="text-muted-foreground p-12 text-center text-sm">
            Searching for “{activeQuery}”…
          </div>
        ) : null}

        {!isLoading && sources.length > 0 ? (
          <div className="grid grid-cols-1 items-start gap-6 md:grid-cols-2">
            {sources.map((source) => (
              <SourceColumn key={source.key} source={source} />
            ))}
          </div>
        ) : null}

        {!activeQuery && !isLoading && (
          <div className="text-muted-foreground flex flex-1 items-center justify-center p-12 text-center">
            <p>Enter a query above to search configured Audiobookshelf and Calibre sources.</p>
          </div>
        )}
      </main>
    </div>
  );
}
