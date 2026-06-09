# Model artifacts

Performance Model v4 files must live here:

```
ml-service/models/performance_model/
  model_calibrated.pkl
  model_raw.pkl
  shap_explainer.pkl
  features_behavioral.pkl
  hp_train_medians.pkl
  train_medians.pkl
```

## Copy from monorepo (local / HF build)

From the AcademIQ repo root:

```bash
mkdir -p ml-service/models/performance_model
cp models/performance_model/*.pkl ml-service/models/performance_model/
```

Or set `MODEL_DIR` to the monorepo path when running locally:

```bash
export MODEL_DIR=../models/performance_model   # relative to ml-service/
```

## Source of truth

Training notebooks and scripts: `ai/Performance Model/`  
Runtime loader: `ml-service/app/performance_model.py`
