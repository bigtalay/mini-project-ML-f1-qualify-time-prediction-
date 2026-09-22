import { useApi, reasonText } from "../lib";
import type { Event, Schema } from "../lib";
import { API, Status, Download, fmtInt } from "../ui";
import type { QueryState } from "../ui";
export default function Method({
  event,
  state,
}: {
  event: Event;
  state: QueryState;
}) {
  const scope = state.query.get("scope") === "event";
  const quality = useApi<Schema["Quality"]>(
    `${API}/quality${scope ? `?event_id=${event.event_id}` : ""}`,
  );
  const evaluation = useApi<Schema["Evaluation"]>(`${API}/evaluation`);
  return (
    <div className="method-layout">
      <section className="panel">
        <div className="panel-title">
          <span className="section-number">01</span>
          <h2>Follow the data</h2>
          <label>
            ขอบเขต
            <select
              aria-label="ขอบเขตรายงานข้อมูล"
              value={scope ? "event" : "all"}
              onChange={(e) => state.update({ scope: e.target.value })}
            >
              <option value="all">ทั้งหมด 2021–2023</option>
              <option value="event">รายการที่เลือก</option>
            </select>
          </label>
        </div>
        <p className="panel-caption">
          จากแถวต้นทางถึง input ของโมเดล ทุกขั้นตอนใช้ฟังก์ชันเดียวกับ Notebook
        </p>
        <Status {...quality} />
        {quality.data && (
          <>
            <ol className="lineage">
              <li>
                <span>01 / RAW</span>
                <h3>{fmtInt(quality.data.raw_laps)} practice laps</h3>
                <p>
                  {fmtInt(quality.data.raw_results)} qualifying result rows ·
                  raw เก็บแยกจากข้อมูลที่ผ่านการเตรียม
                </p>
              </li>
              <li>
                <span>02 / CLEANING</span>
                <h3>{fmtInt(quality.data.kept_laps)} usable laps</h3>
                {Object.entries(quality.data.removals).map(([k, v]) => (
                  <p key={k}>
                    − {fmtInt(v)} · {reasonText[k] || k}
                  </p>
                ))}
                <small>
                  ตัดตามลำดับ: ซ้ำ → ไม่มีเวลา/นักขับ → เวลาไม่บวก → Deleted →
                  Inaccurate → Generated
                </small>
              </li>
              <li>
                <span>03 / TIME CUTOFF</span>
                <h3>
                  {fmtInt(quality.data.pre_qualifying_laps)} pre-qualifying laps
                </h3>
                <p>
                  กันออกอีก {fmtInt(quality.data.after_qualifying_laps)} lap
                  ที่ไม่ยืนยันว่าจบก่อน Qualifying จาก SessionInfo
                </p>
              </li>
              <li>
                <span>04 / FEATURES</span>
                <h3>{fmtInt(quality.data.feature_rows)} driver / event rows</h3>
                <p>
                  ใช้เวลาเร็วที่สุดของแต่ละ Practice · target = min(Q1,Q2,Q3)
                  ที่เป็นบวก
                </p>
                <p>
                  ไม่มี target {quality.data.missing_targets} แถว · ไม่มี
                  Practice {quality.data.no_practice_rows} แถว
                </p>
              </li>
            </ol>
            <h3>Missing values ก่อน ML imputation</h3>
            <div className="table-scroll">
              <table>
                <thead>
                  <tr>
                    <th>Feature</th>
                    <th>Missing rows</th>
                  </tr>
                </thead>
                <tbody>
                  {Object.entries(quality.data.missing_features).map(
                    ([k, v]) => (
                      <tr key={k}>
                        <td>{k}</td>
                        <td>{v}</td>
                      </tr>
                    ),
                  )}
                </tbody>
              </table>
            </div>
            <details>
              <summary>Flags ที่ทับซ้อนกัน — ห้ามบวกเป็นยอดตัด</summary>
              {Object.entries(quality.data.overlapping_flags).map(([k, v]) => (
                <p key={k}>
                  {reasonText[k] || k}: {fmtInt(v)}
                </p>
              ))}
            </details>
            <Download
              href={`${API}/events/${event.event_id}/export?kind=audit`}
            >
              ↓ Audit ราย lap ของ {event.name}
            </Download>
            <div className="source-note">
              <b>DATASET {quality.data.version}</b>
              {Object.entries(quality.data.checksums).map(([file, hash]) => (
                <p key={file}>
                  {file}
                  <code>{hash}</code>
                </p>
              ))}
              SHA-256 หลัง normalize CRLF → LF
            </div>
          </>
        )}
      </section>
      <aside className="panel method-notes">
        <div className="panel-title">
          <span className="section-number">02</span>
          <h2>Method & limitations</h2>
        </div>
        <div className="prose">
          <h3>Raw ในงานนี้หมายถึงอะไร</h3>
          <p>
            ข้อมูลระดับ result, lap และ weather timestamp ที่ส่งออกจาก FastF1
            โดยเลือกคอลัมน์และแปลงเวลาเป็นวินาทีแล้ว FastF1
            เองมีการประมวลผลแหล่งข้อมูล จึงไม่ใช่ raw feed ทั้งหมดจากระบบจับเวลา
          </p>
          <h3>ข้อมูลที่ใช้ก่อนทำนาย</h3>
          <p>
            ใช้เฉพาะ Practice ที่ EndDate มาก่อน StartDate ของ Qualifying ตาม
            SessionInfo ของ FastF1 ข้อมูลเวลานี้เป็น metadata
            ที่แหล่งข้อมูลรายงาน ไม่ใช่การวัดเวลาจบจริงใหม่ของเรา
          </p>
          <p>
            ไม่ใช้ weather ระหว่าง Qualifying, Q1/Q2/Q3 หรือ Position เป็น
            feature
          </p>
          <h3>การเตรียม input</h3>
          <p>
            Median imputation → event-grouped target encoding สำหรับ Driver
            และสนาม → one-hot Team → scaling → เลือกสูงสุด 15 features ทุกขั้น
            fit บน training partition เท่านั้น Unknown category ใช้ fallback จาก
            training
          </p>
          <h3>สี่ส่วนที่แยกจากกัน</h3>
          <Status {...evaluation} />
          {evaluation.data && (
            <ol className="split-list">
              {[
                ["training", "2021 / ฝึกเบื้องต้น"],
                ["selection", "2022 รอบ 1–11 / เลือกโมเดล"],
                ["calibration", "2022 รอบ 12–22 / วัดช่วง error"],
                ["test", "2023 / ทดสอบสุดท้าย"],
              ].map(([k, label]) => (
                <li key={k}>
                  <b>{label}</b>
                  <span>
                    {evaluation.data!.partitions[k].rows} rows ·{" "}
                    {evaluation.data!.partitions[k].events.length} events
                  </span>
                </li>
              ))}
            </ol>
          )}
          <p>
            หลังเลือกโมเดล ฝึกใหม่ด้วย 2021 + ชุด selection เท่านั้น ไม่ใช้
            calibration หรือ test มาปรับโมเดล
          </p>
          <h3>สิ่งที่กราฟยังตอบไม่ได้</h3>
          <p>
            ไม่ทราบเชื้อเพลิง setup หรือ run plan จึงไม่สรุปสาเหตุจากความต่างของ
            lap time ไม่แสดง tyre degradation หรือ telemetry ต่อเนื่องจากข้อมูล
            speed trap เพียงไม่กี่จุด
          </p>
          <h3>ข้อมูลขาด</h3>
          <p>
            ช่องว่างคือไม่มีข้อมูล ไม่ใช่ศูนย์ ในรายละเอียด lap ไม่มีการเติมค่า
            ส่วนการเติม input ของโมเดลเกิดภายหลังแยกชุดข้อมูลแล้ว
          </p>
          <a
            href="https://github.com/theOehrly/Fast-F1"
            target="_blank"
            rel="noreferrer"
          >
            แหล่งข้อมูลและโครงการ FastF1 ↗
          </a>
        </div>
      </aside>
    </div>
  );
}
