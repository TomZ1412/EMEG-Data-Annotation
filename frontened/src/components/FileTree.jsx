import React, { memo, useMemo, useState } from "react";

const FILTERS = {
  all: "全部",
  annotated: "已标注",
  unannotated: "未标注",
};

function fileVisible(node, filter) {
  if (node.type !== "file") return true;
  if (filter === "annotated") return Boolean(node.is_annotated);
  if (filter === "unannotated") return !node.is_annotated;
  return true;
}

function filterTree(nodes, filter) {
  return nodes
    .map((node) => {
      if (node.type === "file") return fileVisible(node, filter) ? node : null;
      const children = filterTree(node.children || [], filter);
      return children.length ? { ...node, children } : null;
    })
    .filter(Boolean);
}

function countFiles(nodes) {
  const counts = { total: 0, annotated: 0, unannotated: 0, active: 0, discarded: 0 };

  const walk = (items) => {
    items.forEach((node) => {
      if (node.type === "file") {
        counts.total += 1;
        if (node.is_annotated) counts.annotated += 1;
        else counts.unannotated += 1;
        if (node.is_active) counts.active += 1;
      } else {
        if (node.is_discarded) counts.discarded += 1;
        walk(node.children || []);
      }
    });
  };

  walk(nodes);
  return counts;
}

const Node = memo(function Node({ node, onSelect, currentUser, isTopLevel = false, onDatasetMark }) {
  const [open, setOpen] = useState(false);
  const [menu, setMenu] = useState(null);

  if (node.type === "dir") {
    const handleContextMenu = (event) => {
      if (!isTopLevel) return;
      event.preventDefault();
      event.stopPropagation();
      setMenu({ x: event.clientX, y: event.clientY });
    };

    const markDataset = async (action) => {
      if (onDatasetMark) await onDatasetMark(node.name, action);
      setMenu(null);
    };

    return (
      <div onContextMenu={handleContextMenu}>
        <div style={styles.dirRow} onClick={() => setOpen((value) => !value)}>
          <span style={styles.caret}>{open ? "v" : ">"}</span>
          <span>{node.name}</span>
          {node.is_discarded && <span style={styles.discarded}>已弃用</span>}
        </div>

        {open && (
          <div style={styles.children}>
            {(node.children || []).map((child) => (
              <Node
                key={`${child.type}:${child.path || child.name}`}
                node={child}
                onSelect={onSelect}
                currentUser={currentUser}
                onDatasetMark={onDatasetMark}
              />
            ))}
          </div>
        )}

        {menu && isTopLevel && (
          <div style={{ ...styles.contextMenu, top: menu.y, left: menu.x }} onClick={(event) => event.stopPropagation()}>
            {node.is_discarded ? (
              <button type="button" style={styles.contextButton} onClick={() => markDataset("cancel")}>
                取消弃用
              </button>
            ) : (
              <button type="button" style={{ ...styles.contextButton, color: "#dc2626" }} onClick={() => markDataset("discard")}>
                标记为弃用
              </button>
            )}
          </div>
        )}
      </div>
    );
  }

  const isAnnotated = Boolean(node.is_annotated);
  const isActive = Boolean(node.is_active);
  const activeUser = node.active_user;
  const isOwnedByCurrentUser = isActive && activeUser === currentUser;
  const isClickable = !isActive || isOwnedByCurrentUser;

  return (
    <button
      type="button"
      style={fileStyle(isAnnotated, isActive, isClickable)}
      disabled={!isClickable}
      onClick={() => onSelect(node.path)}
      title={isAnnotated ? "已标注" : isActive ? `正在被 ${activeUser} 标注` : "未标注"}
    >
      <span style={styles.fileName}>{node.name}</span>
      {isAnnotated && <span style={styles.annotatedMark}>OK</span>}
      {isActive && <span style={styles.activeMark}>{isOwnedByCurrentUser ? "ME" : "BUSY"}</span>}
    </button>
  );
});

export default function FileTree({ tree, onSelect, currentUser, onDatasetMark }) {
  const [filter, setFilter] = useState("all");
  const visibleTree = useMemo(() => filterTree(tree, filter), [tree, filter]);
  const counts = useMemo(() => countFiles(tree), [tree]);

  return (
    <div onClick={() => {}}>
      <div style={styles.toolbar}>
        <div style={styles.toolbarRow}>
          <label htmlFor="file-filter" style={styles.label}>文件筛选</label>
          <select id="file-filter" value={filter} onChange={(event) => setFilter(event.target.value)} style={styles.select}>
            {Object.entries(FILTERS).map(([value, label]) => (
              <option key={value} value={value}>{label}</option>
            ))}
          </select>
        </div>

        <div style={styles.counts}>
          <span>总计 {counts.total}</span>
          <span style={{ color: "#15803d" }}>已标注 {counts.annotated}</span>
          <span style={{ color: "#2563eb" }}>未标注 {counts.unannotated}</span>
          <span style={{ color: "#d97706" }}>占用 {counts.active}</span>
          <span style={{ color: "#dc2626" }}>弃用数据集 {counts.discarded}</span>
        </div>
      </div>

      <div style={styles.tree}>
        {visibleTree.map((node) => (
          <Node
            key={`${node.type}:${node.path || node.name}`}
            node={node}
            onSelect={onSelect}
            currentUser={currentUser}
            isTopLevel
            onDatasetMark={onDatasetMark}
          />
        ))}
        {!visibleTree.length && <div style={styles.empty}>暂无匹配文件</div>}
      </div>
    </div>
  );
}

const styles = {
  toolbar: {
    marginBottom: 12,
    padding: 10,
    background: "#f8fafc",
    borderBottom: "1px solid #e5e7eb",
  },
  toolbarRow: {
    display: "flex",
    alignItems: "center",
    justifyContent: "space-between",
    gap: 8,
    marginBottom: 8,
  },
  label: {
    fontSize: 14,
    fontWeight: 700,
  },
  select: {
    padding: "4px 8px",
    borderRadius: 4,
    border: "1px solid #cbd5e1",
    fontSize: 12,
  },
  counts: {
    display: "grid",
    gridTemplateColumns: "repeat(2, minmax(0, 1fr))",
    gap: 4,
    fontSize: 12,
    color: "#475569",
  },
  tree: {
    maxHeight: "calc(100vh - 190px)",
    overflowY: "auto",
    padding: "0 8px 14px",
  },
  dirRow: {
    display: "flex",
    alignItems: "center",
    gap: 6,
    padding: "4px 5px",
    borderRadius: 4,
    cursor: "pointer",
    fontWeight: 700,
    color: "#111827",
    userSelect: "none",
  },
  caret: {
    width: 12,
    color: "#64748b",
    fontFamily: "monospace",
  },
  children: {
    marginLeft: 14,
  },
  discarded: {
    padding: "1px 5px",
    borderRadius: 4,
    background: "#fee2e2",
    color: "#dc2626",
    fontSize: 11,
  },
  contextMenu: {
    position: "fixed",
    zIndex: 1000,
    minWidth: 120,
    padding: 4,
    border: "1px solid #cbd5e1",
    borderRadius: 6,
    background: "#fff",
    boxShadow: "0 8px 24px rgba(15, 23, 42, 0.18)",
  },
  contextButton: {
    width: "100%",
    padding: "8px 10px",
    border: "none",
    background: "transparent",
    textAlign: "left",
    cursor: "pointer",
  },
  fileName: {
    overflow: "hidden",
    textOverflow: "ellipsis",
    whiteSpace: "nowrap",
  },
  annotatedMark: {
    color: "#15803d",
    fontSize: 11,
    fontWeight: 800,
  },
  activeMark: {
    color: "#d97706",
    fontSize: 11,
    fontWeight: 800,
  },
  empty: {
    padding: 20,
    color: "#94a3b8",
    textAlign: "center",
    fontStyle: "italic",
  },
};

function fileStyle(isAnnotated, isActive, isClickable) {
  return {
    width: "100%",
    display: "flex",
    alignItems: "center",
    gap: 5,
    padding: "3px 4px",
    border: "none",
    background: "transparent",
    color: isAnnotated ? "#15803d" : isActive ? "#d97706" : "#2563eb",
    cursor: isClickable ? "pointer" : "not-allowed",
    textAlign: "left",
    textDecoration: isClickable ? "underline" : "none",
    fontWeight: isAnnotated ? 700 : 400,
    opacity: isClickable ? 1 : 0.6,
  };
}
