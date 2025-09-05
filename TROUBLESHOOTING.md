# Crypto Trading Journal - Troubleshooting Guide

## Table of Contents

1. [Installation Issues](#installation-issues)
2. [Application Startup Problems](#application-startup-problems)
3. [Exchange Connection Issues](#exchange-connection-issues)
4. [Data Synchronization Problems](#data-synchronization-problems)
5. [Performance Issues](#performance-issues)
6. [Data and Configuration Issues](#data-and-configuration-issues)
7. [Docker-Related Problems](#docker-related-problems)
8. [Network and Connectivity Issues](#network-and-connectivity-issues)
9. [Error Messages Reference](#error-messages-reference)
10. [Getting Additional Help](#getting-additional-help)

## Installation Issues

### Docker Not Found

**Error**: `docker: command not found` or `docker-compose: command not found`

**Solution**:
1. Install Docker Desktop from [docker.com](https://www.docker.com/products/docker-desktop)
2. Ensure Docker is running (check system tray/menu bar)
3. Restart your terminal/command prompt
4. Verify installation:
   ```bash
   docker --version
   docker-compose --version
   ```

### Permission Denied Errors (Linux/macOS)

**Error**: `Permission denied` when running Docker commands

**Solution**:
1. Add your user to the docker group:
   ```bash
   sudo usermod -aG docker $USER
   ```
2. Log out and log back in
3. Or use sudo for Docker commands:
   ```bash
   sudo docker-compose up -d
   ```

### Setup Script Won't Run

**Error**: `Permission denied: ./setup-production.sh`

**Solution**:
```bash
chmod +x setup-production.sh
./setup-production.sh
```

## Application Startup Problems

### Port Already in Use

**Error**: `Port 8501 is already in use`

**Symptoms**: Can't access application, Docker fails to start

**Solutions**:
1. **Find what's using the port**:
   ```bash
   # Linux/macOS
   lsof -i :8501
   
   # Windows
   netstat -ano | findstr :8501
   ```

2. **Stop the conflicting service** or **use a different port**:
   ```yaml
   # In docker-compose.yml, change:
   ports:
     - "8502:8501"  # Use port 8502 instead
   ```

3. **Kill existing containers**:
   ```bash
   docker-compose down
   docker ps -a | grep trading-journal
   docker rm -f <container-id>
   ```

### Container Exits Immediately

**Symptoms**: Container starts then stops immediately

**Diagnosis**:
```bash
# Check container logs
docker-compose logs trading-journal

# Check container status
docker-compose ps
```

**Common Solutions**:
1. **Missing data directory**:
   ```bash
   mkdir -p data
   chmod 755 data
   ```

2. **Invalid configuration**:
   - Check `data/config.json` for syntax errors
   - Remove corrupted config files and restart

3. **Memory issues**:
   - Increase Docker memory allocation
   - Close other applications to free memory

### Health Check Failures

**Symptoms**: Container shows as "unhealthy"

**Diagnosis**:
```bash
# Check health status
docker inspect --format='{{.State.Health.Status}}' crypto-trading-journal-prod

# View health check logs
docker inspect --format='{{range .State.Health.Log}}{{.Output}}{{end}}' crypto-trading-journal-prod
```

**Solutions**:
1. **Increase health check timeout**:
   ```yaml
   healthcheck:
     timeout: 30s
     start_period: 120s
   ```

2. **Check if Streamlit is responding**:
   ```bash
   curl -f http://localhost:8501/_stcore/health
   ```

## Exchange Connection Issues

### API Key Authentication Failures

**Error**: "Invalid API key" or "Authentication failed"

**Solutions**:
1. **Verify API key**:
   - Check for typos when copying
   - Ensure key hasn't been deleted from exchange
   - Verify key has read permissions

2. **Check API key format**:
   - Remove any extra spaces or characters
   - Ensure complete key was copied

3. **Test directly with exchange**:
   - Use exchange's API testing tools
   - Verify account status and permissions

### Connection Timeouts

**Error**: "Connection timeout" or "Network error"

**Solutions**:
1. **Check internet connectivity**:
   ```bash
   ping google.com
   curl -I https://api.bitunix.com
   ```

2. **Verify exchange API status**:
   - Check exchange status page
   - Look for maintenance announcements

3. **IP restrictions**:
   - Check if your IP changed
   - Update IP whitelist on exchange
   - Temporarily disable IP restrictions for testing

### Rate Limiting Issues

**Error**: "Rate limit exceeded" or "Too many requests"

**Solutions**:
1. **Wait and retry**:
   - Wait 5-10 minutes before retrying
   - Rate limits usually reset automatically

2. **Check for multiple connections**:
   - Ensure only one instance is running
   - Stop other trading bots or applications

3. **Reduce sync frequency**:
   - Sync less frequently
   - Use manual sync instead of automatic

## Data Synchronization Problems

### No Data Imported

**Symptoms**: Sync completes but no trades appear

**Diagnosis**:
1. **Check if you have trading history**:
   - Verify you have closed positions on the exchange
   - Check the date range of your trading activity

2. **Review sync logs**:
   ```bash
   docker-compose logs trading-journal | grep -i sync
   ```

**Solutions**:
1. **Verify API permissions**:
   - Ensure read access to trading history
   - Check account verification status

2. **Check date filters**:
   - Sync may be limited to recent data
   - Verify exchange API data availability

### Partial Data Import

**Symptoms**: Some trades missing or incomplete

**Solutions**:
1. **Check position status**:
   - Partially closed positions may not import completely
   - Wait for positions to fully close

2. **Manual refresh**:
   - Try multiple sync attempts
   - Check for API rate limiting

3. **Data validation**:
   - Compare with exchange records
   - Look for trades outside supported date range

### Sync Errors

**Common Error Messages**:

**"Failed to parse position data"**:
- Exchange API response format changed
- Check application logs for details
- May need application update

**"Insufficient permissions"**:
- API key lacks required permissions
- Enable read access for trading history

**"Account not found"**:
- API key may be for wrong account
- Verify account status and KYC completion

## Performance Issues

### Slow Loading

**Symptoms**: Pages take long time to load, charts don't render

**Solutions**:
1. **Check system resources**:
   ```bash
   docker stats trading-journal
   ```

2. **Increase memory allocation**:
   ```yaml
   # In docker-compose.yml
   deploy:
     resources:
       limits:
         memory: 2G
   ```

3. **Clear browser cache**:
   - Hard refresh (Ctrl+F5 or Cmd+Shift+R)
   - Clear browser cache and cookies

### High Memory Usage

**Symptoms**: System becomes slow, out of memory errors

**Solutions**:
1. **Restart application**:
   ```bash
   docker-compose restart trading-journal
   ```

2. **Optimize data**:
   - Archive old trade data
   - Reduce chart data points

3. **Increase system resources**:
   - Close other applications
   - Increase Docker memory limits

### Database Corruption

**Symptoms**: Data appears corrupted, application crashes

**Solutions**:
1. **Restore from backup**:
   ```bash
   # Stop application
   docker-compose down
   
   # Restore backup
   cp backup-YYYYMMDD.tar.gz ./
   tar -xzf backup-YYYYMMDD.tar.gz
   
   # Restart
   docker-compose up -d
   ```

2. **Reset data** (last resort):
   ```bash
   # Backup current data first
   cp -r data data-backup
   
   # Clear data
   rm -rf data/*
   touch data/.gitkeep
   
   # Restart and re-sync
   docker-compose restart
   ```

## Data and Configuration Issues

### Configuration Corruption

**Symptoms**: Settings not saving, application won't start

**Solutions**:
1. **Check config file**:
   ```bash
   cat data/config.json
   ```

2. **Validate JSON syntax**:
   - Use online JSON validator
   - Look for missing commas, brackets

3. **Reset configuration**:
   ```bash
   # Backup first
   cp data/config.json data/config.json.backup
   
   # Remove corrupted config
   rm data/config.json
   
   # Restart application (will create new config)
   docker-compose restart
   ```

### Lost API Keys

**Symptoms**: Need to re-enter API keys after restart

**Solutions**:
1. **Check credentials file**:
   ```bash
   ls -la data/credentials.enc
   ```

2. **Verify file permissions**:
   ```bash
   chmod 600 data/credentials.enc
   ```

3. **Re-enter credentials**:
   - Go to Config page
   - Re-enter API keys
   - Test and save

### Data Migration Issues

**Symptoms**: Data format errors after update

**Solutions**:
1. **Check migration logs**:
   ```bash
   docker-compose logs | grep -i migration
   ```

2. **Manual migration**:
   - May require manual data conversion
   - Check application documentation for migration steps

## Docker-Related Problems

### Image Build Failures

**Error**: Docker build fails with various errors

**Solutions**:
1. **Clean Docker cache**:
   ```bash
   docker system prune -af
   docker-compose build --no-cache
   ```

2. **Check Dockerfile syntax**:
   - Verify Dockerfile is not corrupted
   - Check for syntax errors

3. **Network issues during build**:
   - Check internet connectivity
   - Try building again (may be temporary network issue)

### Volume Mount Issues

**Error**: Data not persisting between restarts

**Solutions**:
1. **Check volume configuration**:
   ```bash
   docker-compose config
   ```

2. **Verify directory permissions**:
   ```bash
   ls -la data/
   chmod 755 data/
   ```

3. **Recreate volumes**:
   ```bash
   docker-compose down -v
   docker-compose up -d
   ```

### Container Resource Limits

**Symptoms**: Container killed, out of memory errors

**Solutions**:
1. **Increase Docker resources**:
   - Docker Desktop → Settings → Resources
   - Increase memory allocation

2. **Optimize container limits**:
   ```yaml
   deploy:
     resources:
       limits:
         memory: 2G
         cpus: '1.0'
   ```

## Network and Connectivity Issues

### DNS Resolution Problems

**Error**: Can't resolve exchange API hostnames

**Solutions**:
1. **Check DNS settings**:
   ```bash
   nslookup api.bitunix.com
   ```

2. **Use different DNS**:
   - Try Google DNS (8.8.8.8)
   - Or Cloudflare DNS (1.1.1.1)

3. **Docker DNS configuration**:
   ```yaml
   services:
     trading-journal:
       dns:
         - 8.8.8.8
         - 1.1.1.1
   ```

### Firewall Issues

**Symptoms**: Can't connect to exchange APIs

**Solutions**:
1. **Check firewall settings**:
   - Allow outbound HTTPS (port 443)
   - Allow Docker network access

2. **Corporate networks**:
   - Check proxy settings
   - May need to configure Docker proxy

### SSL/TLS Certificate Issues

**Error**: SSL certificate verification failed

**Solutions**:
1. **Update system certificates**:
   ```bash
   # Linux
   sudo apt-get update && sudo apt-get install ca-certificates
   
   # macOS
   brew install ca-certificates
   ```

2. **Check system time**:
   - Ensure system clock is accurate
   - SSL certificates are time-sensitive

## Error Messages Reference

### Common Error Patterns

| Error Message | Likely Cause | Solution |
|---------------|--------------|----------|
| `Connection refused` | Service not running | Check if container is running |
| `Permission denied` | File/directory permissions | Fix permissions with chmod |
| `Port already in use` | Port conflict | Change port or stop conflicting service |
| `Invalid API key` | Wrong/expired API key | Verify and update API key |
| `Rate limit exceeded` | Too many API requests | Wait and reduce request frequency |
| `Network timeout` | Network connectivity | Check internet connection |
| `JSON decode error` | Corrupted config file | Validate and fix JSON syntax |
| `Health check failed` | Application not responding | Check logs and restart if needed |

### Log Analysis

**View recent logs**:
```bash
docker-compose logs --tail=100 trading-journal
```

**Search for specific errors**:
```bash
docker-compose logs trading-journal | grep -i error
docker-compose logs trading-journal | grep -i "api key"
docker-compose logs trading-journal | grep -i "connection"
```

**Follow logs in real-time**:
```bash
docker-compose logs -f trading-journal
```

## Getting Additional Help

### Before Seeking Help

1. **Check logs** for specific error messages
2. **Try basic troubleshooting** steps above
3. **Verify prerequisites** are met
4. **Test with minimal configuration**

### Information to Provide

When seeking help, include:

1. **System Information**:
   - Operating system and version
   - Docker version
   - Available memory and disk space

2. **Error Details**:
   - Exact error messages
   - When the error occurs
   - Steps to reproduce

3. **Configuration**:
   - Docker compose configuration (remove sensitive data)
   - Application logs (last 50-100 lines)

4. **Environment**:
   - Network setup (corporate, home, etc.)
   - Firewall or proxy configuration
   - Other running applications

### Diagnostic Commands

Run these commands to gather diagnostic information:

```bash
# System information
docker --version
docker-compose --version
docker info

# Container status
docker-compose ps
docker stats --no-stream

# Application logs
docker-compose logs --tail=50 trading-journal

# Network connectivity
ping google.com
curl -I https://api.bitunix.com

# Disk space
df -h
du -sh data/

# File permissions
ls -la data/
```

### Self-Help Resources

1. **Application logs**: Most issues can be diagnosed from logs
2. **Docker documentation**: For Docker-specific issues
3. **Exchange API documentation**: For API-related problems
4. **Community forums**: Docker and cryptocurrency trading communities

---

**Remember**: Most issues can be resolved by checking logs, verifying configuration, and following the troubleshooting steps above. Always backup your data before making significant changes.