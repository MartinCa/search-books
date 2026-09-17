import { beforeEach, describe, expect, it, vi, type Mock } from "vitest";
import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ThemeProvider } from "@/components/theme-provider";
import { api } from "@/lib/api";
import type { components } from "@/lib/api-types";
import { App } from "@/App";

vi.mock("@/lib/api", () => ({
  api: { get: vi.fn() },
}));

type SearchResponse = components["schemas"]["SearchResponse"];

type GetSearchMock = Mock<
  (path: string, options?: { query?: { q?: string } }) => Promise<SearchResponse>
>;

function makeResponse(query: string, titles: string[]): SearchResponse {
  return {
    query,
    shelfmark_url: null,
    sources: [
      {
        key: "audiobookshelf",
        label: "Audiobookshelf",
        status: "ok",
        count: titles.length,
        results: titles.map((title, index) => ({
          id: `${query}-${index}`,
          title,
        })),
      },
    ],
  };
}

interface Deferred<T> {
  promise: Promise<T>;
  resolve: (value: T) => void;
}

function deferred<T>(): Deferred<T> {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((res) => {
    resolve = res;
  });
  return { promise, resolve };
}

function renderApp(queryClient: QueryClient) {
  return render(
    <ThemeProvider>
      <QueryClientProvider client={queryClient}>
        <App />
      </QueryClientProvider>
    </ThemeProvider>,
  );
}

describe("App search results", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("keeps the previous results visible while a re-search is fetching", async () => {
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });
    const pending = deferred<SearchResponse>();
    const getMock = api.get as unknown as GetSearchMock;

    getMock.mockImplementation((path, options) => {
      if (path !== "/search") return Promise.reject(new Error(`unexpected path: ${path}`));
      return options?.query?.q === "second"
        ? pending.promise
        : Promise.resolve(makeResponse(options?.query?.q ?? "", ["The Hobbit"]));
    });

    renderApp(queryClient);

    const input = screen.getByRole("searchbox");
    fireEvent.change(input, { target: { value: "found" } });
    fireEvent.submit(screen.getByRole("search"));

    expect(await screen.findByText("The Hobbit")).toBeInTheDocument();
    expect(getMock).toHaveBeenCalledWith("/search", { query: { q: "found" } });

    fireEvent.change(input, { target: { value: "second" } });
    fireEvent.submit(screen.getByRole("search"));

    // The re-search is in flight and the button reflects it...
    await waitFor(() => {
      expect(screen.getByRole("button", { name: /Searching/ })).toBeInTheDocument();
    });
    expect(getMock).toHaveBeenCalledWith("/search", { query: { q: "second" } });

    // ...but the first query's results are still on screen.
    expect(screen.getByText("The Hobbit")).toBeInTheDocument();

    await act(async () => {
      pending.resolve(makeResponse("second", ["Harry Potter and the Philosopher's Stone"]));
      await pending.promise;
    });

    expect(await screen.findByText("Harry Potter and the Philosopher's Stone")).toBeInTheDocument();
    await waitFor(() => {
      expect(screen.queryByText("The Hobbit")).not.toBeInTheDocument();
    });
  });
});
