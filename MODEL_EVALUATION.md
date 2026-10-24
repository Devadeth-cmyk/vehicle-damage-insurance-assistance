# Model Evaluation Evidence

This page documents the model-performance evidence for AutoInsight's computer vision and RAG pipelines, transcribed from the new training runs in `notebooks/car-damage.ipynb` and `notebooks/car-parts-training.ipynb`.

## Artifacts

- `evaluation/model_metrics.json` — structured metrics transcribed from saved notebook validation and test outputs.
- `evaluation/visualizations/overall_map_comparison.svg` — overall mAP comparison across the damage and vehicle-part tasks.
- `evaluation/visualizations/damage_detection_by_class.svg` — per-damage-class mAP50–95.
- `evaluation/visualizations/part_segmentation_by_class.svg` — per-part mask mAP50–95 across 13 vehicle parts.
- `evaluation/visualizations/rag_top1_similarity.svg` — top-result retrieval similarities for the successful RAG benchmark queries.
- `evaluation/generate_visualizations.py` — standard-library-only generator for the SVG charts.

Regenerate the figures from the repository root:

```powershell
python evaluation/generate_visualizations.py
```

## Recorded Computer-Vision Results (New Models)

The upgraded models are `YOLO26m-seg` models trained on dual Tesla T4 GPUs with PyTorch 2.11 and Ultralytics 8.4.184.

### 1. Overall Model Performance Comparison

| Task / Model | Split | Precision | Recall | mAP50 | mAP50–95 |
|---|---|---:|---:|---:|---:|
| **Damage Detection (boxes)** | Validation (810 img / 1,744 inst) | **0.831** | **0.726** | **0.789** | **0.614** |
| **Damage Segmentation (masks)** | Validation (810 img / 1,744 inst) | **0.838** | **0.730** | **0.783** | **0.599** |
| *Damage Detection (boxes, held-out test)* | Held-out test (374 img / 785 inst) | 0.792 | 0.723 | 0.763 | 0.594 |
| *Damage Segmentation (masks, held-out test)* | Held-out test (374 img / 785 inst) | 0.797 | 0.722 | 0.760 | 0.574 |
| **Vehicle-Part Detection (boxes)** | Validation (401 img / 2,041 inst) | **0.843** | **0.847** | **0.881** | **0.772** |
| **Vehicle-Part Segmentation (masks)** | Validation (401 img / 2,041 inst) | **0.863** | **0.855** | **0.904** | **0.767** |

> **Performance Gain vs Previous Generation Models:**
> - Damage box mAP50 increased from **0.709 → 0.789** (+8.0%), mAP50–95 from **0.554 → 0.614** (+6.0%).
> - Vehicle parts mask mAP50 increased from **0.697 → 0.904** (+20.7%), mask mAP50–95 from **0.558 → 0.767** (+20.9%).
> - Vehicle parts box mAP50 increased from **0.685 → 0.881** (+19.6%), box mAP50–95 from **0.572 → 0.772** (+20.0%).

---

### 2. Per-Class Damage Detection & Segmentation Metrics

From `notebooks/car-damage.ipynb` (run `damage_seg_kaggle_20261023_1902`, 143 epochs):

| Damage Class | Val Instances | Precision | Recall | Box mAP50 | Box mAP50–95 | Mask mAP50–95 |
|---|---:|---:|---:|---:|---:|---:|
| **glass shatter** | 135 | 1.000 | 0.979 | 0.995 | 0.919 | 0.954 |
| **tire flat** | 62 | 0.941 | 0.903 | 0.970 | 0.913 | 0.927 |
| **lamp broken** | 141 | 0.957 | 0.837 | 0.924 | 0.798 | 0.800 |
| **scratch** | 728 | 0.684 | 0.556 | 0.631 | 0.368 | 0.325 |
| **dent** | 501 | 0.767 | 0.539 | 0.636 | 0.360 | 0.330 |
| **crack** | 177 | 0.639 | 0.540 | 0.579 | 0.327 | 0.254 |

---

### 3. Per-Class Vehicle Part Segmentation Metrics

From `notebooks/car-parts-training.ipynb` (run `parts_seg_kaggle_20261023_1859`, 145 epochs, 13 classes with sided variants consolidated and non-repairable `object` class pruned):

| Vehicle Part | Val Instances | Precision | Recall | Mask mAP50 | Mask mAP50–95 | Box mAP50–95 |
|---|---:|---:|---:|---:|---:|---:|
| **front_glass** | 214 | 0.958 | 0.968 | 0.986 | 0.948 | 0.945 |
| **hood** | 214 | 0.953 | 0.950 | 0.972 | 0.923 | 0.910 |
| **front_bumper** | 208 | 0.931 | 0.962 | 0.974 | 0.918 | 0.902 |
| **back_glass** | 115 | 0.953 | 0.974 | 0.981 | 0.878 | 0.894 |
| **back_door** | 186 | 0.923 | 0.835 | 0.943 | 0.862 | 0.874 |
| **front_door** | 194 | 0.900 | 0.876 | 0.930 | 0.851 | 0.868 |
| **back_bumper** | 94 | 0.921 | 0.904 | 0.966 | 0.817 | 0.813 |
| **front_light** | 429 | 0.944 | 0.904 | 0.941 | 0.733 | 0.757 |
| **back_light** | 258 | 0.910 | 0.857 | 0.924 | 0.708 | 0.731 |
| **mirror** | 62 | 0.931 | 0.919 | 0.976 | 0.691 | 0.687 |
| **trunk** | 9 | 0.621 | 0.778 | 0.771 | 0.687 | 0.744 |
| **tailgate** | 5 | 0.571 | 0.600 | 0.736 | 0.616 | 0.543 |
| **wheel** | 53 | 0.704 | 0.582 | 0.655 | 0.338 | 0.369 |

---

## RAG Retrieval Benchmark

The latest recorded run indexed **1,043 chunks from 11 insurers** and passed **10/10 pooled questions (100% keyword-hit rate)**:
- Vector search retrieves relevant context using embeddings from `sentence-transformers/all-MiniLM-L6-v2`.
- Mean top-1 cosine similarity on specific policy queries reaches **0.55–0.69**.
- General exclusions query uses direct section matching.

---

## Methodological Notes & Next Steps

1. **Held-out Generalization:** `car-damage.ipynb` includes both validation split (810 images) and an independent held-out test split (374 images) confirming strong generalization (Test Box mAP50–95 = **0.594**, Mask mAP50–95 = **0.574**).
2. **Class Consolidations:** Consolidating sided door and light labels (`front_left_door` + `front_right_door` → `front_door`) and removing the unrepairable `object` class dramatically stabilized parts segmentation, eliminating zero-AP failure modes.
3. **Severity Calculation:** As noted in the codebase, severity estimation utilizes bounding-box area ratios and threshold heuristics; dedicated ground-truth severity classification dataset creation remains recommended for future iterations.
