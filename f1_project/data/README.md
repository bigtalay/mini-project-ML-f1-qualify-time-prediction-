# Data lineage — final snapshot 2021–2023

ข้อมูลสำหรับ `final.ipynb` และเว็บอยู่ที่ `data/final/` เท่านั้น หน้าเว็บโหลดโมเดล `models/qualifying-circuit.joblib` และตรวจ raw/circuit checksums ก่อนเริ่ม ไม่ดาวน์โหลดหรือฝึกใหม่ตอนเปิด

## Raw จาก FastF1

| ไฟล์ใต้ final/raw/ | ระดับข้อมูล | จำนวน |
|---|---|---:|
| events.csv | รายการแข่งและกำหนดการ | 66 events |
| practice_laps.csv | แต่ละ lap ของ FP1–FP3 | 79,661 rows |
| qualifying_results.csv | นักขับ/รายการ Qualifying | 1,320 rows |
| sessions.csv | เวลาเริ่ม/จบ UTC ของ FP และ Q, สถานะและที่มา | เก็บตาม session |
| events/<event_id>/ | CSV แยกรายการและ complete.json | 66 directories |

Notebook 2.2 อ่าน/ดึง schedule และเพิ่ม `Year` กับ `event_id = Year-RoundNumber` (เช่น 2021-01) ข้อ 2.3 ใช้ `get_session(Year, RoundNumber, FP/Q)` แล้วใส่ event_id ของรายการที่ร้องขอลงใน laps/results/session metadata ก่อนบันทึก ไม่จับคู่ข้อมูลด้วยเวลารอบหรือคาดเดาจากชื่อ

ข้อ 2.4 ดาวน์โหลดเฉพาะรายการที่ยังไม่ครบและบันทึก CSV กับ completion checksums ราย event ข้อ 2.5 รวมเป็นไฟล์ใหญ่ ตรวจ byte-level SHA256 เพื่อไม่เขียนทับ raw ที่สมบูรณ์ การ clone มีไฟล์ครบทั้ง 66 รายการ จึงข้ามการดาวน์โหลดได้โดยไม่ต้องมี FastF1 cache

**Raw ของโครงการไม่ใช่ timing feed ที่ยังไม่ผ่านการประมวลผลใด ๆ:** FastF1 parse/merge และอาจสร้างแถวเองก่อนส่งให้เรา การ export ใน Notebook ยังไม่ clean lap, aggregate หรือเติม missing โดยเก็บคอลัมน์ที่ FastF1 ส่งกลับไว้ เวลา timedelta ยังเป็นข้อความ เช่น `0 days 00:01:30.500000` แล้วค่อยแปลงเป็นวินาทีตอนเตรียมข้อมูล เก็บ `IsAccurate`, `Deleted` และ `FastF1Generated` ไว้ตรวจสอบด้วย

`sessions.csv` เก็บ StartDate/EndDate จาก FastF1 SessionInfo ไม่ใช่เวลาที่อนุมานจากเวลารอบ ใช้ยืนยันว่า Practice จบก่อน Q; FP ที่ตามหลัง Q ใน sprint weekend ต้องไม่เข้า features ส่วน FP3 ของ Russian GP 2021 ถูกยกเลิก เก็บสถานะว่า cancelled ไม่สร้าง lap ปลอม

## Cleaning audit

Notebook 2.6–2.7 สร้าง `processed/lap_audit.csv` และ `practice_clean.csv` โดยไม่แก้ raw

| กฎตามลำดับ | ตัดเพิ่มเติม | เหลือ |
|---|---:|---:|
| Raw | — | 79,661 |
| แถวซ้ำ | 0 | 79,661 |
| ไม่มีเวลา/นักขับ | 14,734 | 64,927 |
| เวลาไม่เป็นบวก | 0 | 64,927 |
| Deleted | 609 | 64,318 |
| IsAccurate = false | 13,902 | 50,416 |
| FastF1Generated | 0 เพิ่มเติม | 50,416 |
| ยืนยันไม่ได้ว่า Practice จบก่อน Q | 2,662 | 47,754 |

แต่ละแถวมี `reason` เป็นเหตุผลแรกที่ตัด และ `flag_*` แยกเงื่อนไขที่ซ้อนกัน จำนวน flags ห้ามบวกเป็นจำนวนที่ตัด ตัวอย่าง inaccurate ทั้งหมด 28,648 flags และ generated 16 flags ซ้อนกับกฎก่อนหน้าได้

`source_row` อ้างถึงเลขแถวใน CSV รวม (header คือแถว 1) เว็บใช้ `lap-<source_row>` เป็น lap ID เพื่อเปิดต้นทาง ตาราง/กราฟ/export ใช้ข้อมูลและตัวกรองเดียวกัน ข้อมูล weather ไม่อยู่ใน snapshot นี้

## รายละเอียดสนามจาก F1DB

Notebook **2.8.1–2.8.3** มีโค้ดดาวน์โหลดและตรวจต้นฉบับจริง แล้วจับคู่รายการข้ามแหล่งด้วย **ปี + ชื่อ Grand Prix ที่ normalize** พร้อมตรวจวันแข่งท้องถิ่น/UTC ชื่อทางการที่ตรงกันเป็น fallback ไม่ใช้ round ข้ามแหล่งหรือสร้าง event_id/circuit mapping ด้วยมือ

เก็บ original YAML/indexes + URL/SHA256 manifest ที่ `reference/f1db/<revision>/` และบันทึก `circuit_matches.csv` เป็นหลักฐานชื่อ/วันที่/วิธีจับคู่/ต้นฉบับ ก่อนสร้าง `circuits.csv` ตรวจ unmatched, duplicate หรือวันที่ไม่ตรงแล้วหยุด ยกเว้น Turkey 2021 ที่ระบุความต่างของวันต้นทางไว้ชัดเจน

อ่านรายละเอียด layout ตามปี ข้อยกเว้น และ attribution ใน [Circuit reference](final/reference/README.md)

## ตารางฝึกและโมเดล

ข้อ 2.8.4 เลือก lap เร็วที่สุดราย `event_id + Driver + Session` เมื่อเวลาเท่ากันใช้ source row ก่อน รวมกับผล Q ด้วย `event_id + Driver` แล้ว join สนามด้วย event_id แบบ many-to-one ตรวจว่าครบทุก event

- Target: ต่ำสุดของ Q1/Q2/Q3 ที่เป็นบวก หน่วยวินาที; ไม่เติม target ที่หาย
- X: FP1_Time, FP2_Time, FP3_Time, circuit_length_km, corner_count เท่านั้น
- ไม่มี Practice เลยไม่ฝึก/ไม่ทำนาย; FP ที่ขาดเติมด้วยเวลา FP ที่เร็วที่สุดของนักขับคนเดียวกันในรายการเดียวกันและเก็บ `FP*_filled_from`
- Geometry ต้องครบ ไม่เติมด้วย median; ทีม/นักขับ/ปี/รหัสสนามใช้เชื่อมหรือแบ่งข้อมูล ไม่เป็น features
- `features_before_fill.csv` เก็บค่าก่อนเติมและ source rows; `model_dataset.csv` เก็บแถวที่ใช้ train/evaluate
- StandardScaler fit ปี 2021 สำหรับทดลอง/tuning แล้ว refit ปี 2021–2022 หลังเลือกโมเดล; ใช้ transform ปี 2023 ไม่ fit ด้วยปี 2023 และไม่ scale target

มี Training 432 rows, Validation 436 rows, refit 868 rows และ retrospective 2023 431 rows ทดลอง 4 regressors เลือกด้วย Validation RMSE เท่านั้น ไม่เลือกใหม่จากปี 2023 ไม่มี calibration/Prediction Interval ในรุ่นนี้

ไฟล์ `evaluation_2023.csv`, `evaluation_by_event.csv`, `tuning_validation.csv` และ `test_predictions_2023.csv` บันทึกผลตาม Notebook เว็บคำนวณรายงานซ้ำจาก artifact ที่โหลดจริงเพื่อตรวจผลตรงกัน

## การเปลี่ยนชุดข้อมูล

รันการดาวน์โหลดตาม Notebook และตรวจ completion/audit/source matches ให้ครบก่อนสร้าง processed และฝึกโมเดล ห้ามแก้ raw ระหว่างให้เว็บใช้ artifact เดิม หากเปลี่ยน raw หรือสนามโดยตั้งใจ ต้องฝึก/save โมเดลใหม่พร้อม checksums แล้ว restart app

`.gitattributes` รักษา bytes ใต้ data/final/ ให้เหมือนกันบน Windows/Linux; อย่าเปลี่ยน line endings ของ CSV ด้วย editor เพราะ checksum ตรวจระดับ byte
