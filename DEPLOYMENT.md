# Crypto Trading Journal - Deployment Guide

## Overview

This guide covers the deployment of the Crypto Trading Journal application using Docker and Docker Compose. The application is designed to run in a containerized environment with persistent data storage.

## Prerequisites

- Docker Engine 20.10+ 
- Docker Compose 2.0+
- At least 1GB of available RAM
- 2GB of available disk space

## Quick Start

### 1. Clone and Setup

```bash
git clone <repository-url>
cd crypto-trading-journal
mkdir -p data
```

### 2. Development Deployment

For development with hot-reload:

```bash
# Start development environment
docker-compose --profile dev up -d trading-journal-dev

# View logs
docker-compose logs -f trading-journal-dev

# Access application at http://localhost:8502
```

### 3. Production Deployment

For production deployment:

```bash
# Build and start production container
docker-compose -f docker-compose.prod.yml up -d

# View logs
docker-compose -f docker-compose.prod.yml logs -f

# Access application at http://localhost:8501
```

## Configuration Options

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `DATA_PATH` | `/app/data` | Path to persistent data directory |
| `LOG_LEVEL` | `INFO` | Logging level (DEBUG, INFO, WARNING, ERROR) |
| `TZ` | `UTC` | Timezone for the container |
| `STREAMLIT_SERVER_PORT` | `8501` | Port for Streamlit server |

### Volume Configuration

The application requires a persistent volume for data storage:

```yaml
volumes:
  - type: bind
    source: ./data
    target: /app/data
```

**Important**: Ensure the `./data` directory exists and has proper permissions:

```bash
mkdir -p data
chmod 755 data
```

## Security Configuration

### Production Security Features

The production configuration includes several security enhancements:

- **Non-root user**: Application runs as user `appuser` (UID 1000)
- **Read-only filesystem**: Container filesystem is read-only except for specific directories
- **Dropped capabilities**: All Linux capabilities dropped except essential ones
- **No new privileges**: Prevents privilege escalation
- **Resource limits**: Memory and CPU limits to prevent resource exhaustion

### Network Security

- Application only exposes port 8501
- Uses isolated Docker network
- CORS disabled for production
- XSRF protection enabled

## Health Checks

The application includes comprehensive health checks:

```yaml
healthcheck:
  test: ["CMD", "curl", "-f", "http://localhost:8501/_stcore/health"]
  interval: 30s
  timeout: 15s
  retries: 5
  start_period: 90s
```

## Monitoring and Logging

### Log Configuration

Logs are configured with rotation to prevent disk space issues:

```yaml
logging:
  driver: "json-file"
  options:
    max-size: "50m"
    max-file: "5"
```

### Viewing Logs

```bash
# View real-time logs
docker-compose logs -f trading-journal

# View last 100 lines
docker-compose logs --tail=100 trading-journal

# View logs for specific time period
docker-compose logs --since="2024-01-01T00:00:00" trading-journal
```

## Backup and Recovery

### Data Backup

The application data is stored in the `./data` directory. To backup:

```bash
# Create backup
tar -czf backup-$(date +%Y%m%d-%H%M%S).tar.gz data/

# Restore from backup
tar -xzf backup-YYYYMMDD-HHMMSS.tar.gz
```

### Container Backup

```bash
# Export container image
docker save crypto-trading-journal:latest | gzip > trading-journal-image.tar.gz

# Import container image
docker load < trading-journal-image.tar.gz
```

## Troubleshooting

### Common Issues

#### Container Won't Start

1. Check Docker daemon is running:
   ```bash
   docker info
   ```

2. Verify port availability:
   ```bash
   netstat -tulpn | grep 8501
   ```

3. Check container logs:
   ```bash
   docker-compose logs trading-journal
   ```

#### Permission Issues

If you encounter permission errors with the data directory:

```bash
# Fix ownership (Linux/macOS)
sudo chown -R 1000:1000 data/

# Fix permissions
chmod -R 755 data/
```

#### Health Check Failures

If health checks are failing:

1. Check if Streamlit is responding:
   ```bash
   curl -f http://localhost:8501/_stcore/health
   ```

2. Increase health check timeout in docker-compose.yml:
   ```yaml
   healthcheck:
     timeout: 30s
     start_period: 120s
   ```

#### Memory Issues

If the container is running out of memory:

1. Check memory usage:
   ```bash
   docker stats trading-journal
   ```

2. Increase memory limits in docker-compose.prod.yml:
   ```yaml
   deploy:
     resources:
       limits:
         memory: 2G
   ```

### Performance Optimization

#### For Large Datasets

If working with large amounts of trade data:

1. Increase memory allocation
2. Consider using SSD storage for the data directory
3. Monitor container resource usage regularly

#### Network Optimization

For better network performance:

1. Use host networking for local deployments:
   ```yaml
   network_mode: host
   ```

2. Optimize Docker network settings if needed

## Maintenance

### Regular Maintenance Tasks

1. **Log Rotation**: Logs are automatically rotated, but monitor disk usage
2. **Image Updates**: Regularly rebuild images with updated dependencies
3. **Data Backup**: Schedule regular backups of the data directory
4. **Security Updates**: Keep Docker and base images updated

### Updating the Application

```bash
# Stop the application
docker-compose down

# Pull latest changes
git pull

# Rebuild and restart
docker-compose build --no-cache
docker-compose up -d
```

## Advanced Configuration

### Custom Docker Compose Override

Create `docker-compose.override.yml` for local customizations:

```yaml
version: '3.8'
services:
  trading-journal:
    ports:
      - "8080:8501"  # Custom port
    environment:
      - LOG_LEVEL=DEBUG
```

### Multi-Stage Deployment

For complex deployments, consider using Docker Swarm or Kubernetes configurations based on the provided Docker setup.

## Support

For deployment issues:

1. Check the troubleshooting section above
2. Review container logs for error messages
3. Verify all prerequisites are met
4. Ensure proper file permissions on the data directory

## Security Considerations

- Never expose the application directly to the internet without proper authentication
- Use HTTPS in production with a reverse proxy (nginx, traefik)
- Regularly update the base Docker images
- Monitor container resource usage
- Implement proper backup and disaster recovery procedures