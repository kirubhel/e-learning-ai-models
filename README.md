# E-Learning AI Models

This repository contains various AI models and services designed to enhance the e-learning platform experience. These models handle tasks such as speech-to-text transcription, student churn prediction, and content difficulty assessment.

## Project Structure

- **`transcribe_model/`**: AI service for audio transcription (using WhisperX).
- **`churn_model/`**: Predictive model to identify students at risk of dropping out.
- **`easy_medium_hard/`**: Classification model to determine content difficulty levels.

## Branching Strategy

To maintain code quality, we follow the **Matrix Technology** branching standard:
- **`main`**: Production-ready code. Protected branch (requires Pull Request).
- **`test`**: Integration and staging environment.
- **`dev`**: Active development branch.

## Getting Started

1. Clone the repository:
   ```bash
   git clone https://github.com/kirubhel/e-learning-ai-models.git
   ```
2. Navigate to the specific model directory for implementation details.

## Collaboration

We welcome contributions! Please follow our [Contributing Guidelines](CONTRIBUTING.md).
