# EEG Annotation Platform Guide for Interns

Version: v1.0  
Audience: annotation interns  
Last updated: 2026-05-19

## 1. Purpose

This platform is used to review EEG data and mark data quality problems. The main tasks are:

- mark bad channels in the PSD view
- mark bad channels in the waveform view
- mark artifact time intervals in the waveform view
- optionally mark a whole file as discarded when the signal quality is too poor
- submit the annotation result to the server

The annotation result will be used later for data cleaning, quality control, and downstream analysis.

Recommended image: `images/intern/01-overview.png`  
Image description: full-page screenshot with labels for the file tree, visualization area, and annotation panel.

## 2. Before You Start

Use a stable network connection and open the website in a modern browser such as Chrome or Edge.

When you first enter the platform, enter your username. The username is used to record who is annotating a file and to prevent multiple users from editing the same file at the same time.

Recommended username examples:

```text
zhangsan
intern01
```

Recommended image: `images/intern/02-username.png`  
Image description: username prompt shown when entering the platform.

## 3. Page Layout

The page has three main areas:

| Area | Purpose |
|---|---|
| Left file tree | Select the data file to annotate |
| Middle visualization area | View PSD and waveform data |
| Right annotation panel | Check current labels and submit annotations |

The visualization area shows the relative path of the current data file. Always check this path before submitting.

Recommended image: `images/intern/03-layout.png`  
Image description: screenshot showing the left file tree, middle PSD/waveform area, and right annotation panel.

## 4. File Status

The left file tree shows the status of each file.

| Status | Meaning |
|---|---|
| Unannotated | The file has not been submitted yet |
| Annotated | The file already has an annotation record |
| Busy | Another user is currently annotating the file |
| ME | The file is currently occupied by you |

If a file is busy and belongs to another user, choose another file.

Recommended image: `images/intern/04-file-status.png`  
Image description: file tree examples for unannotated, annotated, busy, and current-user files.

## 5. Recommended Workflow

For each file, follow this workflow:

1. Select an unannotated file from the left file tree.
2. Review the PSD view first to find globally abnormal channels.
3. Switch to the waveform view to inspect each time window.
4. Mark waveform bad channels for each problematic window.
5. Mark artifact intervals if a channel has a clear time-limited artifact.
6. If the whole file is unusable, check `Discard this file`.
7. Review the right annotation panel.
8. Click `Submit annotation`.

Recommended image: `images/intern/05-workflow.png`  
Image description: simple flowchart of the recommended annotation workflow.

## 6. PSD View

The PSD view shows the power spectrum of all channels. Use it to detect channels that are globally abnormal across frequencies.

Available operations:

| Operation | Result |
|---|---|
| Hover over a PSD curve | Highlight the corresponding channel |
| Hover over a channel name | Highlight the corresponding PSD curve |
| Click a PSD curve | Mark or unmark that channel as a PSD bad channel |
| Click a channel name | Mark or unmark that channel as a PSD bad channel |
| Box-select or lasso-select curves | Batch mark or unmark selected channels |

PSD bad channels are global for the file. They are saved separately from waveform bad channels.

Recommended images:

- `images/intern/06-psd-view.png`  
  Image description: PSD view with multiple colored channel curves.
- `images/intern/07-psd-hover.png`  
  Image description: one PSD channel highlighted by mouse hover.
- `images/intern/08-psd-selection.png`  
  Image description: box selection or lasso selection in the PSD view.
- `images/intern/09-psd-bad-channel.png`  
  Image description: a PSD bad channel shown in red.

## 7. Waveform View

The waveform view shows EEG signals in time windows. Each window is called a sub-block.

Available operations:

| Operation | Result |
|---|---|
| Left-click a waveform channel | Mark or unmark that channel as bad in the current sub-block |
| Hover over a waveform channel | Highlight the channel |
| Adjust `Scale` | Change waveform amplitude display |
| Use the bottom slider | Jump to another sub-block |
| Use the number input | Jump to a specific sub-block |
| Click `Marked sub-blocks` | Jump to a sub-block that already has waveform bad channels |

Waveform bad channels are saved by sub-block. A channel marked bad in one sub-block is not automatically bad in other sub-blocks.

Recommended images:

- `images/intern/10-waveform-view.png`  
  Image description: waveform view showing multiple EEG channels.
- `images/intern/11-waveform-scale.png`  
  Image description: scale control in the waveform view.
- `images/intern/12-sub-block-control.png`  
  Image description: bottom slider and sub-block number input.
- `images/intern/13-marked-sub-blocks.png`  
  Image description: marked sub-block navigation bar.

## 8. Artifact Annotation

Artifact annotation is used for short time intervals that are abnormal within a specific channel. This is different from marking a whole channel as bad.

Use the right mouse button in the waveform view:

1. Right-click the artifact start point on a channel.
2. Right-click the artifact end point on the same channel.
3. The selected interval will be shown as an orange shaded region.

Important notes:

- Artifact annotation does not automatically mark the channel as bad.
- Bad channel annotation and artifact annotation are independent.
- Artifact times are saved as global file time, not local window time.
- For example, if the third 30-second window contains an artifact from 10s to 12s, it is saved approximately as 70s to 72s.

Recommended images:

- `images/intern/14-artifact-start.png`  
  Image description: first right-click on a waveform channel with the artifact start prompt.
- `images/intern/15-artifact-region.png`  
  Image description: orange shaded artifact interval after the second right-click.

## 9. Right Annotation Panel

The right panel summarizes the current annotations.

It may include:

- current sub-block index
- discard checkbox
- PSD bad channels
- current waveform bad channels
- marked waveform sub-blocks
- artifact segments
- submit button

Before submitting, check that the right panel matches your intended labels.

Recommended image: `images/intern/16-annotation-panel.png`  
Image description: right annotation panel showing PSD bad channels, waveform bad channels, artifact intervals, and submit button.

## 10. Discarding a File

Use `Discard this file` only when the entire file is not suitable for analysis.

Examples:

- most channels are severely noisy
- signal is missing for a large portion of the file
- the file appears corrupted
- the recording quality is too poor to make reliable annotations

After checking `Discard this file`, you still need to click `Submit annotation`.

Recommended image: `images/intern/17-discard-file.png`  
Image description: discard checkbox in the right annotation panel.

## 11. Submitting

Click `Submit annotation` after finishing a file.

The platform will save:

- global PSD bad channels
- waveform bad channels by sub-block
- artifact intervals with global start and end times
- discard status
- annotator username

After submission, the platform will release the file and move to the next available unannotated file when possible.

Recommended image: `images/intern/18-submit.png`  
Image description: submit button and successful submission prompt.

## 12. Quality Guidelines

Use the following principles during annotation:

- Start with PSD to quickly identify globally abnormal channels.
- Use waveform view to confirm whether the abnormality is persistent or time-limited.
- Mark a channel as waveform bad only in the sub-blocks where it is clearly bad.
- Use artifact intervals for short, localized problems.
- Do not over-label uncertain cases. If unsure, inspect nearby sub-blocks.
- Check the right panel before submitting.

## 13. Common Questions

### 13.1 I cannot see the file list

Try:

- click `Refresh files`
- refresh the browser page
- check network connection
- contact the platform administrator if the problem remains

### 13.2 The file is stuck at Loading

Try:

- wait a few seconds
- click `Refresh data`
- switch to another file and then switch back
- contact the administrator if the file still cannot load

### 13.3 I marked the wrong bad channel

Click the same channel again to cancel the bad-channel mark.

### 13.4 I marked the wrong artifact interval

At the moment, artifact intervals are shown in the panel and saved during submission. If an interval is clearly wrong and the interface does not provide a direct delete control, record the file path and inform the project maintainer so the annotation can be corrected.

### 13.5 The file is shown as Busy

Another user is annotating the file. Select another file.

### 13.6 I submitted too early

Open the same file again, correct the labels, and submit again. The latest annotation record will be used.

## 14. What to Report

If you find a problem, report the following information:

- your username
- file relative path shown above the visualization
- what you were doing
- browser zoom level
- screenshot if possible
- whether the problem happens in PSD view or waveform view

Recommended image: `images/intern/19-report-info.png`  
Image description: screenshot showing where to find the current file path and view type.

## 15. Version History

| Version | Date | Notes |
|---|---|---|
| v1.0 | 2026-05-19 | Initial intern annotation guide |
