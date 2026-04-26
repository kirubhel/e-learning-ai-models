#!/bin/bash

# Deploy Letter Arrangement AI Service to Remote Server
# Usage: ./deploy-to-server.sh [server_user@server_ip]

set -e

# Configuration
SERVER="${1:-administrator@196.189.50.57}"
SERVER_PASS="${SERVER_PASS:-Girar@2025}"
SERVICE_DIR="~/letter-arrangement-ai"
IMAGE_NAME="letter-arrangement-ai:latest"
CONTAINER_NAME="letter-arrangement-ai"
PORT=9017
NETWORK="e-learning_elearning-network"

echo "=========================================="
echo "Deploying Letter Arrangement AI Service"
echo "=========================================="
echo ""

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Check if sshpass is available
if ! command -v sshpass &> /dev/null; then
    echo -e "${RED}sshpass is required but not installed.${NC}"
    echo "Install with: brew install sshpass (macOS) or apt-get install sshpass (Linux)"
    exit 1
fi

echo -e "${YELLOW}[1] Building Docker image locally for linux/amd64...${NC}"
docker buildx build --platform linux/amd64 -t $IMAGE_NAME . --load

if [ $? -ne 0 ]; then
    echo -e "${RED}Failed to build Docker image${NC}"
    exit 1
fi
echo -e "${GREEN}✓ Image built successfully${NC}"
echo ""

echo -e "${YELLOW}[2] Saving Docker image to tar file...${NC}"
docker save $IMAGE_NAME | gzip > /tmp/letter-arrangement-ai.tar.gz
echo -e "${GREEN}✓ Image saved${NC}"
echo ""

echo -e "${YELLOW}[3] Copying image to server...${NC}"
sshpass -p "$SERVER_PASS" scp /tmp/letter-arrangement-ai.tar.gz $SERVER:/tmp/
echo -e "${GREEN}✓ Image copied${NC}"
echo ""

echo -e "${YELLOW}[4] Loading image on server...${NC}"
sshpass -p "$SERVER_PASS" ssh $SERVER "docker load < /tmp/letter-arrangement-ai.tar.gz"
echo -e "${GREEN}✓ Image loaded${NC}"
echo ""

echo -e "${YELLOW}[5] Stopping existing container (if any)...${NC}"
sshpass -p "$SERVER_PASS" ssh $SERVER "docker stop $CONTAINER_NAME 2>/dev/null || true; docker rm $CONTAINER_NAME 2>/dev/null || true"
echo -e "${GREEN}✓ Cleaned up existing container${NC}"
echo ""

echo -e "${YELLOW}[6] Starting new container...${NC}"
sshpass -p "$SERVER_PASS" ssh $SERVER "docker network create $NETWORK 2>/dev/null || true; docker run -d \
    --name $CONTAINER_NAME \
    --restart unless-stopped \
    -p ${PORT}:${PORT} \
    -e PORT=${PORT} \
    -e HOST=0.0.0.0 \
    --network $NETWORK \
    $IMAGE_NAME"

if [ $? -ne 0 ]; then
    echo -e "${RED}Failed to start container${NC}"
    exit 1
fi
echo -e "${GREEN}✓ Container started successfully${NC}"
echo ""

echo -e "${YELLOW}[7] Waiting for service to be ready...${NC}"
sleep 10

# Check health
for i in {1..10}; do
    if sshpass -p "$SERVER_PASS" ssh $SERVER "curl -s http://localhost:${PORT}/health > /dev/null 2>&1"; then
        echo -e "${GREEN}✓ Service is healthy${NC}"
        break
    fi
    if [ $i -eq 10 ]; then
        echo -e "${RED}Service health check failed after 10 attempts${NC}"
        sshpass -p "$SERVER_PASS" ssh $SERVER "docker logs $CONTAINER_NAME"
        exit 1
    fi
    sleep 2
done
echo ""

echo -e "${YELLOW}[8] Cleaning up temporary files...${NC}"
rm -f /tmp/letter-arrangement-ai.tar.gz
sshpass -p "$SERVER_PASS" ssh $SERVER "rm -f /tmp/letter-arrangement-ai.tar.gz"
echo -e "${GREEN}✓ Cleanup complete${NC}"
echo ""

echo -e "${GREEN}=========================================="
echo "Deployment Complete!"
echo "==========================================${NC}"
echo ""
echo "Service Details:"
echo "  Server: $SERVER"
echo "  Container: $CONTAINER_NAME"
echo "  Port: $PORT"
echo "  Network: $NETWORK"
echo "  Health: http://$SERVER:${PORT}/health (from server)"
echo ""
echo "Test the service:"
echo "  sshpass -p '$SERVER_PASS' ssh $SERVER 'curl http://localhost:${PORT}/health'"
echo ""

