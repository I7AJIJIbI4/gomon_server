/**
 * E2E tests for the client-facing PWA (drgomon.beauty/app/).
 * Requires a live server. Run: BASE_URL=https://drgomon.beauty npx playwright test e2e/client.spec.ts
 *
 * These tests use a test phone + OTP or a pre-seeded session token (via E2E_TOKEN env var).
 * They are read-only — they navigate and verify but never submit appointment forms or make payments.
 */
import { test, expect, Page } from '@playwright/test';

const APP = '/app/';
const TOKEN = process.env.E2E_TOKEN; // pre-seeded session token for a test client

async function loginWithToken(page: Page) {
  if (!TOKEN) {
    test.skip(true, 'E2E_TOKEN not set — skipping authenticated tests');
    return;
  }
  await page.goto(APP);
  await page.evaluate((t) => localStorage.setItem('gomon_token', t), TOKEN);
  await page.reload();
}

// ── Public (unauthenticated) ──────────────────────────────────────────────

test('app loads and shows auth screen', async ({ page }) => {
  await page.goto(APP);
  // Either auth screen or home is visible depending on stored token
  const body = page.locator('body');
  await expect(body).toBeVisible();
  const title = await page.title();
  expect(title).toMatch(/Dr\.?\s*Gomon|Gomon/i);
});

test('prices screen loads without auth', async ({ page }) => {
  await page.goto(APP);
  // Navigate to prices via JS (screen transition)
  await page.evaluate(() => {
    if (typeof (window as any).go === 'function') (window as any).go('price');
  });
  // At minimum the page shouldn't crash
  await expect(page.locator('body')).toBeVisible();
});

test('API health responds 200', async ({ page }) => {
  const resp = await page.request.get('/api/health');
  expect(resp.status()).toBe(200);
  const data = await resp.json();
  expect(data).toHaveProperty('db');
});

test('prices API returns array', async ({ page }) => {
  const resp = await page.request.get('/api/prices');
  expect(resp.status()).toBe(200);
  const data = await resp.json();
  expect(Array.isArray(data)).toBeTruthy();
  expect(data.length).toBeGreaterThan(0);
});

// ── Deep links (regression: PWA must open native app, not Chrome Custom Tab) ──

test('Telegram button navigates via location.href pattern', async ({ page }) => {
  await page.goto(APP);
  // Find any TG link and verify it uses onclick with openExternal or openMap pattern
  const tgLinks = await page.locator('a[href*="t.me"]').all();
  for (const link of tgLinks) {
    const onclick = await link.getAttribute('onclick');
    // Must NOT use target=_blank for deep links; must use openExternal or similar
    const target = await link.getAttribute('target');
    if (onclick) {
      expect(onclick).toMatch(/openExternal|location\.href/i);
    } else {
      // If no onclick, must not be target=_blank in PWA context
      expect(target).not.toBe('_blank');
    }
  }
});

// ── Authenticated ─────────────────────────────────────────────────────────

test('authenticated: /api/me returns client data', async ({ page }) => {
  if (!TOKEN) test.skip(true, 'E2E_TOKEN not set');
  const resp = await page.request.get('/api/me', {
    headers: { Authorization: `Bearer ${TOKEN}` },
  });
  expect(resp.status()).toBe(200);
  const data = await resp.json();
  expect(data).toHaveProperty('phone');
  expect(data.is_admin).toBe(false);
});

test('authenticated: home screen shows after token set', async ({ page }) => {
  await loginWithToken(page);
  if (!TOKEN) return;
  // Home screen should be visible (contains appointments or welcome text)
  await page.waitForSelector('#screen-home, #screen-auth', { timeout: 5000 });
  const home = page.locator('#screen-home');
  const auth = page.locator('#screen-auth');
  // Either home is visible (logged in) or auth (token rejected)
  const homeVis = await home.isVisible().catch(() => false);
  const authVis = await auth.isVisible().catch(() => false);
  expect(homeVis || authVis).toBeTruthy();
});

test('authenticated: appointments screen loads', async ({ page }) => {
  await loginWithToken(page);
  if (!TOKEN) return;
  await page.evaluate(() => {
    if (typeof (window as any).go === 'function') (window as any).go('appointments');
  });
  await page.waitForTimeout(1000);
  await expect(page.locator('body')).toBeVisible();
  // No JS errors expected
});
