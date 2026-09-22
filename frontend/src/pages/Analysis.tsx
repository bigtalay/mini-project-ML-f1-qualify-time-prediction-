import React, { useState, useEffect, useMemo } from "react";
import Chart from "../Chart";
import { useApi, time, number, teamColor, reasonText } from "../lib";
import type { Overview, Lap, Schema } from "../lib";
import { API, Status, Empty, Download, fmtInt } from "../ui";
import type { QueryState } from "../ui";
const axis = {
  axisLine: { lineStyle: { color: "#454b52" } },
  axisLabel: { color: "#939da8", fontFamily: "IBM Plex Mono" },
  splitLine: { lineStyle: { color: "#2c3036" } },
};
const tip = {
  backgroundColor: "#20252c",
  borderColor: "#525b67",
  textStyle: { color: "#e8ebee" },
  renderMode: "richText" as const,
};
export default function Analysis({
  overview,
  state,
  compare,
}: {
  overview: Overview;
  state: QueryState;
  compare: boolean;
}) {
  const { query, update } = state;
  const results = overview.results;
  const known = new Set(results.map((r) => r.Driver));
  const chosen = (
    query.get("drivers") ||
    results
      .slice(0, 2)
      .map((r) => r.Driver)
      .join(",")
  )
    .split(",")
    .filter((d) => known.has(d))
    .slice(0, 4);
  const drivers = chosen.length
    ? chosen
    : results.slice(0, 2).map((r) => r.Driver);
  const practice = overview.sessions.filter((s) => s.session !== "Q");
  const session =
    query.get("session") ||
    practice.find((s) => s.session === "FP2")?.session ||
    practice[0]?.session ||
    "FP1";
  const compound = query.get("compound") || "";
  const search = query.get("search") || "";
  const sort = query.get("sort") || "Time";
  const descending = query.get("desc") === "true";
  const metric = [
    "LapTime",
    "Sector1Time",
    "Sector2Time",
    "Sector3Time",
    "SpeedST",
  ].includes(query.get("metric") || "")
    ? query.get("metric")!
    : "LapTime";
  const [selectionNotice, setSelectionNotice] = useState("");
  const [page, setPage] = useState(0);
  const rankSort = query.get("rank") || "Position";
  const rankSearch = query.get("rankingSearch") || "";
  const phase = (
    ["Q1", "Q2", "Q3"].includes(query.get("phase") || "")
      ? query.get("phase")
      : "Q3"
  ) as "Q1" | "Q2" | "Q3";
  const params = new URLSearchParams({
    drivers: drivers.join(","),
    session,
    sort,
    descending: String(descending),
    search,
    limit: "4000",
  });
  if (compound) params.set("compound", compound);
  const base = `${API}/events/${overview.event.event_id}`;
  const data = useApi<Schema["LapPage"]>(`${base}/laps?${params}`);
  const filtered = data.data?.items || [];
  const comparison = useApi<Schema["Comparison"][]>(
    compare && drivers.length >= 2 ? `${base}/compare?${params}` : null,
  );
  const selectedLap =
    filtered.find((l) => l.lap_id === query.get("lap")) || null;
  useEffect(
    () => setPage(0),
    [session, compound, search, drivers.join(","), sort, descending],
  );
  const toggle = (driver: string) => {
    const exists = drivers.includes(driver);
    if (!exists && drivers.length === 4) {
      setSelectionNotice("เลือกได้สูงสุด 4 คน — ยกเลิกคนเดิมก่อนเพิ่ม");
      return;
    }
    if (exists && drivers.length === 1) {
      setSelectionNotice("คงนักขับอย่างน้อย 1 คนสำหรับกราฟ");
      return;
    }
    setSelectionNotice("");
    update({
      drivers: exists
        ? drivers.filter((d) => d !== driver).join(",")
        : [...drivers, driver].join(","),
      lap: null,
    });
  };
  const chart = useMemo(
    () => ({
      tooltip: { ...tip, trigger: "item" },
      grid: { left: 64, right: 22, top: 26, bottom: 68 },
      xAxis: { type: "value", name: "LAP", minInterval: 1, ...axis },
      yAxis: {
        type: "value",
        scale: true,
        name: metric === "SpeedST" ? "km/h" : "SECONDS",
        ...axis,
      },
      dataZoom: [
        { type: "inside", filterMode: "none" },
        {
          type: "slider",
          bottom: 8,
          height: 18,
          borderColor: "#333942",
          fillerColor: "#777f9128",
          textStyle: { color: "#939da8" },
        },
      ],
      series: drivers.map((driver, index) => ({
        name: driver,
        type: "line",
        showSymbol: true,
        symbol: ["circle", "diamond", "triangle", "rect"][index],
        symbolSize: 7,
        connectNulls: false,
        lineStyle: { width: 1.5, type: index % 2 ? "dashed" : "solid" },
        itemStyle: {
          color: teamColor(results.find((r) => r.Driver === driver)?.Team),
        },
        data: filtered
          .filter((l) => l.Driver === driver)
          .sort((a, b) => (a.LapNumber || 0) - (b.LapNumber || 0))
          .map((l) => ({
            value: [l.LapNumber, l[metric as keyof Lap]],
            name: `${driver} / Lap ${l.LapNumber} / ${l.Compound || "ไม่ระบุยาง"}`,
            lap_id: l.lap_id,
          })),
      })),
    }),
    [data.data, drivers.join(","), metric],
  );
  const ranked = [...results]
    .filter((r) =>
      `${r.Driver} ${r.Team}`.toLowerCase().includes(rankSearch.toLowerCase()),
    )
    .sort((a, b) => {
      if (rankSort === "Driver") return a.Driver.localeCompare(b.Driver);
      return (
        ((a[rankSort as keyof typeof a] as number) ?? Infinity) -
        ((b[rankSort as keyof typeof b] as number) ?? Infinity)
      );
    });
  const weather = overview.weather.filter((w) => w.Rainfall != null);
  const rain = weather.some((w) => Number(w.Rainfall) > 0);
  return (
    <>
      <div className="session-strip">
        <div className="session-list">
          {practice.map((s) => (
            <button
              className={session === s.session ? "selected" : ""}
              onClick={() =>
                update({ session: s.session, lap: null, choices: null })
              }
              key={s.session}
            >
              <b>{s.session}</b>
              <span>
                {s.lap_count ? `${fmtInt(s.lap_count)} laps` : "ไม่มี lap"}
              </span>
              {!s.before_qualifying && <small>หลัง Qualifying</small>}
            </button>
          ))}
        </div>
        <div className="weather-note">
          QUALIFYING WEATHER{" "}
          <strong>
            {weather.length ? (rain ? "พบฝน" : "ไม่พบฝน") : "ไม่มีข้อมูล"}
          </strong>
          <span>ใช้วิเคราะห์ย้อนหลังเท่านั้น</span>
        </div>
      </div>
      <div className="analysis-grid">
        <aside className="classification panel">
          <div className="panel-title">
            <span className="section-number">01</span>
            <h2>Qualifying order</h2>
            <Download
              href={`${base}/export?kind=results&result_sort=${rankSort}&search=${encodeURIComponent(rankSearch)}`}
            />
          </div>
          <p className="panel-caption">เลือกนักขับจากตาราง · สูงสุด 4 คน</p>
          <div className="rank-controls">
            <label>
              ค้นหา
              <input
                aria-label="ค้นหา Qualifying"
                value={rankSearch}
                placeholder="Driver / team"
                onChange={(e) =>
                  update({ rankingSearch: e.target.value }, true)
                }
              />
            </label>
            <label>
              เรียงตาม
              <select
                aria-label="เรียงผล Qualifying"
                value={rankSort}
                onChange={(e) => update({ rank: e.target.value })}
              >
                {["Position", "Driver", "Q1", "Q2", "Q3"].map((v) => (
                  <option key={v}>{v}</option>
                ))}
              </select>
            </label>
            <div className="phase-switch" aria-label="รอบ Qualifying">
              {(["Q1", "Q2", "Q3"] as const).map((p) => (
                <button
                  key={p}
                  aria-pressed={phase === p}
                  className={phase === p ? "selected" : ""}
                  onClick={() => update({ phase: p })}
                >
                  {p}
                </button>
              ))}
            </div>
          </div>
          <div className="rank-header">
            <span>POS</span>
            <span>DRIVER / TEAM</span>
            <span>{phase}</span>
          </div>
          <div className="rank-list">
            {ranked.map((row) => (
              <button
                className={`driver-row ${drivers.includes(row.Driver) ? "chosen" : ""}`}
                key={row.Driver}
                aria-pressed={drivers.includes(row.Driver)}
                aria-label={`เลือก ${row.Driver}`}
                onClick={() => toggle(row.Driver)}
                style={{ "--team": teamColor(row.Team) } as React.CSSProperties}
              >
                <span className="position">{row.Position ?? "—"}</span>
                <span className="driver-name">
                  <b>{row.Driver}</b>
                  <small>{row.Team}</small>
                </span>
                <span
                  className={`rank-time ${row[phase] != null && row[phase] === Math.min(...ranked.map((r) => r[phase] ?? Infinity)) ? "best" : ""}`}
                >
                  {time(row[phase])}
                </span>
                <span className="selection-mark">
                  {drivers.includes(row.Driver) ? "−" : "+"}
                </span>
              </button>
            ))}
          </div>
          {!ranked.length && <Empty>ไม่พบนักขับตามคำค้น</Empty>}
          <p className="footnote">
            อันดับจาก Position ต้นทาง · สีม่วงคือเวลาเร็วที่สุดในกลุ่มที่แสดง
          </p>
          <p className="selection-notice" role="status">
            {selectionNotice}
          </p>
        </aside>
        <section className="trace panel">
          <div className="panel-title">
            <span className="section-number">02</span>
            <h2>{compare ? "Driver comparison" : "Practice trace"}</h2>
            <span className="live-label">{session}</span>
          </div>
          <div className="trace-controls">
            <label>
              ค่าที่แสดง
              <select
                aria-label="ค่าบนกราฟ"
                value={metric}
                onChange={(e) => update({ metric: e.target.value })}
              >
                <option value="LapTime">Lap time</option>
                <option value="Sector1Time">Sector 1</option>
                <option value="Sector2Time">Sector 2</option>
                <option value="Sector3Time">Sector 3</option>
                <option value="SpeedST">Speed trap</option>
              </select>
            </label>
            <label>
              ยาง
              <select
                aria-label="ชนิดยาง"
                value={compound}
                onChange={(e) =>
                  update({ compound: e.target.value, lap: null, choices: null })
                }
              >
                <option value="">ทุกชนิด</option>
                {[
                  "SOFT",
                  "MEDIUM",
                  "HARD",
                  "INTERMEDIATE",
                  "WET",
                  "UNKNOWN",
                ].map((c) => (
                  <option key={c}>{c}</option>
                ))}
              </select>
            </label>
          </div>
          <div className="driver-legend">
            {drivers.map((d, i) => (
              <span key={d}>
                <i
                  style={{
                    color: teamColor(results.find((r) => r.Driver === d)?.Team),
                  }}
                >
                  {["●", "◆", "▲", "■"][i]}
                </i>
                {d}
              </span>
            ))}
            <span className="muted">
              {fmtInt(data.data?.total || 0)} usable laps
            </span>
          </div>
          <Status {...data} />
          {!data.loading &&
            !data.error &&
            (filtered.length ? (
              <Chart
                option={chart}
                onPoint={(id) => update({ lap: id })}
                label={`${session}: ${metric} ราย lap ของ ${drivers.join(", ")}`}
              />
            ) : (
              <Empty>
                ไม่มี lap ที่ผ่านการตรวจในตัวกรองนี้ ลองเปลี่ยน session
                หรือชนิดยาง
              </Empty>
            ))}
          <p className="chart-hint">
            ลากช่วงด้านล่างเพื่อซูม · กดจุดเพื่อดู lap ·
            ใช้ตารางด้านล่างแทนกราฟได้
          </p>
          {compare &&
            (drivers.length < 2 ? (
              <Empty>เลือกนักขับเพิ่มอีก 1 คนเพื่อเปรียบเทียบ</Empty>
            ) : (
              <>
                <Status {...comparison} />
                {comparison.data && (
                  <Comparison
                    rows={comparison.data}
                    laps={filtered}
                    state={state}
                  />
                )}
              </>
            ))}
        </section>
        <aside className="lap-detail panel">
          <div className="panel-title">
            <span className="section-number">03</span>
            <h2>Lap inspection</h2>
          </div>
          {selectedLap ? (
            <LapDetail
              lap={selectedLap}
              result={results.find((r) => r.Driver === selectedLap.Driver)}
            />
          ) : (
            <div className="inspect-empty">
              <span>↖</span>
              <h3>เริ่มจากหนึ่ง lap</h3>
              <p>
                กดจุดบนกราฟ หรือเลือกแถวในตาราง เพื่อดูเวลา sector
                และข้อมูลต้นทาง
              </p>
              <div className="rule" />
              <small>ไม่มีการเติมค่าในรายละเอียด lap</small>
            </div>
          )}
        </aside>
      </div>
      <section className="panel lap-table">
        <div className="panel-title">
          <h2>Lap log</h2>
          <span className="muted">{data.data?.total ?? 0} rows</span>
          <Download href={`${base}/export?${params}`}>
            ↓ ดาวน์โหลดตามตัวกรอง
          </Download>
        </div>
        <div className="table-tools">
          <label>
            ค้นหานักขับ / ทีม
            <input
              aria-label="ค้นหา lap"
              value={search}
              onChange={(e) => update({ search: e.target.value }, true)}
              placeholder="เช่น VER หรือ Ferrari"
            />
          </label>
          <label>
            เรียงตาม
            <select
              aria-label="เรียง lap"
              value={sort}
              onChange={(e) => update({ sort: e.target.value })}
            >
              {[
                "Time",
                "LapTime",
                "LapNumber",
                "Driver",
                "Sector1Time",
                "Sector2Time",
                "Sector3Time",
                "SpeedST",
                "TyreLife",
              ].map((c) => (
                <option key={c}>{c}</option>
              ))}
            </select>
          </label>
          <button
            onClick={() => update({ desc: descending ? "false" : "true" })}
            aria-label="สลับทิศทางเรียง"
          >
            {descending ? "↓ มากไปน้อย" : "↑ น้อยไปมาก"}
          </button>
        </div>
        <div className="table-scroll">
          <table>
            <thead>
              <tr>
                <th>Driver</th>
                <th>Lap</th>
                <th>Lap time</th>
                <th>S1</th>
                <th>S2</th>
                <th>S3</th>
                <th>Tyre</th>
                <th>Age</th>
                <th>Speed trap</th>
                <th>Source row</th>
              </tr>
            </thead>
            <tbody>
              {filtered.slice(page * 20, page * 20 + 20).map((l) => (
                <tr
                  key={l.lap_id}
                  className={
                    selectedLap?.lap_id === l.lap_id ? "selected-row" : ""
                  }
                >
                  <td>
                    <button
                      className="text-button"
                      onClick={() => update({ lap: l.lap_id })}
                      aria-label={`ดู ${l.Driver} lap ${l.LapNumber}`}
                    >
                      {l.Driver} ↗
                    </button>
                  </td>
                  <td>{l.LapNumber}</td>
                  <td>{time(l.LapTime)}</td>
                  <td>{number(l.Sector1Time)}</td>
                  <td>{number(l.Sector2Time)}</td>
                  <td>{number(l.Sector3Time)}</td>
                  <td>
                    <span className={`tyre ${l.Compound?.toLowerCase()}`}>
                      {l.Compound || "—"}
                    </span>
                  </td>
                  <td>{l.TyreLife ?? "—"}</td>
                  <td>{number(l.SpeedST, 1)}</td>
                  <td>{l.source_row}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {!filtered.length && !data.loading && (
          <Empty>ไม่พบข้อมูลตามตัวกรอง</Empty>
        )}
        <div className="pagination">
          <span>
            หน้า {page + 1} / {Math.max(1, Math.ceil(filtered.length / 20))}
          </span>
          <button disabled={page === 0} onClick={() => setPage((p) => p - 1)}>
            ← ก่อนหน้า
          </button>
          <button
            disabled={(page + 1) * 20 >= filtered.length}
            onClick={() => setPage((p) => p + 1)}
          >
            ถัดไป →
          </button>
        </div>
      </section>
    </>
  );
}

function LapDetail({
  lap,
  result,
}: {
  lap: Lap;
  result?: Overview["results"][number];
}) {
  return (
    <div className="inspection" data-testid="lap-inspection">
      <div className="inspect-driver" style={{ color: teamColor(lap.Team) }}>
        {lap.Driver}
        <span>
          {lap.Session} / LAP {lap.LapNumber}
        </span>
      </div>
      <div className="big-time">{time(lap.LapTime)}</div>
      <p className="muted">{lap.Team}</p>
      <dl>
        {["Sector1Time", "Sector2Time", "Sector3Time"].map((c, i) => (
          <React.Fragment key={c}>
            <dt>Sector {i + 1}</dt>
            <dd>
              {number(lap[c as keyof Lap] as number)}
              <small>s</small>
            </dd>
          </React.Fragment>
        ))}
        <dt>Speed trap</dt>
        <dd>
          {number(lap.SpeedST, 1)}
          <small>km/h</small>
        </dd>
        <dt>Compound</dt>
        <dd>{lap.Compound || "—"}</dd>
        <dt>Tyre age</dt>
        <dd>
          {lap.TyreLife ?? "—"}
          <small>laps</small>
        </dd>
        <dt>Stint</dt>
        <dd>{lap.Stint ?? "—"}</dd>
      </dl>
      <p className="audit-tag">
        {reasonText[lap.reason]} · {lap.pre_qualifying ? "ก่อน" : "หลัง"}{" "}
        Qualifying
      </p>
      <div className="source-note">
        SOURCE / practice_laps.csv
        <br />
        แถว {lap.source_row} · {lap.lap_id}
      </div>
      {result && (
        <>
          <h3>Qualifying reference</h3>
          <dl>
            {(["Q1", "Q2", "Q3"] as const).map((q) => (
              <React.Fragment key={q}>
                <dt>{q}</dt>
                <dd>{time(result[q])}</dd>
              </React.Fragment>
            ))}
          </dl>
        </>
      )}
    </div>
  );
}

function Comparison({
  rows,
  laps,
  state,
}: {
  rows: Schema["Comparison"][];
  laps: Lap[];
  state: QueryState;
}) {
  const selected = Object.fromEntries(
    (state.query.get("choices") || "")
      .split(",")
      .filter(Boolean)
      .map((s) => s.split(":")),
  );
  const chosen = rows.map((r) => ({
    row: r,
    lap:
      laps.find(
        (l) => l.Driver === r.driver && l.lap_id === selected[r.driver],
      ) || r.best_lap,
  }));
  const option = useMemo(
    () => ({
      tooltip: { ...tip, trigger: "axis" },
      legend: { textStyle: { color: "#a7adb5" }, bottom: 0 },
      grid: { left: 48, right: 20, top: 20, bottom: 70 },
      xAxis: {
        type: "category",
        data: chosen.map((c) => c.row.driver),
        ...axis,
      },
      yAxis: { type: "value", name: "SECONDS", ...axis },
      series: [1, 2, 3].map((n, i) => ({
        type: "bar",
        name: `Sector ${n}`,
        stack: "lap",
        barMaxWidth: 45,
        itemStyle: { color: ["#b292e5", "#737f96", "#485568"][i] },
        data: chosen.map((c) => ({
          value: c.lap?.[`Sector${n}Time` as keyof Lap] ?? null,
          lap_id: c.lap?.lap_id,
        })),
      })),
    }),
    [JSON.stringify(chosen)],
  );
  return (
    <div className="comparison">
      <h3>เสียเวลาตรงไหน?</h3>
      <p className="muted">
        เทียบ sector จาก lap จริงที่เลือก · ค่าเริ่มต้นคือ lap
        เร็วที่สุดตามตัวกรอง
      </p>
      <div className="lap-selectors">
        {chosen.map(({ row, lap }) => (
          <label key={row.driver}>
            {row.driver}
            <select
              aria-label={`lap เปรียบเทียบ ${row.driver}`}
              value={lap?.lap_id || ""}
              onChange={(e) =>
                state.update({
                  choices: Object.entries({
                    ...selected,
                    [row.driver]: e.target.value,
                  })
                    .map(([k, v]) => `${k}:${v}`)
                    .join(","),
                  lap: e.target.value,
                })
              }
            >
              <option value="" disabled>
                ไม่มี lap
              </option>
              {laps
                .filter((l) => l.Driver === row.driver)
                .map((l) => (
                  <option key={l.lap_id} value={l.lap_id}>
                    Lap {l.LapNumber} · {time(l.LapTime)}
                  </option>
                ))}
            </select>
          </label>
        ))}
      </div>
      <Chart
        option={option}
        height={245}
        label="Sector ของ lap ที่เลือกจริงแต่ละนักขับ"
        onPoint={(id) => state.update({ lap: id })}
      />
      <div className="table-scroll">
        <table>
          <thead>
            <tr>
              <th>Driver / lap</th>
              <th>S1</th>
              <th>S2</th>
              <th>S3</th>
              <th>Speed trap</th>
            </tr>
          </thead>
          <tbody>
            {chosen.map(({ row, lap }) => (
              <tr key={row.driver}>
                <td>
                  {row.driver} / {lap?.LapNumber ?? "—"}
                </td>
                {[1, 2, 3].map((i) => (
                  <td key={i}>
                    {number(lap?.[`Sector${i}Time` as keyof Lap] as number)}
                  </td>
                ))}
                <td>{number(lap?.SpeedST, 1)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <h3>ความสม่ำเสมอภายใต้ตัวกรองเดียวกัน</h3>
      <div className="table-scroll">
        <table>
          <thead>
            <tr>
              <th>Driver</th>
              <th>Laps</th>
              <th>Median</th>
              <th>IQR</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.driver}>
                <td>{r.driver}</td>
                <td>{r.count}</td>
                <td>{time(r.median)}</td>
                <td>
                  {r.enough_laps
                    ? `${number(r.iqr)}s`
                    : "ข้อมูลไม่พอ (<5 laps)"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="footnote">
        Practice ต่างกันได้จากเชื้อเพลิง โปรแกรมวิ่ง และสภาพสนาม
        กราฟนี้ไม่ได้แยกผลของปัจจัยเหล่านั้น
      </p>
    </div>
  );
}
