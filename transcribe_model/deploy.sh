#!/bin/bash

# Deployment script for transcription service
# Server: 196.189.50.57
# Port: 9022

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
SERVER_IP="196.189.50.57"
SERVER_USER="administrator"
SERVER_PASSWORD="Girar@2025"
APP_PORT="9022"
APP_NAME="transcribe-service"
IMAGE_NAME="transcribe-service"
CONTAINER_NAME="transcribe-service"
REMOTE_DIR="/home/administrator/transcribe-service"

echo -e "${GREEN}Starting deployment to ${SERVER_IP}...${NC}"

# Test SSH connection
echo -e "${YELLOW}Testing SSH connection...${NC}"
sshpass -p "$SERVER_PASSWORD" ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null ${SERVER_USER}@${SERVER_IP} "echo 'Connection successful'" || {
    echo -e "${RED}Failed to connect to server${NC}"
    exit 1
}

echo -e "${GREEN}Step 1: Building Docker image locally for Linux AMD64...${NC}"
docker build --platform linux/amd64 -t ${IMAGE_NAME}:latest . || {
    echo -e "${RED}Failed to build Docker image locally${NC}"
    exit 1
}

echo -e "${GREEN}Step 2: Saving Docker image to tar file...${NC}"
IMAGE_TAR="${IMAGE_NAME}.tar"
docker save -o "${IMAGE_TAR}" ${IMAGE_NAME}:latest || {
    echo -e "${RED}Failed to save Docker image${NC}"
    exit 1
}

echo -e "${GREEN}Step 3: Creating remote directory...${NC}"
sshpass -p "$SERVER_PASSWORD" ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null ${SERVER_USER}@${SERVER_IP} \
    "mkdir -p ${REMOTE_DIR}" || {
    echo -e "${RED}Failed to create remote directory${NC}"
    exit 1
}

echo -e "${GREEN}Step 4: Uploading image (this may take time)...${NC}"
sshpass -p "$SERVER_PASSWORD" scp -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
    "${IMAGE_TAR}" \
    ${SERVER_USER}@${SERVER_IP}:${REMOTE_DIR}/ || {
    echo -e "${RED}Failed to upload files${NC}"
    exit 1
}

echo -e "${GREEN}Step 5: Executing remote deployment...${NC}"
sshpass -p "$SERVER_PASSWORD" ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null ${SERVER_USER}@${SERVER_IP} << 'ENDSSH'
cd /home/administrator/transcribe-service

echo "Loading Docker image..."
docker load -i transcribe-service.tar

echo "Stopping existing container if running..."
docker stop transcribe-service 2>/dev/null || true
docker rm transcribe-service 2>/dev/null || true

echo "Starting new container..."
docker run -d \
    --name transcribe-service \
    --restart unless-stopped \
    -p 9022:9022 \
    transcribe-service:latest

echo "Connecting to e-learning_elearning-network..."
docker network connect e-learning_elearning-network transcribe-service 2>/dev/null || true

echo "Cleaning up tar file..."
rm -f transcribe-service.tar

echo "Deployment completed!"
docker ps | grep transcribe-service
ENDSSH

echo -e "${GREEN}Step 6: Cleaning up local files...${NC}"
rm -f "${IMAGE_TAR}"

echo -e "${GREEN}Deployment completed successfully!${NC}"
echo -e "${GREEN}Transcription service available at: http://${SERVER_IP}:${APP_PORT}${NC}"
echo -e "${GREEN}Health check: http://${SERVER_IP}:${APP_PORT}/health${NC}"
echo -e "${GREEN}API endpoint: http://${SERVER_IP}:${APP_PORT}/evaluate${NC}"
