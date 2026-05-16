import React, { useEffect, useMemo, useRef, useState } from "react";
import axios from "axios";
import FileTree from "./components/FileTree.jsx";
import WaveformViewer from "./components/WaveformViewer.jsx";

const API_BASE_URL = (import.meta.env.VITE_API_HOST || "localhost:10000")
  .replace(/^https?:\/\//, "")
  .replace(/\/api\/?$/, "");

const apiUrl = (path) => `http://${API_BASE_URL}/api${path}`;

const emptyAnnotation = { bad_channels: {}, discarded: false };

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

function App() {
  const [fileTree, setFileTree] = useState([]);
  const [selectedFile, setSelectedFile] = useState(null);
  const [visData, setVisData] = useState({});
  const [badChannels, setBadChannels] = useState({});
  const [tempBadChannels, setTempBadChannels] = useState({});
  const [loadingTree, setLoadingTree] = useState(false);
  const [loadingData, setLoadingData] = useState(false);
  const [error, setError] = useState(null);
  const [currentUser, setCurrentUser] = useState("");
  const [subBlockIndex, setSubBlockIndex] = useState(0);
  const [isDataDiscarded, setIsDataDiscarded] = useState(false);
  const [fileAnnotationCache, setFileAnnotationCache] = useState({});

  const keepAliveRef = useRef(null);
  const activeFileRef = useRef(null);
  const visualizationCacheRef = useRef(new Map());
  const visualizationRequestRef = useRef(0);

  const allFiles = useMemo(() => flattenFiles(fileTree), [fileTree]);
  const selectedFileIndex = allFiles.findIndex((file) => file.path === selectedFile);
  const currentBadChannels = tempBadChannels[subBlockIndex] || [];

  useEffect(() => {
    const savedUser = localStorage.getItem("annotation_user");
    if (savedUser) {
      setCurrentUser(savedUser);
      return;
    }

    const user = prompt("请输入您的用户名");
    if (user?.trim()) {
      setCurrentUser(user.trim());
      localStorage.setItem("annotation_user", user.trim());
    }
  }, []);

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
      if (cancelled) return;

      if (!started) {
        setSelectedFile(null);
        setVisData({});
        setLoadingData(false);
        return;
      }

      activeFileRef.current = selectedFile;
      startKeepAlive(selectedFile);

      const cachedAnnotation = fileAnnotationCache[selectedFile];
      if (cachedAnnotation) {
        applyAnnotation(cachedAnnotation);
      } else {
        await fetchAnnotationData(selectedFile);
      }

      if (!cancelled) fetchVisualizationData(selectedFile, subBlockIndex);
    };

    openFile();

    return () => {
      cancelled = true;
    };
  }, [selectedFile, currentUser]);

  useEffect(() => {
    if (!selectedFile || !currentUser) return;
    fetchVisualizationData(selectedFile, subBlockIndex);
    setTempBadChannels((prev) => {
      if (prev[subBlockIndex] !== undefined) return prev;
      return { ...prev, [subBlockIndex]: badChannels[subBlockIndex] || [] };
    });
  }, [subBlockIndex]);

  const fetchFileTree = async () => {
    if (!currentUser) return;
    setLoadingTree(true);
    try {
      const res = await axios.get(apiUrl("/file_tree"));
      setFileTree(res.data);
      setError(null);
    } catch (err) {
      console.error("获取文件列表失败", err);
      setError("获取文件列表失败，请检查后端服务和 Nginx 代理配置。");
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
        alert(err.response.data?.detail || "该文件正在被其他用户标注。");
      } else {
        console.error("开始标注失败", err);
        alert("开始标注失败，请稍后重试。");
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
      console.error("结束标注失败", err);
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
        .catch((err) => console.error("心跳失败", err));
    }, 60000);
  };

  const fetchVisualizationData = async (filePath, blockIndex = 0, force = false) => {
    const cacheKey = `${filePath}::${blockIndex}`;
    const requestId = ++visualizationRequestRef.current;

    if (!force && visualizationCacheRef.current.has(cacheKey)) {
      setVisData(visualizationCacheRef.current.get(cacheKey));
      setError(null);
      return;
    }

    setLoadingData(true);
    setError(null);

    try {
      const res = await axios.get(apiUrl(`/visualization/${filePath}?sub_block=${blockIndex}`));
      if (requestId !== visualizationRequestRef.current) return;
      visualizationCacheRef.current.set(cacheKey, res.data);
      setVisData(res.data);
      setError(null);
    } catch (err) {
      if (requestId !== visualizationRequestRef.current) return;
      console.error("加载可视化数据失败", err);
      setVisData({});
      setError("加载可视化数据失败，请检查数据文件是否完整。");
    } finally {
      if (requestId === visualizationRequestRef.current) setLoadingData(false);
    }
  };

  const applyAnnotation = (annotation) => {
    setBadChannels(annotation.bad_channels || {});
    setTempBadChannels(annotation.bad_channels || {});
    setIsDataDiscarded(Boolean(annotation.discarded));
  };

  const fetchAnnotationData = async (filePath) => {
    try {
      const res = await axios.get(apiUrl(`/annotation/${filePath}`));
      const annotation = {
        bad_channels: res.data?.subblock_bad_channels || res.data?.bad_channels || {},
        discarded: Boolean(res.data?.discarded),
      };
      setFileAnnotationCache((prev) => ({ ...prev, [filePath]: annotation }));
      applyAnnotation(annotation);
      return annotation;
    } catch (err) {
      console.error("加载标注信息失败", err);
      setFileAnnotationCache((prev) => ({ ...prev, [filePath]: emptyAnnotation }));
      applyAnnotation(emptyAnnotation);
      return emptyAnnotation;
    }
  };

  const handleFileSelect = async (filePath) => {
    if (!filePath || filePath === selectedFile) return;

    const previousFile = activeFileRef.current;
    activeFileRef.current = null;
    if (keepAliveRef.current) clearInterval(keepAliveRef.current);
    if (previousFile) await endAnnotation(previousFile);

    setSubBlockIndex(0);
    setSelectedFile(filePath);
    setVisData({});
    setTempBadChannels({});
    setBadChannels({});
    setIsDataDiscarded(false);
    setError(null);
  };

  const handleBadChannelsChange = (newBadChannels) => {
    setTempBadChannels((prev) => ({
      ...prev,
      [subBlockIndex]: newBadChannels,
    }));
  };

  const getSubBlocksWithBadChannels = () =>
    Object.keys(tempBadChannels)
      .filter((index) => tempBadChannels[index]?.length > 0)
      .map(Number)
      .sort((a, b) => a - b);

  const handleAnnotate = async () => {
    if (!selectedFile) return;
    if (!currentUser) {
      alert("请先设置用户名。");
      return;
    }

    setLoadingData(true);
    try {
      const payload = {
        file_path: selectedFile,
        subblock_bad_channels: tempBadChannels,
        bad_channels: tempBadChannels,
        user: currentUser,
        discarded: isDataDiscarded,
        sub_block_index: subBlockIndex,
      };
      const response = await axios.post(apiUrl("/annotate"), payload);
      const annotation = { bad_channels: tempBadChannels, discarded: isDataDiscarded };

      setBadChannels(tempBadChannels);
      setFileAnnotationCache((prev) => ({ ...prev, [selectedFile]: annotation }));
      await endAnnotation(selectedFile);
      activeFileRef.current = null;
      alert(`标注成功 (${response.data.action})`);
      await fetchFileTree();
      handleNextUnannotated();
    } catch (err) {
      console.error("提交标注失败", err);
      alert("提交标注失败，请重试。");
    } finally {
      setLoadingData(false);
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
        alert("所有文件都已标注完成。");
      }
    } catch (err) {
      if (err.response?.status === 404) {
        alert("所有文件都已标注完成或正在被其他用户标注。");
      } else {
        console.error("获取下一个文件失败", err);
        setError("获取下一个文件失败，请稍后重试。");
      }
    }
  };

  const handleDatasetMark = async (datasetPath, discarded) => {
    if (!currentUser) {
      alert("请先设置用户名。");
      return;
    }

    setLoadingTree(true);
    try {
      await axios.post(apiUrl("/mark_dataset"), {
        dataset_path: datasetPath,
        discarded,
        user: currentUser,
      });
      await fetchFileTree();
      alert(discarded ? "数据集已标记为弃用。" : "已取消数据集弃用标记。");
    } catch (err) {
      console.error("标记数据集失败", err);
      alert("标记数据集失败，请重试。");
    } finally {
      setLoadingTree(false);
    }
  };

  const refreshCurrentData = () => {
    if (!selectedFile) return;
    visualizationCacheRef.current.delete(`${selectedFile}::${subBlockIndex}`);
    fetchVisualizationData(selectedFile, subBlockIndex, true);
    fetchAnnotationData(selectedFile);
  };

  return (
    <div style={styles.appShell}>
      <header style={styles.header}>
        <div>
          <h1 style={styles.title}>EEG 数据标注</h1>
          <div style={styles.subtitle}>
            {selectedFile
              ? `当前文件 ${selectedFileIndex + 1}/${Math.max(allFiles.length, 1)}`
              : "请选择左侧文件开始标注"}
          </div>
        </div>
        <div style={styles.headerActions}>
          <button style={styles.secondaryButton} onClick={fetchFileTree} disabled={loadingTree}>
            刷新文件
          </button>
          <button
            style={styles.secondaryButton}
            onClick={() => {
              const user = prompt("请输入新的用户名", currentUser);
              if (user?.trim()) {
                setCurrentUser(user.trim());
                localStorage.setItem("annotation_user", user.trim());
              }
            }}
          >
            {currentUser || "设置用户"}
          </button>
        </div>
      </header>

      <div style={styles.content}>
        <aside style={styles.sidebar}>
          <FileTree
            tree={fileTree}
            onSelect={handleFileSelect}
            currentUser={currentUser}
            onDatasetMark={handleDatasetMark}
          />
        </aside>

        <main style={styles.main}>
          {error && <div style={styles.error}>{error}</div>}

          {selectedFile ? (
            <div style={styles.workbench}>
              <section style={styles.viewerPanel}>
                <WaveformViewer
                  data={visData}
                  badChannels={currentBadChannels}
                  setBadChannels={handleBadChannelsChange}
                  loading={loadingData}
                  onSelectSubBlock={setSubBlockIndex}
                  currentSubBlockIndex={subBlockIndex}
                />
              </section>

              <aside style={styles.annotationPanel}>
                <div style={styles.panelBlock}>
                  <div style={styles.panelLabel}>子图</div>
                  <div style={styles.panelValue}>
                    {subBlockIndex + 1}/{Math.max(1, Number(visData.totalSubBlocks || 1))}
                  </div>
                </div>

                <div style={styles.panelBlock}>
                  <label style={styles.checkboxLabel}>
                    <input
                      type="checkbox"
                      checked={isDataDiscarded}
                      onChange={(event) => setIsDataDiscarded(event.target.checked)}
                    />
                    弃用该数据
                  </label>
                </div>

                <div style={styles.panelBlock}>
                  <div style={styles.panelLabel}>当前坏道</div>
                  <div style={styles.badChannelBox}>
                    {currentBadChannels.length ? currentBadChannels.join(", ") : "无"}
                  </div>
                </div>

                <div style={styles.panelBlock}>
                  <div style={styles.panelLabel}>已标注子图</div>
                  <div style={styles.badChannelBox}>
                    {getSubBlocksWithBadChannels().length
                      ? getSubBlocksWithBadChannels().map((index) => index + 1).join(", ")
                      : "无"}
                  </div>
                </div>

                <button style={styles.primaryButton} onClick={handleAnnotate} disabled={loadingData}>
                  提交标注
                </button>
                <button style={styles.secondaryButtonWide} onClick={refreshCurrentData} disabled={loadingData}>
                  刷新数据
                </button>
                <button style={styles.secondaryButtonWide} onClick={handleNextUnannotated}>
                  下一个未标注
                </button>
              </aside>
            </div>
          ) : (
            <div style={styles.emptyState}>
              {loadingTree ? "正在加载文件列表..." : "请从左侧选择一个数据文件。"}
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
    display: "grid",
    gridTemplateColumns: "minmax(0, 1fr) minmax(170px, 220px)",
    gap: 12,
  },
  viewerPanel: {
    minWidth: 0,
    minHeight: 0,
    padding: 10,
    border: "1px solid #dbe3ef",
    borderRadius: 8,
    background: "#ffffff",
    overflow: "hidden",
  },
  annotationPanel: {
    minWidth: 0,
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

export default App;
