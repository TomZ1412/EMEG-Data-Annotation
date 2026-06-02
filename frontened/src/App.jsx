import React, { useEffect, useMemo, useRef, useState } from "react";
import axios from "axios";
import FileTree from "./components/FileTree.jsx";
import WaveformViewer from "./components/WaveformViewer.jsx";

const API_BASE_URL = (import.meta.env.VITE_API_HOST || "localhost:10000")
  .replace(/^https?:\/\//, "")
  .replace(/\/api\/?$/, "");

const apiUrl = (path) => `http://${API_BASE_URL}/api${path}`;

const ARTIFACT_WINDOW_SECONDS = 30;
const emptyAnnotation = {
  psd_bad_channels: [],
  wav_bad_channels: {},
  psd_channel_scores: {},
  wav_channel_scores: {},
  artifacts: [],
  discarded: false,
};
const LAYER_COLORS = [
  "#7c3aed",
  "#059669",
  "#d97706",
  "#0891b2",
  "#db2777",
  "#4f46e5",
  "#65a30d",
  "#dc2626",
  "#0d9488",
  "#9333ea",
  "#ca8a04",
  "#0284c7",
];

const TEXT = {
  en: {
    enterUsername: "Please enter your username",
    newUsername: "Please enter a new username",
    loadFileListError: "Failed to load the file list. Please check the backend service and Nginx proxy.",
    fileBusy: "This file is being annotated by another user.",
    startAnnotationError: "Failed to start annotation. Please try again later.",
    loadVisualizationError: "Failed to load visualization data. Please check whether the data file is complete.",
    setUserFirst: "Please set a username first.",
    annotationSaved: (action) => `Annotation saved (${action})`,
    submitError: "Failed to submit annotation. Please try again.",
    allAnnotated: "All files have been annotated.",
    allAnnotatedOrBusy: "All files are annotated or currently busy.",
    nextFileError: "Failed to get the next file. Please try again later.",
    title: "EEG Data Annotation",
    currentFile: (current, total) => `Current file ${current}/${total}`,
    selectFile: "Select a file from the left to start annotation",
    refreshFiles: "Refresh files",
    setUser: "Set user",
    language: "中文",
    current: "Current",
    subBlock: "Sub-block",
    discardFile: "Discard this file",
    psdBadChannels: "PSD bad channels",
    currentWavBadChannels: "Current waveform bad channels",
    psdChannelScores: "PSD channel scores",
    currentWavChannelScores: "Current waveform scores",
    markedSubBlocks: "Marked waveform sub-blocks",
    artifactSegments: "Artifact segments",
    overlayMode: "Other annotations",
    overlayModes: {
      mine: "Mine only",
      others: "Show others",
      othersOnly: "Others only",
    },
    none: "None",
    submitAnnotation: "Submit annotation",
    submitting: "Submitting...",
    refreshData: "Refresh data",
    nextUnannotated: "Next unannotated",
    loadingFileList: "Loading file list...",
    selectDataFile: "Select a data file from the left.",
  },
  zh: {
    enterUsername: "请输入您的用户名",
    newUsername: "请输入新的用户名",
    loadFileListError: "获取文件列表失败，请检查后端服务和 Nginx 代理配置。",
    fileBusy: "该文件正在被其他用户标注。",
    startAnnotationError: "开始标注失败，请稍后重试。",
    loadVisualizationError: "加载可视化数据失败，请检查数据文件是否完整。",
    setUserFirst: "请先设置用户名。",
    annotationSaved: (action) => `标注已保存 (${action})`,
    submitError: "提交标注失败，请重试。",
    allAnnotated: "所有文件都已标注完成。",
    allAnnotatedOrBusy: "所有文件都已标注完成或正在被其他用户标注。",
    nextFileError: "获取下一个文件失败，请稍后重试。",
    title: "EEG 数据标注",
    currentFile: (current, total) => `当前文件 ${current}/${total}`,
    selectFile: "请选择左侧文件开始标注",
    refreshFiles: "刷新文件",
    setUser: "设置用户",
    language: "English",
    current: "当前",
    subBlock: "子图",
    discardFile: "弃用该数据",
    psdBadChannels: "PSD 坏道",
    currentWavBadChannels: "当前波形坏道",
    psdChannelScores: "PSD 通道评分",
    currentWavChannelScores: "当前波形评分",
    markedSubBlocks: "已标注波形子图",
    none: "无",
    submitAnnotation: "提交标注",
    submitting: "正在提交...",
    refreshData: "刷新数据",
    nextUnannotated: "下一个未标注",
    loadingFileList: "正在加载文件列表...",
    selectDataFile: "请从左侧选择一个数据文件。",
  },
};

function flattenFiles(nodes = []) {
  const files = [];
  const walk = (items) => {
    items.forEach((item) => {
      if (item.type === "file") files.push(item);
      if (item.children) walk(item.children);
    });
  };
  walk(nodes);
  return files;
}

function displayRelativePath(filePath) {
  if (!filePath) return "";
  const normalized = filePath.replace(/\\/g, "/");
  const processedIndex = normalized.lastIndexOf("/processed/");
  if (processedIndex >= 0) {
    return normalized.slice(processedIndex + "/processed/".length);
  }
  const dataIndex = normalized.lastIndexOf("/data/");
  if (dataIndex >= 0) {
    return normalized.slice(dataIndex + 1);
  }
  return normalized.replace(/^\/+/, "");
}

function normalizeArtifacts(value) {
  if (Array.isArray(value)) return value;
  if (!value || typeof value !== "object") return [];

  return Object.entries(value).flatMap(([blockIndex, items]) => {
    const offset = Number(blockIndex) * ARTIFACT_WINDOW_SECONDS;
    if (!Array.isArray(items)) return [];
    return items
      .filter((item) => item?.channel)
      .map((item) => ({
        channel: item.channel,
        start_time: offset + Number(item.start_time || 0),
        end_time: offset + Number(item.end_time || 0),
      }));
  });
}

function normalizeChannelScores(value) {
  if (!value || typeof value !== "object" || Array.isArray(value)) return {};
  return Object.entries(value).reduce((scores, [channel, rawScore]) => {
    const score = Number(rawScore);
    if (Number.isInteger(score) && score >= 1 && score <= 5) {
      scores[channel] = score;
    }
    return scores;
  }, {});
}

function normalizeSubblockScores(value) {
  if (!value || typeof value !== "object" || Array.isArray(value)) return {};
  return Object.entries(value).reduce((subblocks, [blockIndex, scores]) => {
    const normalized = normalizeChannelScores(scores);
    if (Object.keys(normalized).length) subblocks[blockIndex] = normalized;
    return subblocks;
  }, {});
}

function formatScores(scores = {}) {
  const entries = Object.entries(scores).sort(([left], [right]) => left.localeCompare(right));
  return entries.length ? entries.map(([channel, score]) => `${channel}: ${score}`).join(", ") : "";
}

function diffChannelScores(current = {}, base = {}) {
  const diff = {};
  const channels = new Set([...Object.keys(current || {}), ...Object.keys(base || {})]);
  channels.forEach((channel) => {
    const currentScore = Number(current?.[channel] || 0);
    const baseScore = Number(base?.[channel] || 0);
    if (currentScore === baseScore) return;
    diff[channel] = currentScore;
  });
  return diff;
}

function diffSubblockScores(current = {}, base = {}) {
  const diff = {};
  const blockIndexes = new Set([...Object.keys(current || {}), ...Object.keys(base || {})]);
  blockIndexes.forEach((blockIndex) => {
    const blockDiff = diffChannelScores(current?.[blockIndex] || {}, base?.[blockIndex] || {});
    if (Object.keys(blockDiff).length) diff[blockIndex] = blockDiff;
  });
  return diff;
}

function decorateAnnotationLayers(layers = [], currentUser = "") {
  const orderedLayers = [...layers].sort((left, right) => {
    if (left.user === currentUser) return -1;
    if (right.user === currentUser) return 1;
    return String(left.user || "").localeCompare(String(right.user || ""));
  });

  return orderedLayers.map((layer, index) => ({
    ...layer,
    color: LAYER_COLORS[index % LAYER_COLORS.length],
    isCurrentUser: Boolean(currentUser) && layer.user === currentUser,
  }));
}

function App() {
  const [fileTree, setFileTree] = useState([]);
  const [selectedFile, setSelectedFile] = useState(null);
  const [visData, setVisData] = useState({});
  const [psdBadChannels, setPsdBadChannels] = useState([]);
  const [wavBadChannels, setWavBadChannels] = useState({});
  const [psdChannelScores, setPsdChannelScores] = useState({});
  const [wavChannelScores, setWavChannelScores] = useState({});
  const [artifactSegments, setArtifactSegments] = useState([]);
  const [loadingTree, setLoadingTree] = useState(false);
  const [loadingData, setLoadingData] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState(null);
  const [currentUser, setCurrentUser] = useState("");
  const [subBlockIndex, setSubBlockIndex] = useState(0);
  const [isDataDiscarded, setIsDataDiscarded] = useState(false);
  const [fileAnnotationCache, setFileAnnotationCache] = useState({});
  const [annotationLayers, setAnnotationLayers] = useState([]);
  const [llmPreannotation, setLlmPreannotation] = useState(emptyAnnotation);
  const [llmPreannotationEnabled, setLlmPreannotationEnabled] = useState(false);
  const [overlayMode, setOverlayMode] = useState("mine");
  const [selectedOverlayUser, setSelectedOverlayUser] = useState("");
  const [language, setLanguage] = useState(() => localStorage.getItem("annotation_language") || "en");
  const [annotationMode, setAnnotationMode] = useState("bad_channel");

  const keepAliveRef = useRef(null);
  const activeFileRef = useRef(null);
  const visualizationCacheRef = useRef(new Map());
  const psdCacheRef = useRef(new Map());
  const visualizationRequestRef = useRef(0);

  const allFiles = useMemo(() => flattenFiles(fileTree), [fileTree]);
  const selectedFileIndex = allFiles.findIndex((file) => file.path === selectedFile);
  const labels = TEXT[language] || TEXT.en;
  const isScoreMode = annotationMode === "channel_score";
  const currentWavScoreMap = wavChannelScores[subBlockIndex] || {};
  const currentWavBadChannels = isScoreMode ? [] : wavBadChannels[subBlockIndex] || [];
  const currentArtifactStart = subBlockIndex * ARTIFACT_WINDOW_SECONDS;
  const currentArtifactEnd = currentArtifactStart + ARTIFACT_WINDOW_SECONDS;
  const currentArtifacts = artifactSegments.filter((item) => {
    const start = Number(item.start_time);
    const end = Number(item.end_time);
    return Number.isFinite(start) && Number.isFinite(end) && start < currentArtifactEnd && end > currentArtifactStart;
  });
  const selectedRelativePath = displayRelativePath(selectedFile);
  const decoratedAnnotationLayers = useMemo(
    () => decorateAnnotationLayers(annotationLayers, currentUser),
    [annotationLayers, currentUser]
  );
  const visibleAnnotationLayers = useMemo(() => {
    if (overlayMode === "mine") return [];
    const otherLayers = decoratedAnnotationLayers.filter((layer) => !layer.isCurrentUser);
    if (!selectedOverlayUser) return [];
    return otherLayers.filter((layer) => layer.user === selectedOverlayUser);
  }, [decoratedAnnotationLayers, overlayMode, selectedOverlayUser]);
  const overlayLegendLayers = useMemo(
    () => decoratedAnnotationLayers.filter((layer) => !layer.isCurrentUser),
    [decoratedAnnotationLayers]
  );
  const showCurrentAnnotation = overlayMode !== "othersOnly";
  const overlayLabels = labels.overlayModes || TEXT.en.overlayModes;

  useEffect(() => {
    axios
      .get(apiUrl("/health"))
      .then((res) => {
        setAnnotationMode(res.data?.annotation_mode === "channel_score" ? "channel_score" : "bad_channel");
      })
      .catch((err) => console.error("Failed to load server settings", err));
  }, []);

  useEffect(() => {
    const savedUser = localStorage.getItem("annotation_user");
    if (savedUser) {
      setCurrentUser(savedUser);
      return;
    }

    const user = prompt(labels.enterUsername);
    if (user?.trim()) {
      setCurrentUser(user.trim());
      localStorage.setItem("annotation_user", user.trim());
    }
  }, [labels.enterUsername]);

  useEffect(() => {
    if (!currentUser) return;
    fetchFileTree();
  }, [currentUser]);

  useEffect(() => {
    return () => {
      if (keepAliveRef.current) clearInterval(keepAliveRef.current);
      if (activeFileRef.current) endAnnotation(activeFileRef.current);
    };
  }, []);

  useEffect(() => {
    if (fileTree.length > 0 && !selectedFile && currentUser) {
      handleNextUnannotated();
    }
  }, [fileTree, currentUser]);

  useEffect(() => {
    if (!selectedFile || !currentUser) return;

    let cancelled = false;

    const openFile = async () => {
      setLoadingData(true);
      setError(null);

      const started = await startAnnotation(selectedFile);
      if (cancelled) {
        setLoadingData(false);
        return;
      }

      if (!started) {
        setSelectedFile(null);
        setVisData({});
        setLoadingData(false);
        return;
      }

      activeFileRef.current = selectedFile;
      startKeepAlive(selectedFile);

      await fetchAnnotationData(selectedFile);
      await fetchAnnotationLayers(selectedFile);

      if (!cancelled) {
        fetchVisualizationData(selectedFile, subBlockIndex);
      } else {
        setLoadingData(false);
      }
    };

    openFile();

    return () => {
      cancelled = true;
    };
  }, [selectedFile, currentUser]);

  useEffect(() => {
    if (!selectedFile || !currentUser) return;
    fetchVisualizationData(selectedFile, subBlockIndex);
  }, [subBlockIndex]);

  const fetchFileTree = async (refresh = false) => {
    if (!currentUser) return;
    setLoadingTree(true);
    try {
      const res = await axios.get(apiUrl("/file_tree"), {
        params: { user: currentUser, ...(refresh ? { refresh: true } : {}) },
      });
      setFileTree(res.data);
      setError(null);
    } catch (err) {
      console.error("Failed to load file list", err);
      setError(labels.loadFileListError);
    } finally {
      setLoadingTree(false);
    }
  };

  const startAnnotation = async (filePath) => {
    if (!currentUser) return false;
    try {
      await axios.post(apiUrl("/start_annotation"), {
        file_path: filePath,
        user: currentUser,
      });
      return true;
    } catch (err) {
      if (err.response?.status === 409) {
        alert(err.response.data?.detail || labels.fileBusy);
      } else {
        console.error("Failed to start annotation", err);
        alert(labels.startAnnotationError);
      }
      return false;
    }
  };

  const endAnnotation = async (filePath) => {
    if (!currentUser || !filePath) return;
    try {
      await axios.post(apiUrl("/end_annotation"), {
        file_path: filePath,
        user: currentUser,
      });
    } catch (err) {
      console.error("Failed to end annotation", err);
    }
  };

  const startKeepAlive = (filePath) => {
    if (keepAliveRef.current) clearInterval(keepAliveRef.current);
    keepAliveRef.current = setInterval(() => {
      axios
        .post(apiUrl("/keep_alive"), {
          file_path: filePath,
          user: currentUser,
        })
        .catch((err) => console.error("Keep-alive failed", err));
    }, 60000);
  };

  const fetchVisualizationData = async (filePath, blockIndex = 0, force = false) => {
    const cacheKey = `${filePath}::${blockIndex}`;
    const psdKey = filePath;
    const requestId = ++visualizationRequestRef.current;

    if (!force && visualizationCacheRef.current.has(cacheKey) && psdCacheRef.current.has(psdKey)) {
      setVisData({
        ...visualizationCacheRef.current.get(cacheKey),
        psd: psdCacheRef.current.get(psdKey),
      });
      setError(null);
      setLoadingData(false);
      return;
    }

    setLoadingData(true);
    setError(null);

    try {
      const wavRequest = axios.get(apiUrl(`/visualization/${filePath}`), {
        params: { sub_block: blockIndex, include_psd: false },
      });
      const psdRequest = !force && psdCacheRef.current.has(psdKey)
        ? Promise.resolve({ data: psdCacheRef.current.get(psdKey) })
        : axios.get(apiUrl(`/visualization_psd/${filePath}`));
      const [wavRes, psdRes] = await Promise.all([wavRequest, psdRequest]);
      if (requestId !== visualizationRequestRef.current) return;
      visualizationCacheRef.current.set(cacheKey, wavRes.data);
      psdCacheRef.current.set(psdKey, psdRes.data);
      setVisData({ ...wavRes.data, psd: psdRes.data });
      setError(null);
    } catch (err) {
      if (requestId !== visualizationRequestRef.current) return;
      console.error("Failed to load visualization data", err);
      setVisData({});
      setError(labels.loadVisualizationError);
    } finally {
      if (requestId === visualizationRequestRef.current) setLoadingData(false);
    }
  };

  const applyAnnotation = (annotation) => {
    setPsdBadChannels(annotation.psd_bad_channels || []);
    setWavBadChannels(annotation.wav_bad_channels || {});
    setPsdChannelScores(normalizeChannelScores(annotation.psd_channel_scores));
    setWavChannelScores(normalizeSubblockScores(annotation.wav_channel_scores || annotation.subblock_channel_scores));
    setLlmPreannotation({
      psd_channel_scores: normalizeChannelScores(annotation.llm_preannotation?.psd_channel_scores),
      wav_channel_scores: normalizeSubblockScores(
        annotation.llm_preannotation?.wav_channel_scores || annotation.llm_preannotation?.subblock_channel_scores
      ),
    });
    setLlmPreannotationEnabled(Boolean(annotation.llm_preannotation_enabled));
    setArtifactSegments(normalizeArtifacts(annotation.artifacts));
    setIsDataDiscarded(Boolean(annotation.discarded));
  };

  const fetchAnnotationData = async (filePath) => {
    try {
      const res = await axios.get(apiUrl(`/annotation/${filePath}`), {
        params: { user: currentUser },
      });
      const annotation = {
        psd_bad_channels: res.data?.psd_bad_channels || [],
        wav_bad_channels: res.data?.wav_bad_channels || res.data?.subblock_bad_channels || {},
        psd_channel_scores: normalizeChannelScores(res.data?.psd_channel_scores),
        wav_channel_scores: normalizeSubblockScores(res.data?.wav_channel_scores || res.data?.subblock_channel_scores),
        llm_preannotation: res.data?.llm_preannotation || null,
        llm_preannotation_enabled: Boolean(res.data?.llm_preannotation_enabled),
        artifacts: normalizeArtifacts(res.data?.artifacts),
        discarded: Boolean(res.data?.discarded),
      };
      setFileAnnotationCache((prev) => ({ ...prev, [filePath]: annotation }));
      applyAnnotation(annotation);
      return annotation;
    } catch (err) {
      console.error("Failed to load annotation data", err);
      setFileAnnotationCache((prev) => ({ ...prev, [filePath]: emptyAnnotation }));
      applyAnnotation(emptyAnnotation);
      return emptyAnnotation;
    }
  };

  const fetchAnnotationLayers = async (filePath) => {
    try {
      const res = await axios.get(apiUrl(`/annotation_layers/${filePath}`), {
        params: { user: currentUser },
      });
      setAnnotationLayers(Array.isArray(res.data?.layers) ? res.data.layers : []);
    } catch (err) {
      console.error("Failed to load annotation layers", err);
      setAnnotationLayers([]);
    }
  };

  const handleFileSelect = async (filePath) => {
    if (!filePath) return;
    if (filePath === selectedFile) {
      visualizationCacheRef.current.delete(`${filePath}::${subBlockIndex}`);
      psdCacheRef.current.delete(filePath);
      await fetchAnnotationData(filePath);
      await fetchAnnotationLayers(filePath);
      fetchVisualizationData(filePath, subBlockIndex, true);
      return;
    }

    const previousFile = activeFileRef.current;
    activeFileRef.current = null;
    if (keepAliveRef.current) clearInterval(keepAliveRef.current);
    if (previousFile) await endAnnotation(previousFile);

    setSubBlockIndex(0);
    setSelectedFile(filePath);
    setVisData({});
    setPsdBadChannels([]);
    setWavBadChannels({});
    setPsdChannelScores({});
    setWavChannelScores({});
    setLlmPreannotation(emptyAnnotation);
    setLlmPreannotationEnabled(false);
    setArtifactSegments([]);
    setAnnotationLayers([]);
    setSelectedOverlayUser("");
    setIsDataDiscarded(false);
    setError(null);
  };

  const handleWavBadChannelsChange = (newBadChannels) => {
    setWavBadChannels((prev) => ({
      ...prev,
      [subBlockIndex]: newBadChannels,
    }));
  };

  const handleWavChannelScoresChange = (newScores) => {
    setWavChannelScores((prev) => ({
      ...prev,
      [subBlockIndex]: normalizeChannelScores(newScores),
    }));
  };

  const handleArtifactsChange = (newArtifacts) => {
    setArtifactSegments(newArtifacts);
  };

  const getSubBlocksWithBadChannels = () =>
    Object.keys(isScoreMode ? wavChannelScores : wavBadChannels)
      .filter((index) =>
        isScoreMode
          ? Object.keys(wavChannelScores[index] || {}).length > 0
          : wavBadChannels[index]?.length > 0
      )
      .map(Number)
      .sort((a, b) => a - b);

  const handleAnnotate = async () => {
    if (!selectedFile) return;
    if (!currentUser) {
      alert(labels.setUserFirst);
      return;
    }

    setSubmitting(true);
    try {
      const payload = isScoreMode
        ? {
            file_path: selectedFile,
            psd_channel_scores: llmPreannotationEnabled
              ? diffChannelScores(psdChannelScores, llmPreannotation.psd_channel_scores)
              : psdChannelScores,
            wav_channel_scores: llmPreannotationEnabled
              ? diffSubblockScores(wavChannelScores, llmPreannotation.wav_channel_scores)
              : wavChannelScores,
            subblock_channel_scores: llmPreannotationEnabled
              ? diffSubblockScores(wavChannelScores, llmPreannotation.wav_channel_scores)
              : wavChannelScores,
            is_delta: llmPreannotationEnabled,
            annotation_base: llmPreannotationEnabled ? "llm" : "",
            artifacts: artifactSegments,
            user: currentUser,
            discarded: isDataDiscarded,
            sub_block_index: subBlockIndex,
          }
        : {
            file_path: selectedFile,
            psd_bad_channels: psdBadChannels,
            wav_bad_channels: wavBadChannels,
            subblock_bad_channels: wavBadChannels,
            artifacts: artifactSegments,
            user: currentUser,
            discarded: isDataDiscarded,
            sub_block_index: subBlockIndex,
          };
      const response = await axios.post(apiUrl("/annotate"), payload);
      const annotation = isScoreMode
        ? {
            psd_bad_channels: [],
            wav_bad_channels: {},
            psd_channel_scores: psdChannelScores,
            wav_channel_scores: wavChannelScores,
            artifacts: artifactSegments,
            discarded: isDataDiscarded,
          }
        : {
            psd_bad_channels: psdBadChannels,
            wav_bad_channels: wavBadChannels,
            artifacts: artifactSegments,
            discarded: isDataDiscarded,
          };

      setFileAnnotationCache((prev) => ({ ...prev, [selectedFile]: annotation }));
      await fetchAnnotationLayers(selectedFile);
      await endAnnotation(selectedFile);
      activeFileRef.current = null;
      alert(labels.annotationSaved(response.data.action));
      await fetchFileTree();
      handleNextUnannotated();
    } catch (err) {
      console.error("Failed to submit annotation", err);
      alert(labels.submitError);
    } finally {
      setSubmitting(false);
    }
  };

  const handleNextUnannotated = async () => {
    if (!currentUser) return;

    try {
      const res = await axios.get(apiUrl("/next_unannotated"), {
        params: {
          user: currentUser,
          current_file: selectedFile || "",
        },
      });

      if (res.data?.file_path) {
        handleFileSelect(res.data.file_path);
      } else if (allFiles.length > 0) {
        alert(labels.allAnnotated);
      }
    } catch (err) {
      if (err.response?.status === 404) {
        alert(labels.allAnnotatedOrBusy);
      } else {
        console.error("Failed to get the next file", err);
        setError(labels.nextFileError);
      }
    }
  };

  const refreshCurrentData = () => {
    if (!selectedFile) return;
    visualizationCacheRef.current.delete(`${selectedFile}::${subBlockIndex}`);
    psdCacheRef.current.delete(selectedFile);
    fetchVisualizationData(selectedFile, subBlockIndex, true);
    fetchAnnotationData(selectedFile);
    fetchAnnotationLayers(selectedFile);
  };

  return (
    <div style={styles.appShell}>
      <style>{buttonStateStyles}</style>
      <header style={styles.header}>
        <div>
          <h1 style={styles.title}>{labels.title}</h1>
          <div style={styles.subtitle}>
            {selectedFile
              ? labels.currentFile(selectedFileIndex + 1, Math.max(allFiles.length, 1))
              : labels.selectFile}
          </div>
        </div>
        <div style={styles.headerActions}>
          <button style={styles.secondaryButton} onClick={() => fetchFileTree(true)} disabled={loadingTree}>
            {labels.refreshFiles}
          </button>
          <button
            style={styles.secondaryButton}
            onClick={() => {
              const nextLanguage = language === "en" ? "zh" : "en";
              setLanguage(nextLanguage);
              localStorage.setItem("annotation_language", nextLanguage);
            }}
          >
            {labels.language}
          </button>
          <button
            style={styles.secondaryButton}
            onClick={() => {
              const user = prompt(labels.newUsername, currentUser);
              if (user?.trim()) {
                setCurrentUser(user.trim());
                localStorage.setItem("annotation_user", user.trim());
              }
            }}
          >
            {currentUser || labels.setUser}
          </button>
        </div>
      </header>

      <div style={styles.content}>
        <aside style={styles.sidebar}>
          <FileTree
            tree={fileTree}
            onSelect={handleFileSelect}
            currentUser={currentUser}
            language={language}
          />
        </aside>

        <main style={styles.main}>
          {error && <div style={styles.error}>{error}</div>}

          {selectedFile ? (
            <div style={styles.workbench}>
              <section style={styles.viewerPanel}>
                <div style={styles.currentPathBar} title={selectedFile}>
                  <span style={styles.currentPathLabel}>{labels.current}</span>
                  <span style={styles.currentPathText}>{selectedRelativePath}</span>
                </div>
                <WaveformViewer
                  data={visData}
                  psdBadChannels={showCurrentAnnotation ? psdBadChannels : []}
                  wavBadChannels={showCurrentAnnotation ? currentWavBadChannels : []}
                  annotationMode={annotationMode}
                  psdChannelScores={showCurrentAnnotation ? psdChannelScores : {}}
                  wavChannelScores={showCurrentAnnotation ? currentWavScoreMap : {}}
                  setPsdBadChannels={setPsdBadChannels}
                  setWavBadChannels={handleWavBadChannelsChange}
                  setPsdChannelScores={setPsdChannelScores}
                  setWavChannelScores={handleWavChannelScoresChange}
                  artifacts={showCurrentAnnotation ? artifactSegments : []}
                  setArtifacts={handleArtifactsChange}
                  annotationLayers={visibleAnnotationLayers}
                  annotationReadOnly={overlayMode === "othersOnly"}
                  loading={loadingData}
                  onSelectSubBlock={setSubBlockIndex}
                  currentSubBlockIndex={subBlockIndex}
                  markedSubBlocks={getSubBlocksWithBadChannels()}
                  language={language}
                />
              </section>

              <aside style={styles.annotationPanel}>
                <div style={styles.panelBlock}>
                  <div style={styles.panelLabel}>{labels.subBlock}</div>
                  <div style={styles.panelValue}>
                    {subBlockIndex + 1}/{Math.max(1, Number(visData.totalSubBlocks || 1))}
                  </div>
                </div>

                <div style={styles.panelBlock}>
                  <label htmlFor="overlay-mode" style={styles.panelLabel}>
                    {labels.overlayMode || TEXT.en.overlayMode}
                  </label>
                  <select
                    id="overlay-mode"
                    value={overlayMode}
                    onChange={(event) => {
                      setOverlayMode(event.target.value);
                      if (event.target.value === "mine") setSelectedOverlayUser("");
                    }}
                    style={styles.selectInput}
                  >
                    <option value="mine">{overlayLabels.mine}</option>
                    <option value="others">{overlayLabels.others}</option>
                    <option value="othersOnly">{overlayLabels.othersOnly}</option>
                  </select>
                  {overlayLegendLayers.length > 0 && overlayMode !== "mine" && (
                    <div style={styles.layerLegend}>
                      {overlayLegendLayers.map((layer) => (
                        <button
                          key={layer.user}
                          type="button"
                          style={layerLegendItemStyle(selectedOverlayUser === layer.user)}
                          title={layer.user}
                          onClick={() => setSelectedOverlayUser((user) => (user === layer.user ? "" : layer.user))}
                        >
                          {layer.user}
                        </button>
                      ))}
                    </div>
                  )}
                </div>

                <div style={styles.panelBlock}>
                  <label style={styles.checkboxLabel}>
                    <input
                      type="checkbox"
                      checked={isDataDiscarded}
                      onChange={(event) => setIsDataDiscarded(event.target.checked)}
                    />
                    {labels.discardFile}
                  </label>
                </div>

                <div style={styles.panelBlock}>
                  <div style={styles.panelLabel}>{isScoreMode ? labels.psdChannelScores : labels.psdBadChannels}</div>
                  <div style={styles.badChannelBox}>
                    {isScoreMode
                      ? formatScores(psdChannelScores) || labels.none
                      : psdBadChannels.length ? psdBadChannels.join(", ") : labels.none}
                  </div>
                </div>

                <div style={styles.panelBlock}>
                  <div style={styles.panelLabel}>{isScoreMode ? labels.currentWavChannelScores : labels.currentWavBadChannels}</div>
                  <div style={styles.badChannelBox}>
                    {isScoreMode
                      ? formatScores(currentWavScoreMap) || labels.none
                      : currentWavBadChannels.length ? currentWavBadChannels.join(", ") : labels.none}
                  </div>
                </div>

                <div style={styles.panelBlock}>
                  <div style={styles.panelLabel}>{labels.markedSubBlocks}</div>
                  <div style={styles.badChannelBox}>
                    {getSubBlocksWithBadChannels().length
                      ? getSubBlocksWithBadChannels().map((index) => index + 1).join(", ")
                      : labels.none}
                  </div>
                </div>

                <div style={styles.panelBlock}>
                  <div style={styles.panelLabel}>{labels.artifactSegments || "Artifact segments"}</div>
                  <div style={styles.badChannelBox}>
                    {currentArtifacts.length
                      ? currentArtifacts
                          .map((item) => `${item.channel}: ${Number(item.start_time).toFixed(2)}-${Number(item.end_time).toFixed(2)}s`)
                          .join(", ")
                      : labels.none}
                  </div>
                </div>

                <button style={styles.primaryButton} onClick={handleAnnotate} disabled={submitting}>
                  {submitting ? labels.submitting : labels.submitAnnotation}
                </button>
                <button style={styles.secondaryButtonWide} onClick={refreshCurrentData} disabled={loadingData}>
                  {labels.refreshData}
                </button>
                <button style={styles.secondaryButtonWide} onClick={handleNextUnannotated}>
                  {labels.nextUnannotated}
                </button>
              </aside>
            </div>
          ) : (
            <div style={styles.emptyState}>
              {loadingTree ? labels.loadingFileList : labels.selectDataFile}
            </div>
          )}
        </main>
      </div>
    </div>
  );
}

const styles = {
  appShell: {
    height: "100vh",
    minWidth: 0,
    display: "flex",
    flexDirection: "column",
    background: "#f8fafc",
    color: "#111827",
    overflow: "hidden",
    fontFamily: "system-ui, -apple-system, BlinkMacSystemFont, Segoe UI, sans-serif",
  },
  header: {
    flex: "0 0 auto",
    display: "flex",
    alignItems: "center",
    justifyContent: "space-between",
    gap: 16,
    padding: "12px 18px",
    borderBottom: "1px solid #dbe3ef",
    background: "#ffffff",
  },
  title: {
    margin: 0,
    fontSize: 20,
    lineHeight: 1.2,
  },
  subtitle: {
    marginTop: 4,
    fontSize: 13,
    color: "#64748b",
    wordBreak: "break-all",
  },
  headerActions: {
    display: "flex",
    gap: 8,
    alignItems: "center",
    flexWrap: "wrap",
    justifyContent: "flex-end",
  },
  content: {
    flex: "1 1 auto",
    minHeight: 0,
    display: "flex",
    overflow: "hidden",
  },
  sidebar: {
    flex: "0 0 clamp(260px, 24vw, 360px)",
    minWidth: 240,
    maxWidth: 390,
    overflow: "auto",
    borderRight: "1px solid #dbe3ef",
    background: "#ffffff",
  },
  main: {
    flex: "1 1 auto",
    minWidth: 0,
    minHeight: 0,
    display: "flex",
    flexDirection: "column",
    padding: 12,
    gap: 10,
    overflow: "hidden",
  },
  workbench: {
    flex: "1 1 auto",
    minHeight: 0,
    minWidth: 0,
    display: "flex",
    gap: 12,
    overflow: "hidden",
    isolation: "isolate",
  },
  viewerPanel: {
    position: "relative",
    zIndex: 1,
    contain: "layout paint",
    flex: "1 1 auto",
    minWidth: 0,
    minHeight: 0,
    display: "flex",
    flexDirection: "column",
    gap: 8,
    padding: 10,
    border: "1px solid #dbe3ef",
    borderRadius: 8,
    background: "#ffffff",
    overflow: "hidden",
  },
  currentPathBar: {
    flex: "0 0 auto",
    display: "flex",
    alignItems: "center",
    gap: 8,
    minHeight: 32,
    padding: "6px 9px",
    border: "1px solid #e5e7eb",
    borderRadius: 6,
    background: "#f8fafc",
    minWidth: 0,
  },
  currentPathLabel: {
    flex: "0 0 auto",
    color: "#64748b",
    fontSize: 12,
    fontWeight: 800,
  },
  currentPathText: {
    minWidth: 0,
    overflow: "hidden",
    textOverflow: "ellipsis",
    whiteSpace: "nowrap",
    color: "#0f172a",
    fontSize: 13,
    fontFamily: "Consolas, Monaco, monospace",
  },
  annotationPanel: {
    position: "relative",
    zIndex: 2000,
    isolation: "isolate",
    pointerEvents: "auto",
    flex: "0 0 220px",
    width: 220,
    minWidth: 220,
    maxWidth: 220,
    display: "flex",
    flexDirection: "column",
    gap: 10,
    padding: 10,
    border: "1px solid #dbe3ef",
    borderRadius: 8,
    background: "#ffffff",
    overflow: "auto",
  },
  panelBlock: {
    display: "flex",
    flexDirection: "column",
    gap: 6,
  },
  panelLabel: {
    fontSize: 12,
    color: "#64748b",
    fontWeight: 700,
  },
  panelValue: {
    fontSize: 18,
    fontWeight: 800,
  },
  selectInput: {
    width: "100%",
    padding: "7px 8px",
    border: "1px solid #cbd5e1",
    borderRadius: 6,
    background: "#ffffff",
    color: "#334155",
    fontSize: 13,
  },
  layerLegend: {
    display: "flex",
    flexWrap: "wrap",
    gap: 5,
  },
  layerDot: {
    flex: "0 0 auto",
    width: 8,
    height: 8,
    borderRadius: "50%",
  },
  checkboxLabel: {
    display: "flex",
    alignItems: "center",
    gap: 8,
    fontSize: 14,
    cursor: "pointer",
  },
  badChannelBox: {
    minHeight: 34,
    padding: "8px 10px",
    border: "1px solid #e5e7eb",
    borderRadius: 6,
    background: "#f8fafc",
    color: "#334155",
    fontSize: 13,
    lineHeight: 1.4,
    wordBreak: "break-word",
  },
  primaryButton: {
    position: "relative",
    zIndex: 2001,
    pointerEvents: "auto",
    width: "100%",
    padding: "10px 12px",
    border: "none",
    borderRadius: 6,
    background: "#2563eb",
    color: "#ffffff",
    fontWeight: 700,
    cursor: "pointer",
  },
  secondaryButton: {
    padding: "8px 12px",
    border: "1px solid #cbd5e1",
    borderRadius: 6,
    background: "#ffffff",
    color: "#334155",
    cursor: "pointer",
  },
  secondaryButtonWide: {
    width: "100%",
    padding: "9px 12px",
    border: "1px solid #cbd5e1",
    borderRadius: 6,
    background: "#ffffff",
    color: "#334155",
    cursor: "pointer",
  },
  error: {
    flex: "0 0 auto",
    padding: "10px 12px",
    border: "1px solid #fecaca",
    borderRadius: 6,
    background: "#fef2f2",
    color: "#b91c1c",
  },
  emptyState: {
    flex: "1 1 auto",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    color: "#64748b",
    border: "1px dashed #cbd5e1",
    borderRadius: 8,
    background: "#ffffff",
  },
};

function layerLegendItemStyle(active) {
  return {
    display: "inline-flex",
    alignItems: "center",
    gap: 4,
    maxWidth: "100%",
    padding: "3px 5px",
    border: "1px solid",
    borderColor: active ? "#2563eb" : "#e5e7eb",
    borderRadius: 5,
    background: active ? "#eff6ff" : "#f8fafc",
    color: active ? "#1d4ed8" : "#475569",
    fontSize: 11,
    overflow: "hidden",
    textOverflow: "ellipsis",
    whiteSpace: "nowrap",
    cursor: "pointer",
  };
}

const buttonStateStyles = `
  button:not(:disabled) {
    transition: background-color 140ms ease, border-color 140ms ease, color 140ms ease, box-shadow 140ms ease, transform 100ms ease;
  }

  button:not(:disabled):hover {
    filter: brightness(0.96);
    box-shadow: 0 2px 8px rgba(15, 23, 42, 0.16);
  }

  button:not(:disabled):active {
    box-shadow: 0 1px 3px rgba(15, 23, 42, 0.18);
  }

  button:disabled {
    cursor: not-allowed !important;
    opacity: 0.55;
  }
`;

export default App;
