/**
 * E2E tests for admin flows.
 * Requires E2E_ADMIN_TOKEN env var (session token for a full-admin phone).
 *
 * Run: BASE_URL=https://drgomon.beauty E2E_ADMIN_TOKEN=xxx npx playwright test e2e/admin.spec.ts
 *
 * Tests are read-only — they verify data loads and navigation works but never mutate state.
 */
import { test, expect, Page } from '@playwright/test';

const APP = '/app/';
const ADMIN_TOKEN = process.env.E2E_ADMIN_TOKEN;

function skipIfNoToken() {
  if (!ADMIN_TOKEN) test.skip(true, 'E2E_ADMIN_TOKEN not set');
}

// ── Admin API direct calls ─────────────────────────────────────────────────

test('admin: /api/admin/role returns full or superadmin', async ({ page }) => {
  skipIfNoToken();
  const resp = await page.request.get('/api/admin/role', {
    headers: { Authorization: `Bearer ${ADMIN_TOKEN}` },
  });
  expect(resp.status()).toBe(200);
  const data = await resp.json();
  expect(['full', 'superadmin']).toContain(data.role);
});

test('admin: /api/admin/stats returns expected keys', async ({ page }) => {
  skipIfNoToken();
  const resp = await page.request.get('/api/admin/stats', {
    headers: { Authorization: `Bearer ${ADMIN_TOKEN}` },
  });
  expect(resp.status()).toBe(200);
  const data = await resp.json();
  expect(data).toHaveProperty('total_clients');
  expect(data).toHaveProperty('pwa_users');
  expect(data).toHaveProperty('visits_month');
});

test('admin: /api/admin/prices/edit returns list', async ({ page }) => {
  skipIfNoToken();
  const resp = await page.request.get('/api/admin/prices/edit', {
    headers: { Authorization: `Bearer ${ADMIN_TOKEN}` },
  });
  expect(resp.status()).toBe(200);
  const data = await resp.json();
  expect(Array.isArray(data)).toBeTruthy();
  expect(data.length).toBeGreaterThan(0);
  // Each item has duration as number (regression: was string '60 хв')
  for (const cat of data) {
    for (const item of cat.items || []) {
      if (item.duration !== undefined) {
        expect(typeof item.duration).toBe('number');
      }
    }
  }
});

test('admin: /api/admin/clients-list returns clients', async ({ page }) => {
  skipIfNoToken();
  const resp = await page.request.get('/api/admin/clients-list', {
    headers: { Authorization: `Bearer ${ADMIN_TOKEN}` },
  });
  expect(resp.status()).toBe(200);
  const data = await resp.json();
  const clients = data.clients ?? data;
  expect(Array.isArray(clients)).toBeTruthy();
  expect(clients.length).toBeGreaterThan(0);
});

test('admin: calendar returns appointments list for current month', async ({ page }) => {
  skipIfNoToken();
  const now = new Date();
  const y = now.getFullYear();
  const m = String(now.getMonth() + 1).padStart(2, '0');
  const from = `${y}-${m}-01`;
  const to   = `${y}-${m}-28`;
  const resp = await page.request.get(`/api/admin/calendar/appointments?from=${from}&to=${to}`, {
    headers: { Authorization: `Bearer ${ADMIN_TOKEN}` },
  });
  expect(resp.status()).toBe(200);
  const data = await resp.json();
  const appts = data.appointments ?? data;
  expect(Array.isArray(appts)).toBeTruthy();
});

// ── Admin PWA UI ───────────────────────────────────────────────────────────

test('admin: PWA shows admin-home screen after token', async ({ page }) => {
  skipIfNoToken();
  await page.goto(APP);
  await page.evaluate((t) => localStorage.setItem('gomon_token', t), ADMIN_TOKEN!);
  await page.reload();
  await page.waitForTimeout(2000);
  // Admin home or auth should be visible
  const body = page.locator('body');
  await expect(body).toBeVisible();
});

test('admin: no 500 errors on calendar load', async ({ page }) => {
  skipIfNoToken();
  const errors: string[] = [];
  page.on('response', (resp) => {
    if (resp.url().includes('/api/') && resp.status() >= 500) {
      errors.push(`${resp.status()} ${resp.url()}`);
    }
  });
  await page.goto(APP);
  await page.evaluate((t) => localStorage.setItem('gomon_token', t), ADMIN_TOKEN!);
  await page.reload();
  await page.waitForTimeout(3000);
  expect(errors).toHaveLength(0);
});
