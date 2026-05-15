import React, { useEffect, useRef, useState } from "react";
import * as Plotly from "plotly.js-dist-min";

export default function WaveformViewer({ 
  data, badChannels, setBadChannels, loading, onDataDiscardedChange, onSelectSubBlock
}) {
  const scrollPositionRef = useRef(0);
  const waveformContainerRef = useRef(null);
  const psdContainerRef = useRef(null);
  const plotlyRefs = useRef([]);
  const [activeView, setActiveView] = useState("wav");
  const [scalingFactor, setScalingFactor] = useState(1);
  const [isDataDiscarded, setIsDataDiscarded] = useState(false);
  const [subBlockPosition, setSubBlockPosition] = useState(0);
  const [totalSubBlocks, setTotalSubBlocks] = useState(1);
  const [currentSubBlockIndex, setCurrentSubBlockIndex] = useState(0); // 当前子图索引
  
  // console.log(data);

  // 获取当前活动视图的数据
  const getCurrentData = () => {
    if (!data) return {};
    return data[activeView] || {};
  };

  // 获取PSD数据
  const getPsdData = () => {
    if (!data || !data["psd"]) return null;
    return data["psd"];
  };

  const getScalingFactor = () => {
    if (!data) return 1;
    return data["scaling_factor"] || 1;
  };

  // 获取所有通道名称（用于统计）
  const getAllChannelNames = () => {
    if (!data) return [];
    
    // 优先使用波形数据的通道，如果没有则使用PSD数据的通道
    if (data.wav && Object.keys(data.wav).length > 0) {
      return Object.keys(data.wav);
    }
    
    if (data.psd && data.psd.psd) {
      return Object.keys(data.psd.psd);
    }
    
    return [];
  };

  // 获取当前显示的通道数量
  const getCurrentChannelCount = () => {
    const currentData = getCurrentData();
    if (currentData && Object.keys(currentData).length > 0) {
      return Object.keys(currentData).length;
    }
    
    // 对于PSD视图，特殊处理
    if (activeView === "psd") {
      const psdData = getPsdData();
      if (psdData && psdData.psd) {
        return Object.keys(psdData.psd).length;
      }
    }
    
    return 0;
  };

  // 计算自动缩放因子
  const calculateAutoScalingFactor = (currentData) => {
    return getScalingFactor();
  };

  // 清理Plotly图表
  const cleanupPlotlyCharts = () => {
    plotlyRefs.current.forEach(ref => {
      if (ref && ref.parentNode) {
        Plotly.purge(ref);
      }
    });
    plotlyRefs.current = [];
  };

  // 组件卸载时清理
  useEffect(() => {
    return () => {
      cleanupPlotlyCharts();
    };
  }, []);

  useEffect(() => {
    if (data) {
      // 尝试从不同位置获取子图数量
      let subBlocks = 1;
      
      if (data.totalSubBlocks !== undefined) {
        subBlocks = data.totalSubBlocks;
      } else if (data.metadata && data.metadata.totalSubBlocks !== undefined) {
        subBlocks = data.metadata.totalSubBlocks;
      } else if (data.info && data.info.totalSubBlocks !== undefined) {
        subBlocks = data.info.totalSubBlocks;
      }
      
      setTotalSubBlocks(Math.max(1, subBlocks));
    }
  }, [data]);

  // 自动计算初始缩放因子
  useEffect(() => {
    if (data && activeView === "wav") {
      const currentData = getCurrentData();
      const factor = calculateAutoScalingFactor(currentData);
      setScalingFactor(factor);
    }
  }, [data, activeView]);

  // 子图位置变化时请求数据
  useEffect(() => {
    if (onSelectSubBlock && totalSubBlocks > 1) {
      const subBlockIndex = Math.floor(subBlockPosition * (totalSubBlocks - 1));
      setCurrentSubBlockIndex(subBlockIndex);
      onSelectSubBlock(subBlockIndex);
    }
  }, [subBlockPosition, totalSubBlocks, onSelectSubBlock]);

  // 渲染波形视图
  useEffect(() => {
    if (activeView !== "wav") {
      return;
    }
  
    const currentData = getCurrentData();
    if (!currentData || Object.keys(currentData).length === 0) return;
  
    const container = waveformContainerRef.current;
    if (!container) return;
  
    setTimeout(() => {
      cleanupPlotlyCharts();
      container.innerHTML = "";
    
      const channelNames = Object.keys(currentData);
      const nChannels = channelNames.length;
      
      // 设置总时长为30秒
      const totalDuration = 30; // 秒
      const nSamples = Math.max(...channelNames.map(ch => currentData[ch].length));
      
      // 计算实际采样率
      const actualSamplingRate = nSamples / totalDuration;
      
      // 生成时间轴：0 到 30 秒
      const time = Array.from({ length: nSamples }, (_, i) => i * (totalDuration / nSamples));
    
      const offset = 0.6;
    
      const traces = channelNames.map((ch, idx) => {
        const channelData = currentData[ch];
        const mean = channelData.reduce((sum, val) => sum + val, 0) / channelData.length;
        const scaledData = channelData.map(v => 
          (v - mean) * scalingFactor + (nChannels - idx - 1) * offset
        );
      
        return {
          x: time,
          y: scaledData,
          name: ch,
          mode: "lines",
          line: {
            color: badChannels.includes(ch) ? "red" : "#1565c0",
            width: badChannels.includes(ch) ? 1.5 : 1,
          },
          hoverinfo: "x+y+name",
          opacity: 0.9,
        };
      });
    
      const annotations = channelNames.map((ch, idx) => ({
        x: -0.02,
        y: (nChannels - idx - 1) * offset,
        xref: "paper",
        yref: "y",
        text: ch,
        showarrow: false,
        font: {
          size: 10,
          color: badChannels.includes(ch) ? "red" : "black",
        },
        xanchor: "right",
        align: "right",
      }));
    
      const layout = {
        margin: { l: 60, r: 20, t: 10, b: 40 },
        xaxis: {
          title: "时间 (s)",
          showgrid: false,
          range: [0, totalDuration], // 固定X轴范围为0-30秒
        },
        yaxis: {
          showticklabels: false,
          showgrid: false,
          zeroline: false,
          title: "通道",
          range: [-offset, nChannels * offset],
        },
        height: 80 + nChannels * 40,
        paper_bgcolor: "#fff",
        plot_bgcolor: "#fff",
        showlegend: false,
        annotations,
      };
    
      const plotDiv = document.createElement("div");
      plotDiv.style.width = "100%";
      plotDiv.style.height = `${layout.height}px`;
      container.appendChild(plotDiv);
      plotlyRefs.current.push(plotDiv);
    
      Plotly.newPlot(plotDiv, traces, layout, { displayModeBar: false });
    
      plotDiv.on("plotly_click", (event) => {
        const point = event.points?.[0];
        if (!point) return;
        const ch = point.data.name;
      
        scrollPositionRef.current = waveformContainerRef.current?.scrollTop || 0;
      
        setBadChannels((prev) =>
          prev.includes(ch)
            ? prev.filter((c) => c !== ch)
            : [...prev, ch]
        );
      });
    
      if (waveformContainerRef.current && scrollPositionRef.current > 0) {
        waveformContainerRef.current.scrollTop = scrollPositionRef.current;
      }
    }, 0);
  }, [data, badChannels, setBadChannels, activeView, scalingFactor]);

  // 渲染PSD视图 - 修复：正确显示通道总数
  useEffect(() => {
    if (activeView !== "psd") {
      return;
    }

    const psdData = getPsdData();
    if (!psdData || !psdData.frequencies || !psdData.psd) return;

    const container = psdContainerRef.current;
    if (!container) return;

    setTimeout(() => {
      cleanupPlotlyCharts();
      container.innerHTML = "";

      const { frequencies, psd } = psdData;
      const channelNames = Object.keys(psd);
      const totalChannels = channelNames.length;

      const plotDiv = document.createElement("div");
      plotDiv.style.width = "100%";
      plotDiv.style.height = "500px";
      container.appendChild(plotDiv);
      plotlyRefs.current.push(plotDiv);

      const traces = channelNames.map((ch) => ({
        x: frequencies,
        y: psd[ch],
        name: ch,
        mode: "lines",
        line: {
          width: badChannels.includes(ch) ? 2 : 1,
          color: badChannels.includes(ch) ? "red" : undefined,
        },
        opacity: badChannels.includes(ch) ? 1 : 0.7,
        hoverinfo: "x+y+name",
      }));

      const layout = {
        title: `功率谱密度 (${totalChannels} 个通道)`,
        xaxis: {
          title: "频率 (Hz)",
          showgrid: true,
          gridcolor: "#f0f0f0",
        },
        yaxis: {
          title: "功率谱密度 (dB/Hz)",
          type: "log",
          showgrid: true,
          gridcolor: "#f0f0f0",
        },
        margin: { l: 60, r: 30, t: 50, b: 50 },
        paper_bgcolor: "#fff",
        plot_bgcolor: "#fff",
        showlegend: true,
        legend: {
          x: 1.05,
          y: 1,
          xanchor: "left",
          yanchor: "top",
          bgcolor: "rgba(255,255,255,0.8)",
        },
        hovermode: "closest",
      };

      Plotly.newPlot(plotDiv, traces, layout, { displayModeBar: true });

      plotDiv.on("plotly_click", (event) => {
        const point = event.points?.[0];
        if (!point) return;
        const ch = point.data.name;

        setBadChannels((prev) =>
          prev.includes(ch)
            ? prev.filter((c) => c !== ch)
            : [...prev, ch]
        );
      });
    }, 0);
  }, [data, badChannels, setBadChannels, activeView]);

  // 缩放控制组件
  const ScalingControl = () => {
    const currentData = getCurrentData();
    if (!currentData || Object.keys(currentData).length === 0 || activeView !== "wav") {
      return null;
    }

    const handleScalingChange = (value) => {
      setScalingFactor(parseFloat(value));
    };

    const autoScale = () => {
      const factor = calculateAutoScalingFactor(currentData);
      setScalingFactor(factor);
    };

    const zoomIn = () => {
      setScalingFactor(prev => prev * 1.2);
    };

    const zoomOut = () => {
      setScalingFactor(prev => prev * 0.8);
    };

    return (
      <div style={{
        padding: "10px",
        backgroundColor: "#f5f5f5",
        border: "1px solid #ddd",
        borderRadius: "4px",
        marginBottom: "10px",
        width: "70%"
      }}>
        <div style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          marginBottom: "8px"
        }}>
          <span style={{ fontSize: "14px", fontWeight: "bold" }}>
            信号缩放: {scalingFactor.toFixed(2)}x
          </span>
          <div style={{ display: "flex", gap: "8px" }}>
            <button
              onClick={zoomOut}
              style={{
                padding: "4px 8px",
                fontSize: "12px",
                backgroundColor: "#2196F3",
                color: "white",
                border: "none",
                borderRadius: "3px",
                cursor: "pointer"
              }}
            >
              缩小
            </button>
            <button
              onClick={autoScale}
              style={{
                padding: "4px 8px",
                fontSize: "12px",
                backgroundColor: "#4CAF50",
                color: "white",
                border: "none",
                borderRadius: "3px",
                cursor: "pointer"
              }}
            >
              自动缩放
            </button>
            <button
              onClick={zoomIn}
              style={{
                padding: "4px 8px",
                fontSize: "12px",
                backgroundColor: "#2196F3",
                color: "white",
                border: "none",
                borderRadius: "3px",
                cursor: "pointer"
              }}
            >
              放大
            </button>
          </div>
        </div>
        
        <input
          type="range"
          min="0.1"
          max="5"
          step="0.1"
          value={scalingFactor}
          onChange={(e) => handleScalingChange(e.target.value)}
          style={{ width: "100%" }}
        />
        {/* 自动缩放使通道极差的平均值占通道宽度的80% */}
        {/* <div style={{ fontSize: "12px", color: "#666", marginTop: "4px" }}>
          自动缩放使通道极差的平均值占通道宽度的80%
        </div> */}
      </div>
    );
  };

  // 数据弃用控制组件
  const DataDiscardControl = () => {
    return (
      <div style={{
        padding: "10px",
        backgroundColor: isDataDiscarded ? "#ffebee" : "#e8f5e8",
        border: `1px solid ${isDataDiscarded ? "#f44336" : "#4CAF50"}`,
        borderRadius: "4px",
        marginBottom: "10px",
        width: "70%",
        display: "flex",
        justifyContent: "space-between",
        alignItems: "center"
      }}>
        <span style={{
          fontSize: "14px",
          fontWeight: "bold",
          color: isDataDiscarded ? "#d32f2f" : "#2e7d32"
        }}>
          数据状态: {isDataDiscarded ? "已弃用" : "正常使用"}
        </span>
        <button
          onClick={() => {
            const confirmMessage = isDataDiscarded 
              ? "确定要恢复使用此数据吗？"
              : "确定要弃用此数据吗？弃用的数据将不会被后续分析使用。";
            
            if (window.confirm(confirmMessage)) {
              setIsDataDiscarded(!isDataDiscarded);
            }
          }}
          style={{
            padding: "6px 12px",
            fontSize: "12px",
            backgroundColor: isDataDiscarded ? "#4CAF50" : "#f44336",
            color: "white",
            border: "none",
            borderRadius: "3px",
            cursor: "pointer"
          }}
        >
          {isDataDiscarded ? "恢复使用" : "弃用数据"}
        </button>
      </div>
    );
  };

  // 子图选择器组件
  const SubBlockSelector = () => {
    if (totalSubBlocks <= 1) return null;
  
    // 计算当前子图索引
    const currentSubBlock = Math.floor(subBlockPosition * (totalSubBlocks - 1)) + 1;
    const currentIndex = Math.floor(subBlockPosition * (totalSubBlocks - 1));
  
    // 处理上一个子图
    const handlePrev = () => {
      if (currentIndex > 0) {
        const newPosition = (currentIndex - 1) / (totalSubBlocks - 1);
        setSubBlockPosition(newPosition);
      }
    };
  
    // 处理下一个子图
    const handleNext = () => {
      if (currentIndex < totalSubBlocks - 1) {
        const newPosition = (currentIndex + 1) / (totalSubBlocks - 1);
        setSubBlockPosition(newPosition);
      }
    };
  
    const handlePositionChange = (value) => {
      setSubBlockPosition(parseFloat(value));
    };
  
    return (
      <div style={{
        padding: "10px",
        backgroundColor: "#e3f2fd",
        border: "1px solid #90caf9",
        borderRadius: "4px",
        marginBottom: "10px",
        width: "70%"
      }}>
        {/* <div style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          marginBottom: "8px"
        }}>
          <span style={{ fontSize: "14px", fontWeight: "bold", color: "#1565c0" }}>
            子图选择: {currentSubBlock} / {totalSubBlocks}
          </span>
          <div style={{ display: "flex", gap: "4px" }}>
            {Array.from({ length: totalSubBlocks }, (_, i) => (
              <div
                key={i}
                style={{
                  width: "8px",
                  height: "8px",
                  borderRadius: "50%",
                  backgroundColor: i === currentIndex ? "#1565c0" : "#90caf9",
                  cursor: "pointer"
                }}
                onClick={() => setSubBlockPosition(i / (totalSubBlocks - 1))}
                title={`跳转到子图 ${i + 1}`}
              />
            ))}
          </div>
        </div> */}
        
        {/* 滑条和按钮容器 */}
        <div style={{
          display: "flex",
          alignItems: "center",
          gap: "10px",
          width: "100%"
        }}>
          {/* 上一个按钮 */}
          <button
            onClick={handlePrev}
            disabled={currentIndex <= 0}
            style={{
              width: "32px",
              height: "32px",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              backgroundColor: currentIndex <= 0 ? "#e0e0e0" : "#2196F3",
              color: "white",
              border: "none",
              borderRadius: "4px",
              cursor: currentIndex <= 0 ? "not-allowed" : "pointer",
              transition: "all 0.2s ease"
            }}
            title="上一个子图"
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
              <path 
                d="M15 18L9 12L15 6" 
                stroke={currentIndex <= 0 ? "#9e9e9e" : "white"} 
                strokeWidth="2" 
                strokeLinecap="round" 
                strokeLinejoin="round"
              />
            </svg>
          </button>
          
          {/* 滑条 */}
          <div style={{ flex: 1 }}>
            <input
              type="range"
              min="0"
              max="1"
              step={1 / (totalSubBlocks - 1)}
              value={subBlockPosition}
              onChange={(e) => handlePositionChange(e.target.value)}
              style={{ width: "100%" }}
            />
          </div>
          
          {/* 下一个按钮 */}
          <button
            onClick={handleNext}
            disabled={currentIndex >= totalSubBlocks - 1}
            style={{
              width: "32px",
              height: "32px",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              backgroundColor: currentIndex >= totalSubBlocks - 1 ? "#e0e0e0" : "#2196F3",
              color: "white",
              border: "none",
              borderRadius: "4px",
              cursor: currentIndex >= totalSubBlocks - 1 ? "not-allowed" : "pointer",
              transition: "all 0.2s ease"
            }}
            title="下一个子图"
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
              <path 
                d="M9 18L15 12L9 6" 
                stroke={currentIndex >= totalSubBlocks - 1 ? "#9e9e9e" : "white"} 
                strokeWidth="2" 
                strokeLinecap="round" 
                strokeLinejoin="round"
              />
            </svg>
          </button>
        </div>
        
        <div style={{ fontSize: "12px", color: "#1565c0", marginTop: "4px" }}>
          拖动滑块选择不同时间段的子图数据，点按上方圆点可快速跳转，使用左右箭头可逐个子图切换
        </div>
      </div>
    );
  };

  // 视图切换标签
  const ViewTabs = () => {
    const tabs = [
      { key: "wav", label: "时域波形" },
      { key: "psd", label: "功率谱密度" }
    ];

    return (
      <div style={{ 
        display: "flex", 
        width: "70%",
        borderBottom: "1px solid #ccc",
        marginBottom: "10px"
      }}>
        {tabs.map(tab => (
          <button
            key={tab.key}
            onClick={() => setActiveView(tab.key)}
            style={{
              padding: "8px 16px",
              backgroundColor: activeView === tab.key ? "#2196F3" : "transparent",
              color: activeView === tab.key ? "white" : "#333",
              border: "none",
              borderBottom: activeView === tab.key ? "2px solid #2196F3" : "2px solid transparent",
              cursor: "pointer",
              fontSize: "14px",
              fontWeight: activeView === tab.key ? "bold" : "normal",
              transition: "all 0.2s"
            }}
          >
            {tab.label}
          </button>
        ))}
      </div>
    );
  };

  // 渲染波形视图内容
  const WaveformView = () => {
    const currentData = getCurrentData();
    
    if (loading) {
      return (
        <div style={{ 
          display: "flex", 
          alignItems: "center", 
          justifyContent: "center", 
          height: "100%", 
          color: "#666",
          fontSize: "16px"
        }}>
          正在加载波形数据...
        </div>
      );
    }

    if (!currentData || Object.keys(currentData).length === 0) {
      return (
        <div style={{ 
          display: "flex", 
          alignItems: "center", 
          justifyContent: "center", 
          height: "100%", 
          color: "#999",
          fontSize: "14px"
        }}>
          暂无波形数据
        </div>
      );
    }

    return (
      <div
        ref={waveformContainerRef}
        style={{
          width: "100%",
          height: "100%",
          overflowY: "scroll"
        }}
      />
    );
  };

  // 渲染PSD视图
  const PsdView = () => {
    const psdData = getPsdData();
    
    if (loading) {
      return (
        <div style={{ 
          display: "flex", 
          alignItems: "center", 
          justifyContent: "center", 
          height: "100%", 
          color: "#666",
          fontSize: "16px"
        }}>
          正在加载功率谱数据...
        </div>
      );
    }

    if (!psdData) {
      return (
        <div style={{ 
          display: "flex", 
          alignItems: "center", 
          justifyContent: "center", 
          height: "100%", 
          color: "#999",
          fontSize: "14px"
        }}>
          暂无PSD数据
        </div>
      );
    }

    return (
      <div
        ref={psdContainerRef}
        style={{
          width: "100%",
          height: "100%",
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: "center",
          padding: "20px"
        }}
      />
    );
  };

  const allChannelNames = getAllChannelNames();
  const currentChannelCount = getCurrentChannelCount();
  
  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%" }}>
      {/* 数据弃用控制 */}
      {/* <DataDiscardControl /> */}
      
      {/* 视图切换标签 */}
      <ViewTabs />

      
      
      {/* 缩放控制（仅在波形视图显示） */}
      {activeView === "wav" && <ScalingControl />}
      
      {/* 坏道统计信息 - 修复：正确显示通道总数 */}
      <div style={{ 
        padding: "8px 12px", 
        backgroundColor: "#f0f0f0", 
        borderBottom: "1px solid #ccc",
        fontSize: "14px",
        fontWeight: "bold",
        display: "flex",
        justifyContent: "space-between",
        alignItems: "center",
        width: "70%"
      }}>
        <div>
          坏道: {badChannels.length} / {allChannelNames.length}
          {badChannels.length > 0 && (
            <span style={{ marginLeft: "10px", color: "red" }}>
              {badChannels.join(", ")}
            </span>
          )}
        </div>
        
        {/* 操作按钮 */}
        <div style={{ display: "flex", gap: "8px" }}>
          <button
            onClick={() => {
              const confirmed = window.confirm("确定要清空所有坏道标记吗？");
              if (confirmed) {
                setBadChannels([]);
              }
            }}
            disabled={badChannels.length === 0 || loading}
            style={{ 
              padding: "4px 8px",
              fontSize: "12px",
              borderRadius: "4px",
              backgroundColor: badChannels.length === 0 ? "#ccc" : "#ff9800",
              color: "white",
              border: "none",
              cursor: badChannels.length === 0 || loading ? "not-allowed" : "pointer"
            }}
          >
            清空选择
          </button>
          
          <button
            onClick={() => {
              if (allChannelNames.length > 0) {
                setBadChannels([...allChannelNames]);
              }
            }}
            disabled={allChannelNames.length === 0 || loading}
            style={{ 
              padding: "4px 8px",
              fontSize: "12px",
              borderRadius: "4px",
              backgroundColor: allChannelNames.length === 0 ? "#ccc" : "#f44336",
              color: "white",
              border: "none",
              cursor: allChannelNames.length === 0 || loading ? "not-allowed" : "pointer"
            }}
          >
            全选为坏道
          </button>
        </div>
      </div>
      
      {/* 内容容器 */}
      <div
        style={{
          width: "70%",
          height: "600px",
          border: "1px solid #ccc",
          borderRadius: "0 0 8px 8px",
          backgroundColor: "#fafafa",
          position: "relative",
          overflow: activeView === "wav" ? "hidden" : "visible"
        }}
      >
        {activeView === "wav" ? <WaveformView /> : <PsdView />}
      </div>

      {/* 子图选择器 */}
      <SubBlockSelector />
      
      {/* 使用说明 */}
      <div style={{ 
        marginTop: "10px", 
        padding: "8px 12px",
        backgroundColor: "#e3f2fd",
        borderRadius: "4px",
        fontSize: "12px",
        color: "#1565c0",
        width: "70%"
      }}>
        <strong>使用说明:</strong> 
        {activeView === "wav" 
          ? "点击通道名称/波形可以标记/取消标记为坏道。已标记的坏道会显示为红色。使用缩放控制可以调整信号显示幅度，自动缩放使通道极差的平均值占通道宽度的80%。" 
          : "点击PSD图中的线条可以标记/取消标记为坏道。坏道显示为红色粗线。"}
        {totalSubBlocks > 1 && " 使用子图选择器可以查看不同时间段的数据。"}
        {isDataDiscarded && " 当前数据已被标记为弃用。"}
        {" 坏道标记在所有子图间共享。"}
      </div>
    </div>
  );
}