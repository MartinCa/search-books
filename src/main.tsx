import { QueryClientProvider } from "@tanstack/react-query";
import { createRoot } from "react-dom/client";
import { ThemeProvider } from "@/components/theme-provider";
import { createQueryClient } from "@/lib/query";
import { App } from "@/App";
import "./index.css";

const queryClient = createQueryClient();

const rootElement = document.getElementById("root");
if (rootElement) {
  createRoot(rootElement).render(
    <ThemeProvider>
      <QueryClientProvider client={queryClient}>
        <App />
      </QueryClientProvider>
    </ThemeProvider>,
  );
}
