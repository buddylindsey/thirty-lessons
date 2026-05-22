import { defineConfig } from '@playwright/test';

export default defineConfig({
  testDir: './tests/e2e',
  use: {
    baseURL: process.env.PLAYWRIGHT_BASE_URL || 'http://127.0.0.1:8000',
  },
  webServer: process.env.E2E_DOCKER === '1'
    ? undefined
    : {
        command: '.venv312/bin/python manage.py migrate --noinput && .venv312/bin/python manage.py runserver 127.0.0.1:8000',
        url: 'http://127.0.0.1:8000',
        reuseExistingServer: !process.env.CI,
        timeout: 120_000,
      },
});
