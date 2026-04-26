import logging
import os
import pickle
import time
from typing import Tuple

import pandas as pd
from flask import Flask, jsonify, render_template, request
from flask_cors import CORS

# --- Configure Logging ---
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("progression-service")

app = Flask(__name__)
CORS(app)

# --- Configuration ---
# The model is now loaded from a pickle file instead of being trained from Google Sheets
MODEL_PATH = os.path.join(os.path.dirname(__file__), "progression_model.pickle")

# Global model variable
model = None

def load_model():
    """Loads the pre-trained progression model from a pickle file."""
    global model
    try:
        if not os.path.exists(MODEL_PATH):
            logger.warning(f"Model file not found at {MODEL_PATH}. Inference will be unavailable.")
            return None
        
        with open(MODEL_PATH, "rb") as f:
            model = pickle.load(f)
        logger.info("Successfully loaded progression model.")
        return model
    except Exception as e:
        logger.error(f"Failed to load model: {str(e)}")
        return None

# Initialize model on startup
model = load_model()

progression_features = [
   'session_duration_min',
   'retry_requests',
   'hint_usage_frequency',
   'time_to_success_sec',
   'response_latency_sec'
]

def get_ai_progression_recommendation(student_game_stats):
    """
    Core logic provided by user for predicting student progression recommendation.
    """
    if model is None:
        return {"error": "Prediction engine is not initialized."}

    # Ensure we use a DataFrame with the correct column names for the model
    input_df = pd.DataFrame([student_game_stats], columns=progression_features)

    # Prediction (0: MOVE_DOWN, 1: STAY, 2: MOVE_UP)
    prediction = model.predict(input_df)[0]

    # Calculate confidence from probabilities
    probabilities = model.predict_proba(input_df)[0]
    confidence = round(max(probabilities) * 100, 2)

    action_map = {
        0: {"action": "MOVE_DOWN", "message": "🔋Let’s Recharge! Let’s try with basics to get your confidence back."},
        1: {"action": "STAY", "message": "✨Keep Growing! You’re getting better with every single click. Let’s do another!"},
        2: {"action": "MOVE_UP", "message": "🌟SUPERSTAR STATUS! You just breezed through that. Let's try something even cooler!"}
    }

    result = action_map[prediction].copy()
    result["confidence"] = f"{confidence}%"

    return result

@app.route('/health', methods=['GET'])
def health_check():
    """Service health and model availability status with metadata."""
    model_metadata = {}
    if os.path.exists(MODEL_PATH):
        mtime = os.path.getmtime(MODEL_PATH)
        model_metadata = {
            "load_status": "loaded" if model is not None else "ready_on_disk",
            "last_modified": time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(mtime)),
            "model_path": MODEL_PATH
        }

    return jsonify({
        "status": "operational",
        "model_ready": model is not None,
        "model_metadata": model_metadata,
        "features": progression_features
    }), 200

@app.route('/predict', methods=['POST'])
def predict_progression():
    """
    Predicts the ideal progression action based on game performance metrics.
    Includes input validation and a 'Frustration Guardrail'.
    """
    if model is None:
        return jsonify({"error": "Prediction engine is not initialized."}), 503

    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "Request body must be valid JSON"}), 400

        # Support both 'stats' wrapper or direct fields
        stats = data.get('stats', data)
        
        # Prepare input dict with defaults for missing features
        input_data = {}
        for feature in progression_features:
            val = stats.get(feature, 0)
            # Basic guardrail: ensure no negative numbers or extreme outliers
            try:
                numeric_val = float(val)
                input_data[feature] = max(0.0, min(numeric_val, 10000.0))
            except (ValueError, TypeError):
                input_data[feature] = 0.0

        # --- Removed the Frustration Guardrail ---
        # The AI now always base its recommendation on the predictive model output
        recommendation = get_ai_progression_recommendation(input_data)

        
        if "error" in recommendation:
             return jsonify(recommendation), 500

        logger.info(f"Prediction result: {recommendation['action']} (Frustration check: {'PASS' if recommendation.get('action') != 'MOVE_DOWN' or 'reason' not in recommendation else 'TRIGGERED'})")

        return jsonify(recommendation), 200

    except Exception as e:
        logger.exception("Error during inference")
        return jsonify({"error": str(e)}), 500

@app.route('/retrain', methods=['POST'])
def trigger_retrain():
    """Reload the model from the pickle file."""
    if load_model():
        return jsonify({"message": "Model successfully reloaded."}), 200
    return jsonify({"error": "Failed to reload model."}), 500

@app.route('/', methods=['GET'])
def index():
    """Serve the static monitoring UI."""
    try:
        return render_template('index.html')
    except Exception:
        return jsonify({"message": "Progression AI Service is running."})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 9017))
    app.run(host='0.0.0.0', port=port, debug=False)




