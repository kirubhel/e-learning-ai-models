#!/bin/bash

# Deploy Letter Arrangement AI Service
# This script builds and deploys the AI service to the server

set -e

echo "=========================================="
echo "Deploying Letter Arrangement AI Service"
echo "=========================================="
echo ""

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
SERVICE_NAME="letter-arrangement-ai"
IMAGE_NAME="letter-arrangement-ai:latest"
CONTAINER_NAME="letter-arrangement-ai"
PORT=9017
NETWORK="e-learning_elearning-network"

# Ensure network exists
docker network create $NETWORK 2>/dev/null || true

echo -e "${YELLOW}[1] Building Docker image...${NC}"
docker build -t $IMAGE_NAME .

if [ $? -ne 0 ]; then
    echo "Failed to build Docker image"
    exit 1
fi
echo -e "${GREEN}✓ Image built successfully${NC}"
echo ""

echo -e "${YELLOW}[2] Stopping existing container (if any)...${NC}"
docker stop $CONTAINER_NAME 2>/dev/null || true
docker rm $CONTAINER_NAME 2>/dev/null || true
echo -e "${GREEN}✓ Cleaned up existing container${NC}"
echo ""

echo -e "${YELLOW}[3] Starting new container...${NC}"
docker run -d \
    --name $CONTAINER_NAME \
    --restart unless-stopped \
    -p ${PORT}:${PORT} \
    -e PORT=${PORT} \
    -e HOST=0.0.0.0 \
    --network $NETWORK \
    $IMAGE_NAME

if [ $? -ne 0 ]; then
    echo "Failed to start container"
    exit 1
fi
echo -e "${GREEN}✓ Container started successfully${NC}"
echo ""

echo -e "${YELLOW}[4] Waiting for service to be ready...${NC}"
sleep 5

# Check health
for i in {1..10}; do
    if curl -s http://localhost:${PORT}/health > /dev/null 2>&1; then
        echo -e "${GREEN}✓ Service is healthy${NC}"
        break
    fi
    if [ $i -eq 10 ]; then
        echo "Service health check failed after 10 attempts"
        docker logs $CONTAINER_NAME
        exit 1
    fi
    sleep 2
done
echo ""

echo -e "${GREEN}=========================================="
echo "Deployment Complete!"
echo "==========================================${NC}"
echo ""
echo "Service Details:"
echo "  Container: $CONTAINER_NAME"
echo "  Port: $PORT"
echo "  Network: $NETWORK"
echo "  Health: http://localhost:${PORT}/health"
echo ""
echo "Test the service:"
echo "  curl http://localhost:${PORT}/health"
echo ""

