# Case Study: EqlipZ Pay Fraud Detection Model

## Overview
EqlipZ Pay utilizes a robust AI model for transaction risk calculation. Rather than just returning binary outputs (fraud vs. legitimate), the system relies on a **LightGBM classifier** wrapped in a **SplitConformalClassifier (using MAPIE)**. This provides mathematically bounded predictions which allow the system to intelligently place ambiguous transactions on **HOLD** instead of just rejecting them.

## The Model
- **Algorithm:** LightGBM wrapped with SplitConformalClassifier
- **Calibration:** Split Conformal Prediction (MAPIE)
- **Dataset Scale:** Trained on over **7.7 Million** transactions

## Benchmark & Evaluation

Our evaluation on the hold-out test set (~1.5M transactions) yields the following metrics:

| Metric | Score |
| --- | --- |
| Precision | 0.932 |
| Recall | 0.857 |
| F1 Score | 0.893 |
| AUCPR | 0.926 |
| Conformal Coverage | 90.6% |

### Performance Visualizations

Below are the benchmark graphs generated from our extensive model training pipeline across the 7.7M transaction dataset.

<div align="center">
  <img src="../frontend/public/static_front/benchmark_line.png" width="400">
  <img src="../frontend/public/static_front/benchmark_bar.png" width="400">
</div>
<div align="center">
  <img src="../frontend/public/static_front/benchmark_hist.png" width="400">
  <img src="../frontend/public/static_front/benchmark_scatter.png" width="400">
</div>
<div align="center">
  <img src="../frontend/public/static_front/benchmark_conf_matrix.png" width="400">
</div>

## Business Impact
The conformal coverage of 90.6% ensures that the vast majority of transactions fall within a bounded prediction set, allowing EqlipZ Pay to dynamically calculate the expected loss exposure (E*). By estimating the false positive cost and incorporating it into the control plane, the model successfully routes transactions to the appropriate status (RELEASE, HOLD, or REFUSE) while minimizing friction and lost revenue.
