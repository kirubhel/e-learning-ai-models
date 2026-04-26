# Letter Arrangement AI Model Service

This service provides AI-powered difficulty level predictions for the Letter Arrangement game based on student progress metrics.

## Features

- Predicts player difficulty level (easy/medium/hard) based on:
  - Time spent
  - Number of retries
  - Average score per question
- Uses RandomForestClassifier trained on Google Sheets data
- RESTful API for easy integration
- Health check endpoint
- Model retraining capability

## API Endpoints

### POST /predict
Predict player level from student progress.

**Request:**
```json
{
  "current_difficulty": "medium",
  "progress": {
    "time_spent": 43,
    "retries": 1,
    "avg_score_per_question": 6.89
  }
}
```

**Response:**
```json
{
  "current_difficulty": "medium",
  "progress": {
    "time_spent": 43,
    "retries": 1,
    "avg_score_per_question": 6.89
  },
  "predicted_player_level": "medium",
  "recommended_level": "medium"
}
```

### GET /health
Health check endpoint.

**Response:**
```json
{
  "status": "healthy",
  "model_loaded": true,
  "encoder_loaded": true
}
```

### POST /retrain
Retrain the model with latest data from Google Sheets.

## Deployment

### Using Docker Compose
```bash
docker-compose up -d --build
```

### Using Docker
```bash
docker build -t letter-arrangement-ai .
docker run -d -p 9015:9015 --name letter-arrangement-ai letter-arrangement-ai
```

## Environment Variables

- `PORT`: Server port (default: 9015)
- `HOST`: Server host (default: 0.0.0.0)

## Integration

The backend Go service can call this service at:
```
http://letter-arrangement-ai:9014/predict
```

Or from outside Docker network:
```
http://localhost:9014/predict
```

