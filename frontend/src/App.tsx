import { useEffect } from "react";
import { useApi, useQuery } from "./lib";
import type { Event, Overview } from "./lib";
import { API, Status } from "./ui";
import type { QueryState } from "./ui";
import Analysis from "./pages/Analysis";
import Prediction from "./pages/Prediction";
import Method from "./pages/Method";
const tabs = [
  ["weekend", "Weekend", "ภาพรวม"],
  ["compare", "Compare", "เทียบนักขับ"],
  ["prediction", "Prediction", "ผลทำนาย"],
  ["method", "Data & Method", "ข้อมูลและวิธีการ"],
];
export default function App() {
  const state = useQuery();
  const events = useApi<Event[]>(`${API}/events`);
  const year = Number(state.query.get("year") || "2023");
  const choices = events.data?.filter((e) => e.year === year) || [];
  const event =
    choices.find((e) => e.event_id === state.query.get("event")) || choices[0];
  const view = tabs.some((t) => t[0] === state.query.get("view"))
    ? state.query.get("view")!
    : "weekend";
  useEffect(() => {
    if (!events.data?.length) return;
    if (!event) {
      state.update({ year: "2023", event: "2023-01" }, true);
      return;
    }
    if (
      state.query.get("year") !== String(event.year) ||
      state.query.get("event") !== event.event_id
    )
      state.update({ year: String(event.year), event: event.event_id }, true);
  }, [events.data, event?.event_id, year]);
  const changeEvent = (id: string, y: number) =>
    state.update({
      event: id,
      year: String(y),
      drivers: null,
      driver: null,
      session: null,
      lap: null,
      choices: null,
      search: null,
      compound: null,
    });
  return (
    <>
      <a className="skip" href="#main">
        ข้ามไปเนื้อหา
      </a>
      <header className="masthead">
        <a className="identity" href="?year=2023&event=2023-01">
          <span className="monogram">
            WI<span>/</span>
          </span>
          <span>
            WEEKEND
            <br />
            <b>INTELLIGENCE</b>
          </span>
        </a>
        <div className="edition">
          <span className="dot" /> HISTORICAL DATA{" "}
          <span className="muted">2021 — 2023</span>
        </div>
        <span className="header-note">Formula 1 / Independent analysis</span>
      </header>
      <div className="workspace-bar">
        <div className="event-controls">
          <label>
            SEASON
            <select
              aria-label="Season"
              value={year}
              onChange={(e) => {
                const y = Number(e.target.value);
                const first = events.data?.find((x) => x.year === y);
                if (first) changeEvent(first.event_id, y);
              }}
            >
              {[2023, 2022, 2021].map((y) => (
                <option key={y}>{y}</option>
              ))}
            </select>
          </label>
          <label>
            GRAND PRIX
            <select
              aria-label="Grand Prix"
              value={event?.event_id || ""}
              onChange={(e) => changeEvent(e.target.value, year)}
            >
              {choices.map((e) => (
                <option value={e.event_id} key={e.event_id}>
                  {String(e.round).padStart(2, "0")} / {e.name}
                </option>
              ))}
            </select>
          </label>
        </div>
        <nav aria-label="หน้าวิเคราะห์">
          {tabs.map(([key, en, th]) => (
            <button
              key={key}
              aria-current={view === key ? "page" : undefined}
              className={view === key ? "active" : ""}
              onClick={() => state.update({ view: key })}
            >
              <span>{en}</span>
              <small>{th}</small>
            </button>
          ))}
        </nav>
      </div>
      <main id="main">
        <Status {...events} />
        {event && (
          <Workspace
            key={event.event_id}
            event={event}
            view={view}
            state={state}
          />
        )}
      </main>
      <footer>
        <span>WI / ข้อมูล FastF1 · เวลาในหน่วยวินาที</span>
        <span>
          ข้อมูลย้อนหลัง • ไม่มี live timing • ไม่เกี่ยวข้องกับ Formula 1
          companies
        </span>
      </footer>
    </>
  );
}

function Workspace({
  event,
  view,
  state,
}: {
  event: Event;
  view: string;
  state: QueryState;
}) {
  const overview = useApi<Overview>(`${API}/events/${event.event_id}`);
  if (!overview.data) return <Status {...overview} />;
  return (
    <div data-testid="workspace-ready">
      <div className="event-heading">
        <div className="round">
          R<span>{String(event.round).padStart(2, "0")}</span>
        </div>
        <div>
          <p className="eyebrow">
            {event.country.toUpperCase()} <span>/</span> {event.year}{" "}
            <span>/</span>{" "}
            {event.format === "conventional"
              ? "STANDARD WEEKEND"
              : "SPRINT WEEKEND"}
          </p>
          <h1>
            {event.name.replace(" Grand Prix", "")}
            <span> Grand Prix</span>
          </h1>
          <p className="venue">
            {event.circuit} · {event.location}
          </p>
        </div>
        <div className="event-stamp">
          {overview.data.results.length}
          <span>DRIVERS</span>
          <small>ข้อมูลครบตามไฟล์ต้นทาง</small>
        </div>
      </div>
      {view === "method" ? (
        <Method event={event} state={state} />
      ) : view === "prediction" ? (
        <Prediction event={event} state={state} />
      ) : (
        <Analysis
          overview={overview.data}
          state={state}
          compare={view === "compare"}
        />
      )}
    </div>
  );
}
