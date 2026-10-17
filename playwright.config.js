import { defineConfig } from "@playwright/test";
export default defineConfig({
  testDir: "frontend/tests",
  workers: 2,
  use: { baseURL: "http://127.0.0.1:8192", trace: "retain-on-failure" },
  webServer: {
    command: "python -m http.server 8192 --bind 127.0.0.1",
    url: "http://127.0.0.1:8192/frontend/tests/fixture.html",
    reuseExistingServer: false,
  },
});
