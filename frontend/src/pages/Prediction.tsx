import { useState, useEffect } from "react";
import { useApi, time, number, delta } from "../lib";
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
                            onClick={() => state.update({ driver: row.Driver })}
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
      <aside className="panel scenario">
        <div className="panel-title">
          <span className="section-number">02</span>
          <h2>What-if workbench</h2>
        </div>
        {selected && event.year === 2023 ? (
          <Scenario
            key={`${event.event_id}-${driver}`}
            event={event}
            row={selected}
          />
        ) : (
          <Empty>เลือกนักขับในชุดทดสอบปี 2023 เพื่อเริ่มทดลอง</Empty>
        )}
      </aside>
    </div>
  );
}

function Scenario({ event, row }: { event: Event; row: PredictionRow }) {
  const columns = ["FP1_Time", "FP2_Time", "FP3_Time"] as const;
  const [values, setValues] = useState<Record<string, string>>(
    Object.fromEntries(
      columns.map((c) => [c, row[c] == null ? "" : String(row[c])]),
    ),
  );
  const [response, setResponse] = useState<Schema["ScenarioResponse"]>();
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  useEffect(() => {
    if (!row.predictable) return;
    const overrides = Object.fromEntries(
      columns.filter((c) => row[c] != null).map((c) => [c, Number(values[c])]),
    );
    if (
      Object.entries(overrides).some(
        ([key, v]) =>
          values[key].trim() === "" || !Number.isFinite(v) || v <= 0,
      )
    ) {
      setError("เวลา Practice ต้องมากกว่า 0 วินาที");
      setResponse(undefined);
      return;
    }
    const controller = new AbortController();
    setLoading(true);
    setError("");
    setResponse(undefined);
    const timer = setTimeout(
      () =>
        fetch(`${API}/predict`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            event_id: event.event_id,
            driver: row.Driver,
            overrides,
          }),
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
            setResponse(data);
            setLoading(false);
          })
          .catch((e) => {
            if (!controller.signal.aborted) {
              setError(e.message);
              setLoading(false);
            }
          }),
      300,
    );
    return () => {
      clearTimeout(timer);
      controller.abort();
    };
  }, [JSON.stringify(values)]);
  if (!row.predictable)
    return (
      <Empty>
        {row.Driver} ไม่มี Practice ที่ใช้ได้ก่อน Qualifying จึงไม่ออก
        prediction
      </Empty>
    );
  return (
    <div className="scenario-body">
      <div className="scenario-driver">
        {row.Driver}
        <span>PRE-QUALIFYING INPUTS</span>
      </div>
      <p>ปรับเวลา Practice เพื่อดูการตอบสนองของโมเดล</p>
      {columns.map((c) => (
        <label className="scenario-input" key={c}>
          {c.replace("_Time", "")}
          <div>
            <input
              aria-label={`What-if ${c}`}
              type="number"
              min="0.001"
              step="0.001"
              disabled={row[c] == null}
              value={values[c]}
              onChange={(e) => setValues({ ...values, [c]: e.target.value })}
            />
            <span>s</span>
          </div>
          <small>
            {row[c] == null
              ? "ไม่มี session / ไม่มี lap ที่ใช้ได้ก่อน Qualifying"
              : `ต้นทาง ${time(row[c])}`}
          </small>
        </label>
      ))}
      <button
        className="reset-button"
        onClick={() =>
          setValues(
            Object.fromEntries(
              columns.map((c) => [c, row[c] == null ? "" : String(row[c])]),
            ),
          )
        }
      >
        ↺ คืนค่าจากข้อมูลจริง
      </button>
      <Status loading={loading} error={error} />
      {response && (
        <div
          className="scenario-output"
          aria-live="polite"
          data-testid="scenario-result"
        >
          <span>SCENARIO RESULT</span>
          <strong>{time(response.prediction)}</strong>
          <p>
            {delta(response.delta)}{" "}
            <span className="muted">จาก input เดิม</span>
          </p>
          <small>
            ช่วงอ้างอิง {time(response.lower)} – {time(response.upper)}
          </small>
          {response.warnings.map((w) => (
            <p className="notice" key={w}>
              {w}
            </p>
          ))}
        </div>
      )}
      <p className="footnote">
        เป็นการทดลอง input ของโมเดล ไม่ใช่หลักฐานว่าการปรับ Practice
        จะทำให้รถเร็วขึ้นจริง ช่วง error จากข้อมูลย้อนหลังอาจไม่ครอบคลุม
        scenario ใหม่
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
        เลือก <b>{report.selected_model}</b> จาก validation ปี 2022 ก่อนเปิด
        test ปี 2023
      </p>
      {active.rmse > baseline.rmse && (
        <div className="notice">
          ในปี 2023 โมเดลที่เลือกมี RMSE สูงกว่า Practice baseline —
          ควรอ่านผลทำนายพร้อมข้อจำกัดนี้
        </div>
      )}
      <ScoreTable title="Held-out test / 2023" rows={report.test} />
      {eventScores.length > 0 && (
        <ScoreTable title="ผลเฉพาะรายการที่กำลังดู" rows={eventScores} />
      )}
      <details>
        <summary>ดูคะแนนที่ใช้เลือกโมเดล (2022 / 11 รายการแรก)</summary>
        <ScoreTable title="Model selection" rows={report.selection} />
      </details>
      <p className="footnote">
        ชุด test {active.count} แถว · ไม่ประเมิน {report.excluded_test_rows}{" "}
        แถวที่ไม่มี target หรือ Practice ที่ใช้ได้
      </p>
      <div className="interval-note">
        <b>ช่วงอ้างอิงจาก residual percentile 5–95</b>
        <p>
          คำนวณจาก calibration {report.interval.calibration_count}{" "}
          แถวในครึ่งหลังของปี 2022 ช่วงนี้ครอบคลุมผลจริงใน test ปี 2023{" "}
          {(report.interval.test_coverage * 100).toFixed(1)}%
          ไม่ใช่การรับประกันความแม่นยำ 90%
        </p>
      </div>
    </div>
  );
}
