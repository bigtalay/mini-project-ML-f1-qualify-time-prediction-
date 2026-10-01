import { useState, useEffect, useRef, useCallback } from "react";
import { useApi, time, delta } from "../lib";
import type { Event, PredictionRow, Schema } from "../lib";
import { API, Status, Empty, Download, ScoreTable } from "../ui";
import type { QueryState } from "../ui";
export default function Prediction({
  event,
  state,
}: {
  event: Event;
  state: QueryState;
}) {
  const evaluation = useApi<Schema["Evaluation"]>(`${API}/evaluation`);
  const predictions = useApi<PredictionRow[]>(
    event.year === 2023 ? `${API}/events/${event.event_id}/predictions` : null,
  );
  const driver =
    state.query.get("driver") ||
    predictions.data?.find((r) => r.predictable)?.Driver ||
    "";
  const selected = predictions.data?.find((r) => r.Driver === driver);
  const mode = state.query.get("mode");
  const manual =
    event.year !== 2023 ||
    mode === "manual" ||
    (mode !== "history" && !state.query.has("driver"));
  return (
    <div className="prediction-layout">
      <section
        className="panel prediction-primary"
        aria-labelledby="prediction-form-title"
      >
        <div className="panel-title">
          <span className="section-number">01</span>
          <h2 id="prediction-form-title">กรอกเวลาซ้อมเพื่อทำนาย</h2>
          <span className="prediction-feature-label">
            PRACTICE → QUALIFYING
          </span>
        </div>
        <div className="mode-switch" aria-label="โหมดทำนาย">
          <button
            aria-pressed={manual}
            onClick={() => state.update({ mode: "manual" })}
          >
            กรอกเอง
          </button>
          <button
            aria-pressed={!manual}
            disabled={event.year !== 2023}
            onClick={() => state.update({ mode: "history" })}
          >
            ใช้ข้อมูลย้อนหลัง
          </button>
          {!manual && predictions.data && (
            <label className="prediction-driver-select">
              นักขับสำหรับเติมค่าซ้อม
              <select
                aria-label="นักขับสำหรับข้อมูลย้อนหลัง"
                value={driver}
                onChange={(e) =>
                  state.update({ driver: e.target.value, mode: "history" })
                }
              >
                {predictions.data.map((row) => (
                  <option key={row.Driver} value={row.Driver}>
                    {row.Driver}
                  </option>
                ))}
              </select>
            </label>
          )}
        </div>
        {manual || selected ? (
          <Scenario
            key={`${event.event_id}-${manual ? "manual" : driver}`}
            event={event}
            row={manual ? undefined : selected}
          />
        ) : (
          <>
            <Status {...predictions} />
            <Empty>เลือกนักขับปี 2023 หรือเลือกโหมดกรอกเอง</Empty>
          </>
        )}
      </section>
      <section className="panel">
        <div className="panel-title">
          <span className="section-number">02</span>
          <h2>ผลย้อนหลังและการประเมินโมเดล</h2>
          {event.year === 2023 && (
            <Download
              href={`${API}/events/${event.event_id}/export?kind=predictions`}
            />
          )}
        </div>
        <p className="panel-caption">
          เป้าหมาย: เวลาต่ำสุดใน Q1/Q2/Q3 · ผลต่าง = ทำนาย − เวลาจริง
        </p>
        {event.year !== 2023 ? (
          <Empty>
            ปี {event.year} ใช้ฝึกหรือเลือกโมเดล ไม่แสดงเป็นผลทดสอบ
            <br />
            เลือกปี 2023 เพื่อดูผลย้อนหลังและทดลอง What-if
          </Empty>
        ) : (
          <>
            <Status {...predictions} />
            {predictions.data && (
              <div className="table-scroll">
                <table>
                  <thead>
                    <tr>
                      <th>Driver</th>
                      <th>Actual</th>
                      <th>Predicted</th>
                      <th>Error</th>
                      <th>ช่วงอ้างอิง</th>
                    </tr>
                  </thead>
                  <tbody>
                    {predictions.data.map((row) => (
                      <tr
                        key={row.Driver}
                        className={driver === row.Driver ? "selected-row" : ""}
                      >
                        <td>
                          <button
                            className="text-button"
                            onClick={() =>
                              state.update({
                                driver: row.Driver,
                                mode: "history",
                              })
                            }
                          >
                            {row.Driver} ↗
                          </button>
                        </td>
                        <td>{time(row.QualiTime)}</td>
                        <td>{time(row.prediction)}</td>
                        <td
                          className={Math.abs(row.error || 0) > 3 ? "warm" : ""}
                        >
                          {delta(row.error)}
                        </td>
                        <td>
                          {row.prediction == null
                            ? row.predictable
                              ? "ไม่มี target สำหรับประเมิน"
                              : "ไม่มี Practice ที่ใช้ได้"
                            : row.lower == null
                              ? "ยังไม่ได้คำนวณช่วง"
                              : `${time(row.lower)} – ${time(row.upper)}`}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </>
        )}
        <Status {...evaluation} />
        {evaluation.data && (
          <Evaluation report={evaluation.data} eventId={event.event_id} />
        )}
      </section>
    </div>
  );
}

const sessions = ["FP1", "FP2", "FP3"] as const;
type SessionName = (typeof sessions)[number];
type FormSession = {
  enabled: boolean;
  time: string;
};

function initialForm(row?: PredictionRow): Record<SessionName, FormSession> {
  return Object.fromEntries(
    sessions.map((s) => [
      s,
      {
        enabled: row ? row[`${s}_Time`] != null : s === "FP1",
        time: row?.[`${s}_Time`] == null ? "" : String(row[`${s}_Time`]),
      },
    ]),
  ) as Record<SessionName, FormSession>;
}
function Scenario({ event, row }: { event: Event; row?: PredictionRow }) {
  const [values, setValues] = useState(() => initialForm(row));
  const [response, setResponse] = useState<
    Schema["CustomResponse"] & { delta?: number }
  >();
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const serialized = JSON.stringify(values);
  const eventId = event.event_id;
  const historical = !!row;
  const driver = row?.Driver;
  const request = useRef<AbortController | null>(null);
  const runPrediction = useCallback(
    async (fields: Record<SessionName, FormSession>) => {
      request.current?.abort();
      const controller = new AbortController();
      request.current = controller;
      setResponse(undefined);
      setError("");
      setLoading(true);
      try {
        const enabled = sessions.filter((s) => fields[s].enabled);
        if (!enabled.length)
          throw new Error("ไม่มี Practice ที่ใช้ได้ จึงไม่ออกคำทำนาย");
        if (enabled.some((s) => fields[s].time.trim() === ""))
          throw new Error("กรอกเวลาให้ครบทุก session ที่เลือก");
        const payload = Object.fromEntries(
          enabled.map((s) => [s, { time: fields[s].time.trim() }]),
        );
        const result = await fetch(`${API}/predict${driver ? "" : "/custom"}`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(
            driver
              ? { event_id: eventId, driver, sessions: payload }
              : { event_id: eventId, ...payload },
          ),
          signal: controller.signal,
        });
        const data = await result.json();
        if (!result.ok)
          throw new Error(
            typeof data.detail === "string" ? data.detail : "ข้อมูลไม่ถูกต้อง",
          );
        if (!controller.signal.aborted) setResponse(data);
      } catch (e) {
        if (!controller.signal.aborted)
          setError(e instanceof Error ? e.message : "ทำนายไม่สำเร็จ");
      } finally {
        if (!controller.signal.aborted) setLoading(false);
      }
    },
    [eventId, driver],
  );
  useEffect(() => {
    request.current?.abort();
    setResponse(undefined);
    setError("");
    setLoading(false);
    const timer = historical
      ? setTimeout(() => void runPrediction(JSON.parse(serialized)), 300)
      : undefined;
    return () => {
      clearTimeout(timer);
      request.current?.abort();
    };
  }, [serialized, historical, runPrediction]);
  function update(s: SessionName, patch: Partial<FormSession>) {
    setValues((previous) => ({
      ...previous,
      [s]: { ...previous[s], ...patch },
    }));
  }
  return (
    <div className="scenario-body">
      <form
        className="prediction-inputs"
        onSubmit={(e) => {
          e.preventDefault();
          void runPrediction(values);
        }}
      >
        <p className="prediction-instruction">
          {row
            ? `เติมเวลาจริงของ ${row.Driver} แล้ว · ปรับค่าเพื่อทดลอง What-if`
            : "ใส่เวลารอบซ้อมที่เร็วที่สุดของแต่ละ FP ก่อน Qualifying"}
          <span>
            รับทั้งวินาที เช่น 90.123 หรือรูปแบบ 1:30.123 · มีข้อมูลอย่างน้อย 1
            session
          </span>
        </p>
        <div className="source-note">
          <b>
            {event.name} · {event.year}
          </b>
          <p>
            ความยาวสนาม {event.circuit_length_km.toFixed(3)} km ·{" "}
            {event.corner_count} โค้ง
          </p>
          <details>
            <summary>รายละเอียดสนามและแหล่งข้อมูล</summary>
            <p>ผัง {event.layout_id} — ใช้รายละเอียดตามสนามและปีที่เลือก</p>
            <a href={event.source_url} target="_blank" rel="noreferrer">
              แหล่งข้อมูลสนาม: F1DB (CC BY 4.0) ↗
            </a>
          </details>
        </div>
        <div className="practice-grid">
          {sessions.map((s) => (
            <fieldset
              className={`practice-session ${values[s].enabled ? "" : "session-missing"}`}
              key={s}
            >
              <legend>{s}</legend>
              <label className="session-toggle">
                <input
                  type="checkbox"
                  checked={values[s].enabled}
                  disabled={!!row}
                  onChange={(e) => update(s, { enabled: e.target.checked })}
                  aria-label={`มีข้อมูล ${s}`}
                />{" "}
                {values[s].enabled ? "มีเวลาซ้อม" : "ไม่มีข้อมูล"}
              </label>
              {values[s].enabled ? (
                <>
                  <label className="scenario-input">
                    เวลา (วินาที หรือ m:ss.sss)
                    <input
                      aria-label={`What-if ${s}_Time`}
                      inputMode="decimal"
                      required
                      placeholder="90.123 หรือ 1:30.123"
                      value={values[s].time}
                      onChange={(e) => update(s, { time: e.target.value })}
                    />
                  </label>

                  {row?.[`${s}_lap_id`] && (
                    <a
                      href={`?year=2023&event=${event.event_id}&view=weekend&drivers=${row.Driver}&session=${s}&lap=${row[`${s}_lap_id`]}`}
                    >
                      ดู lap ต้นทาง {s} ↗
                    </a>
                  )}
                </>
              ) : (
                <p className="footnote">
                  ไม่มี session: ใช้เวลาจาก Practice ที่เร็วที่สุดที่กรอกไว้
                </p>
              )}
            </fieldset>
          ))}
        </div>
        <div className="prediction-actions">
          {!historical && (
            <button type="submit" className="predict-button" disabled={loading}>
              {loading ? "กำลังทำนาย…" : "ทำนายเวลา Qualifying"}
              <span aria-hidden="true"> →</span>
            </button>
          )}
          <button
            type="button"
            className="reset-button"
            onClick={() => {
              setValues(initialForm(row));
              if (!historical) {
                request.current?.abort();
                setResponse(undefined);
                setError("");
                setLoading(false);
              }
            }}
          >
            {row ? "↺ คืนค่าจากข้อมูลจริง" : "ล้างค่าที่กรอก"}
          </button>
        </div>
        <p className="footnote">
          FP ที่ไม่มีข้อมูลจะใช้เวลาซ้อมที่เร็วที่สุดจากค่าที่มี · ไม่ใช้ทีม
          นักขับ หรือยางเป็น feature
        </p>
      </form>
      <section
        className="prediction-result-panel"
        aria-label="ผลทำนายเวลา Qualifying"
        aria-live="polite"
        aria-busy={loading}
      >
        <h3>เวลา Qualifying ที่คาดการณ์</h3>
        <Status loading={loading} error={error} />
        {!loading && !error && !response && (
          <div className="prediction-placeholder">
            <strong>—:—.———</strong>
            <p>
              {historical
                ? "ปรับเวลาซ้อมเพื่อทดลอง ผลจะคำนวณอัตโนมัติ"
                : "กรอกเวลาซ้อม แล้วกดทำนายเพื่อดูผลตรงนี้"}
            </p>
          </div>
        )}
        {response && (
          <div className="scenario-output" data-testid="scenario-result">
            <span>{historical ? "WHAT-IF RESULT" : "PREDICTED LAP TIME"}</span>
            <strong>{time(response.prediction)}</strong>
            {response.delta != null && (
              <p>
                {delta(response.delta)}{" "}
                <span className="muted">จาก input เดิม</span>
              </p>
            )}
            <small>
              โมเดล {response.model} · จาก final.ipynb ·
              ยังไม่ได้คำนวณช่วงความคลาดเคลื่อน
            </small>
            {response.imputations.map((message) => (
              <p className="footnote" key={message}>
                {message}
              </p>
            ))}
            {response.warnings.map((message) => (
              <p className="notice" key={message}>
                {message}
              </p>
            ))}
            <details>
              <summary>ค่าที่โมเดลได้รับหลังเติม missing</summary>
              <dl>
                {Object.entries(response.inputs).map(([key, value]) => (
                  <div key={key}>
                    <dt>{key}</dt>
                    <dd>{String(value)}</dd>
                  </div>
                ))}
              </dl>
            </details>
          </div>
        )}
        <p className="footnote">
          ค่าประมาณจากเวลาซ้อมและรายละเอียดสนาม ไม่ใช่เวลาอย่างเป็นทางการ
          และยังไม่มี Prediction Interval การเปลี่ยน input
          ไม่ใช่หลักฐานว่าจะทำให้รถเร็วขึ้นจริง
        </p>
      </section>
    </div>
  );
}
function Evaluation({
  report,
  eventId,
}: {
  report: Schema["Evaluation"];
  eventId: string;
}) {
  const eventScores = report.per_event.filter((e) => e.event_id === eventId);
  const active = report.test.find((r) => r.model === report.selected_model)!;
  const baseline = report.test.find((r) => r.model === "Practice baseline")!;
  return (
    <div className="evaluation">
      <h3>โมเดลผ่านการทดสอบแค่ไหน?</h3>
      <p>
        เลือก <b>{report.selected_model}</b> ของชุดเวลา+สนาม จาก validation ปี
        2022 ไม่เลือกใหม่ด้วยคะแนนปี 2023
      </p>
      {active.rmse > baseline.rmse && (
        <div className="notice">
          ในปี 2023 โมเดลที่เลือกมี RMSE สูงกว่า Practice baseline —
          ควรอ่านผลทำนายพร้อมข้อจำกัดนี้
        </div>
      )}
      <p>
        ปี 2023 เคยใช้วิเคราะห์ปัญหาแล้ว ไม่ใช่ untouched test ผู้ชนะจาก
        validation: {Object.values(report.winners).join(" และ ")}
      </p>

      <ScoreTable
        title="2023 / โมเดลจาก Notebook เทียบ baseline"
        rows={report.test}
      />

      {eventScores.length > 0 && (
        <ScoreTable title="ผลเฉพาะรายการที่กำลังดู" rows={eventScores} />
      )}
      <details>
        <summary>
          ดูคะแนนที่ใช้เลือกโมเดล (2022 / ทั้งปี หลังปรับพารามิเตอร์)
        </summary>
        <ScoreTable title="Model selection" rows={report.selection} />
      </details>
      <p className="footnote">
        ประเมิน {active.count} แถว · ไม่ประเมิน {report.excluded_test_rows}{" "}
        แถวที่ไม่มี target หรือ Practice ที่ใช้ได้
      </p>
      <div className="interval-note">
        <b>ใช้โมเดลที่บันทึกจาก final.ipynb โดยตรง</b>
        <p>
          ฝึกปี 2021 เลือกโมเดลและพารามิเตอร์ด้วยปี 2022 แล้ว refit ทั้งสองปี
          ไม่มีชุด calibration แยก จึงยังไม่แสดง Prediction Interval
        </p>
      </div>
    </div>
  );
}
