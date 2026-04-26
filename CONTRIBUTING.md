# Contributing to AI Models

Thank you for your interest in contributing to the E-Learning AI Models project!

## How to Contribute

1. **Fork the repository** to your own GitHub account.
2. **Create a feature branch** from the `dev` branch:
   ```bash
   git checkout dev
   git pull origin dev
   git checkout -b feature/your-feature-name
   ```
3. **Make your changes** and ensure they follow our coding standards.
4. **Commit your changes** with descriptive commit messages.
5. **Push to your fork** and **submit a Pull Request** targeting the `dev` branch.

## Branching Flow

1. All development happens in `dev` or feature branches.
2. Features are merged into `dev` after review.
3. `dev` is merged into `test` for integration testing.
4. `test` is merged into `main` for production releases.

## Code Standards

- Follow Python PEP 8 standards where applicable.
- Ensure all new services include a `Dockerfile` for deployment.
- Document any new API endpoints or model parameters.
