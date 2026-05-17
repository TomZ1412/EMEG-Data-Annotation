import React, { useEffect, useMemo, useRef, useState } from "react";
import * as Plotly from "plotly.js-dist-min";

const BAD_COLOR = "#dc2626";
const HOVER_COLOR = "#f59e0b";
const GOOD_COLOR = "#2563eb";
const CHANNEL_COLORS = [
  "#1f77b4",
  "#ff7f0e",
  "#2ca02c",
  "#d62728",
  "#9467bd",
  "#8c564b",
  "#e377c2",
  "#7f7f7f",
  "#bcbd22",
  "#17becf",
  "#4c78a8",
  "#f58518",
  "#54a24b",
  "#b279a2",
  "#72b7b2",
  "#eeca3b",
];

export default function WaveformViewer({
  data,
  badChannels = [],
  setBadChannels,
  loading,
  onSelectSubBlock,
  currentSubBlockIndex = 0,
  markedSubBlocks = [],
}) {
  const waveformRef = useRef(null);
  const psdRef = useRef(null);
  const activePlotRef = useRef(null);
  const scrollTopRef = useRef(0);
  const badChannelsRef = useRef(badChannels);

  const [activeView, setActiveView] = useState("psd");
  const [scalingFactor, setScalingFactor] = useState(8000);
  const [hoveredChannel, setHoveredChannel] = useState(null);

  const totalSubBlocks = Math.max(1, Number(data?.totalSubBlocks || 1));
  const wavData = data?.wav || {};
  const psdData = data?.psd || null;
  const psdSeries = psdData?.psd || {};
  const psdFrequencies = psdData?.frequencies || [];

  useEffect(() => {
    badChannelsRef.current = badChannels;
  }, [badChannels]);

  const channelNames = useMemo(() => {
    if (Object.keys(wavData).length) return Object.keys(wavData);
    if (Object.keys(psdSeries).length) return Object.keys(psdSeries);
    return [];
  }, [wavData, psdSeries]);

  useEffect(() => {
    if (activeView === "psd" && !Object.keys(psdSeries).length && Object.keys(wavData).length) {
      setActiveView("wav");
    }
    if (activeView === "wav" && !Object.keys(wavData).length && Object.keys(psdSeries).length) {
      setActiveView("psd");
    }
  }, [activeView, wavData, psdSeries]);

  useEffect(() => {
    return () => {
      if (activePlotRef.current) Plotly.purge(activePlotRef.current);
    };
  }, []);

  const toggleChannel = (channel) => {
    if (!channel || !setBadChannels) return;
    const currentBadChannels = badChannelsRef.current;
    setBadChannels(
      currentBadChannels.includes(channel)
        ? currentBadChannels.filter((item) => item !== channel)
        : [...currentBadChannels, channel]
    );
  };

  const toggleSelectedChannels = (channels) => {
    if (!channels.length || !setBadChannels) return;
    const currentBadChannels = badChannelsRef.current;
    const uniqueChannels = [...new Set(channels)];
    const shouldClear = uniqueChannels.every((channel) => currentBadChannels.includes(channel));
    if (shouldClear) {
      setBadChannels(currentBadChannels.filter((channel) => !uniqueChannels.includes(channel)));
    } else {
      setBadChannels([...new Set([...currentBadChannels, ...uniqueChannels])]);
    }
  };

  const channelMatchesBox = (values, xRange, yRange) => {
    const [xMin, xMax] = [Math.min(...xRange), Math.max(...xRange)];
    const [yMin, yMax] = [Math.min(...yRange), Math.max(...yRange)];

    return values.some((value, index) => {
      const x = psdFrequencies[index];
      if (x < xMin || x > xMax) return false;

      const yCandidates = [value];
      if (value > 0) yCandidates.push(Math.log10(value));
      return yCandidates.some((y) => y >= yMin && y <= yMax);
    });
  };

  const pointInPolygon = (x, y, polygonX, polygonY) => {
    let inside = false;
    for (let i = 0, j = polygonX.length - 1; i < polygonX.length; j = i++) {
      const xi = polygonX[i];
      const yi = polygonY[i];
      const xj = polygonX[j];
      const yj = polygonY[j];
      const intersects = yi > y !== yj > y && x < ((xj - xi) * (y - yi)) / (yj - yi || Number.EPSILON) + xi;
      if (intersects) inside = !inside;
    }
    return inside;
  };

  const channelMatchesLasso = (values, polygonX, polygonY) =>
    values.some((value, index) => {
      const x = psdFrequencies[index];
      if (value > 0 && pointInPolygon(x, Math.log10(value), polygonX, polygonY)) return true;
      return pointInPolygon(x, value, polygonX, polygonY);
    });

  const channelsFromSelection = (eventData) => {
    const channels = Object.keys(psdSeries);
    if (eventData?.range?.x && eventData?.range?.y) {
      return channels.filter((channel) => channelMatchesBox(psdSeries[channel] || [], eventData.range.x, eventData.range.y));
    }

    if (eventData?.lassoPoints?.x?.length && eventData?.lassoPoints?.y?.length) {
      return channels.filter((channel) =>
        channelMatchesLasso(psdSeries[channel] || [], eventData.lassoPoints.x, eventData.lassoPoints.y)
      );
    }

    return [];
  };

  const psdTraceStyle = (channels) => {
    const currentBadChannels = badChannelsRef.current;
    return {
      colors: channels.map((channel, index) =>
        currentBadChannels.includes(channel)
          ? BAD_COLOR
          : hoveredChannel === channel
            ? HOVER_COLOR
            : CHANNEL_COLORS[index % CHANNEL_COLORS.length] || GOOD_COLOR
      ),
      widths: channels.map((channel) => (currentBadChannels.includes(channel) || hoveredChannel === channel ? 2.4 : 1)),
      opacities: channels.map((channel) => (currentBadChannels.includes(channel) || hoveredChannel === channel ? 1 : 0.58)),
    };
  };

  const wavTraceStyle = (channels) => {
    const currentBadChannels = badChannelsRef.current;
    return {
      colors: channels.map((channel) =>
        currentBadChannels.includes(channel) ? BAD_COLOR : hoveredChannel === channel ? HOVER_COLOR : GOOD_COLOR
      ),
      widths: channels.map((channel) => (currentBadChannels.includes(channel) || hoveredChannel === channel ? 2.4 : 1)),
      opacities: channels.map((channel) => (currentBadChannels.includes(channel) || hoveredChannel === channel ? 1 : 0.88)),
    };
  };

  const channelLine = (channel, index = 0, colorful = false) => {
    const isBad = badChannels.includes(channel);
    const isHovered = hoveredChannel === channel;
    return {
      color: isBad
        ? BAD_COLOR
        : isHovered
          ? HOVER_COLOR
          : colorful
            ? CHANNEL_COLORS[index % CHANNEL_COLORS.length] || GOOD_COLOR
            : GOOD_COLOR,
      width: isBad || isHovered ? 2.4 : 1,
    };
  };

  useEffect(() => {
    if (activeView !== "wav") return;
    const container = waveformRef.current;
    if (!container || !Object.keys(wavData).length) return;

    let cancelled = false;

    const render = async () => {
      if (activePlotRef.current) {
        Plotly.purge(activePlotRef.current);
        activePlotRef.current = null;
      }
      container.innerHTML = "";

      const channels = Object.keys(wavData);
      const samples = Math.max(...channels.map((channel) => wavData[channel]?.length || 0));
      if (!samples) return;

      const totalDuration = 30;
      const time = Array.from({ length: samples }, (_, index) => index * (totalDuration / samples));
      const offset = 0.75;

      const traces = channels.map((channel, index) => {
        const values = wavData[channel] || [];
        const mean = values.reduce((sum, value) => sum + value, 0) / Math.max(1, values.length);
        const line = channelLine(channel, index, false);
        return {
          x: time.slice(0, values.length),
          y: values.map((value) => (value - mean) * scalingFactor + (channels.length - index - 1) * offset),
          name: channel,
          mode: "lines",
          line,
          hoverinfo: "x+y+name",
          opacity: badChannels.includes(channel) ? 1 : 0.88,
        };
      });

      const annotations = channels.map((channel, index) => ({
        x: -0.01,
        y: (channels.length - index - 1) * offset,
        xref: "paper",
        yref: "y",
        text: channel,
        showarrow: false,
        font: {
          size: 10,
          color: badChannels.includes(channel) ? BAD_COLOR : "#111827",
        },
        xanchor: "right",
        align: "right",
      }));

      const plotDiv = document.createElement("div");
      plotDiv.style.width = "100%";
      plotDiv.style.height = `${Math.max(420, 72 + channels.length * 34)}px`;
      container.appendChild(plotDiv);
      activePlotRef.current = plotDiv;

      await Plotly.newPlot(
        plotDiv,
        traces,
        {
          margin: { l: 108, r: 20, t: 8, b: 38 },
          xaxis: { title: "Time (s)", showgrid: false, range: [0, totalDuration] },
          yaxis: {
            showticklabels: false,
            showgrid: false,
            zeroline: false,
            range: [-offset, channels.length * offset],
          },
          paper_bgcolor: "#fff",
          plot_bgcolor: "#fff",
          showlegend: false,
          annotations,
          autosize: true,
        },
        { displayModeBar: false, responsive: true }
      );

      if (cancelled) return;
      plotDiv.on("plotly_click", (event) => {
        scrollTopRef.current = container.scrollTop;
        toggleChannel(event.points?.[0]?.data?.name);
      });
      plotDiv.on("plotly_hover", (event) => setHoveredChannel(event.points?.[0]?.data?.name || null));
      plotDiv.on("plotly_unhover", () => setHoveredChannel(null));
      container.scrollTop = scrollTopRef.current;
    };

    render();
    return () => {
      cancelled = true;
    };
  }, [activeView, wavData, badChannels, scalingFactor]);

  useEffect(() => {
    if (activeView !== "wav" || !activePlotRef.current || !Object.keys(wavData).length) return;
    const channels = Object.keys(wavData);
    const style = wavTraceStyle(channels);
    Plotly.restyle(activePlotRef.current, {
      "line.color": style.colors,
      "line.width": style.widths,
      opacity: style.opacities,
    });
  }, [activeView, wavData, badChannels, hoveredChannel]);

  useEffect(() => {
    if (activeView !== "psd") return;
    const container = psdRef.current;
    if (!container || !psdFrequencies.length || !Object.keys(psdSeries).length) return;

    let cancelled = false;

    const render = async () => {
      if (activePlotRef.current) {
        Plotly.purge(activePlotRef.current);
        activePlotRef.current = null;
      }
      container.innerHTML = "";

      const channels = Object.keys(psdSeries);
      const style = psdTraceStyle(channels);
      const traces = channels.map((channel, index) => {
        return {
          x: psdFrequencies,
          y: psdSeries[channel],
          name: channel,
          mode: "lines",
          line: { color: style.colors[index], width: style.widths[index] },
          opacity: style.opacities[index],
        };
      });

      const plotDiv = document.createElement("div");
      plotDiv.style.width = "100%";
      plotDiv.style.height = "100%";
      container.appendChild(plotDiv);
      activePlotRef.current = plotDiv;

      await Plotly.newPlot(
        plotDiv,
        traces,
        {
          dragmode: "select",
          hovermode: "closest",
          selectdirection: "any",
          margin: { l: 58, r: 16, t: 16, b: 46 },
          xaxis: { title: "Frequency (Hz)", showgrid: true, gridcolor: "#eef2f7", fixedrange: false },
          yaxis: { title: "PSD", type: "log", showgrid: true, gridcolor: "#eef2f7", fixedrange: false },
          paper_bgcolor: "#fff",
          plot_bgcolor: "#fff",
          showlegend: false,
          autosize: true,
        },
        {
          displayModeBar: true,
          displaylogo: false,
          scrollZoom: true,
          responsive: true,
          modeBarButtonsToAdd: ["select2d", "lasso2d"],
        }
      );

      if (cancelled) return;
      plotDiv.on("plotly_selected", (eventData) => {
        const selectedChannels = channelsFromSelection(eventData);
        if (!selectedChannels.length) return;
        toggleSelectedChannels(selectedChannels);
        Plotly.relayout(plotDiv, { selections: [] });
      });
      plotDiv.on("plotly_click", (event) => toggleChannel(event.points?.[0]?.data?.name));
      plotDiv.on("plotly_hover", (event) => setHoveredChannel(event.points?.[0]?.data?.name || null));
      plotDiv.on("plotly_unhover", () => setHoveredChannel(null));
    };

    render();
    return () => {
      cancelled = true;
    };
  }, [activeView, psdFrequencies, psdSeries]);

  useEffect(() => {
    if (activeView !== "psd" || !activePlotRef.current || !Object.keys(psdSeries).length) return;
    const channels = Object.keys(psdSeries);
    const style = psdTraceStyle(channels);
    Plotly.restyle(activePlotRef.current, {
      "line.color": style.colors,
      "line.width": style.widths,
      opacity: style.opacities,
    });
  }, [activeView, psdSeries, badChannels, hoveredChannel]);

  const setAllChannels = () => {
    if (channelNames.length && setBadChannels) setBadChannels(channelNames);
  };

  const clearChannels = () => {
    if (setBadChannels) setBadChannels([]);
  };

  const setSubBlock = (value) => {
    const number = Number(value);
    if (!Number.isFinite(number)) return;
    const index = Math.min(totalSubBlocks - 1, Math.max(0, number));
    if (onSelectSubBlock) onSelectSubBlock(index);
  };

  const autoScale = () => setScalingFactor(Number(data?.scaling_factor || 1));

  return (
    <div style={styles.shell}>
      <div style={styles.topbar}>
        <div style={styles.tabs}>
          {[
            ["psd", "PSD"],
            ["wav", "Waveform"],
          ].map(([key, label]) => (
            <button key={key} onClick={() => setActiveView(key)} style={tabStyle(activeView === key)}>
              {label}
            </button>
          ))}
        </div>

        <div style={styles.actions}>
          <strong>{badChannels.length}</strong>
          <span>/ {channelNames.length} bad channels</span>
          <button type="button" onClick={setAllChannels} disabled={!channelNames.length || loading} style={buttonStyle("#dc2626")}>
            Mark all
          </button>
          <button type="button" onClick={clearChannels} disabled={!badChannels.length || loading} style={buttonStyle("#f59e0b")}>
            Clear
          </button>
        </div>
      </div>

      {activeView === "wav" && (
        <div style={styles.controlBar}>
          <span style={{ minWidth: 88 }}>Scale {scalingFactor.toFixed(2)}x</span>
          <input
            type="range"
            min="0.1"
            max="8000"
            step="0.1"
            value={scalingFactor}
            onChange={(event) => setScalingFactor(Number(event.target.value))}
            style={{ flex: 1 }}
          />
          <button type="button" onClick={() => setScalingFactor((value) => value * 0.8)} style={buttonStyle("#2563eb")}>
            -
          </button>
          <button type="button" onClick={() => setScalingFactor(8000)} style={buttonStyle("#16a34a")}>
            8000
          </button>
          <button type="button" onClick={() => setScalingFactor((value) => value * 1.2)} style={buttonStyle("#2563eb")}>
            +
          </button>
        </div>
      )}

      {activeView === "wav" && (
        <MarkedSubBlockBar
          blocks={markedSubBlocks}
          currentSubBlockIndex={currentSubBlockIndex}
          onSelectSubBlock={onSelectSubBlock}
        />
      )}

      <div style={styles.plotFrame}>
        <div style={styles.plotArea}>
          {loading && <LoadingOverlay />}
          {activeView === "wav" ? (
            Object.keys(wavData).length ? (
              <div ref={waveformRef} style={styles.waveformPlot} />
            ) : (
              <EmptyState text="No waveform data" />
            )
          ) : Object.keys(psdSeries).length ? (
            <div ref={psdRef} style={styles.psdPlot} />
          ) : (
            <EmptyState text="No PSD data" />
          )}
        </div>

        {activeView === "psd" && Object.keys(psdSeries).length > 0 && (
          <ChannelList
            channels={Object.keys(psdSeries)}
            badChannels={badChannels}
            hoveredChannel={hoveredChannel}
            onHover={setHoveredChannel}
            onToggle={toggleChannel}
          />
        )}
      </div>

      {activeView === "wav" && totalSubBlocks > 1 && (
        <div style={styles.controlBar}>
          <button type="button" onClick={() => setSubBlock(currentSubBlockIndex - 1)} disabled={currentSubBlockIndex <= 0} style={iconButtonStyle}>
            &lt;
          </button>
          <input
            type="range"
            min="0"
            max={totalSubBlocks - 1}
            step="1"
            value={currentSubBlockIndex}
            onChange={(event) => setSubBlock(event.target.value)}
            style={{ flex: 1 }}
          />
          <button
            type="button"
            onClick={() => setSubBlock(currentSubBlockIndex + 1)}
            disabled={currentSubBlockIndex >= totalSubBlocks - 1}
            style={iconButtonStyle}
          >
            &gt;
          </button>
          <input
            type="number"
            min="1"
            max={totalSubBlocks}
            value={currentSubBlockIndex + 1}
            onChange={(event) => setSubBlock(Number(event.target.value) - 1)}
            style={styles.blockInput}
          />
          <span style={{ color: "#374151" }}>/ {totalSubBlocks}</span>
        </div>
      )}
    </div>
  );
}

function ChannelList({ channels, badChannels, hoveredChannel, onHover, onToggle }) {
  return (
    <div style={styles.channelList}>
      {channels.map((channel, index) => {
        const isBad = badChannels.includes(channel);
        const isHovered = hoveredChannel === channel;
        return (
          <button
            key={channel}
            type="button"
            onMouseEnter={() => onHover(channel)}
            onMouseLeave={() => onHover(null)}
            onClick={() => onToggle(channel)}
            title={channel}
            style={channelButtonStyle(isBad, isHovered, index)}
          >
            <span style={colorDotStyle(index, isBad, isHovered)} />
            {channel}
          </button>
        );
      })}
    </div>
  );
}

function MarkedSubBlockBar({ blocks, currentSubBlockIndex, onSelectSubBlock }) {
  if (!blocks.length) {
    return (
      <div style={styles.markedBar}>
        <span style={styles.markedLabel}>Marked sub-blocks</span>
        <span style={styles.markedEmpty}>None</span>
      </div>
    );
  }

  return (
    <div style={styles.markedBar}>
      <span style={styles.markedLabel}>Marked sub-blocks</span>
      <div style={styles.markedScroller}>
        {blocks.map((index) => {
          const active = index === currentSubBlockIndex;
          return (
            <button
              key={index}
              type="button"
              onClick={() => onSelectSubBlock?.(index)}
              style={markedButtonStyle(active)}
              title={`Go to sub-block ${index + 1}`}
            >
              {index + 1}
            </button>
          );
        })}
      </div>
    </div>
  );
}

function EmptyState({ text }) {
  return <div style={styles.emptyState}>{text}</div>;
}

function LoadingOverlay() {
  return <div style={styles.loadingOverlay}>Loading...</div>;
}

const styles = {
  shell: {
    height: "100%",
    minHeight: 0,
    display: "flex",
    flexDirection: "column",
    gap: 8,
  },
  topbar: {
    display: "flex",
    alignItems: "center",
    justifyContent: "space-between",
    gap: 12,
    flexWrap: "wrap",
  },
  tabs: {
    display: "flex",
    borderBottom: "1px solid #d1d5db",
  },
  actions: {
    display: "flex",
    alignItems: "center",
    gap: 8,
    fontSize: 13,
    flexWrap: "wrap",
  },
  controlBar: {
    display: "flex",
    alignItems: "center",
    gap: 8,
    padding: "8px 10px",
    border: "1px solid #e5e7eb",
    background: "#f8fafc",
    fontSize: 13,
  },
  markedBar: {
    display: "flex",
    alignItems: "center",
    gap: 8,
    minHeight: 34,
    padding: "6px 10px",
    border: "1px solid #fee2e2",
    background: "#fff7ed",
    fontSize: 13,
    overflow: "hidden",
  },
  markedLabel: {
    flex: "0 0 auto",
    color: "#9a3412",
    fontWeight: 700,
  },
  markedEmpty: {
    color: "#78716c",
  },
  markedScroller: {
    flex: "1 1 auto",
    minWidth: 0,
    display: "flex",
    gap: 5,
    overflowX: "auto",
    paddingBottom: 1,
  },
  plotFrame: {
    flex: 1,
    minHeight: 0,
    display: "flex",
    border: "1px solid #d1d5db",
    background: "#fff",
  },
  plotArea: {
    flex: 1,
    minWidth: 0,
    position: "relative",
  },
  waveformPlot: {
    width: "100%",
    height: "100%",
    overflowY: "auto",
    overflowX: "hidden",
  },
  psdPlot: {
    width: "100%",
    height: "100%",
    minHeight: 420,
  },
  channelList: {
    width: 190,
    borderLeft: "1px solid #e5e7eb",
    overflowY: "auto",
    padding: 8,
  },
  blockInput: {
    width: 64,
    padding: "5px 6px",
  },
  emptyState: {
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    height: "100%",
    color: "#6b7280",
  },
  loadingOverlay: {
    position: "absolute",
    inset: 0,
    zIndex: 2,
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    background: "rgba(255,255,255,0.68)",
    color: "#374151",
    fontWeight: 600,
  },
};

function tabStyle(active) {
  return {
    padding: "8px 14px",
    border: "none",
    borderBottom: active ? "2px solid #2563eb" : "2px solid transparent",
    background: active ? "#eff6ff" : "transparent",
    color: active ? "#1d4ed8" : "#374151",
    cursor: "pointer",
    fontWeight: active ? 700 : 500,
  };
}

function buttonStyle(background) {
  return {
    padding: "5px 8px",
    borderRadius: 4,
    border: "none",
    background,
    color: "#fff",
    cursor: "pointer",
    fontSize: 12,
  };
}

const iconButtonStyle = {
  width: 30,
  height: 30,
  borderRadius: 4,
  border: "1px solid #cbd5e1",
  background: "#fff",
  cursor: "pointer",
  fontSize: 18,
  lineHeight: 1,
};

function channelButtonStyle(isBad, isHovered, index) {
  return {
    width: "100%",
    display: "flex",
    alignItems: "center",
    gap: 6,
    textAlign: "left",
    padding: "5px 7px",
    marginBottom: 3,
    border: "1px solid",
    borderColor: isBad ? "#fecaca" : isHovered ? "#fde68a" : "#e5e7eb",
    borderRadius: 4,
    background: isBad ? "#fef2f2" : isHovered ? "#fffbeb" : "#fff",
    color: isBad ? BAD_COLOR : CHANNEL_COLORS[index % CHANNEL_COLORS.length] || "#111827",
    cursor: "pointer",
    fontSize: 12,
    overflow: "hidden",
    textOverflow: "ellipsis",
    whiteSpace: "nowrap",
  };
}

function markedButtonStyle(active) {
  return {
    flex: "0 0 auto",
    minWidth: 30,
    height: 24,
    padding: "0 8px",
    borderRadius: 4,
    border: active ? "1px solid #dc2626" : "1px solid #fdba74",
    background: active ? "#dc2626" : "#ffffff",
    color: active ? "#ffffff" : "#c2410c",
    cursor: "pointer",
    fontWeight: 700,
    fontSize: 12,
  };
}

function colorDotStyle(index, isBad, isHovered) {
  return {
    flex: "0 0 auto",
    width: isHovered ? 10 : 8,
    height: isHovered ? 10 : 8,
    borderRadius: "50%",
    background: isBad ? BAD_COLOR : CHANNEL_COLORS[index % CHANNEL_COLORS.length] || GOOD_COLOR,
  };
}
