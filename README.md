# Anno v4

This project is now usable as a normal web app. Electron is still kept for compatibility, but deployment no longer depends on it.

## Data Layout

The backend can run without raw data. In the recommended deployment, `data` only needs:

```text
data/
  processed/      # visualization JSON files, such as *_wav_0.json and *_psd.json
  annotations/    # annotation JSONL and dataset status
  cache/          # generated file tree cache
```

When `ANNO_DATA_SOURCE=processed` is used, the file tree is built from `processed`.
Files with the same logical base name are merged:

```text
subject01/session01_wav_0.json
subject01/session01_wav_1.json
subject01/session01_psd.json
```

becomes one frontend file node:

```text
subject01/session01
```

## Backend

Choose a data profile with `ANNO_PROFILE`:

- `not_used`: original `backend/app` data paths.
- `annotate`: original `backend/app_annotate` data paths.
- `check`: original `backend/app_check` data paths.

Run:

```bash
cd backend
pip install -r requirements.txt
ANNO_PROFILE=annotate PORT=10000 ./run_server.sh
```

On Windows PowerShell:

```powershell
cd backend
pip install -r requirements.txt
$env:ANNO_PROFILE="annotate"
$env:PORT="10000"
.\run_server.ps1
```

You can override paths without editing code:

- `ANNO_DATA_SOURCE` defaults to `processed`; set to `raw` only for legacy raw-tree mode.
- `ANNO_VIS_DATA_ROOT`
- `ANNO_ANNOTATION_FILE`
- `ANNO_CACHE_TREE_PATH`
- `ANNO_FILE_SUFFIXES`
- `ANNO_CHANNEL_FILTERS`
- `ANNO_SHOW_ANNOTATION_LAYERS`: defaults to `true`; set to `false` to hide other users' annotation overlays.
- `ANNO_ANNOTATION_MODE`: defaults to `bad_channel`; set to `channel_score` to score every channel from 0 to 5.
- `ANNO_SCORE_ANNOTATION_FILE`: JSONL output path for `channel_score` mode. Defaults to a sibling file named like `*_scores.jsonl`.
- `ANNO_LOAD_LLM_PREANNOTATIONS`: defaults to `false`; set to `true` to preload LLM score annotations as a baseline.
- `ANNO_LLM_ANNOTATION_FILE`: JSONL path for LLM preannotations. User submissions save only score changes relative to this baseline.

Recommended processed-only server environment:

```bash
ANNO_DATA_SOURCE=processed
ANNO_VIS_DATA_ROOT=/data/anno/processed
ANNO_ANNOTATION_FILE=/data/anno/annotations/bad_channels.jsonl
ANNO_CACHE_TREE_PATH=/data/anno/cache/file_tree
```

Scoring-mode example:

```bash
ANNO_PROFILE=annotate
ANNO_ANNOTATION_MODE=channel_score
ANNO_SCORE_ANNOTATION_FILE=/data/anno/annotations/channel_scores.jsonl
ANNO_LOAD_LLM_PREANNOTATIONS=true
ANNO_LLM_ANNOTATION_FILE=/data/anno/annotations/llm_channel_scores.jsonl
```

## Frontend Web Deployment

Edit `frontened/.env.production` before building:

```env
VITE_API_HOST=YOUR_SERVER_IP:10000
```

Build and serve:

```bash
npm run build:web
PORT=8080 npm run serve:web
```

Then open:

```text
http://YOUR_SERVER_IP:8080
```
