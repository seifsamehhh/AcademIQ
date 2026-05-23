from app.schemas.features import FeatureVector
from app.ml.model_loader import ModelLoader

class Predictor:
    def __init__(self):
        self.loader = ModelLoader()

    def predict_from_features(self, features: FeatureVector) -> dict:
        """
        Accept FeatureVector and return ML predictions
        """
        predictions = self.loader.predict(features)
        # Optional: map numeric risk_level to enum string
        risk_map = {0: "LOW", 1: "MEDIUM", 2: "HIGH"}
        predictions["risk_level"] = risk_map.get(predictions["risk_level"], "UNKNOWN")
        return predictions
