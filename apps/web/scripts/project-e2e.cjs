// Run against a local Q instance. Creates a clearly labeled synthetic project.
// Requires Playwright and an installed browser; never downloads browser binaries.
/* eslint-disable @typescript-eslint/no-require-imports -- CommonJS CLI resolves an optional externally installed Playwright runtime. */
const { chromium } = require(process.env.Q_PLAYWRIGHT_MODULE || 'playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

async function main() {
  const base = process.argv[2] || 'http://127.0.0.1:5273';
  const output = path.resolve(process.argv[3] || 'outputs/verification/project-browser');
  fs.mkdirSync(output, { recursive: true });
  const browser = await chromium.launch({ headless: true, channel: process.env.Q_E2E_BROWSER_CHANNEL || 'msedge' });
  const page = await browser.newPage({ viewport: { width: 1600, height: 1100 } });
  page.setDefaultTimeout(45000);
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  const api = '/integrations/engine/api/research/projects';
  let project;
  async function action(label, suffix, status = 201) {
    const response = page.waitForResponse(r => r.request().method() === 'POST' && new URL(r.url()).pathname === api + suffix);
    await page.getByRole('button', { name: label, exact: true }).click();
    const received = await response;
    const body = await received.json();
    assert.equal(received.status(), status, JSON.stringify(body));
    // Wait for the action's refresh/enable, not just a stale option label.
    await page.getByRole('button', { name: 'Refresh project', exact: true }).waitFor();
    await page.waitForFunction(() => ![...document.querySelectorAll('button')].find(b => b.textContent === 'Refresh project')?.disabled);
    return body;
  }
  async function stateUntil(test) {
    const end = Date.now() + 240000;
    while (Date.now() < end) {
      const response = await page.request.get(base + api + '/' + project.id);
      assert.equal(response.status(), 200);
      const state = await response.json();
      if (test(state)) { project = state; return state; }
      await page.waitForTimeout(500);
    }
    throw new Error('Project job did not reach expected terminal state');
  }
  async function refresh() {
    const response = page.waitForResponse(r => r.request().method() === 'GET' && new URL(r.url()).pathname === api + '/' + project.id);
    await page.getByRole('button', { name: 'Refresh project', exact: true }).click();
    await response;
    await page.waitForFunction(() => ![...document.querySelectorAll('button')].find(b => b.textContent === 'Refresh project')?.disabled);
  }
  const stage = name => page.getByRole('navigation', { name: 'Research lifecycle' }).getByRole('button', { name, exact: true }).click();
  try {
    await page.goto(base, { waitUntil: 'networkidle' });
    await page.getByRole('heading', { name: 'Research projects', exact: true }).waitFor();
    await page.getByLabel('Project title', { exact: true }).fill('SYNTHETIC lifecycle browser acceptance ' + new Date().toISOString());
    project = await action('Create research project', '');
    const originalRevision = project.revision_id;
    await stage('SIGNAL');
    await page.getByLabel('Portfolio weighting', { exact: true }).selectOption('equal');
    await action('Save new specification revision', '/' + project.id + '/revisions');
    await stage('VALIDATION');
    await page.getByText('Versioned statistical protocol', { exact: true }).click();
    await page.getByLabel('Survival protocol JSON').fill(JSON.stringify({ bootstrap_samples: 100, cscv_blocks: 4, max_folds: 4 }));
    await action('Save protocol revision', '/' + project.id + '/revisions');
    await stage('DATA');
    await action('Capture dataset snapshot', '/' + project.id + '/datasets', 202);
    await stateUntil(s => s.datasets.length === 1 || s.tasks.some(t => t.status === 'failed'));
    assert.equal(project.datasets.length, 1, JSON.stringify(project.tasks));
    assert.equal(project.datasets[0].partition.development_observations, 720);
    await refresh();
    await stage('EXPERIMENTS');
    await page.getByLabel('Lookbacks (comma separated; blank uses saved candidate)').fill('63,80');
    await action('Run parameter experiments', '/' + project.id + '/trials', 202);
    await stateUntil(s => s.trials.length === 2 && s.trials.every(t => ['completed', 'failed'].includes(t.status)));
    assert.ok(project.trials.every(t => t.status === 'completed'), JSON.stringify(project.trials.map(t => t.error)));
    await refresh();
    const candidate = project.trials.find(t => t.request.sleeves[0].lookback === 63);
    const neighbor = project.trials.find(t => t.request.sleeves[0].lookback === 80);
    await page.getByLabel('Selected trial', { exact: true }).selectOption(neighbor.id);
    await page.getByLabel('Research decision / reason', { exact: true }).fill('Retain this diagnostic neighbor but reject promotion: it was not the prespecified candidate.');
    await action('Reject selected trial', '/' + project.id + '/trials/' + neighbor.id + '/decision');
    await page.getByLabel('Selected trial', { exact: true }).selectOption(candidate.id);
    await page.screenshot({ path: path.join(output, 'experiments.png'), fullPage: true });
    await stage('COMPARE');
    await page.getByRole('checkbox', { name: 'Compare trial ' + candidate.id.slice(0, 8), exact: true }).check();
    await page.getByRole('checkbox', { name: 'Compare trial ' + neighbor.id.slice(0, 8), exact: true }).check();
    await page.getByText('Matched data, dates, engine and account convention.', { exact: false }).waitFor();
    const comparisonTable = page.getByRole('table').filter({ has: page.getByText('Stored experiment evidence · development only', { exact: true }) });
    assert.equal(await comparisonTable.getByText('rejected', { exact: true }).count(), 1);
    assert.equal(await comparisonTable.getByRole('row').filter({ hasText: 'Commission / slippage' }).count(), 1);
    assert.equal(await page.locator('main').evaluate(main => getComputedStyle(main).overflowY), 'auto', 'Project evidence must remain scrollable on desktop');
    await page.getByText('Compare retained experiments', { exact: true }).evaluate(heading => heading.scrollIntoView({ block: 'start' }));
    await page.screenshot({ path: path.join(output, 'comparison.png'), fullPage: true });
    await page.setViewportSize({ width: 900, height: 1100 });
    await page.waitForFunction(() => document.querySelector('[aria-label="Toggle Codex panel"]')?.getAttribute('aria-expanded') === 'false');
    await page.getByText('Compare retained experiments', { exact: true }).evaluate(heading => heading.scrollIntoView({ block: 'start' }));
    assert.ok(await page.locator('main').evaluate(main => main.scrollWidth <= main.clientWidth + 1), 'Comparison must scroll within its table, not overflow the workspace');
    await page.screenshot({ path: path.join(output, 'comparison-compact.png'), fullPage: true });
    await page.setViewportSize({ width: 1600, height: 1100 });
    await stage('VALIDATION');
    const submitted = await action('Run existing Survival validation', '/' + project.id + '/trials/' + candidate.id + '/validate', 202);
    await stateUntil(s => s.validations.some(v => v.id === submitted.id && ['completed', 'failed'].includes(v.status)));
    const validation = project.validations.find(v => v.id === submitted.id);
    assert.equal(validation.status, 'completed', JSON.stringify(validation.error));
    assert.equal(validation.result.layers.length, 18);
    assert.equal(validation.result.summary.research_gates_satisfied, true);
    assert.equal(validation.result.layers.find(l => l.id === 10).metrics.dsr, null);
    await refresh();
    await stage('ROBUSTNESS');
    await page.getByText('Complete local lookback surface; no optimum selected', { exact: true }).waitFor();
    await page.screenshot({ path: path.join(output, 'robustness.png'), fullPage: true });
    await stage('OOS');
    await page.getByLabel('Research decision / reason', { exact: true }).fill('Reveal the prespecified candidate once; retain permanent access history and no unseen-OOS claim.');
    await action('Reveal reserved OOS and record access', '/' + project.id + '/trials/' + candidate.id + '/reveal', 202);
    await stateUntil(s => s.oos.length === 1 || s.tasks.some(t => t.kind === 'oos' && t.status === 'failed'));
    assert.equal(project.oos.length, 1, JSON.stringify(project.tasks));
    await refresh();
    await action('Reveal reserved OOS and record access', '/' + project.id + '/trials/' + candidate.id + '/reveal', 409);
    await stage('FREEZE');
    await page.getByLabel('Basis for expectations', { exact: true }).fill('No empirical performance expectation follows from this synthetic acceptance test.');
    const frozen = await action('Freeze candidate specification', '/' + project.id + '/freezes');
    assert.equal(frozen.synthetic, true);
    assert.equal(frozen.live_eligible, false);
    await stage('FORWARD');
    await action('Register frozen forward protocol', '/' + project.id + '/forward');
    await page.getByText(/0 observations/).waitFor();
    await stage('MONITOR');
    await page.getByText('No threshold breach recorded. Missing observations do not establish safety or strategy survival.', { exact: true }).waitFor();
    const comparison = await (await page.request.get(base + api + '/' + project.id + '/versions/' + frozen.strategy_version_id + '/comparison')).json();
    assert.ok(Number.isFinite(comparison.table.find(r => r.metric === 'cagr').historical));
    assert.ok(Number.isFinite(comparison.table.find(r => r.metric === 'volatility').historical));
    assert.ok(comparison.table.every(r => r.prospective === null));
    await page.screenshot({ path: path.join(output, 'monitor.png'), fullPage: true });
    await stage('PAPER');
    const saved = page.waitForEvent('download');
    await page.getByRole('link', { name: 'Download research paper (Markdown)', exact: true }).click();
    await (await saved).saveAs(path.join(output, 'research-paper.md'));
    const packed = page.waitForEvent('download');
    await page.getByRole('link', { name: 'Download reproducibility ZIP', exact: true }).click();
    await (await packed).saveAs(path.join(output, 'research-project.zip'));
    assert.equal((fs.readFileSync(path.join(output, 'research-paper.md'), 'utf8').match(/\n## /g) || []).length, 21);
    // New browser load proves persisted selection, not merely retained React state.
    await page.reload({ waitUntil: 'networkidle' });
    const loaded = page.waitForResponse(r => r.request().method() === 'GET' && new URL(r.url()).pathname === api + '/' + project.id);
    await page.getByLabel('Open research project', { exact: true }).selectOption(project.id);
    project = await (await loaded).json();
    await page.getByLabel('Project title', { exact: true }).waitFor();
    assert.equal(await page.getByLabel('Project title', { exact: true }).inputValue(), project.spec.thesis.title);
    assert.notEqual(project.revision_id, originalRevision);
    assert.equal(project.trials.length, 2);
    assert.equal(project.forward.length, 1);
    assert.equal(project.integrity.oos_reveals, 1);
    assert.ok(project.journal.some(e => e.action === 'experiment_decision_recorded' && e.body.status === 'rejected'));
    assert.deepEqual(errors, []);
    await page.screenshot({ path: path.join(output, 'reopened.png'), fullPage: true });
    const result = { passed: true, project_id: project.id, title: project.spec.thesis.title, trial_id: candidate.id,
      strategy_version_id: frozen.strategy_version_id, trials: project.trials.length, integrity: project.integrity,
      validation: validation.result.summary, errors, output, prospective_observations: 0 };
    fs.writeFileSync(path.join(output, 'summary.json'), JSON.stringify(result, null, 2));
    console.log(JSON.stringify(result, null, 2));
  } catch (error) {
    await page.screenshot({ path: path.join(output, 'failure.png'), fullPage: true });
    fs.writeFileSync(path.join(output, 'failure.json'), JSON.stringify({ error: String(error), project_id: project?.id, errors, body: await page.locator('body').innerText() }, null, 2));
    throw error;
  } finally { await browser.close(); }
}
main().catch(error => { console.error(error); process.exitCode = 1; });
