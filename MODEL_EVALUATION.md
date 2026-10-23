# Model Evaluation Evidence

This page documents the model-performance evidence currently present in the project and the visualizations generated from it.

## Artifacts

- `evaluation/model_metrics.json` — structured metrics transcribed from saved notebook validation output.
- `evaluation/visualizations/overall_map_comparison.svg` — overall mAP comparison across the damage and vehicle-part tasks.
- `evaluation/visualizations/damage_detection_by_class.svg` — per-damage-class mAP50–95.
- `evaluation/visualizations/part_segmentation_by_class.svg` — per-part mask mAP50–95.
- `evaluation/generate_visualizations.py` — standard-library-only generator for the SVG charts.

Regenerate the figures from the repository root:

```powershell
python evaluation/generate_visualizations.py
```

## Recorded computer-vision results

| Task | Validation split | Precision | Recall | mAP50 | mAP50–95 |
|---|---:|---:|---:|---:|---:|
| Damage bounding-box detection | 810 images / 1,744 instances | 0.749 | 0.666 | 0.709 | 0.554 |
| Vehicle-part boxes | 401 images / 2,042 instances | 0.608 | 0.786 | 0.685 | 0.572 |
| Vehicle-part masks | 401 images / 2,042 instances | 0.616 | 0.794 | 0.697 | 0.558 |

The damage detection values are recorded in `notebooks/damage_detection_training.ipynb`, cell 17 output. Per-class precision, recall, mAP50, and mAP50–95 are recorded there as well. Vehicle-part segmentation results are recorded in `notebooks/vehicle_parts_training.ipynb`, cell 13 output. The class chart uses mask mAP50–95 from that output.

The charts use the standard 0–1 metric scale. mAP50 is average precision at an IoU threshold of 0.50. mAP50–95 averages across IoU thresholds 0.50 through 0.95 and is the stricter summary.

## Limits on what these numbers prove

These are notebook-recorded **validation** results, not a newly run independent test. The original labeled image datasets, dataset configuration files, per-image predictions, confusion matrices, and Ultralytics `results.csv` files are not checked into this workspace. The model weights are present locally under `backend/models/`, but validation cannot be reproduced from the current repository without the corresponding datasets and exact dataset YAML files. Do not describe these figures as independent test-set performance.

The classes have uneven validation support. Damage detection has much lower recall / AP for crack, scratch, and dent than for glass shatter, broken lamps, and flat tires. In the parts model, several rare classes have only 5–30 validation instances, and the `object` class has one instance with zero AP. Per-class figures for such small groups are unstable.

The `damage_severity_estimation.ipynb` notebook does **not** establish severity-classification performance. Its training/evaluation output is for the same six damage labels, while the notebook's severity function assigns severity from bounding-box area thresholds. There is no severity-labeled ground-truth evaluation or confusion matrix in the repository. The application also falls back to heuristic severity rules. Therefore no severity accuracy chart is included.

The RAG retrieval benchmark in `backend/rag_pipeline/scripts/evaluate_retrieval.py` has ten hand-written keyword-hit questions. It is not a full answer-quality or factuality evaluation, and currently does not save machine-readable per-question results. It could not be executed in this environment because the configured `all-MiniLM-L6-v2` embedding model was not cached and network access to Hugging Face was unavailable. No RAG performance chart is included until a reproducible run produces data.

## Recommended next steps for defensible performance claims

1. Restore and version the exact damage and parts datasets (or publish stable dataset references), label maps, and YAML files. Keep a held-out test split separate from model selection.
2. Re-evaluate the exact deployed weight files on that held-out test split and save the Ultralytics JSON/CSV outputs, confusion matrices, PR curves, and per-class support.
3. Evaluate the end-to-end fusion pipeline with manually labeled damage-to-part matches. Report match precision/recall, unmatched rate, review-trigger rate, and IoU/overlap quality.
4. Build a severity-labeled image set with adjudicated Minor/Moderate/Severe labels. Report macro-F1, per-class precision/recall, confusion matrix, and agreement between reviewers.
5. Expand RAG evaluation to a reviewed query/reference-answer set; measure retrieval Recall@k / MRR and answer faithfulness, answer relevance, and citation correctness. Save raw per-query outputs and the exact embedding and LLM model versions.
6. Record dataset version/hash, weight SHA-256, evaluation command, library versions, date, thresholds, and hardware alongside each evaluation artifact.

These artifacts provide a transparent summary of the evidence currently in the notebooks; the caveats above should travel with any presentation or report using the charts.
