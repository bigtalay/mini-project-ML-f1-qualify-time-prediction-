import type React from "react";
import { number } from "./lib";
import type { Schema, useQuery } from "./lib";
export const API = "/api/v1";
export type QueryState = ReturnType<typeof useQuery>;
export const fmtInt = (n: number) => n.toLocaleString("en-US");
export function Status({
  loading,
  error,
  retry,
}: {
  loading: boolean;
  error?: string;
  retry?: () => void;
}) {
  if (error)
    return (
      <div className="notice error" role="alert">
        {error} {retry && <button onClick={retry}>ลองใหม่</button>}
      </div>
    );
  return loading ? (
    <div className="loading" role="status">
      <span className="loading-line" />
      กำลังอ่านข้อมูล…
    </div>
  ) : null;
}
export function Empty({ children }: { children: React.ReactNode }) {
  return <div className="empty">{children}</div>;
}
export function Download({
  href,
  children = "↓ CSV",
}: {
  href: string;
  children?: React.ReactNode;
}) {
  return (
    <a className="download" href={href} download>
      {children}
    </a>
  );
}

export function ScoreTable({
  title,
  rows,
}: {
  title: string;
  rows: Schema["ModelScore"][];
}) {
  return (
    <>
      <h4>{title}</h4>
      <div className="table-scroll">
        <table>
          <thead>
            <tr>
              <th>Model</th>
              <th>N</th>
              <th>MAE (s)</th>
              <th>RMSE (s)</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.model}>
                <td>{r.model}</td>
                <td>{r.count}</td>
                <td>{number(r.mae)}</td>
                <td>{number(r.rmse)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}
