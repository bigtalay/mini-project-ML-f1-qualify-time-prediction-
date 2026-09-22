import { test, expect } from "@playwright/test";
import fs from "node:fs/promises";

test("open, compare, inspect real lap, persist filters and download matching CSV", async ({
  page,
}, info) => {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await page.goto("/?year=2023&event=2023-01&drivers=VER,HAM&session=FP2");
  await expect(page.getByTestId("workspace-ready")).toBeVisible();
  await expect(
    page.getByRole("button", { name: /ดู VER lap/ }).first(),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "Compare เทียบนักขับ", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "เสียเวลาตรงไหน?" }),
  ).toBeVisible();
  await page.getByLabel("ชนิดยาง", { exact: true }).selectOption("SOFT");
  await expect(page.getByLabel("lap เปรียบเทียบ VER")).toBeVisible();
  await page
    .getByRole("button", { name: /ดู VER lap/ })
    .first()
    .click();
  await expect(page.getByTestId("lap-inspection")).toContainText(
    "SOURCE / practice_laps.csv",
  );
  const selectedURL = page.url();
  await page.reload();
  await expect(page.getByTestId("lap-inspection")).toBeVisible();
  await expect(page.getByLabel("ชนิดยาง", { exact: true })).toHaveValue("SOFT");
  expect(page.url()).toBe(selectedURL);
  const downloadPromise = page.waitForEvent("download");
  await page
    .getByRole("link", { name: "↓ ดาวน์โหลดตามตัวกรอง", exact: true })
    .click();
  const download = await downloadPromise;
  const body = await fs.readFile((await download.path())!, "utf8");
  expect(body).toContain("lap_id");
  const parsed = body.trim().split(/\r?\n/);
  const response = await page.request.get(
    "/api/v1/events/2023-01/laps?drivers=VER,HAM&session=FP2&compound=SOFT",
  );
  expect(parsed.length - 1).toBe((await response.json()).total);
  await page.screenshot({
    path: info.outputPath("compare.png"),
    fullPage: true,
  });
  expect(errors).toEqual([]);
});

test("what-if uses the selected event, shows limitations and validates inputs", async ({
  page,
}, info) => {
  await page.goto("/?year=2023&event=2023-01&view=prediction&driver=VER");
  await expect(page.getByTestId("scenario-result")).toBeVisible();
  const input = page.getByLabel("What-if FP2_Time", { exact: true });
  const original = await input.inputValue();
  await input.fill(String(Number(original) + 1));
  await expect(page.getByTestId("scenario-result")).toBeVisible();
  await expect(
    page.getByText(/โมเดลที่เลือกมี RMSE สูงกว่า Practice baseline/),
  ).toBeVisible();
  await input.fill("-1");
  await expect(page.getByRole("alert")).toContainText(
    "เวลา Practice ต้องมากกว่า 0",
  );
  await page.getByRole("button", { name: "↺ คืนค่าจากข้อมูลจริง" }).click();
  await expect(input).toHaveValue(original);
  await expect(page.getByTestId("scenario-result")).toContainText("+0.000s");
  await page.screenshot({
    path: info.outputPath("prediction.png"),
    fullPage: true,
  });
  await page.getByLabel("Season", { exact: true }).selectOption("2021");
  await expect(page.getByText(/ปี 2021 ใช้ฝึกหรือเลือกโมเดล/)).toBeVisible();
  await expect(
    page.getByLabel("What-if FP2_Time", { exact: true }),
  ).toHaveCount(0);
});

test("sprint, rain, missing data and audit are explicit", async ({
  page,
}, info) => {
  await page.goto("/?year=2021&event=2021-10&session=FP2");
  await expect(
    page.getByRole("button", { name: /FP2.*หลัง Qualifying/ }),
  ).toBeVisible();
  await page
    .getByRole("button", {
      name: "Data & Method ข้อมูลและวิธีการ",
      exact: true,
    })
    .click();
  await expect(
    page.getByText("79,661 practice laps", { exact: true }),
  ).toBeVisible();
  await page.getByLabel("ขอบเขตรายงานข้อมูล").selectOption("event");
  await expect(
    page.getByText("79,661 practice laps", { exact: true }),
  ).toHaveCount(0);
  await page.screenshot({
    path: info.outputPath("method.png"),
    fullPage: true,
  });
  await page.goto("/?year=2023&event=2023-04&session=FP3");
  await expect(
    page.getByText(/ไม่มี lap ที่ผ่านการตรวจในตัวกรองนี้/),
  ).toBeVisible();
  await page.goto("/?year=2021&event=2021-12");
  await expect(page.locator(".weather-note strong")).toHaveText("พบฝน");
});

test("read API failure can be retried and layout does not overflow", async ({
  page,
}, info) => {
  await page.route("**/api/v1/events", (route) =>
    route.fulfill({
      status: 503,
      contentType: "application/json",
      body: JSON.stringify({ detail: "ทดสอบการโหลดไม่สำเร็จ" }),
    }),
  );
  await page.goto("/");
  await expect(page.getByRole("alert")).toContainText("ทดสอบการโหลดไม่สำเร็จ");
  await page.unroute("**/api/v1/events");
  await page.getByRole("button", { name: "ลองใหม่" }).click();
  await expect(page.getByTestId("workspace-ready")).toBeVisible();
  await expect(
    page.getByRole("button", { name: /ดู VER lap/ }).first(),
  ).toBeVisible();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth + 1,
    ),
  ).toBe(true);
  await page.screenshot({
    path: info.outputPath("weekend.png"),
    fullPage: true,
  });
});

test("local startup readiness and warm API timing", async ({ page }, info) => {
  const start = performance.now();
  await page.goto("/?year=2023&event=2023-01");
  await expect(
    page.getByRole("button", { name: /ดู VER lap/ }).first(),
  ).toBeVisible();
  await expect(page.locator("canvas").first()).toBeVisible();
  const readyMs = performance.now() - start;
  const apiMs: number[] = [];
  for (let i = 0; i < 10; i++) {
    const start = performance.now();
    const r = await page.request.get(
      "/api/v1/events/2023-01/laps?drivers=VER,HAM&session=FP2",
    );
    expect(r.ok()).toBe(true);
    await r.json();
    apiMs.push(performance.now() - start);
  }
  const report = {
    project: info.project.name,
    readyMs,
    apiMs,
    maxApiMs: Math.max(...apiMs),
    userAgent: await page.evaluate(() => navigator.userAgent),
    measurement:
      "wall-clock local browser readiness and full HTTP response; warm server; no throttling",
  };
  await fs.writeFile(
    info.outputPath("performance.json"),
    JSON.stringify(report, null, 2),
  );
  await info.attach("performance", {
    body: JSON.stringify(report),
    contentType: "application/json",
  });
  expect(Math.max(...apiMs)).toBeLessThan(500);
  expect(readyMs).toBeLessThan(3000);
});

test("keyboard can select a driver without a pointing device", async ({
  page,
}) => {
  await page.goto("/?year=2023&event=2023-01");
  const button = page.getByRole("button", { name: "เลือก LEC", exact: true });
  await expect(button).toBeVisible();
  await button.focus();
  await page.keyboard.press("Enter");
  await expect(button).toHaveAttribute("aria-pressed", "true");
  await expect(page).toHaveURL(/drivers=.*LEC/);
});
