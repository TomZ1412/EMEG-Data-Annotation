import React, { useState, useRef, useEffect } from "react";

function Node({ node, onSelect, filter, currentUser, isTopLevel = false, onDatasetMark }) {
  const [contextMenu, setContextMenu] = useState({ visible: false, x: 0, y: 0 });
  const nodeRef = useRef(null);

  // 处理右键点击
  const handleContextMenu = (e) => {
    // 只有顶级目录才显示右键菜单
    if (isTopLevel && node.type === "dir") {
      e.preventDefault();
      e.stopPropagation();
      
      // 先关闭任何已存在的菜单，然后打开新的
      setContextMenu({
        visible: true,
        x: e.clientX,
        y: e.clientY
      });
    }
  };

  // 关闭右键菜单
  const closeContextMenu = () => {
    setContextMenu({ visible: false, x: 0, y: 0 });
  };

  // 点击页面其他地方关闭菜单
  useEffect(() => {
    const handleClickOutside = () => {
      closeContextMenu();
    };

    document.addEventListener('click', handleClickOutside);
    return () => {
      document.removeEventListener('click', handleClickOutside);
    };
  }, []);

  // 处理标记操作
  const handleMark = async (action) => {
    try {
      // 调用父组件传递的处理函数
      if (onDatasetMark) {
        // console.log(node.name, action);
        await onDatasetMark(node.name, action);
      }
      closeContextMenu();
    } catch (error) {
      console.error('标记数据集失败:', error);
    }
  };

  // 递归过滤子节点，保留包含有效文件的文件夹结构
  const filterChildren = (children) => {
    if (!children) return [];
    
    return children
      .map(child => {
        if (child.type === "file") {
          // 文件节点：根据筛选条件决定是否保留
          if (filter === "all") return child;
          if (filter === "annotated") return child.is_annotated ? child : null;
          if (filter === "unannotated") return !child.is_annotated ? child : null;
          return child;
        } else if (child.type === "dir") {
          // 目录节点：递归过滤子节点
          const filteredChildren = filterChildren(child.children);
          // 如果过滤后还有子节点，保留该目录
          if (filteredChildren.length > 0) {
            return {
              ...child,
              children: filteredChildren
            };
          }
          // 如果没有子节点，不保留该目录
          return null;
        }
        return null;
      })
      .filter(Boolean); // 过滤掉null值
  };

  if (node.type === "dir") {
    // 过滤子节点，保留包含有效文件的文件夹结构
    const filteredChildren = filterChildren(node.children);

    // 如果过滤后没有子节点且不是全部显示，则不显示该目录
    if (filteredChildren.length === 0 && filter !== "all") {
      return null;
    }

    return (
      <div ref={nodeRef} onContextMenu={handleContextMenu}>
        <details>
          <summary style={{ 
            cursor: "pointer", 
            fontWeight: "bold",
            backgroundColor: node.is_discarded ? "#ffe6e6" : "transparent",
            padding: "2px 5px",
            borderRadius: "3px"
          }}>
            {node.name}
            {node.is_discarded && (
              <span style={{ 
                color: "red", 
                fontSize: "12px",
                marginLeft: "5px"
              }}>
                [已丢弃]
              </span>
            )}
          </summary>
          <div style={{ marginLeft: "15px" }}>
            {filteredChildren.map((c, i) => (
              <Node 
                key={i} 
                node={c} 
                onSelect={onSelect} 
                filter={filter} 
                currentUser={currentUser}
                onDatasetMark={onDatasetMark}
              />
            ))}
          </div>
        </details>

        {/* 右键菜单 */}
        {contextMenu.visible && isTopLevel && (
          <div
            style={{
              position: "fixed",
              top: contextMenu.y,
              left: contextMenu.x,
              backgroundColor: "white",
              border: "1px solid #ccc",
              borderRadius: "4px",
              boxShadow: "0 2px 10px rgba(0,0,0,0.1)",
              zIndex: 1000,
              minWidth: "120px"
            }}
            onClick={(e) => e.stopPropagation()}
          >
            {!node.is_discarded ? (
              <div
                style={{
                  padding: "8px 12px",
                  cursor: "pointer",
                  borderBottom: "1px solid #eee",
                  color: "red"
                }}
                onClick={() => handleMark("discard")}
                onMouseEnter={(e) => e.target.style.backgroundColor = "#f5f5f5"}
                onMouseLeave={(e) => e.target.style.backgroundColor = "white"}
              >
                标记为丢弃
              </div>
            ) : (
              <div
                style={{
                  padding: "8px 12px",
                  cursor: "pointer",
                  borderBottom: "1px solid #eee",
                  color: "green"
                }}
                onClick={() => handleMark("cancel")}
                onMouseEnter={(e) => e.target.style.backgroundColor = "#f5f5f5"}
                onMouseLeave={(e) => e.target.style.backgroundColor = "white"}
              >
                取消丢弃标记
              </div>
            )}
          </div>
        )}
      </div>
    );
  } else {
    // 文件节点：根据筛选条件决定是否显示
    if (filter === "annotated" && !node.is_annotated) return null;
    if (filter === "unannotated" && node.is_annotated) return null;

    // 获取标注状态和活跃状态
    const isAnnotated = node.is_annotated || false;
    const isActive = node.is_active || false;
    const activeUser = node.active_user;
    const isOwnedByCurrentUser = isActive && activeUser === currentUser;
    
    // 决定是否可点击
    const isClickable = !isActive || isOwnedByCurrentUser;
    
    return (
      <div
        style={{
          cursor: isClickable ? "pointer" : "not-allowed",
          color: isAnnotated ? "green" : isActive ? "orange" : "blue",
          marginLeft: "10px",
          textDecoration: isClickable ? "underline" : "none",
          fontWeight: isAnnotated ? "bold" : "normal",
          display: "flex",
          alignItems: "center",
          gap: "5px",
          padding: "2px 0",
          opacity: isClickable ? 1 : 0.6
        }}
        onClick={() => isClickable && onSelect(node.path)}
        title={
          isAnnotated ? "已标注" : 
          isActive ? `正在被 ${activeUser} 标注` : 
          "未标注"
        }
      >
        {node.name}
        {isAnnotated && (
          <span style={{ 
            color: "green", 
            fontSize: "12px",
            fontWeight: "bold"
          }}>
            ✓
          </span>
        )}
        {isActive && (
          <span style={{ 
            color: "orange", 
            fontSize: "12px",
            fontWeight: "bold"
          }}>
            {isOwnedByCurrentUser ? "●" : "🔒"}
          </span>
        )}
      </div>
    );
  }
}

export default function FileTree({ tree, onSelect, currentUser, onDatasetMark }) {
  // const [filter, setFilter] = useState("all"); // all, annotated, unannotated
  const [filter, setFilter] = useState("annotated"); // all, annotated, unannotated
  const [activeContextMenu, setActiveContextMenu] = useState(null);

  // 关闭所有右键菜单
  const closeAllContextMenus = () => {
    setActiveContextMenu(null);
  };

  // 处理节点右键菜单
  const handleNodeContextMenu = (nodeName, menuState) => {
    if (menuState.visible) {
      setActiveContextMenu({ nodeName, ...menuState });
    } else {
      setActiveContextMenu(null);
    }
  };

  // 统计文件数量（基于当前筛选条件）
  const countFiles = (nodes) => {
    let total = 0;
    let annotated = 0;
    let active = 0;
    let discarded = 0;
    
    const countRecursive = (nodeList) => {
      nodeList.forEach(node => {
        if (node.type === "file") {
          // 根据筛选条件统计文件
          const shouldCount = 
            filter === "all" ||
            (filter === "annotated" && node.is_annotated) ||
            (filter === "unannotated" && !node.is_annotated);
          
          if (shouldCount) {
            total++;
            if (node.is_annotated) annotated++;
            if (node.is_active) active++;
          }
        } else if (node.type === "dir") {
          if (node.is_discarded) discarded++;
          if (node.children) {
            countRecursive(node.children);
          }
        }
      });
    };
    
    countRecursive(tree);
    return { total, annotated, unannotated: total - annotated, active, discarded };
  };

  const fileCounts = countFiles(tree);

  return (
    <div onClick={closeAllContextMenus}>
      {/* 筛选控件 */}
      <div style={{ 
        marginBottom: "15px", 
        padding: "10px", 
        backgroundColor: "#f5f5f5", 
        borderRadius: "4px" 
      }}>
        <div style={{ 
          display: "flex", 
          justifyContent: "space-between", 
          alignItems: "center",
          marginBottom: "8px"
        }}>
          <label htmlFor="file-filter" style={{ fontSize: "14px", fontWeight: "bold" }}>
            文件筛选:
          </label>
          <select
            id="file-filter"
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
            style={{
              padding: "4px 8px",
              borderRadius: "4px",
              border: "1px solid #ccc",
              fontSize: "12px"
            }}
          >
            <option value="all">全部文件</option>
            <option value="annotated">已标记</option>
            <option value="unannotated">未标记</option>
          </select>
        </div>
        
        {/* 文件统计信息 */}
        <div style={{ fontSize: "12px", color: "#666" }}>
          <div>总计: {fileCounts.total} 个文件</div>
          <div style={{ color: "green" }}>已标记: {fileCounts.annotated}</div>
          <div style={{ color: "blue" }}>未标记: {fileCounts.unannotated}</div>
          <div style={{ color: "orange" }}>正在标注: {fileCounts.active}</div>
          <div style={{ color: "red" }}>已丢弃数据集: {fileCounts.discarded}</div>
        </div>
        
        {/* 图例 */}
        <div style={{ fontSize: "10px", marginTop: "8px", padding: "4px", backgroundColor: "white", borderRadius: "3px" }}>
          <div>图例: 
            <span style={{color: "green"}}>✓ 已标注</span> | 
            <span style={{color: "orange"}}>● 自己标注</span> | 
            <span style={{color: "orange"}}>🔒 他人标注</span> |
            <span style={{color: "red"}}>[已丢弃] 丢弃的数据集</span>
          </div>
          <div style={{ marginTop: "2px", fontSize: "12px", color: "#666" }}>
            右键点击数据集文件夹可以标记为丢弃/取消,点击页面其他位置可以关闭右键菜单
          </div>
        </div>
      </div>

      {/* 文件树 */}
      <div style={{ maxHeight: "calc(100vh - 250px)", overflowY: "auto" }}>
        {tree.map((node, idx) => (
          <Node 
            key={idx} 
            node={node} 
            onSelect={onSelect} 
            filter={filter} 
            currentUser={currentUser}
            isTopLevel={true}
            onDatasetMark={onDatasetMark}
          />
        ))}
        
        {/* 无文件提示 */}
        {tree.length === 0 && (
          <div style={{ 
            textAlign: "center", 
            color: "#999", 
            padding: "20px",
            fontStyle: "italic"
          }}>
            暂无文件
          </div>
        )}
        
        {/* 筛选结果为空提示 */}
        {tree.length > 0 && (() => {
          // 检查当前筛选条件下是否有文件显示
          const hasVisibleFiles = tree.some(node => {
            const checkNode = (n) => {
              if (n.type === "file") {
                if (filter === "all") return true;
                if (filter === "annotated") return n.is_annotated;
                if (filter === "unannotated") return !n.is_annotated;
              }
              if (n.type === "dir" && n.children) {
                return n.children.some(checkNode);
              }
              return false;
            };
            return checkNode(node);
          });
          
          if (!hasVisibleFiles) {
            return (
              <div style={{ 
                textAlign: "center", 
                color: "#999", 
                padding: "20px",
                fontStyle: "italic"
              }}>
                {filter === "annotated" 
                  ? "暂无已标记的文件" 
                  : "暂无未标记的文件"}
              </div>
            );
          }
          return null;
        })()}
      </div>
    </div>
  );
}