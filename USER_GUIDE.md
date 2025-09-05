# Crypto Trading Journal - User Guide

## Table of Contents

1. [Getting Started](#getting-started)
2. [Application Setup](#application-setup)
3. [Exchange Configuration](#exchange-configuration)
4. [Using the Application](#using-the-application)
5. [Features Overview](#features-overview)
6. [Troubleshooting](#troubleshooting)
7. [Best Practices](#best-practices)

## Getting Started

The Crypto Trading Journal is a web-based application that helps you track, analyze, and improve your cryptocurrency trading performance. It connects to your exchange accounts via API to automatically import trade data and provides comprehensive analysis tools.

### What You'll Need

- Docker and Docker Compose installed on your system
- API keys from your crypto exchange (currently supports Bitunix)
- A web browser to access the application

### Quick Start

1. **Setup the Application**
   ```bash
   ./setup-production.sh
   ```

2. **Access the Application**
   - Open your web browser
   - Navigate to `http://localhost:8501`

3. **Configure Your Exchange**
   - Go to the Config page
   - Add your exchange API credentials
   - Test the connection

4. **Import Your Data**
   - Click the refresh button to sync your trade data
   - Wait for the import to complete

5. **Start Analyzing**
   - View your trades in the Trade History page
   - Analyze performance in the Trend Analysis page
   - Study confluence effectiveness in the Confluence Analysis page

## Application Setup

### System Requirements

- **Operating System**: Windows, macOS, or Linux
- **Memory**: Minimum 1GB RAM, recommended 2GB+
- **Storage**: 2GB free disk space
- **Network**: Internet connection for exchange API access

### Installation Steps

1. **Install Docker**
   - Download and install Docker Desktop from [docker.com](https://www.docker.com/products/docker-desktop)
   - Ensure Docker is running

2. **Download the Application**
   ```bash
   git clone <repository-url>
   cd crypto-trading-journal
   ```

3. **Run Setup Script**
   ```bash
   ./setup-production.sh
   ```

4. **Verify Installation**
   - The application should be accessible at `http://localhost:8501`
   - You should see the main dashboard

### Manual Setup (Alternative)

If you prefer manual setup:

```bash
# Create data directory
mkdir -p data

# Build and start the application
docker-compose -f docker-compose.prod.yml up -d

# Check status
docker-compose -f docker-compose.prod.yml ps
```

## Exchange Configuration

### Bitunix API Setup

1. **Create API Keys**
   - Log into your Bitunix account
   - Navigate to API Management
   - Create a new API key with read permissions
   - Copy the API key (you won't be able to see it again)

2. **Configure in Application**
   - Go to the Config page in the application
   - Find the Bitunix section
   - Enter your API key
   - Click "Test Connection" to verify
   - Save the configuration

### API Key Security

- **Read-Only Permissions**: Only grant read permissions to API keys
- **IP Restrictions**: Configure IP restrictions on your exchange if possible
- **Regular Rotation**: Rotate API keys periodically for security
- **Secure Storage**: The application encrypts API keys before storing them

### Supported Exchanges

Currently supported:
- **Bitunix**: Full support for position history and trade data

Coming soon:
- Additional exchanges will be added based on user demand

## Using the Application

### Navigation

The application has four main pages accessible from the sidebar:

1. **Trade History**: View and manage your trade records
2. **Trend Analysis**: Analyze your performance over time
3. **Confluence Analysis**: Study the effectiveness of your trading setups
4. **Config**: Manage exchange connections and custom fields

### Data Synchronization

- **Automatic Sync**: The application can automatically sync data on startup
- **Manual Sync**: Use the refresh button to manually sync data
- **Incremental Updates**: Only new and changed data is downloaded
- **Status Indicators**: Check sync status and last update time

## Features Overview

### Trade History Page

**Purpose**: View and manage all your trading records

**Key Features**:
- **Complete Trade List**: All imported trades with detailed information
- **Filtering**: Filter trades by date, symbol, side, or status
- **Sorting**: Sort by any column (date, PnL, symbol, etc.)
- **Trade Details**: Click on any trade to see full details
- **Custom Fields**: Add confluence tags and win/loss status
- **Position Status**: See if positions are fully or partially closed

**How to Use**:
1. Navigate to Trade History page
2. Use filters to find specific trades
3. Click on a trade to edit custom fields
4. Add confluence tags to categorize your setups
5. Mark trades as wins or losses for analysis

### Trend Analysis Page

**Purpose**: Analyze your trading performance over time

**Key Features**:
- **PnL Charts**: Interactive time-series charts of your profit/loss
- **Time Frames**: View daily, weekly, or monthly aggregations
- **Cumulative PnL**: Track your overall performance progression
- **Interactive Charts**: Zoom, pan, and hover for detailed information
- **Export Options**: Export charts and data for external analysis

**How to Use**:
1. Navigate to Trend Analysis page
2. Select your preferred time frame (Daily/Weekly/Monthly)
3. Use chart controls to zoom and explore data
4. Hover over data points for detailed information
5. Export data or charts as needed

### Confluence Analysis Page

**Purpose**: Analyze the effectiveness of your trading setups

**Key Features**:
- **Win Rate Analysis**: See win rates for each confluence type
- **PnL Performance**: Analyze profit/loss by confluence
- **Statistical Significance**: Understand which setups work best
- **Comparison Tools**: Compare different confluence combinations
- **Performance Ranking**: See your best and worst performing setups

**How to Use**:
1. Navigate to Confluence Analysis page
2. Review win rates for each confluence type
3. Identify your most profitable setups
4. Focus on improving or avoiding poor-performing confluences
5. Use filters to analyze specific time periods

### Config Page

**Purpose**: Manage application settings and exchange connections

**Key Features**:
- **Exchange Management**: Add, edit, and test exchange connections
- **API Key Storage**: Securely store and manage API credentials
- **Custom Fields**: Define confluence options and other custom fields
- **Connection Testing**: Verify API connections before saving
- **Data Management**: Backup and restore options

**How to Use**:
1. Navigate to Config page
2. Add your exchange API credentials
3. Test connections to ensure they work
4. Configure custom confluence options
5. Save your settings

## Troubleshooting

### Common Issues

#### Application Won't Start

**Symptoms**: Can't access the application at localhost:8501

**Solutions**:
1. Check if Docker is running:
   ```bash
   docker info
   ```

2. Verify the container is running:
   ```bash
   docker-compose -f docker-compose.prod.yml ps
   ```

3. Check for port conflicts:
   ```bash
   netstat -tulpn | grep 8501
   ```

4. Review container logs:
   ```bash
   docker-compose -f docker-compose.prod.yml logs
   ```

#### API Connection Failures

**Symptoms**: "Connection failed" when testing API keys

**Solutions**:
1. Verify API key is correct and active
2. Check if API key has proper permissions (read access)
3. Ensure your IP is not blocked by the exchange
4. Check exchange API status
5. Review application logs for detailed error messages

#### Data Not Syncing

**Symptoms**: No new trades appearing after sync

**Solutions**:
1. Check API connection status in Config page
2. Verify you have recent trading activity
3. Check if your positions are fully closed
4. Review sync logs for errors
5. Try manual refresh

#### Performance Issues

**Symptoms**: Application is slow or unresponsive

**Solutions**:
1. Check available system memory
2. Restart the application:
   ```bash
   docker-compose -f docker-compose.prod.yml restart
   ```
3. Clear browser cache
4. Check for large datasets that might need optimization

### Getting Help

If you continue to experience issues:

1. **Check Logs**: Always check application logs first
2. **Review Documentation**: Ensure you've followed setup instructions correctly
3. **Verify Prerequisites**: Confirm Docker and system requirements are met
4. **Test Connectivity**: Verify network connectivity to exchanges

### Log Files

Access logs using:
```bash
# View recent logs
docker-compose -f docker-compose.prod.yml logs --tail=100

# Follow logs in real-time
docker-compose -f docker-compose.prod.yml logs -f

# View logs for specific time period
docker-compose -f docker-compose.prod.yml logs --since="1h"
```

## Best Practices

### Security

1. **API Key Management**
   - Use read-only API keys only
   - Rotate keys regularly
   - Never share API keys
   - Use IP restrictions when possible

2. **System Security**
   - Keep Docker updated
   - Use strong passwords for system accounts
   - Don't expose the application to the internet without authentication
   - Regular security updates

### Data Management

1. **Regular Backups**
   ```bash
   # Create backup
   tar -czf backup-$(date +%Y%m%d).tar.gz data/
   ```

2. **Data Validation**
   - Regularly verify trade data accuracy
   - Cross-check with exchange records
   - Monitor for missing or duplicate trades

3. **Performance Optimization**
   - Sync data regularly to avoid large imports
   - Archive old data if performance degrades
   - Monitor disk space usage

### Trading Analysis

1. **Confluence Tagging**
   - Be consistent with confluence naming
   - Tag trades immediately after closing
   - Use specific, descriptive confluence names
   - Review and update confluence definitions regularly

2. **Performance Review**
   - Analyze performance weekly/monthly
   - Focus on confluence effectiveness
   - Identify patterns in winning/losing trades
   - Adjust strategy based on data insights

3. **Record Keeping**
   - Keep detailed notes on trading decisions
   - Document market conditions
   - Track emotional state during trades
   - Review and learn from both wins and losses

### System Maintenance

1. **Regular Updates**
   ```bash
   # Update application
   ./setup-production.sh --update
   ```

2. **Resource Monitoring**
   ```bash
   # Check resource usage
   docker stats
   ```

3. **Cleanup**
   ```bash
   # Clean up unused Docker resources
   ./setup-production.sh --cleanup
   ```

## Advanced Usage

### Custom Confluence Types

You can define custom confluence types in the Config page:

1. Navigate to Config page
2. Find the "Custom Fields" section
3. Add new confluence options
4. Save configuration
5. Use new confluences when tagging trades

### Data Export

Export your data for external analysis:

1. Use the export features in each page
2. Data is exported in CSV format
3. Import into Excel, Google Sheets, or other tools
4. Combine with external data sources for deeper analysis

### Integration with Other Tools

The application stores data in JSON format in the `data/` directory:

- `trades.json`: All trade records
- `config.json`: Application configuration
- `credentials.enc`: Encrypted API credentials

You can build custom tools that read this data for additional analysis.

---

**Need Help?** Check the troubleshooting section or review the application logs for detailed error information.