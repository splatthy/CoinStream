# Crypto Trading Journal

A comprehensive, containerized Python Streamlit application for cryptocurrency trading analysis and performance tracking. Automatically sync trade data from exchanges, analyze performance trends, and optimize trading strategies through detailed confluence analysis.

## 🚀 Quick Start

### Automated Setup (Recommended)

```bash
# Clone the repository
git clone <repository-url>
cd crypto-trading-journal

# Run automated setup
./setup-production.sh
```

The application will be available at `http://localhost:8501`

### Manual Setup

```bash
# Create data directory
mkdir -p data

# Start production environment
docker-compose -f docker-compose.prod.yml up -d

# Check status
docker-compose -f docker-compose.prod.yml ps
```

### Development Mode

```bash
# Start development environment with hot-reload
docker-compose --profile dev up -d trading-journal-dev

# Access at http://localhost:8502
```

## 📚 Documentation

### Setup and Configuration
- **[User Guide](USER_GUIDE.md)** - Complete guide to using the application
- **[Deployment Guide](DEPLOYMENT.md)** - Detailed deployment instructions
- **[Bitunix API Setup](BITUNIX_API_SETUP.md)** - Step-by-step API key configuration

### Development and Features
- **[Development Guide](DEVELOPMENT.md)** - Development environment setup and workflow
- **[Features Documentation](FEATURES.md)** - Comprehensive feature overview
- **[Troubleshooting Guide](TROUBLESHOOTING.md)** - Common issues and solutions

## ✨ Key Features

### 🔄 Automated Data Management
- **Exchange Integration**: Seamless API integration with Bitunix (more exchanges coming)
- **Automatic Sync**: Incremental data synchronization with conflict resolution
- **Data Persistence**: Secure local storage with backup/restore capabilities
- **Real-time Updates**: Track partially closed positions and ongoing trades

### 📊 Advanced Analytics
- **Performance Trends**: Interactive time-series analysis with multiple timeframes
- **Confluence Analysis**: Analyze effectiveness of different trading setups
- **Win Rate Tracking**: Detailed statistics on trading performance
- **Custom Categorization**: Tag trades with custom confluence types

### 🔒 Security & Privacy
- **Local Data Storage**: All data stored locally, never in the cloud
- **Encrypted Credentials**: AES-256 encryption for API keys
- **Read-Only API Access**: Secure integration without trading permissions
- **Container Security**: Hardened Docker configuration with minimal privileges

### 🎯 User Experience
- **Intuitive Interface**: Clean, responsive Streamlit-based web interface
- **Interactive Charts**: Zoom, pan, and explore your trading data
- **Flexible Filtering**: Advanced filtering and sorting capabilities
- **Export Options**: Export data and charts for external analysis

## 🏗️ Architecture

```
crypto-trading-journal/
├── app/                    # Application source code
│   ├── main.py            # Streamlit entry point
│   ├── pages/             # UI pages (Trade History, Analysis, Config)
│   ├── services/          # Business logic and data processing
│   ├── models/            # Data models and validation
│   ├── integrations/      # Exchange API clients
│   └── utils/             # Utilities and helpers
├── data/                  # Persistent data storage (volume mounted)
├── tests/                 # Comprehensive test suite
├── docs/                  # Additional documentation
├── Dockerfile             # Optimized production container
├── docker-compose.yml     # Development configuration
├── docker-compose.prod.yml # Production configuration
└── setup-production.sh   # Automated setup script
```

## 🔧 System Requirements

- **Docker**: Version 20.10 or later
- **Docker Compose**: Version 2.0 or later
- **Memory**: Minimum 1GB RAM, recommended 2GB+
- **Storage**: 2GB free disk space
- **Network**: Internet connection for exchange API access

## 📈 Supported Exchanges

### Currently Supported
- **Bitunix**: Full support for position history and trade data

### Coming Soon
- Additional exchanges based on user demand
- Plugin architecture for easy exchange additions

## 🛠️ Development

### Development Environment

```bash
# Start development environment
docker-compose --profile dev up -d

# View logs
docker-compose logs -f trading-journal-dev

# Run tests
docker-compose exec trading-journal-dev python -m pytest
```

### Testing

```bash
# Run full test suite
make test

# Run specific test categories
make test-unit
make test-integration
make test-security
```

## 🔄 Updates and Maintenance

### Updating the Application

```bash
# Update to latest version
./setup-production.sh --update
```

### Backup and Recovery

```bash
# Create backup
tar -czf backup-$(date +%Y%m%d).tar.gz data/

# Restore from backup
tar -xzf backup-YYYYMMDD.tar.gz
docker-compose restart
```

### Maintenance

```bash
# Clean up Docker resources
./setup-production.sh --cleanup

# View system health
docker-compose logs --tail=50
docker stats trading-journal
```

## 🆘 Support

### Getting Help

1. **Check Documentation**: Review the comprehensive guides above
2. **Troubleshooting**: See [TROUBLESHOOTING.md](TROUBLESHOOTING.md) for common issues
3. **Logs**: Check application logs for detailed error information
4. **System Status**: Use the System Health page for diagnostics

### Common Commands

```bash
# View application status
docker-compose -f docker-compose.prod.yml ps

# View logs
docker-compose -f docker-compose.prod.yml logs -f

# Restart application
docker-compose -f docker-compose.prod.yml restart

# Stop application
docker-compose -f docker-compose.prod.yml down
```

## 🔐 Security

- **API Keys**: Only read-only permissions required
- **Data Privacy**: All data stored locally, never transmitted to third parties
- **Container Security**: Runs as non-root user with minimal privileges
- **Network Security**: HTTPS for all external communications
- **Regular Updates**: Keep Docker and dependencies updated

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🤝 Contributing

Contributions are welcome! Please read the contributing guidelines and submit pull requests for any improvements.

---

**Ready to optimize your trading performance?** Start with the [User Guide](USER_GUIDE.md) and get your trading journal up and running in minutes!