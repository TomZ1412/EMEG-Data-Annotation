import axios from "axios";

export const API_BASE_URL = (
  import.meta.env.VITE_API_BASE_URL || "/api"
).replace(/\/$/, "");

export const apiClient = axios.create({
  baseURL: API_BASE_URL,
  timeout: 120000,
});

const unwrap = (request) => request.then((response) => response.data);

export const getFileTree = () => unwrap(apiClient.get("/file_tree"));
export const startAnnotation = (filePath, user) =>
  unwrap(apiClient.post("/start_annotation", { file_path: filePath, user }));
export const endAnnotation = (filePath, user) =>
  unwrap(apiClient.post("/end_annotation", { file_path: filePath, user }));
export const keepAnnotationAlive = (filePath, user) =>
  unwrap(apiClient.post("/keep_alive", { file_path: filePath, user }));
export const getVisualization = (filePath, subBlock = 0) =>
  unwrap(apiClient.get(`/visualization/${filePath}`, { params: { sub_block: subBlock } }));
export const getAnnotation = (filePath) =>
  unwrap(apiClient.get(`/annotation/${filePath}`));
export const saveAnnotation = (payload) =>
  unwrap(apiClient.post("/annotate", payload));
export const getNextUnannotated = (user, currentFile = "") =>
  unwrap(apiClient.get("/next_unannotated", {
    params: { user, current_file: currentFile },
  }));
export const markDataset = (path, action) =>
  unwrap(apiClient.post("/datasets/mark", { path, action }));
