import { useEffect, useRef } from "react";
import * as echarts from "echarts/core";
import { LineChart, BarChart, ScatterChart } from "echarts/charts";
import {
  GridComponent,
  TooltipComponent,
  LegendComponent,
  DataZoomComponent,
  AriaComponent,
} from "echarts/components";
import { CanvasRenderer } from "echarts/renderers";
import type { EChartsCoreOption } from "echarts/core";
echarts.use([
  LineChart,
  BarChart,
  ScatterChart,
  GridComponent,
  TooltipComponent,
  LegendComponent,
  DataZoomComponent,
  AriaComponent,
  CanvasRenderer,
]);

export default function Chart({
  option,
  onPoint,
  label,
  height = 330,
}: {
  option: EChartsCoreOption;
  onPoint?: (id: string) => void;
  label: string;
  height?: number;
}) {
  const root = useRef<HTMLDivElement>(null);
  const callback = useRef(onPoint);
  callback.current = onPoint;
  useEffect(() => {
    if (!root.current) return;
    const chart = echarts.init(root.current, undefined, { renderer: "canvas" });
    chart.setOption({
      backgroundColor: "transparent",
      textStyle: { fontFamily: "IBM Plex Sans Thai", color: "#a7adb5" },
      animation: !matchMedia("(prefers-reduced-motion: reduce)").matches,
      aria: { enabled: true },
      ...option,
    });
    chart.on("click", (params) => {
      const data = params.data as { lap_id?: string };
      if (data?.lap_id) callback.current?.(data.lap_id);
    });
    const observer = new ResizeObserver(() => chart.resize());
    observer.observe(root.current);
    return () => {
      observer.disconnect();
      chart.dispose();
    };
  }, [option]);
  return (
    <div
      className="chart"
      ref={root}
      role="img"
      aria-label={label}
      style={{ height }}
    />
  );
}
