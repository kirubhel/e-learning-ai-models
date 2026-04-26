import logging
import os
import pickle
from typing import Dict, List, Optional

import pandas as pd
import uvicorn
from fastapi import FastAPI, HTTPException, status
from pydantic import BaseModel, Field

# --- Configure Logging ---
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("churn-service")

app = FastAPI(
    title="Student Churn Prediction Service",
    description="Analyzes student engagement metrics to predict dropout risks and recommend interventions.",
    version="1.1.0"
)

# --- Configuration & Model Loading ---
MODEL_PATH = os.path.join(os.path.dirname(__file__), "churn_model.pkl")
CHURN_FEATURES = [
    'last_login_days_ago',
    'daily_minutes_spent',
    'total_retry_attempts',
    'attention_span_sec',
    'hint_usage_frequency',
    'video_completion_rate'
]

# Global model variable
churn_model = None

@app.on_event("startup")
def load_model():
    """Load the pre-trained churn model on startup."""
    global churn_model
    try:
        if not os.path.exists(MODEL_PATH):
            logger.error(f"Model file not found at {MODEL_PATH}")
            return

        with open(MODEL_PATH, "rb") as f:
            churn_model = pickle.load(f)
        logger.info("Successfully loaded churn prediction model.")
    except Exception as e:
        logger.error(f"Critical error loading model: {str(e)}")
        churn_model = None

# --- Data Models ---
class StudentFeatures(BaseModel):
    """Features used for churn prediction."""
    student_id: str = Field(..., example="std_001")
    last_login_days_ago: float = Field(..., ge=0, example=3.5)
    daily_minutes_spent: float = Field(..., ge=0, example=45.0)
    total_retry_attempts: int = Field(..., ge=0, example=2)
    attention_span_sec: float = Field(..., ge=0, example=1200.5)
    hint_usage_frequency: float = Field(..., ge=0, example=0.15)
    video_completion_rate: float = Field(..., ge=0, le=1, example=0.85)
    is_churned: Optional[int] = Field(0, description="Flag if student is already considered churned")

class PredictionResponse(BaseModel):
    """Output structure for a prediction."""
    student_id: str
    risk_score: float = Field(..., description="Risk score from 0 to 100")
    status: str = Field(..., description="Risk category: HEALTHY, WARNING, or HIGH_RISK")
    recommended_action: Dict

# --- Business Logic Helpers ---
def determine_intervention(risk_score: float) -> Dict:
    """Determine the best intervention strategy based on the risk score."""
    if risk_score > 60:
        return {
            "level_of_seriousness": "critical",
            "action": "Immediate parent notification and recovery session assignment.",
            "system_triggers": ["notify_parent", "simplify_content", "alert_teacher"]
        }
    elif risk_score > 40:
        return {
            "level_of_seriousness": "moderate",
            "action": "Trigger engagement-boosting activities and gamified exercises.",
            "system_triggers": ["gamification_push", "encouragement_nudge"]
        }
    return {
        "level_of_seriousness": "low",
        "action": "Continue regular learning path with standard monitoring.",
        "system_triggers": ["routine_check"]
    }

# --- API Endpoints ---
@app.post("/predict", response_model=PredictionResponse, status_code=status.HTTP_200_OK)
async def predict_single_student(features: StudentFeatures):
    """Process a single student for churn risk assessment."""
    if churn_model is None:
        logger.error("Prediction requested but model is not available.")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Prediction model is currently unavailable."
        )

    # Short-circuit for already churned students
    if features.is_churned == 1:
        return PredictionResponse(
            student_id=features.student_id,
            risk_score=100.0,
            status="ALREADY_CHURNED",
            recommended_action={
                "level_of_seriousness": "critical",
                "action": "Initiate re-engagement campaign.",
                "system_triggers": ["retention_email"]
            }
        )

    try:
        # Prepare data for inference
        input_df = pd.DataFrame([features.dict()])[CHURN_FEATURES]
        
        # Calculate probability of churn (class 1)
        probabilities = churn_model.predict_proba(input_df)
        risk_score = round(float(probabilities[:, 1][0]) * 100, 2)
        
        # Categorize risk level
        if risk_score > 60:
            status_label = "HIGH_RISK"
        elif risk_score > 40:
            status_label = "WARNING"
        else:
            status_label = "HEALTHY"

        logger.info(f"Prediction for {features.student_id}: Score={risk_score}, Status={status_label}")
        
        return PredictionResponse(
            student_id=features.student_id,
            risk_score=risk_score,
            status=status_label,
            recommended_action=determine_intervention(risk_score)
        )

    except Exception as e:
        logger.exception(f"Prediction failed for student {features.student_id}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred during prediction: {str(e)}"
        )

@app.post("/predict-batch", response_model=List[PredictionResponse])
async def predict_batch_students(students: List[StudentFeatures]):
    """Process multiple students and return results sorted by risk."""
    results = []
    for student in students:
        try:
            prediction = await predict_single_student(student)
            results.append(prediction)
        except Exception:
            # Continue processing others if one fails
            continue
    
    # Sort by risk score (most at-risk first)
    return sorted(results, key=lambda x: x.risk_score, reverse=True)

@app.get("/health")
def check_health():
    """Basic health check and model status."""
    return {
        "status": "online",
        "model_loaded": churn_model is not None,
        "features_expected": CHURN_FEATURES
    }

if __name__ == "__main__":
    uvicorn.run("app:app", host="0.0.0.0", port=9020, reload=True)