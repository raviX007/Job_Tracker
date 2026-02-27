import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ProfileProvider } from "@/hooks/use-profile";
import { render } from "@testing-library/react";

export function renderWithProviders(ui: React.ReactElement) {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false, gcTime: 0 },
      mutations: { retry: false },
    },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <ProfileProvider>{ui}</ProfileProvider>
    </QueryClientProvider>,
  );
}
