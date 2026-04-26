#!/bin/bash

# Deployment script for churn prediction service
# Server: 196.189.50.57
# Port: 9020

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
APP_PORT="9020"
APP_NAME="churn-service"
IMAGE_NAME="churn-service"
CONTAINER_NAME="churn-service"
REMOTE_DIR="/home/administrator/churn-service"

echo -e "${GREEN}Starting deployment of Churn Service to ${SERVER_IP}...${NC}"

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

echo -e "${GREEN}Step 4: Uploading image...${NC}"
sshpass -p "$SERVER_PASSWORD" scp -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
    "${IMAGE_TAR}" \
    ${SERVER_USER}@${SERVER_IP}:${REMOTE_DIR}/ || {
    echo -e "${RED}Failed to upload files${NC}"
    exit 1
}

echo -e "${GREEN}Step 5: Executing remote deployment...${NC}"
sshpass -p "$SERVER_PASSWORD" ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null ${SERVER_USER}@${SERVER_IP} << 'ENDSSH'
cd /home/administrator/churn-service

echo "Loading Docker image..."
docker load -i churn-service.tar

echo "Stopping existing container if running..."
docker stop churn-service 2>/dev/null || true
docker rm churn-service 2>/dev/null || true

echo "Starting new container..."
docker run -d \
    --name churn-service \
    --restart unless-stopped \
    -p 9020:9020 \
    churn-service:latest

echo "Connecting to e-learning_elearning-network..."
docker network connect e-learning_elearning-network churn-service 2>/dev/null || true

echo "Cleaning up tar file..."
rm -f churn-service.tar

echo "Deployment completed!"
docker ps | grep churn-service
ENDSSH

echo -e "${GREEN}Step 6: Cleaning up local files...${NC}"
rm -f "${IMAGE_TAR}"

echo -e "${GREEN}Deployment completed successfully!${NC}"
echo -e "${GREEN}Churn service available at: http://${SERVER_IP}:${APP_PORT}${NC}"
echo -e "${GREEN}Health check: http://${SERVER_IP}:${APP_PORT}/health${NC}"
