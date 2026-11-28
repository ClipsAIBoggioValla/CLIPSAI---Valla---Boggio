import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import test from 'node:test'
import ts from 'typescript'

const source = await readFile(new URL('../src/components/billing/billingDisplay.ts', import.meta.url), 'utf8')
const compiled = ts.transpileModule(source, {
  compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2020 },
}).outputText
const { formatCreditBalance, creditBadgeText, creditBadgeLabel } = await import(`data:text/javascript;base64,${Buffer.from(compiled).toString('base64')}`)

test('formats finite and unlimited credit balances for the page and navbar', () => {
  assert.equal(formatCreditBalance(24, false), '24 minutos')
  assert.equal(formatCreditBalance(24, false, true), '24 min')
  assert.equal(formatCreditBalance(null, false), '0 minutos')
  assert.equal(formatCreditBalance(null, true, true), 'Ilimitado')
})

test('shows explicit loading and recoverable error states in the balance badge', () => {
  assert.equal(creditBadgeText(true, false, null), 'Cargando…')
  assert.equal(creditBadgeText(false, true, null), 'No disponible')
  assert.equal(creditBadgeLabel(false, true, null), 'saldo no disponible')
  assert.equal(creditBadgeText(false, false, { balance: null, credits_unlimited: true }), 'Ilimitado')
})

test('keeps the Billing route and redirects the legacy credits route', async () => {
  const app = await readFile(new URL('../src/App.tsx', import.meta.url), 'utf8')
  const badge = await readFile(new URL('../src/components/billing/CreditBalanceBadge.tsx', import.meta.url), 'utf8')
  assert.match(app, /path="\/billing"\s+element={<BillingPage \/>}/)
  assert.match(app, /path="\/credits"\s+element={<Navigate to="\/billing" replace \/>}/)
  assert.match(badge, /creditService\.getCredits\(1, 1\)/)
  assert.match(badge, /Reintentar cargar saldo/)
})

test('keeps billing UI on the existing paginated credits API', async () => {
  const api = await readFile(new URL('../src/services/api.ts', import.meta.url), 'utf8')
  const page = await readFile(new URL('../src/pages/BillingPage.tsx', import.meta.url), 'utf8')
  const sidebar = await readFile(new URL('../src/components/Sidebar.tsx', import.meta.url), 'utf8')
  const upload = await readFile(new URL('../src/pages/UploadPage.tsx', import.meta.url), 'utf8')
  assert.match(api, /getCredits\(page = 1, pageSize = 20\)/)
  assert.match(api, /\/billing\/credits\?page=\$\{page\}&page_size=\$\{pageSize\}/)
  assert.match(page, /creditService\.getCredits\(page, PAGE_SIZE\)/)
  assert.match(page, /Planes de ClipsAI/)
  assert.match(page, /Stripe/)
  assert.match(page, /Mercado Pago/)
  assert.match(sidebar, /to="\/billing"[\s\S]*?Billing/)
  assert.match(upload, /to="\/billing"/)
})
