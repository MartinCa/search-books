import type { components } from "@/lib/api-types";
import { BookCard } from "@/components/BookCard";
import { Badge } from "@/components/ui/badge";

type SourceResult = components["schemas"]["SourceResult"];

export function SourceColumn({ source }: { source: SourceResult }) {
  const { label, status, error, results, count } = source;

  return (
    <section className="border-border bg-card text-card-foreground flex flex-col overflow-hidden rounded-lg border shadow-xs">
      <div className="border-border bg-muted/40 flex items-center justify-between border-b px-4 py-3">
        <h2 className="text-base font-semibold">{label}</h2>
        {status === "ok" && (
          <Badge
            variant={count > 0 ? "default" : "secondary"}
            className={count > 0 ? "bg-status-ok hover:bg-status-ok text-white" : ""}
          >
            {count}
          </Badge>
        )}
        {status === "disabled" && (
          <Badge variant="outline" className="text-muted-foreground">
            off
          </Badge>
        )}
        {status === "error" && <Badge variant="destructive">!</Badge>}
      </div>

      <div className="flex-1">
        {status === "disabled" && (
          <div className="text-muted-foreground p-6 text-center text-sm">
            {label} is not configured.
          </div>
        )}

        {status === "error" && (
          <div className="text-status-error p-6 text-center text-sm">
            {label} could not be searched: {error ?? "Unknown error"}
          </div>
        )}

        {status === "ok" && count === 0 && (
          <div className="text-muted-foreground p-6 text-center text-sm">Not found in {label}.</div>
        )}

        {status === "ok" && results && results.length > 0 && (
          <ol className="divide-border divide-y">
            {results.map((book) => (
              <BookCard key={book.id} book={book} />
            ))}
          </ol>
        )}
      </div>
    </section>
  );
}
