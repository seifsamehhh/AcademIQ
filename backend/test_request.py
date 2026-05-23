import requests

url = "http://127.0.0.1:8000/predict"

data = {

  "total_time_spent": 0,
  "active_days": 0,
  "access_frequency": 0,
  "avg_quiz_score": 0.1,
  "quiz_score_std": 0.1,
  "avg_assignment_score": 0.3,
  "late_submission_ratio": 0.7,
  "risk_cluster": 2,
  "risk_cluster_encoded": 2,
  "avg_final_grade": 0
}


response = requests.post(url, json=data)
print(response.json())
