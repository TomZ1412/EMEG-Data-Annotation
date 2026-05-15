// [file name]: App.jsx
// [file content begin]
import React, { useState, useEffect } from "react";
import axios from "axios";
import FileTree from "./components/FileTree.jsx";
import WaveformViewer from "./components/WaveformViewer.jsx";

const API_BASE_URL = (import.meta.env.VITE_API_HOST || "localhost:10000")
  .replace(/^https?:\/\//, "")
  .replace(/\/api\/?$/, "");

function App() {
  const [fileTree, setFileTree] = useState([]);
  const [selectedFile, setSelectedFile] = useState(null);
  const [visData, setVisData] = useState({});
  const [badChannels, setBadChannels] = useState({}); // 改为对象格式：{子图索引: [坏道列表]}
  const [tempBadChannels, setTempBadChannels] = useState({}); // 临时存储未提交的标注
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [currentUser, setCurrentUser] = useState("");
  const [keepAliveInterval, setKeepAliveInterval] = useState(null);
  const [subBlockIndex, setSubBlockIndex] = useState(0); // 当前子图索引
  const [isDataDiscarded, setIsDataDiscarded] = useState(false); // 数据是否弃用
  const [fileAnnotationCache, setFileAnnotationCache] = useState({}); // 文件标注信息缓存
  const [fileLoadingState, setFileLoadingState] = useState({}); // 跟踪每个文件的加载状态

  // ✅ 初始化用户
  useEffect(() => {
    const savedUser = localStorage.getItem('annotation_user');
    if (savedUser) {
      setCurrentUser(savedUser);
    } else {
      const user = prompt("请输入您的用户名：");
      if (user) {
        setCurrentUser(user);
        localStorage.setItem('annotation_user', user);
      }
    }
  }, []);

  // ✅ 获取文件树
  const fetchFileTree = () => {
    if (!currentUser) return;
    
    setLoading(true);
    axios.get(`http://${API_BASE_URL}/api/file_tree`)
      .then(res => {
        setFileTree(res.data);
        setError(null);
      })
      .catch(err => {
        console.error("获取文件树失败", err);
        setError("获取文件列表失败");
      })
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    if (currentUser) {
      fetchFileTree();
    }
  }, [currentUser]);

  // ✅ 开始标注文件
  const startAnnotation = async (filePath) => {
    if (!currentUser) return false;
    
    try {
      await axios.post(`http://${API_BASE_URL}/api/start_annotation`, {
        file_path: filePath,
        user: currentUser
      });
      return true;
    } catch (err) {
      if (err.response?.status === 409) {
        const activeUser = err.response.data.detail.includes("正在被用户") 
          ? err.response.data.detail.split("正在被用户 ")[1]?.split(" ")[0]
          : "其他用户";
        alert(`文件正在被用户 ${activeUser} 标注，请选择其他文件`);
      } else {
        console.error("开始标注失败", err);
        alert("开始标注失败");
      }
      return false;
    }
  };

  // ✅ 结束标注文件
  const endAnnotation = async (filePath) => {
    if (!currentUser || !filePath) return;
    
    try {
      await axios.post(`http://${API_BASE_URL}/api/end_annotation`, {
        file_path: filePath,
        user: currentUser
      });
    } catch (err) {
      console.error("结束标注失败", err);
    }
  };

  // ✅ 心跳保持活跃状态
  const startKeepAlive = (filePath) => {
    if (keepAliveInterval) {
      clearInterval(keepAliveInterval);
    }
    
    const interval = setInterval(() => {
      if (filePath && currentUser) {
        axios.post(`http://${API_BASE_URL}/api/keep_alive`, {
          file_path: filePath,
          user: currentUser
        }).catch(err => console.error("心跳失败", err));
      }
    }, 60000); // 每分钟发送一次心跳
    
    setKeepAliveInterval(interval);
  };

  // ✅ 获取可视化数据（仅波形数据，不包含标注信息）
  const fetchVisualizationData = (filePath, blockIndex = 0) => {
    setLoading(true);
    setError(null);
    axios.get(`http://${API_BASE_URL}/api/visualization/${filePath}?sub_block=${blockIndex}`)
      .then(visResponse => {
      setVisData(visResponse.data);
      // console.log("visResponse.data", visResponse.data);
      setError(null);
      })
      .catch(err => {
      console.error("加载波形数据失败", err);
      setError("加载波形数据失败，请检查文件路径是否正确");
      setVisData({});
      })
      .finally(() => setLoading(false));
  };

  // ✅ 获取标注信息（坏道和数据弃用状态）
  const fetchAnnotationData = (filePath) => {
    return axios.get(`http://${API_BASE_URL}/api/annotation/${filePath}`)
      .then(annotationResponse => {
        if (annotationResponse.data) {
          // 处理新的数据格式：subblock_bad_channels 或保持兼容
          const annotationData = {
            bad_channels: annotationResponse.data.subblock_bad_channels || annotationResponse.data.bad_channels || {},
            discarded: annotationResponse.data.discarded || false
          };
          
          // 更新缓存
          setFileAnnotationCache(prev => ({
            ...prev,
            [filePath]: annotationData
          }));
          
          // 更新当前状态
          setBadChannels(annotationData.bad_channels);
          setIsDataDiscarded(annotationData.discarded);
          
          // 初始化临时存储（复制已提交的标注）
          setTempBadChannels(annotationData.bad_channels);
          
          return annotationData;
        }
        return null;
      })
      .catch(err => {
        console.error("加载标注信息失败", err);
        // 如果失败，初始化空的标注信息
        const emptyAnnotation = { bad_channels: {}, discarded: false };
        setFileAnnotationCache(prev => ({
          ...prev,
          [filePath]: emptyAnnotation
        }));
        setBadChannels({});
        setTempBadChannels({});
        setIsDataDiscarded(false);
        return emptyAnnotation;
      });
  };

  // ✅ 处理文件选择和初始化
  useEffect(() => {
    if (selectedFile && currentUser) {
    // 先尝试开始标注
      startAnnotation(selectedFile).then(success => {
    if (success) {
      // 开始心跳
          startKeepAlive(selectedFile);
      
          // 获取可视化数据（默认使用当前子图索引）
          fetchVisualizationData(selectedFile, subBlockIndex);
          
          // 获取标注信息（如果缓存中有则使用缓存，否则从后端获取）
          if (fileAnnotationCache[selectedFile]) {
            const cached = fileAnnotationCache[selectedFile];
            setBadChannels(cached.bad_channels);
            setTempBadChannels(cached.bad_channels);
            setIsDataDiscarded(cached.discarded);
          } else {
            fetchAnnotationData(selectedFile);
          }
    } else {
      setLoading(false);
      setSelectedFile(null);
    }
      });
    }
  }, [selectedFile, currentUser]);

  // ✅ 处理子图切换 - 只获取波形数据，不重新获取标注信息
  useEffect(() => {
    if (selectedFile && currentUser && subBlockIndex !== undefined) {
        // 仅获取可视化数据，标注信息保持不变
        fetchVisualizationData(selectedFile, subBlockIndex);
      
      // 确保当前子图的临时标注数据存在
      setTempBadChannels(prev => {
        if (prev[subBlockIndex] === undefined) {
          return {
            ...prev,
            [subBlockIndex]: badChannels[subBlockIndex] || [] // 优先使用已提交的，没有则空数组
          };
        }
        return prev;
      });
    }
  }, [subBlockIndex]);

  // ✅ 自动跳转到第一个可用的未标注文件
  useEffect(() => {
    if (fileTree.length > 0 && !selectedFile && currentUser) {
      handleNextUnannotated();
    }
  }, [fileTree, currentUser]);

  // ✅ 提交标注（包括数据弃用状态）
  const handleAnnotate = () => {
    if (!currentUser) {
      alert("请先设置用户名");
      return;
    }
    
    setLoading(true);
    
    // 提交时使用临时存储的标注数据
    const annotationData = {
      file_path: selectedFile,
      subblock_bad_channels: tempBadChannels, // 新的字段名，提交所有子图的临时标注
      bad_channels: tempBadChannels, // 保持向后兼容
      user: currentUser,
      discarded: isDataDiscarded,
      sub_block_index: subBlockIndex
    };
    
    axios.post(`http://${API_BASE_URL}/api/annotate`, annotationData)
      .then((response) => {
        alert(`标注成功! (${response.data.action})`);
        
        // 更新已提交的标注数据
        setBadChannels(tempBadChannels);
        
        // 更新缓存中的标注信息
        setFileAnnotationCache(prev => ({
          ...prev,
          [selectedFile]: {
            bad_channels: tempBadChannels,
            discarded: isDataDiscarded
          }
        }));
        
        // 刷新文件树以更新标注状态，不用刷新文件树，因为文件树已经刷新了
        
        // 自动跳转到下一个未标注文件
        setTimeout(() => {
          handleNextUnannotated();
        }, 500);
      })
      .catch((err) => {
        if (err.response?.status === 409) {
          alert("文件已被其他用户占用，请重新选择文件");
          handleNextUnannotated();
        } else {
          console.error("标注失败", err);
          alert("标注失败");
        }
      })
      .finally(() => setLoading(false));
  };

  // ✅ 跳转到下一个未标注文件（修改：传递当前文件路径）
  const handleNextUnannotated = () => {
    if (!currentUser) return;
    
    setLoading(true);
    // 传递当前文件路径给后端
    const params = {
      user: currentUser,
      current_file: selectedFile || '' // 传递当前文件路径
    };
    
    axios.get(`http://${API_BASE_URL}/api/next_unannotated`, { params })
      .then(res => {
        if (res.data.file_path) {
          setSubBlockIndex(0);
          setSelectedFile(res.data.file_path);
          fetchFileTree();
           // 重置子图索引
          setTempBadChannels({}); // 清空临时存储
          
          setError(null);
        } else {
          alert("所有文件都已标注完成或正在被其他用户标注！");
        }
      })
      .catch(err => {
        if (err.response?.status === 404) {
          alert("所有文件都已标注完成或正在被其他用户标注！");
        } else {
          console.error("获取下一个文件失败", err);
          setError("获取下一个文件失败");
        }
      })
      .finally(() => setLoading(false));
  };

  // ✅ 处理文件选择
  const handleFileSelect = async (filePath) => {
    if (filePath === selectedFile) return;
    
    // 结束当前文件的标注
    if (selectedFile) {
      await endAnnotation(selectedFile);
      if (keepAliveInterval) {
        clearInterval(keepAliveInterval);
        setKeepAliveInterval(null);
      }
    }
    setSubBlockIndex(0);
    setSelectedFile(filePath);
     // 重置子图索引
    setTempBadChannels({}); // 清空临时存储
  };

  // ✅ 处理子图选择
  const handleSubBlockSelect = (index) => {
    setSubBlockIndex(index);
  };

  // ✅ 处理数据弃用状态变化
  const handleDataDiscardedChange = (discarded) => {
    setIsDataDiscarded(discarded);
  };

  // ✅ 处理坏道数据变化 - 更新临时存储
  const handleBadChannelsChange = (newBadChannels) => {
    setTempBadChannels(prev => ({
      ...prev,
      [subBlockIndex]: newBadChannels
    }));
  };

  // ✅ 获取当前子图的坏道列表
  const getCurrentBadChannels = () => {
    return tempBadChannels[subBlockIndex] || [];
  };

  // ✅ 获取当前子图的已提交坏道列表（用于显示对比）
  const getCurrentCommittedBadChannels = () => {
    return badChannels[subBlockIndex] || [];
  };

  // ✅ 获取有坏道的子图列表
  const getSubBlocksWithBadChannels = () => {
    const subBlocks = [];
    Object.entries(tempBadChannels).forEach(([index, channels]) => {
      if (channels && channels.length > 0) {
        subBlocks.push({
          index: parseInt(index),
          count: channels.length
        });
      }
    });
    return subBlocks.sort((a, b) => a.index - b.index);
  };

  // ✅ 组件卸载时清理
  useEffect(() => {
    return () => {
      if (selectedFile) {
        endAnnotation(selectedFile);
      }
      if (keepAliveInterval) {
        clearInterval(keepAliveInterval);
      }
    };
  }, []);

  const handleDatasetMark = async (datasetPath, action) => {
    try {
      const response = await fetch(`http://${API_BASE_URL}/api/datasets/mark`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          path: datasetPath,
          action: action // 'discard' 或 'cancel'
        }),
      });
  
    if (!response.ok) {
        throw new Error('标记操作失败');
      }
  
      const result = await response.json();
      
      // 根据返回结果更新界面
      if (result.success) {
        console.log(`数据集 ${datasetPath} ${action === 'discard' ? '已标记为丢弃' : '已取消丢弃标记'}`);
        alert(`数据集 ${datasetPath} ${action === 'discard' ? '已标记为丢弃' : '已取消丢弃标记'}`);
        fetchFileTree();
      }
    } catch (error) {
      console.error('操作失败:', error);
      alert('操作失败，请重试');
    }
  };

  // ✅ 切换用户
  const handleChangeUser = () => {
    const newUser = prompt("请输入新的用户名：", currentUser);
    if (newUser && newUser !== currentUser) {
      // 结束当前文件的标注
      if (selectedFile) {
        endAnnotation(selectedFile);
        if (keepAliveInterval) {
          clearInterval(keepAliveInterval);
          setKeepAliveInterval(null);
        }
      }
      
      setCurrentUser(newUser);
      localStorage.setItem('annotation_user', newUser);
      setSelectedFile(null);
      setBadChannels({});
      setTempBadChannels({});
      setIsDataDiscarded(false);
      setSubBlockIndex(0);
      setFileAnnotationCache({}); // 清空缓存
    }
  };

  // ✅ 清空当前子图的所有标注
  const handleClearCurrentSubBlock = () => {
    handleBadChannelsChange([]);
  };

  // ✅ 获取标注统计信息
  const getAnnotationStats = () => {
    const currentTemp = getCurrentBadChannels();
    const currentCommitted = getCurrentCommittedBadChannels();
    const hasUnsavedChanges = JSON.stringify(currentTemp) !== JSON.stringify(currentCommitted);
    
    return {
      currentCount: currentTemp.length,
      committedCount: currentCommitted.length,
      hasUnsavedChanges
    };
  };

  if (!currentUser) {
    return (
      <div style={{ 
        display: "flex", 
        alignItems: "center", 
        justifyContent: "center", 
        height: "100vh" 
      }}>
        <div>加载中...</div>
      </div>
    );
  }

  const annotationStats = getAnnotationStats();
  const subBlocksWithBadChannels = getSubBlocksWithBadChannels();

  return (
    <div style={{ display: "flex", height: "100vh", fontFamily: "sans-serif" }}>
      <div style={{
        width: "300px", overflowY: "auto", borderRight: "1px solid #ccc", padding: "10px"
      }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "10px" }}>
          <h3>数据文件</h3>
          <button
            onClick={fetchFileTree}
            style={{ 
              padding: "4px 8px", 
              fontSize: "12px",
              borderRadius: "4px",
              backgroundColor: "#f0f0f0",
              border: "1px solid #ccc",
              cursor: "pointer"
            }}
            title="刷新文件列表"
          >
            刷新
          </button>
        </div>

        {/* 用户信息 */}
        <div style={{ 
          padding: "8px", 
          backgroundColor: "#e3f2fd", 
          borderRadius: "4px", 
          marginBottom: "10px",
          fontSize: "14px"
        }}>
          <div>当前用户: <strong>{currentUser}</strong></div>
          <button
            onClick={handleChangeUser}
            style={{
              marginTop: "5px",
              padding: "2px 6px",
              fontSize: "12px",
              backgroundColor: "#bbdefb",
              border: "none",
              borderRadius: "3px",
              cursor: "pointer"
            }}
          >
            切换用户
          </button>
        </div>
        
        {loading && <div style={{padding: "10px", color: "#666"}}>加载文件列表中...</div>}
        {error && <div style={{padding: "10px", color: "red"}}>{error}</div>}
        
        <FileTree tree={fileTree} onSelect={handleFileSelect} currentUser={currentUser} onDatasetMark={handleDatasetMark} />
      </div>

      <div style={{ flex: 1, padding: "10px", display: "flex", flexDirection: "column" }}>
        {selectedFile ? (
          <>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "10px" }}>
              <h3 style={{ margin: 0 }}>
                {selectedFile}
                {fileTree.length > 0 && (
                  <span style={{ 
                    fontSize: "14px", 
                    color: "#666", 
                    marginLeft: "10px",
                    fontWeight: "normal"
                  }}>
                    {(() => {
                      const allFiles = [];
                      function extractFiles(node) {
                        if (node.type === 'file') allFiles.push(node.path);
                        if (node.children) node.children.forEach(extractFiles);
                      }
                      fileTree.forEach(extractFiles);
                      
                      const currentIndex = allFiles.indexOf(selectedFile) + 1;
                      const total = allFiles.length;
                      return `(${currentIndex}/${total})`;
                    })()}
                  </span>
                )}
                {/* 显示当前子图信息 */}
                {visData.totalSubBlocks > 1 && (
                  <span style={{ 
                    fontSize: "14px", 
                    color: "#1565c0", 
                    marginLeft: "10px",
                    fontWeight: "normal",
                    backgroundColor: "#e3f2fd",
                    padding: "2px 6px",
                    borderRadius: "4px"
                  }}>
                    子图: {subBlockIndex + 1}/{visData.totalSubBlocks}
                  </span>
                )}
                {/* 显示数据弃用状态 */}
                {isDataDiscarded && (
                  <span style={{ 
                    fontSize: "14px", 
                    color: "#d32f2f", 
                    marginLeft: "10px",
                    fontWeight: "normal",
                    backgroundColor: "#ffebee",
                    padding: "2px 6px",
                    borderRadius: "4px"
                  }}>
                    数据已弃用
                  </span>
                )}
              </h3>
              
              <button
                onClick={handleNextUnannotated}
                disabled={loading}
                style={{ 
                  padding: "8px 12px", 
                  borderRadius: "6px",
                  backgroundColor: "#4CAF50",
                  color: "white",
                  border: "none",
                  cursor: loading ? "not-allowed" : "pointer",
                  opacity: loading ? 0.6 : 1
                }}
              >
                {loading ? "加载中..." : "下一个可用文件"}
              </button>
            </div>
            
            {/* 标注状态信息 */}
            <div style={{
              padding: "8px 12px",
              backgroundColor: "#f0f0f0",
              border: "1px solid #ccc",
              borderRadius: "4px",
              marginBottom: "10px",
              fontSize: "14px"
            }}>
              <div>
                <strong>当前子图标注状态:</strong>
                <span style={{ marginLeft: "10px" }}>
                  暂存: <strong>{annotationStats.currentCount}</strong> 个坏道
                </span>
                
                {/* 显示有坏道的子图信息 */}
                {subBlocksWithBadChannels.length > 0 && (
                  <span style={{ marginLeft: "15px" }}>
                    <strong>有坏道的子图:</strong>
                    {subBlocksWithBadChannels.map(subBlock => (
                      <span 
                        key={subBlock.index}
                        style={{ 
                          marginLeft: "8px",
                          padding: "2px 6px",
                          backgroundColor: subBlock.index === subBlockIndex ? "#2196F3" : "#e3f2fd",
                          color: subBlock.index === subBlockIndex ? "white" : "#1565c0",
                          borderRadius: "4px",
                          fontSize: "12px",
                          cursor: "pointer"
                        }}
                        onClick={() => setSubBlockIndex(subBlock.index)}
                        title={`子图 ${subBlock.index + 1} 有 ${subBlock.count} 个坏道，点击切换`}
                      >
                        {subBlock.index + 1}({subBlock.count})
                      </span>
                    ))}
                  </span>
                )}
              </div>
            </div>
            
            {/* 加载状态提示 */}
            {loading && (
              <div style={{
                padding: "20px",
                textAlign: "center",
                backgroundColor: "#f8f9fa",
                borderRadius: "6px",
                marginBottom: "10px"
              }}>
                <div>加载数据中，请稍候...</div>
              </div>
            )}
            
            {error && (
              <div style={{
                padding: "15px",
                backgroundColor: "#ffeaa7",
                borderRadius: "6px",
                marginBottom: "10px",
                border: "1px solid #fdcb6e"
              }}>
                <strong>错误:</strong> {error}
              </div>
            )}
            
            {/* 主内容区域 - 波形图和操作面板 */}
            <div style={{ display: "flex", flex: 1, gap: "15px", minHeight: 0, width: "100%"  }}>
              {/* 波形查看器 */}
              <div style={{ flex: 1, minHeight: 0 }}>
                <WaveformViewer
                  data={visData}
                  badChannels={getCurrentBadChannels()}
                  setBadChannels={handleBadChannelsChange}
                  loading={loading}
                  onSelectSubBlock={handleSubBlockSelect}
                  currentSubBlockIndex={subBlockIndex}
                />
              </div>
              
              {/* 操作面板 - 移动到右侧 */}
              <div style={{ 
                width: "200px", 
                display: "flex", 
                flexDirection: "column",
                gap: "10px"
              }}>
                {/* 操作说明 */}
                <div style={{
                  padding: "12px",
                  backgroundColor: "#e8f5e8",
                  border: "1px solid #4caf50",
                  borderRadius: "6px",
                  fontSize: "13px"
                }}>
                  <h4 style={{ margin: "0 0 8px 0", color: "#2e7d32" }}>操作说明</h4>
                  <ul style={{ margin: 0, paddingLeft: "16px" }}>
                    <li>点击左侧数据文件打开对应文件视图</li>
                    <li>点击波形图/PSD视图对应波形标记为坏道</li>
                    <li>数据文件首次打开可能无法正常加载，点击刷新数据可解决</li>
                  </ul>
                </div>
                
                {/* 操作按钮 */}
                <div style={{ 
                  display: "flex", 
                  flexDirection: "column",
                  gap: "8px"
                }}>
                  <button
                    onClick={handleAnnotate}
                    disabled={loading}
                    style={{ 
                      padding: "10px 12px", 
                      borderRadius: "6px",
                      backgroundColor: "#2196F3",
                      color: "white",
                      border: "none",
                      cursor: loading ? "not-allowed" : "pointer",
                      opacity: loading ? 0.6 : 1,
                      fontSize: "14px",
                      fontWeight: "bold"
                    }}
                  >
                    {loading ? "保存中..." : "保存标注"}
                  </button>
                  
                  {/* <button
                    onClick={handleClearCurrentSubBlock}
                    disabled={loading || annotationStats.currentCount === 0}
                    style={{ 
                      padding: "8px 12px", 
                      borderRadius: "6px",
                      backgroundColor: annotationStats.currentCount === 0 ? "#ccc" : "#ff9800",
                      color: "white",
                      border: "none",
                      cursor: (loading || annotationStats.currentCount === 0) ? "not-allowed" : "pointer",
                      opacity: (loading || annotationStats.currentCount === 0) ? 0.6 : 1,
                      fontSize: "14px"
                    }}
                  >
                    清空当前子图
                  </button> */}

                  {/* 手动刷新数据按钮 */}
                  <button
                    onClick={() => {
                      fetchVisualizationData(selectedFile, subBlockIndex);
                    }}
                    disabled={loading}
                    style={{ 
                      padding: "8px 12px", 
                      borderRadius: "6px",
                      backgroundColor: "#9c27b0",
                      color: "white",
                      border: "none",
                      cursor: loading ? "not-allowed" : "pointer",
                      opacity: loading ? 0.6 : 1,
                      fontSize: "14px"
                    }}
                  >
                    刷新数据
                  </button>
                </div>
                
                {/* 标注统计 */}
                {/* <div style={{
                  padding: "12px",
                  backgroundColor: "#fff3e0",
                  border: "1px solid #ff9800",
                  borderRadius: "6px",
                  fontSize: "13px"
                }}>
                  <h4 style={{ margin: "0 0 8px 0", color: "#e65100" }}>标注统计</h4>
                  <div>当前子图坏道: <strong>{annotationStats.currentCount}</strong></div> */}
                  {/* <div>已保存坏道: <strong>{annotationStats.committedCount}</strong></div>
                  {annotationStats.hasUnsavedChanges && (
                    <div style={{ color: "#d32f2f", fontWeight: "bold", marginTop: "5px" }}>
                      有未保存的更改
                    </div>
                  )} */}
                {/* </div> */}
              </div>
            </div>
          </>
        ) : (
          <div style={{ 
            display: "flex", 
            alignItems: "center", 
            justifyContent: "center", 
            height: "100%",
            color: "#666",
            fontSize: "16px"
          }}>
            {loading ? "正在查找可用文件..." : "请选择一个文件查看波形"}
          </div>
        )}
      </div>
    </div>
  );
}

export default App;
// [file content end]
