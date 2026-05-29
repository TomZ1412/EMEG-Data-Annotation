import React, { useEffect, useMemo, useRef, useState } from "react";
import * as Plotly from "plotly.js-dist-min";

const BAD_COLOR = "#dc2626";
const HOVER_COLOR = "#f59e0b";
const GOOD_COLOR = "#2563eb";
const WINDOW_DURATION_SECONDS = 30;
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

const colorWithAlpha = (hex, alpha) => {
  const normalized = String(hex || "").replace("#", "");
  if (normalized.length !== 6) return `rgba(124, 58, 237, ${alpha})`;
  const value = Number.parseInt(normalized, 16);
  const r = (value >> 16) & 255;
  const g = (value >> 8) & 255;
  const b = value & 255;
  return `rgba(${r}, ${g}, ${b}, ${alpha})`;
};

const TEXT = {
  en: {
    waveform: "Waveform",
    badChannels: "bad channels",
    markAll: "Mark all",
    clear: "Clear",
    scale: "Scale",
    markedSubBlocks: "Marked sub-blocks",
    none: "None",
    noWaveformData: "No waveform data",
    noPsdData: "No PSD data",
    loading: "Loading...",
    artifactPending: (channel, time) => `Artifact start: ${channel} @ ${time.toFixed(2)}s`,
    artifactHelp: "Right-click twice on the same waveform channel to mark an artifact interval.",
    goToSubBlock: (index) => `Go to sub-block ${index + 1}`,
  },
  zh: {
    waveform: "波形",
    badChannels: "坏道",
    markAll: "全选",
    clear: "清空",
    scale: "缩放",
    markedSubBlocks: "已标注子图",
    none: "无",
    noWaveformData: "暂无波形数据",
    noPsdData: "暂无 PSD 数据",
    loading: "加载中...",
    goToSubBlock: (index) => `跳转到子图 ${index + 1}`,
  },
};

const ARTIFACT_TEXT = {
  en: {
    pending: (channel, time) => `Artifact start: ${channel} @ ${time.toFixed(2)}s`,
    help: "Right-click twice on the same waveform channel to mark an artifact interval.",
  },
  zh: {
    pending: (channel, time) => `\u4f2a\u8ff9\u8d77\u70b9\uff1a${channel} @ ${time.toFixed(2)}s`,
    help: "\u5728\u540c\u4e00\u6ce2\u5f62\u901a\u9053\u4e0a\u53f3\u952e\u4e24\u6b21\uff0c\u6807\u8bb0\u4e24\u4e2a\u65f6\u95f4\u70b9\u4e4b\u95f4\u7684\u4f2a\u8ff9\u533a\u95f4\u3002",
  },
};

export default function WaveformViewer({
  data,
  psdBadChannels = [],
  wavBadChannels = [],
  artifacts = [],
  setPsdBadChannels,
  setWavBadChannels,
  setArtifacts,
  annotationLayers = [],
  annotationReadOnly = false,
  loading,
  onSelectSubBlock,
  currentSubBlockIndex = 0,
  markedSubBlocks = [],
  language = "en",
}) {
  const waveformRef = useRef(null);
  const psdRef = useRef(null);
  const activePlotRef = useRef(null);
  const scrollTopRef = useRef(0);
  const badChannelsRef = useRef([]);

  const [activeView, setActiveView] = useState("psd");
  const [scalingFactor, setScalingFactor] = useState(8000);
  const [hoveredChannel, setHoveredChannel] = useState(null);
  const [pendingArtifact, setPendingArtifact] = useState(null);

  const totalSubBlocks = Math.max(1, Number(data?.totalSubBlocks || 1));
  const wavData = data?.wav || {};
  const psdData = data?.psd || null;
  const psdSeries = psdData?.psd || {};
  const psdFrequencies = psdData?.frequencies || [];
  const labels = TEXT[language] || TEXT.en;
  const artifactLabels = ARTIFACT_TEXT[language] || ARTIFACT_TEXT.en;
  const activeBadChannels = activeView === "psd" ? psdBadChannels : wavBadChannels;
  const setActiveBadChannels = activeView === "psd" ? setPsdBadChannels : setWavBadChannels;

  useEffect(() => {
    badChannelsRef.current = activeBadChannels;
  }, [activeBadChannels]);

  useEffect(() => {
    setPendingArtifact(null);
  }, [currentSubBlockIndex, activeView]);

  const channelNames = useMemo(() => {
    if (activeView === "psd") return Object.keys(psdSeries);
    if (activeView === "wav") return Object.keys(wavData);
    return [];
  }, [activeView, wavData, psdSeries]);

  useEffect(() => {
    if (activeView === "psd" && !Object.keys(psdSeries).length && Object.keys(wavData).length) {
      setActiveView("wav");
    }
    if (activeView === "wav" && !Object.keys(wavData).length && Object.keys(psdSeries).length) {
      setActiveView("psd");
    }
  }, [activeView, wavData, psdSeries]);

  const badChannelMatches = (item, channel, index) => {
    if (item === channel || String(item) === channel) return true;
    const numericItem = Number(item);
    return Number.isInteger(numericItem) && numericItem === index;
  };

  const isBadChannel = (badChannels, channel, index) =>
    badChannels.some((item) => badChannelMatches(item, channel, index));

  const layerBadChannels = (layer, view) => {
    const annotation = layer?.annotation || {};
    if (view === "psd") return Array.isArray(annotation.psd_bad_channels) ? annotation.psd_bad_channels : [];
    const wavBadChannels = annotation.wav_bad_channels || annotation.subblock_bad_channels || {};
    return Array.isArray(wavBadChannels?.[currentSubBlockIndex]) ? wavBadChannels[currentSubBlockIndex] : [];
  };

  const matchingAnnotationLayers = (channel, index, view = activeView) =>
    annotationLayers.filter((layer) => isBadChannel(layerBadChannels(layer, view), channel, index));

  const firstLayerColor = (channel, index, view = activeView) =>
    matchingAnnotationLayers(channel, index, view)[0]?.color || null;

  const layerUserText = (channel, index, view = activeView) => {
    const users = matchingAnnotationLayers(channel, index, view)
      .map((layer) => layer.user)
      .filter(Boolean);
    return users.length ? users.join(", ") : "";
  };

  useEffect(() => {
    return () => {
      if (activePlotRef.current) Plotly.purge(activePlotRef.current);
    };
  }, []);

  const toggleChannel = (channel) => {
    if (annotationReadOnly) return;
    if (!channel || !setActiveBadChannels) return;
    const currentBadChannels = badChannelsRef.current;
    const index = channelNames.indexOf(channel);
    const alreadyBad = currentBadChannels.some((item) => badChannelMatches(item, channel, index));
    setActiveBadChannels(
      alreadyBad
        ? currentBadChannels.filter((item) => !badChannelMatches(item, channel, index))
        : [...currentBadChannels, channel]
    );
  };

  const toggleSelectedChannels = (channels) => {
    if (annotationReadOnly) return;
    if (!channels.length || !setActiveBadChannels) return;
    const currentBadChannels = badChannelsRef.current;
    const uniqueChannels = [...new Set(channels)];
    const shouldClear = uniqueChannels.every((channel) =>
      currentBadChannels.some((item) => badChannelMatches(item, channel, channelNames.indexOf(channel)))
    );
    if (shouldClear) {
      setActiveBadChannels(
        currentBadChannels.filter(
          (item) => !uniqueChannels.some((channel) => badChannelMatches(item, channel, channelNames.indexOf(channel)))
        )
      );
    } else {
      setActiveBadChannels([...new Set([...currentBadChannels, ...uniqueChannels])]);
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
        isBadChannel(currentBadChannels, channel, index)
          ? BAD_COLOR
          : hoveredChannel === channel
            ? HOVER_COLOR
            : firstLayerColor(channel, index, "psd") || CHANNEL_COLORS[index % CHANNEL_COLORS.length] || GOOD_COLOR
      ),
      widths: channels.map((channel, index) =>
        isBadChannel(currentBadChannels, channel, index) || hoveredChannel === channel || firstLayerColor(channel, index, "psd") ? 2.4 : 1
      ),
      opacities: channels.map((channel, index) =>
        isBadChannel(currentBadChannels, channel, index) || hoveredChannel === channel || firstLayerColor(channel, index, "psd") ? 1 : 0.58
      ),
    };
  };

  const wavTraceStyle = (channels) => {
    const currentBadChannels = badChannelsRef.current;
    return {
      colors: channels.map((channel, index) =>
        isBadChannel(currentBadChannels, channel, index)
          ? BAD_COLOR
          : hoveredChannel === channel
            ? HOVER_COLOR
            : firstLayerColor(channel, index, "wav") || GOOD_COLOR
      ),
      widths: channels.map((channel, index) =>
        isBadChannel(currentBadChannels, channel, index) || hoveredChannel === channel || firstLayerColor(channel, index, "wav") ? 2.4 : 1
      ),
      opacities: channels.map((channel, index) =>
        isBadChannel(currentBadChannels, channel, index) || hoveredChannel === channel || firstLayerColor(channel, index, "wav") ? 1 : 0.88
      ),
    };
  };

  const channelLine = (channel, index = 0, colorful = false) => {
    const currentBadChannels = activeView === "psd" ? psdBadChannels : wavBadChannels;
    const isBad = isBadChannel(currentBadChannels, channel, index);
    const isHovered = hoveredChannel === channel;
    const overlayColor = firstLayerColor(channel, index, activeView);
    return {
      color: isBad
        ? BAD_COLOR
        : isHovered
          ? HOVER_COLOR
          : overlayColor
            ? overlayColor
          : colorful
            ? CHANNEL_COLORS[index % CHANNEL_COLORS.length] || GOOD_COLOR
            : GOOD_COLOR,
      width: isBad || isHovered || overlayColor ? 2.4 : 1,
    };
  };

  const normalizeArtifactTime = (time) => Math.max(0, Math.min(WINDOW_DURATION_SECONDS, Number(time) || 0));
  const currentWindowStart = currentSubBlockIndex * WINDOW_DURATION_SECONDS;

  const artifactShapes = (channels, offset) =>
    artifacts
      .filter((item) => item?.channel && Number.isFinite(Number(item.start_time)) && Number.isFinite(Number(item.end_time)))
      .map((item) => {
        const index = channels.indexOf(item.channel);
        if (index < 0) return null;
        const globalStart = Number(item.start_time);
        const globalEnd = Number(item.end_time);
        if (globalStart >= currentWindowStart + WINDOW_DURATION_SECONDS || globalEnd <= currentWindowStart) return null;
        const center = (channels.length - index - 1) * offset;
        return {
          type: "rect",
          xref: "x",
          yref: "y",
          x0: normalizeArtifactTime(globalStart - currentWindowStart),
          x1: normalizeArtifactTime(globalEnd - currentWindowStart),
          y0: center - offset * 0.38,
          y1: center + offset * 0.38,
          fillcolor: "rgba(245, 158, 11, 0.18)",
          line: { color: "rgba(245, 158, 11, 0.7)", width: 1 },
          layer: "below",
        };
      })
      .filter(Boolean);

  const annotationLayerArtifactShapes = (channels, offset) =>
    annotationLayers.flatMap((layer) => {
      const layerArtifacts = Array.isArray(layer?.annotation?.artifacts) ? layer.annotation.artifacts : [];
      return layerArtifacts
        .filter((item) => item?.channel && Number.isFinite(Number(item.start_time)) && Number.isFinite(Number(item.end_time)))
        .map((item) => {
          const index = channels.indexOf(item.channel);
          if (index < 0) return null;
          const globalStart = Number(item.start_time);
          const globalEnd = Number(item.end_time);
          if (globalStart >= currentWindowStart + WINDOW_DURATION_SECONDS || globalEnd <= currentWindowStart) return null;
          const center = (channels.length - index - 1) * offset;
          return {
            type: "rect",
            xref: "x",
            yref: "y",
            x0: normalizeArtifactTime(globalStart - currentWindowStart),
            x1: normalizeArtifactTime(globalEnd - currentWindowStart),
            y0: center - offset * 0.28,
            y1: center + offset * 0.28,
            fillcolor: colorWithAlpha(layer.color, 0.2),
            line: { color: layer.color || "#7c3aed", width: 1 },
            layer: "below",
          };
        })
        .filter(Boolean);
    });

  const pointFromContextMenu = (event, plotDiv, channels, offset) => {
    const layout = plotDiv?._fullLayout;
    const xaxis = layout?.xaxis;
    const yaxis = layout?.yaxis;
    if (!xaxis?.p2d || !yaxis?.p2d || !layout?._size) return null;

    const rect = plotDiv.getBoundingClientRect();
    const xPixel = event.clientX - rect.left - layout._size.l;
    const yPixel = event.clientY - rect.top - layout._size.t;
    const time = normalizeArtifactTime(xaxis.p2d(xPixel));
    const yValue = yaxis.p2d(yPixel);
    const channelIndex = channels.length - 1 - Math.round(yValue / offset);
    if (channelIndex < 0 || channelIndex >= channels.length) return null;
    return { channel: channels[channelIndex], time };
  };

  const handleArtifactContextMenu = (event, plotDiv, channels, offset) => {
    if (annotationReadOnly) return;
    if (!setArtifacts) return;
    event.preventDefault();
    event.stopPropagation();
    const container = waveformRef.current;
    if (container) scrollTopRef.current = container.scrollTop;
    const point = pointFromContextMenu(event, plotDiv, channels, offset);
    if (!point) return;

    if (!pendingArtifact || pendingArtifact.channel !== point.channel) {
      setPendingArtifact({
        ...point,
        globalTime: currentSubBlockIndex * WINDOW_DURATION_SECONDS + point.time,
      });
      return;
    }

    const pointGlobalTime = currentSubBlockIndex * WINDOW_DURATION_SECONDS + point.time;
    const start = Math.min(pendingArtifact.globalTime, pointGlobalTime);
    const end = Math.max(pendingArtifact.globalTime, pointGlobalTime);
    if (Math.abs(end - start) < 0.01) return;
    setArtifacts([...artifacts, { channel: point.channel, start_time: start, end_time: end }]);
    setPendingArtifact(null);
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

      const totalDuration = WINDOW_DURATION_SECONDS;
      const time = Array.from({ length: samples }, (_, index) => index * (totalDuration / samples));
      const offset = 0.75;

      const traces = channels.map((channel, index) => {
        const values = wavData[channel] || [];
        const mean = values.reduce((sum, value) => sum + value, 0) / Math.max(1, values.length);
        const line = channelLine(channel, index, false);
        const overlayUsers = layerUserText(channel, index, "wav");
        return {
          x: time.slice(0, values.length),
          y: values.map((value) => (value - mean) * scalingFactor + (channels.length - index - 1) * offset),
          name: channel,
          mode: "lines",
          line,
          hovertemplate: overlayUsers
            ? `${channel}<br>Time: %{x:.2f}s<br>Other users: ${overlayUsers}<extra></extra>`
            : `${channel}<br>Time: %{x:.2f}s<extra></extra>`,
          opacity: isBadChannel(wavBadChannels, channel, index) ? 1 : 0.88,
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
          color: isBadChannel(wavBadChannels, channel, index) ? BAD_COLOR : firstLayerColor(channel, index, "wav") || "#111827",
        },
        xanchor: "right",
        align: "right",
      }));
      const shapes = [...artifactShapes(channels, offset), ...annotationLayerArtifactShapes(channels, offset)];
      if (pendingArtifact && channels.includes(pendingArtifact.channel)) {
        const index = channels.indexOf(pendingArtifact.channel);
        const center = (channels.length - index - 1) * offset;
        shapes.push({
          type: "line",
          xref: "x",
          yref: "y",
          x0: pendingArtifact.globalTime - currentWindowStart,
          x1: pendingArtifact.globalTime - currentWindowStart,
          y0: center - offset * 0.45,
          y1: center + offset * 0.45,
          line: { color: "#f59e0b", width: 2, dash: "dot" },
        });
      }

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
          shapes,
          autosize: true,
        },
        { displayModeBar: false, responsive: true }
      );

      if (cancelled) return;
      plotDiv.on("plotly_click", (event) => {
        if (event?.event?.button !== 0) return;
        scrollTopRef.current = container.scrollTop;
        toggleChannel(event.points?.[0]?.data?.name);
      });
      plotDiv.on("plotly_hover", (event) => setHoveredChannel(event.points?.[0]?.data?.name || null));
      plotDiv.on("plotly_unhover", () => setHoveredChannel(null));
      plotDiv.addEventListener("contextmenu", (event) => handleArtifactContextMenu(event, plotDiv, channels, offset));
      container.scrollTop = scrollTopRef.current;
    };

    render();
    return () => {
      cancelled = true;
    };
  }, [activeView, wavData, wavBadChannels, artifacts, pendingArtifact, scalingFactor, annotationLayers]);

  useEffect(() => {
    if (activeView !== "wav" || !activePlotRef.current || !Object.keys(wavData).length) return;
    const channels = Object.keys(wavData);
    const style = wavTraceStyle(channels);
    Plotly.restyle(activePlotRef.current, {
      "line.color": style.colors,
      "line.width": style.widths,
      opacity: style.opacities,
    });
  }, [activeView, wavData, wavBadChannels, hoveredChannel, annotationLayers]);

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
        const overlayUsers = layerUserText(channel, index, "psd");
        return {
          x: psdFrequencies,
          y: psdSeries[channel],
          name: channel,
          mode: "lines",
          line: { color: style.colors[index], width: style.widths[index] },
          opacity: style.opacities[index],
          hovertemplate: overlayUsers
            ? `${channel}<br>Frequency: %{x:.2f} Hz<br>PSD: %{y}<br>Other users: ${overlayUsers}<extra></extra>`
            : `${channel}<br>Frequency: %{x:.2f} Hz<br>PSD: %{y}<extra></extra>`,
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
  }, [activeView, psdFrequencies, psdSeries, annotationLayers]);

  useEffect(() => {
    if (activeView !== "psd" || !activePlotRef.current || !Object.keys(psdSeries).length) return;
    const channels = Object.keys(psdSeries);
    const style = psdTraceStyle(channels);
    Plotly.restyle(activePlotRef.current, {
      "line.color": style.colors,
      "line.width": style.widths,
      opacity: style.opacities,
    });
  }, [activeView, psdSeries, psdBadChannels, hoveredChannel, annotationLayers]);

  const setAllChannels = () => {
    if (annotationReadOnly) return;
    if (channelNames.length && setActiveBadChannels) setActiveBadChannels(channelNames);
  };

  const clearChannels = () => {
    if (annotationReadOnly) return;
    if (setActiveBadChannels) setActiveBadChannels([]);
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
            ["wav", labels.waveform],
          ].map(([key, label]) => (
            <button key={key} onClick={() => setActiveView(key)} style={tabStyle(activeView === key)}>
              {label}
            </button>
          ))}
        </div>

        <div style={styles.actions}>
          <strong>{activeBadChannels.length}</strong>
          <span>/ {channelNames.length} {labels.badChannels}</span>
          <button type="button" onClick={setAllChannels} disabled={!channelNames.length || loading || annotationReadOnly} style={buttonStyle("#dc2626")}>
            {labels.markAll}
          </button>
          <button type="button" onClick={clearChannels} disabled={!activeBadChannels.length || loading || annotationReadOnly} style={buttonStyle("#f59e0b")}>
            {labels.clear}
          </button>
        </div>
      </div>

      {activeView === "wav" && (
        <div style={styles.controlBar}>
          <span style={{ minWidth: 88 }}>{labels.scale} {scalingFactor.toFixed(2)}x</span>
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
          labels={labels}
        />
      )}

      {activeView === "wav" && (
        <div style={styles.artifactHint}>
          {pendingArtifact
            ? artifactLabels.pending(pendingArtifact.channel, pendingArtifact.globalTime)
            : artifactLabels.help}
        </div>
      )}

      <div style={styles.plotFrame}>
        <div style={styles.plotArea}>
          {loading && <LoadingOverlay text={labels.loading} />}
          {activeView === "wav" ? (
            Object.keys(wavData).length ? (
              <div ref={waveformRef} style={styles.waveformPlot} />
            ) : (
              <EmptyState text={labels.noWaveformData} />
            )
          ) : Object.keys(psdSeries).length ? (
            <div ref={psdRef} style={styles.psdPlot} />
          ) : (
            <EmptyState text={labels.noPsdData} />
          )}
        </div>

        {activeView === "psd" && Object.keys(psdSeries).length > 0 && (
          <ChannelList
            channels={Object.keys(psdSeries)}
            badChannels={psdBadChannels}
            annotationLayers={annotationLayers}
            hoveredChannel={hoveredChannel}
            onHover={setHoveredChannel}
            onToggle={toggleChannel}
            isBadChannel={isBadChannel}
            matchingAnnotationLayers={(channel, index) => matchingAnnotationLayers(channel, index, "psd")}
            layerUserText={(channel, index) => layerUserText(channel, index, "psd")}
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

function ChannelList({ channels, badChannels, hoveredChannel, onHover, onToggle, isBadChannel, matchingAnnotationLayers, layerUserText }) {
  return (
    <div style={styles.channelList}>
      {channels.map((channel, index) => {
        const isBad = isBadChannel(badChannels, channel, index);
        const isHovered = hoveredChannel === channel;
        const layers = matchingAnnotationLayers?.(channel, index) || [];
        const users = layerUserText?.(channel, index) || "";
        return (
          <button
            key={channel}
            type="button"
            onMouseEnter={() => onHover(channel)}
            onMouseLeave={() => onHover(null)}
            onClick={() => onToggle(channel)}
            title={users ? `${channel}\nOther users: ${users}` : channel}
            style={channelButtonStyle(isBad, isHovered, index)}
          >
            <span style={colorDotStyle(index, isBad, isHovered)} />
            {channel}
            {layers.length > 0 && (
              <span style={styles.layerDots}>
                {layers.slice(0, 4).map((layer) => (
                  <span key={layer.user} title={layer.user} style={{ ...styles.layerDot, background: layer.color }} />
                ))}
              </span>
            )}
          </button>
        );
      })}
    </div>
  );
}

function MarkedSubBlockBar({ blocks, currentSubBlockIndex, onSelectSubBlock, labels }) {
  if (!blocks.length) {
    return (
      <div style={styles.markedBar}>
        <span style={styles.markedLabel}>{labels.markedSubBlocks}</span>
        <span style={styles.markedEmpty}>{labels.none}</span>
      </div>
    );
  }

  return (
    <div style={styles.markedBar}>
      <span style={styles.markedLabel}>{labels.markedSubBlocks}</span>
      <div style={styles.markedScroller}>
        {blocks.map((index) => {
          const active = index === currentSubBlockIndex;
          return (
            <button
              key={index}
              type="button"
              onClick={() => onSelectSubBlock?.(index)}
              style={markedButtonStyle(active)}
              title={labels.goToSubBlock(index)}
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

function LoadingOverlay({ text }) {
  return <div style={styles.loadingOverlay}>{text}</div>;
}

const styles = {
  shell: {
    height: "100%",
    minHeight: 0,
    minWidth: 0,
    display: "flex",
    flexDirection: "column",
    gap: 8,
    overflow: "hidden",
    contain: "layout paint",
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
  artifactHint: {
    padding: "6px 10px",
    border: "1px solid #fde68a",
    background: "#fffbeb",
    color: "#92400e",
    fontSize: 12,
  },
  plotFrame: {
    flex: 1,
    minHeight: 0,
    minWidth: 0,
    display: "flex",
    border: "1px solid #d1d5db",
    background: "#fff",
    overflow: "hidden",
    contain: "layout paint",
  },
  plotArea: {
    flex: 1,
    minWidth: 0,
    position: "relative",
    overflow: "hidden",
    contain: "layout paint",
  },
  waveformPlot: {
    width: "100%",
    height: "100%",
    overflowY: "auto",
    overflowX: "hidden",
    contain: "layout paint",
  },
  psdPlot: {
    width: "100%",
    height: "100%",
    minHeight: 420,
    overflow: "hidden",
    contain: "layout paint",
  },
  channelList: {
    width: 190,
    borderLeft: "1px solid #e5e7eb",
    overflowY: "auto",
    padding: 8,
  },
  layerDots: {
    flex: "0 0 auto",
    display: "inline-flex",
    alignItems: "center",
    gap: 2,
    marginLeft: "auto",
  },
  layerDot: {
    width: 7,
    height: 7,
    borderRadius: "50%",
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
