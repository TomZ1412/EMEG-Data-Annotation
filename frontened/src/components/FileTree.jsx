import React, { memo, useMemo, useState } from "react";

const TEXT = {
  en: {
    filters: {
      all: "All",
      annotated: "Annotated",
      unannotated: "Unannotated",
    },
    annotated: "Annotated",
    unannotated: "Unannotated",
    busyBy: (user) => `Being annotated by ${user || "another user"}`,
    annotatedLocked: "Already annotated",
    fileFilter: "File filter",
    total: "Total",
    busy: "Busy",
    noMatchingFiles: "No matching files",
  },
  zh: {
    filters: {
      all: "全部",
      annotated: "已标注",
      unannotated: "未标注",
    },
    annotated: "已标注",
    unannotated: "未标注",
    busyBy: (user) => `正在被 ${user || "其他用户"} 标注`,
    annotatedLocked: "已标注，当前不可打开",
    fileFilter: "文件筛选",
    total: "总计",
    busy: "占用",
    noMatchingFiles: "暂无匹配文件",
  },
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
  const counts = { total: 0, annotated: 0, unannotated: 0, active: 0 };

  const walk = (items) => {
    items.forEach((node) => {
      if (node.type === "file") {
        counts.total += 1;
        if (node.is_annotated) counts.annotated += 1;
        else counts.unannotated += 1;
        if (node.is_active) counts.active += 1;
      } else {
        walk(node.children || []);
      }
    });
  };

  walk(nodes);
  return counts;
}

const Node = memo(function Node({ node, onSelect, currentUser, labels }) {
  const [open, setOpen] = useState(false);

  if (node.type === "dir") {
    return (
      <div>
        <div style={styles.dirRow} onClick={() => setOpen((value) => !value)}>
          <span style={styles.caret}>{open ? "v" : ">"}</span>
          <span>{node.name}</span>
        </div>

        {open && (
          <div style={styles.children}>
            {(node.children || []).map((child) => (
              <Node
                key={`${child.type}:${child.path || child.name}`}
                node={child}
                onSelect={onSelect}
                currentUser={currentUser}
                labels={labels}
              />
            ))}
          </div>
        )}
      </div>
    );
  }

  const isAnnotated = Boolean(node.is_annotated);
  const isActive = Boolean(node.is_active);
  const activeUser = node.active_user;
  const isOwnedByCurrentUser = isActive && activeUser === currentUser;
  const canOpen = node.can_open !== false;
  const isClickable = canOpen && (!isActive || isOwnedByCurrentUser);
  const title = !canOpen
    ? labels.annotatedLocked
    : isAnnotated
    ? labels.annotated
    : isActive
      ? labels.busyBy(activeUser)
      : labels.unannotated;

  return (
    <button
      type="button"
      style={fileStyle(isAnnotated, isActive, isClickable)}
      disabled={!isClickable}
      onClick={() => onSelect(node.path)}
      title={title}
    >
      <span style={styles.fileName}>{node.name}</span>
      {isAnnotated && <span style={styles.annotatedMark}>OK</span>}
      {isActive && <span style={styles.activeMark}>{isOwnedByCurrentUser ? "ME" : "BUSY"}</span>}
    </button>
  );
});

export default function FileTree({ tree, onSelect, currentUser, language = "en" }) {
  const [filter, setFilter] = useState("all");
  const labels = TEXT[language] || TEXT.en;
  const visibleTree = useMemo(() => filterTree(tree, filter), [tree, filter]);
  const counts = useMemo(() => countFiles(tree), [tree]);

  return (
    <div>
      <div style={styles.toolbar}>
        <div style={styles.toolbarRow}>
          <label htmlFor="file-filter" style={styles.label}>{labels.fileFilter}</label>
          <select id="file-filter" value={filter} onChange={(event) => setFilter(event.target.value)} style={styles.select}>
            {Object.entries(labels.filters).map(([value, label]) => (
              <option key={value} value={value}>{label}</option>
            ))}
          </select>
        </div>

        <div style={styles.counts}>
          <span>{labels.total} {counts.total}</span>
          <span style={{ color: "#15803d" }}>{labels.annotated} {counts.annotated}</span>
          <span style={{ color: "#2563eb" }}>{labels.unannotated} {counts.unannotated}</span>
          <span style={{ color: "#d97706" }}>{labels.busy} {counts.active}</span>
        </div>
      </div>

      <div style={styles.tree}>
        {visibleTree.map((node) => (
          <Node
            key={`${node.type}:${node.path || node.name}`}
            node={node}
            onSelect={onSelect}
            currentUser={currentUser}
            labels={labels}
          />
        ))}
        {!visibleTree.length && <div style={styles.empty}>{labels.noMatchingFiles}</div>}
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
