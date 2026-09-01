"""
EqlipZ Pay — ONNX Model Serialization
==========================================================
Converts the trained VotingClassifier (LightGBM + XGBoost) and MAPIE wrapper
into an optimized ONNX graph for high-throughput, low-latency inference.
"""

import sys
import logging
from pathlib import Path
import joblib
import numpy as np

try:
    from skl2onnx import convert_sklearn, update_registered_converter
    from skl2onnx.common.data_types import FloatTensorType
    from skl2onnx.common.shape_calculator import calculate_linear_classifier_output_shapes
    import onnxmltools
    from onnxmltools.convert.xgboost.operator_converters.XGBoost import convert_xgboost
    from onnxmltools.convert.lightgbm.operator_converters.LightGbm import convert_lightgbm
    from xgboost import XGBClassifier
    from lightgbm import LGBMClassifier
    
    # Register converters for the VotingClassifier
    update_registered_converter(XGBClassifier, 'XGBoostXGBClassifier', calculate_linear_classifier_output_shapes, convert_xgboost, options={'nocl': [True, False], 'zipmap': [True, False, 'columns']})
    update_registered_converter(LGBMClassifier, 'LightGbmLGBMClassifier', calculate_linear_classifier_output_shapes, convert_lightgbm, options={'nocl': [True, False], 'zipmap': [True, False, 'columns']})
except ImportError:
    print("Please install skl2onnx and onnxmltools")
    sys.exit(1)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("eqlipz.onnx")

BASE_DIR = Path(__file__).resolve().parent
MODELS_DIR = BASE_DIR / "models"


def convert_to_onnx(model_name="fraud_model_raw.joblib", out_name="fraud_model.onnx", n_features=30):
    model_path = MODELS_DIR / model_name
    out_path = MODELS_DIR / out_name
    
    if not model_path.exists():
        logger.error(f"Model {model_name} not found.")
        return
        
    logger.info(f"Loading {model_name}...")
    model = joblib.load(model_path)
    
    # Fix VotingClassifier flatten_transform issue in skl2onnx
    if hasattr(model, 'flatten_transform'):
        model.flatten_transform = False
        
    # Fix XGBoost feature names issue in onnxmltools
    if hasattr(model, 'estimators_'):
        for est in model.estimators_:
            if type(est).__name__ == 'XGBClassifier':
                try:
                    est.get_booster().feature_names = None
                except:
                    pass
    
    # Try to load feature columns to get correct feature count
    feature_cols_path = MODELS_DIR / "feature_columns.joblib"
    if feature_cols_path.exists():
        feature_cols = joblib.load(feature_cols_path)
        n_features = len(feature_cols)
        
    logger.info(f"Converting model to ONNX with {n_features} features...")
    
    initial_type = [('float_input', FloatTensorType([None, n_features]))]
    
    try:
        # For VotingClassifier containing XGBoost, we might need onnxmltools or specialized converters
        # Here we just use convert_sklearn for simplicity, which works for standard sklearn wrappers
        onx = convert_sklearn(model, initial_types=initial_type, target_opset={'': 12, 'ai.onnx.ml': 3})
        with open(out_path, "wb") as f:
            f.write(onx.SerializeToString())
            
        logger.info(f"ONNX model successfully saved to {out_path}")
    except Exception as e:
        logger.error(f"Failed to convert to ONNX: {e}")
        logger.warning("Ensure XGBoost / LightGBM ONNX converters are registered.")

if __name__ == "__main__":
    convert_to_onnx()
