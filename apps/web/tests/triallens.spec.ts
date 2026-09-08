import { expect, test } from "@playwright/test";

const answerFixture = {
  id: "answer-fixture",
  question: "What are the main benefits?",
  short_answer: "The extracted evidence contains benefit signals across trials and literature.",
  direct_answer: "The workspace contains repeated benefit signals [Citation 1]. The size and certainty of benefit vary by source [Citation 2].",
  evidence_map: ["Trials provide outcome context", "Literature provides broader interpretation"],
  reasoning_summary: ["The answer prioritizes directly matched extraction rows."],
  evidence_synthesis: ["Finding one", "Finding two", "Finding three"],
  source_readouts: ["Trial readout", "Literature readout"],
  evidence_quality: ["Evidence quality varies by source type."],
  facet_coverage: ["Benefits covered", "Safety covered"],
  answer_trace: [{ label: "Rows read", value: "10", detail: "Across trials and literature" }],
  evidence: ["Evidence statement"],
  supporting_evidence: ["Supporting statement one", "Supporting statement two"],
  safety_limitations: ["Safety caveat one", "Safety caveat two"],
  uncertainty: ["Important uncertainty remains"],
  limitations: [],
  citations: ["Citation 1", "Citation 2", "Citation 3", "Citation 4", "Citation 5"],
  retrieved_chunks: [
    {
      chunk_id: "chunk-1",
      source_id: "source-1",
      source_type: "pubmed",
      citation: "Citation 1",
      text: "Retrieved passage text.",
      score: 0.92,
      section: "abstract",
      title: "Representative source",
      url: "https://pubmed.ncbi.nlm.nih.gov/1/",
      external_id: "1",
      publication_date: "2025",
      matched_terms: ["benefit"],
      relevance_note: "Directly matched the question.",
    },
    {
      chunk_id: "chunk-2",
      source_id: "source-2",
      source_type: "pubmed",
      citation: "Citation 2",
      text: "A second retrieved passage.",
      score: 0.84,
      section: "results",
      title: "Second representative source",
      url: "https://pubmed.ncbi.nlm.nih.gov/2/",
      external_id: "2",
      publication_date: "2024",
      matched_terms: ["benefit"],
      relevance_note: "Directly matched the question.",
    },
  ],
};

test.beforeEach(async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Follow the evidence." })).toBeVisible();
});

test("persists the user's light and dark theme choice", async ({ page }) => {
  await page.evaluate(() => window.localStorage.removeItem("triallens.theme"));
  await page.reload();

  const switchToDark = page.getByRole("button", { name: "Switch to dark mode" });
  await expect(switchToDark).toBeVisible();
  await expect(switchToDark).toHaveAttribute("aria-pressed", "false");

  await switchToDark.click();
  await expect(page.locator("html")).toHaveClass(/dark/);
  await expect(page.getByRole("button", { name: "Switch to light mode" })).toHaveAttribute("aria-pressed", "true");

  await page.reload();
  await expect(page.locator("html")).toHaveClass(/dark/);
  await expect(page.getByRole("button", { name: "Switch to light mode" })).toBeVisible();
});

test("opens a real workspace and exposes every evidence view", async ({ page }) => {
  await expect(page.getByLabel("Condition")).toBeVisible();
  await expect(page.getByLabel("Drug or intervention")).toBeVisible();
  await expect(page.getByRole("button", { name: "Build workspace" })).toBeEnabled();

  for (const [linkName, tabName] of [["Ask", "Ask"], ["Sources", "Sources"], ["Workspace", "Evidence"]] as const) {
    await page.getByRole("link", { name: linkName, exact: true }).click();
    await expect(page.getByRole("tab", { name: tabName, exact: true })).toHaveAttribute("aria-selected", "true");
  }

  const recentWorkspace = page.locator(".recent-workspace-button").first();
  await expect(recentWorkspace).toBeVisible();
  await recentWorkspace.click();

  await expect(page.getByRole("table")).toBeVisible({ timeout: 20_000 });
  expect(await page.getByRole("row").count()).toBeGreaterThan(1);

  await page.evaluate(() => window.scrollTo({ top: 2_000, behavior: "instant" }));
  await expect.poll(async () => (await page.getByRole("tablist", { name: "Workspace views" }).boundingBox())?.y ?? -1).toBeGreaterThan(70);
  await expect.poll(async () => (await page.getByRole("tablist", { name: "Workspace views" }).boundingBox())?.y ?? 999).toBeLessThan(110);

  const viewExpectations = [
    ["Ask", "Ask the evidence."],
    ["Sources", "Source explorer"],
    ["Brief", "Evidence brief"],
    ["Reliability", "Reliability checks"],
    ["Evidence", "Evidence extraction table"],
  ] as const;

  for (const [tabName, heading] of viewExpectations) {
    const tab = page.getByRole("tab", { name: tabName, exact: true });
    await tab.click();
    await expect(tab).toHaveAttribute("aria-selected", "true");
    await expect(page.getByRole("tabpanel", { name: tabName })).toContainText(heading);
  }

  await page.getByRole("tab", { name: "Brief", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Evidence gaps" })).toBeVisible();
  await page.getByRole("tab", { name: "Reliability", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Scenario checks" })).toBeVisible();
  expect(await page.getByRole("progressbar").count()).toBeGreaterThan(0);
});

test("distills Ask results and keeps complete evidence behind disclosures", async ({ page }) => {
  await page.locator(".recent-workspace-button").first().click();
  await expect(page.getByRole("table")).toBeVisible({ timeout: 20_000 });
  await page.route("**/workspaces/*/ask", (route) => route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(answerFixture) }));

  await page.getByRole("tab", { name: "Ask", exact: true }).click();
  await page.getByRole("button", { name: "What are the main benefits?", exact: true }).click();
  await page.getByRole("button", { name: "Answer with citations", exact: true }).click();

  const answer = page.locator("#answer-result");
  await expect(answer).toBeVisible();
  await expect(answer.getByRole("heading", { name: "What are the main benefits?", exact: true })).toBeVisible();
  await expect(answer.getByRole("link", { name: /Open cited source/ })).toHaveCount(2);
  await expect(answer.getByRole("link", { name: /Open original source/ })).toHaveCount(2);
  await expect(answer.getByRole("heading", { name: "Evidence boundary" })).toBeVisible();
  await expect(page.getByLabel("Ask a follow-up")).toBeVisible();
  await expect(page.getByRole("button", { name: "Ask follow-up" })).toBeDisabled();
  await expect(answer.locator("details")).toHaveCount(4);
  await expect(answer.locator("details[open]")).toHaveCount(0);
  await expect.poll(() => answer.evaluate((element) => document.activeElement === element)).toBe(true);

  const supportingEvidence = answer.locator("details").filter({ hasText: "Supporting evidence" });
  await supportingEvidence.locator("summary").click();
  await expect(supportingEvidence).toHaveAttribute("open", "");
  await expect(supportingEvidence).toContainText("Finding three");
  await expect(supportingEvidence).toContainText("Important uncertainty remains");
});

test("keeps the mobile evidence workspace within the viewport", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.reload();

  await expect(page.getByRole("button", { name: "Build workspace" })).toBeVisible();
  await expect(page.getByRole("tablist", { name: "Workspace views" })).toBeVisible();

  const viewportMetrics = await page.evaluate(() => ({
    clientWidth: document.documentElement.clientWidth,
    scrollWidth: document.documentElement.scrollWidth,
  }));
  expect(viewportMetrics.scrollWidth).toBeLessThanOrEqual(viewportMetrics.clientWidth);

  const themeToggle = page.getByRole("button", { name: /Switch to (dark|light) mode/ });
  const toggleBox = await themeToggle.boundingBox();
  expect(toggleBox?.width).toBeGreaterThanOrEqual(44);
  expect(toggleBox?.height).toBeGreaterThanOrEqual(44);

  await page.locator(".recent-workspace-button").first().click();
  await expect(page.getByRole("table")).toBeVisible({ timeout: 20_000 });
  const tableRegion = page.getByRole("region", { name: "Scrollable evidence table" });
  const tableMetrics = await tableRegion.evaluate((element) => ({ clientWidth: element.clientWidth, scrollWidth: element.scrollWidth }));
  expect(tableMetrics.scrollWidth).toBeGreaterThan(tableMetrics.clientWidth);
  await tableRegion.evaluate((element) => element.scrollTo({ left: element.scrollWidth, behavior: "instant" }));
  expect(await tableRegion.evaluate((element) => element.scrollLeft)).toBeGreaterThan(0);

  await page.evaluate(() => window.scrollTo({ top: 2_000, behavior: "instant" }));
  await expect.poll(async () => (await page.getByRole("tablist", { name: "Workspace views" }).boundingBox())?.y ?? -1).toBeGreaterThanOrEqual(60);
  await expect.poll(async () => (await page.getByRole("tablist", { name: "Workspace views" }).boundingBox())?.y ?? 999).toBeLessThan(90);

  const sourcesTab = page.getByRole("tab", { name: "Sources", exact: true });
  await sourcesTab.click();
  await expect(sourcesTab).toHaveAttribute("aria-selected", "true");
  await expect(page.getByRole("tabpanel", { name: "Sources" })).toContainText("Source explorer");
});
