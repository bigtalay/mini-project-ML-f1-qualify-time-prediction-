import { useState, useEffect } from "react";
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
  const manual = state.query.get("mode") === "manual" || event.year !== 2023;
  return (
    <div className="prediction-layout">
      <section className="panel">
        <div className="panel-title">
          <span className="section-number">01</span>
          <h2>Prediction vs. reality</h2>
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
                            : row.lower == null ? "ยังไม่ได้คำนวณช่วง" : `${time(row.lower)} – ${time(row.upper)}`}
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
      <aside className="panel scenario">
        <div className="panel-title">
          <span className="section-number">02</span>
          <h2>เวลา + ยาง</h2>
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
        </div>
        {manual || selected ? (
          <Scenario
            key={`${manual ? "manual" : event.event_id + driver}`}
            event={event}
            row={manual ? undefined : selected}
          />
        ) : (
          <Empty>เลือกนักขับปี 2023 หรือเลือกโหมดกรอกเอง</Empty>
        )}
      </aside>
    </div>
  );
}

const sessions = ["FP1", "FP2", "FP3"] as const;
type SessionName = (typeof sessions)[number];
type FormSession = {
  enabled: boolean;
  time: string;
  compound: string;
  tyreLife: string;
};
const kinds = ["SOFT", "MEDIUM", "HARD", "INTERMEDIATE", "WET", "UNKNOWN"];

function initialForm(row?: PredictionRow): Record<SessionName, FormSession> {
  return Object.fromEntries(
    sessions.map((s) => [
      s,
      {
        enabled: row ? row[`${s}_Time`] != null : s === "FP1",
        time: row?.[`${s}_Time`] == null ? "" : String(row[`${s}_Time`]),
        compound: kinds.includes(row?.[`${s}_Compound`] || "")
          ? row![`${s}_Compound`]!
          : "UNKNOWN",
        tyreLife:
          row?.[`${s}_TyreLife`] == null ? "" : String(row[`${s}_TyreLife`]),
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
  const eventId = row ? event.event_id : null;
  const driver = row?.Driver;
  useEffect(() => {
    const fields: Record<SessionName, FormSession> = JSON.parse(serialized);
    setResponse(undefined);
    setError("");
    setLoading(false);
    const enabled = sessions.filter((s) => fields[s].enabled);
    if (!enabled.length) {
      setError("ไม่มี Practice ที่ใช้ได้ จึงไม่ออกคำทำนาย");
      return;
    }
    if (enabled.some((s) => fields[s].time.trim() === "")) return;
    const controller = new AbortController();
    const payload = Object.fromEntries(
      enabled.map((s) => [
        s,
        {
          time: fields[s].time.trim(),
          compound: fields[s].compound,
          tyre_life:
            fields[s].tyreLife.trim() === ""
              ? null
              : Number(fields[s].tyreLife),
        },
      ]),
    );
    if (
      enabled.some(
        (s) =>
          fields[s].tyreLife.trim() !== "" &&
          (!Number.isFinite(Number(fields[s].tyreLife)) ||
            Number(fields[s].tyreLife) < 0),
      )
    ) {
      setError("อายุยางต้องไม่ติดลบ หรือเว้นว่าง");
      return;
    }
    setLoading(true);
    const timer = setTimeout(() => {
      fetch(`${API}/predict${eventId ? "" : "/custom"}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(
          eventId ? { event_id: eventId, driver, sessions: payload } : payload,
        ),
        signal: controller.signal,
      })
        .then(async (r) => {
          const data = await r.json();
          if (!r.ok)
            throw new Error(
              typeof data.detail === "string"
                ? data.detail
                : "ข้อมูลไม่ถูกต้อง",
            );
          return data;
        })
        .then((data) => {
          if (!controller.signal.aborted) {
            setResponse(data);
            setLoading(false);
          }
        })
        .catch((e) => {
          if (!controller.signal.aborted) {
            setError(e.message);
            setLoading(false);
          }
        });
    }, 300);
    return () => {
      clearTimeout(timer);
      controller.abort();
    };
  }, [serialized, eventId, driver]);
  function update(s: SessionName, patch: Partial<FormSession>) {
    setValues((previous) => ({
      ...previous,
      [s]: { ...previous[s], ...patch },
    }));
  }
  return (
    <div className="scenario-body">
      <div className="scenario-driver">
        {row ? row.Driver : "กรอก Practice เอง"}
        <span>PRE-QUALIFYING INPUTS</span>
      </div>
      <p>
        {row
          ? "เวลาและยางเติมจาก lap จริง เปลี่ยนค่าเพื่อทดลอง scenario"
          : "ไม่ต้องระบุทีม นักขับ หรือสนาม ใช้ข้อมูลซ้อมที่จบก่อน Qualifying เท่านั้น"}
      </p>
      {sessions.map((s) => (
        <fieldset className="tyre-session" key={s}>
          <legend>{s}</legend>
          <label className="session-toggle">
            <input
              type="checkbox"
              checked={values[s].enabled}
              disabled={!!row}
              onChange={(e) => update(s, { enabled: e.target.checked })}
              aria-label={`มีข้อมูล ${s}`}
            />{" "}
            มีข้อมูล session นี้
          </label>
          {values[s].enabled ? (
            <>
              <label className="scenario-input">
                เวลา (วินาที หรือ m:ss.sss)
                <input
                  aria-label={`What-if ${s}_Time`}
                  inputMode="decimal"
                  placeholder="90.123 หรือ 1:30.123"
                  value={values[s].time}
                  onChange={(e) => update(s, { time: e.target.value })}
                />
              </label>
              <div className="tyre-fields">
                <label>
                  ชนิดยาง
                  <select
                    aria-label={`${s} ชนิดยาง`}
                    value={values[s].compound}
                    onChange={(e) => update(s, { compound: e.target.value })}
                  >
                    {kinds.map((k) => (
                      <option key={k}>{k}</option>
                    ))}
                  </select>
                </label>
                <label>
                  อายุยาง (รอบ)
                  <input
                    aria-label={`${s} อายุยาง`}
                    type="number"
                    min="0"
                    step="any"
                    placeholder="ไม่ทราบ"
                    value={values[s].tyreLife}
                    onChange={(e) => update(s, { tyreLife: e.target.value })}
                  />
                </label>
              </div>
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
              ไม่มี session: ใช้ทั้งเวลาและยางจาก Practice
              ที่เร็วที่สุดที่กรอกไว้
            </p>
          )}
        </fieldset>
      ))}
      <button
        className="reset-button"
        onClick={() => setValues(initialForm(row))}
      >
        {row ? "↺ คืนค่าจากข้อมูลจริง" : "ล้างค่าที่กรอก"}
      </button>
      <Status loading={loading} error={error} />
      {!loading && !error && !response && (
        <p className="footnote">
          กรอกเวลาให้ครบทุก session ที่เลือก ผลจะคำนวณอัตโนมัติ
        </p>
      )}
      {response && (
        <div
          className="scenario-output"
          aria-live="polite"
          data-testid="scenario-result"
        >
          <span>SCENARIO RESULT</span>
          <strong>{time(response.prediction)}</strong>
          {response.delta != null && (
            <p>
              {delta(response.delta)}{" "}
              <span className="muted">จาก input เดิม</span>
            </p>
          )}
          <small>
            โมเดล {response.model} · จาก final.ipynb · ยังไม่ได้คำนวณช่วงความคลาดเคลื่อน
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
        เป็นการทดลอง input ไม่ใช่หลักฐานว่าการเปลี่ยนยางจะทำให้รถเร็วขึ้นจริง
        ไม่มีช่วงรับประกันความแม่นยำสำหรับโมเดลนี้
      </p>
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
        เลือก <b>{report.selected_model}</b> ของชุดเวลา+ยาง จาก validation ปี
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
        <summary>ดูคะแนนที่ใช้เลือกโมเดล (2022 / ทั้งปี หลังปรับพารามิเตอร์)</summary>
        <ScoreTable title="Model selection" rows={report.selection} />
      </details>
      <p className="footnote">
        ประเมิน {active.count} แถว · ไม่ประเมิน {report.excluded_test_rows}{" "}
        แถวที่ไม่มี target หรือ Practice ที่ใช้ได้
      </p>
      <div className="interval-note">
        <b>ใช้โมเดลที่บันทึกจาก final.ipynb โดยตรง</b>
        <p>ฝึกปี 2021 เลือกโมเดลและพารามิเตอร์ด้วยปี 2022 แล้ว refit ทั้งสองปี
          ไม่มีชุด calibration แยก จึงไม่แสดงช่วง error จากโมเดลเก่า</p>
      </div>
    </div>
  );
}
