
import pandas as pd
import numpy as np
import joblib
import tensorflow as tf
import os

# Define paths (assumes models are in the same folder as this script)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SCALER_PATH = os.path.join(BASE_DIR, 'academIQ_scaler.pkl')
RISK_MODEL_PATH = os.path.join(BASE_DIR, 'academIQ_risk_model.keras')
GRADE_MODEL_PATH = os.path.join(BASE_DIR, 'academIQ_grade_model.keras')

class StudentPredictor:
    def __init__(self):
        # Load artifacts
        try:
            self.scaler = joblib.load(SCALER_PATH)
            self.risk_model = tf.keras.models.load_model(RISK_MODEL_PATH)
            self.grade_model = tf.keras.models.load_model(GRADE_MODEL_PATH)
            print("✅ AcademIQ Models loaded successfully.")
        except Exception as e:
            print(f"❌ Error loading models: {e}")
            raise e

    def preprocess(self, data_dict):
        '''
        Transforms raw dictionary data into the scaled format the models expect.
        '''
        # Convert dictionary to DataFrame
        df = pd.DataFrame([data_dict])
        
        # 1. Feature Engineering (Must match training logic exactly)
        # Avoid division by zero with +1
        df['avg_daily_time'] = df['total_time_spent'] / (df['active_days'] + 1)
        df['clicks_per_day'] = df['all_clicks'] / (df['active_days'] + 1)
        
        # 2. Log Transformation for skewed features
        skewed_cols = ['all_clicks', 'material_clicks', 'total_time_spent', 'avg_daily_time', 'clicks_per_day']
        for col in skewed_cols:
            if col in df.columns:
                df[col] = np.log1p(df[col])
        
        # 3. Select & Order Columns (Critical for Scaler)
        # These must match the columns used during X_scaled creation
        expected_cols = [
            'all_clicks', 'active_days', 'access_frequency', 'material_clicks',
            'avg_quiz_score', 'quiz_attempts', 'avg_assignment_score',
            'assignment_submissions', 'total_time_spent', 'avg_daily_time', 'clicks_per_day'
        ]
        
        # Ensure columns exist and are in order (fill missing with 0)
        for col in expected_cols:
            if col not in df.columns:
                df[col] = 0
                
        X_raw = df[expected_cols]
        
        # 4. Scale
        X_scaled = self.scaler.transform(X_raw)
        return X_scaled

    def predict(self, student_data):
        '''
        Main function to call from Backend API.
        Input: dict containing 'all_clicks', 'active_days', etc.
        Output: dict with 'risk_cluster' (int) and 'predicted_grade' (float)
        '''
        # Preprocess
        X_processed = self.preprocess(student_data)
        
        # Inference
        # 1. Predict Risk (Returns cluster ID)
        risk_probs = self.risk_model.predict(X_processed, verbose=0)
        risk_cluster = int(np.argmax(risk_probs, axis=1)[0])
        
        # 2. Predict Grade (Returns 0-100 score)
        predicted_grade = float(self.grade_model.predict(X_processed, verbose=0)[0][0])
        
        # Clip grade to realistic bounds (0 to 100)
        predicted_grade = max(0.0, min(100.0, predicted_grade))
        
        return {
            'risk_cluster': risk_cluster,
            'predicted_grade': round(predicted_grade, 2)
        }

if __name__ == "__main__":
    # Test block for backend developer
    predictor = StudentPredictor()
    
    # Sample Test Data
    test_student = {
        'all_clicks': 500,
        'active_days': 20,
        'access_frequency': 5,
        'material_clicks': 50,
        'avg_quiz_score': 85,
        'quiz_attempts': 10,
        'avg_assignment_score': 90,
        'assignment_submissions': 5,
        'total_time_spent': 1200
    }
    
    print(f"Testing with student data: {test_student}")
    result = predictor.predict(test_student)
    print("Inference Result:", result)
