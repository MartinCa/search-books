import { useState } from "react";
import type { components } from "@/lib/api-types";
import { Badge } from "@/components/ui/badge";

type BookResult = components["schemas"]["BookResult"];

function formatMeta(book: BookResult): string {
  const parts: string[] = [];
  if (book.authors && book.authors.length > 0) {
    parts.push(book.authors.join(", "));
  }
  if (book.series) {
    parts.push(book.series_index ? `${book.series} #${book.series_index}` : book.series);
  }
  if (book.year) {
    parts.push(book.year);
  }
  if (book.narrators && book.narrators.length > 0) {
    parts.push(`Read by ${book.narrators.join(", ")}`);
  }
  return parts.join(" · ");
}

export function BookCard({ book }: { book: BookResult }) {
  const [imageError, setImageError] = useState(false);
  const meta = formatMeta(book);

  return (
    <li className="border-border flex gap-4 border-b p-4 last:border-b-0">
      {/* Cover image container: fixed width to prevent layout collapse */}
      <div className="bg-muted text-muted-foreground flex h-24 w-16 shrink-0 items-center justify-center overflow-hidden rounded-md">
        {book.cover_url && !imageError ? (
          <img
            src={book.cover_url}
            alt=""
            loading="lazy"
            onError={() => setImageError(true)}
            className="h-full w-full object-cover"
          />
        ) : (
          <span className="text-xl" aria-hidden="true">
            📖
          </span>
        )}
      </div>

      <div className="flex min-w-0 flex-1 flex-col justify-center gap-1">
        <div>
          {book.item_url ? (
            <a
              href={book.item_url}
              target="_blank"
              rel="noopener noreferrer"
              className="text-foreground focus-visible:ring-ring font-semibold hover:underline focus-visible:ring-2 focus-visible:outline-none"
            >
              {book.title}
            </a>
          ) : (
            <span className="text-foreground font-semibold">{book.title}</span>
          )}
        </div>

        {book.subtitle ? <p className="text-muted-foreground text-sm">{book.subtitle}</p> : null}

        {meta ? <p className="text-muted-foreground text-xs">{meta}</p> : null}

        {book.formats && book.formats.length > 0 ? (
          <div className="mt-1 flex flex-wrap gap-1">
            {book.formats.map((fmt) => (
              <Badge key={fmt} variant="secondary" className="px-1.5 py-0 text-[10px]">
                {fmt}
              </Badge>
            ))}
          </div>
        ) : null}
      </div>
    </li>
  );
}
