# Bitunix API Key Setup Guide

## Overview

This guide walks you through creating and configuring API keys for Bitunix exchange integration with the Crypto Trading Journal application.

## Prerequisites

- Active Bitunix trading account
- Completed KYC verification (if required)
- Access to Bitunix web platform or mobile app

## Step-by-Step Setup

### 1. Access API Management

1. **Log into Bitunix**
   - Go to [Bitunix website](https://www.bitunix.com)
   - Log in with your credentials
   - Complete 2FA if enabled

2. **Navigate to API Settings**
   - Click on your profile/account icon (usually top-right)
   - Look for "API Management" or "API Keys" in the dropdown menu
   - Click to access the API management page

### 2. Create New API Key

1. **Start API Key Creation**
   - Click "Create API Key" or similar button
   - You may need to verify your identity (2FA, email verification)

2. **Configure API Key Settings**
   - **API Key Name**: Give it a descriptive name (e.g., "Trading Journal Read-Only")
   - **Permissions**: Select **READ ONLY** permissions
     - ✅ Enable: Read account information
     - ✅ Enable: Read trading history
     - ✅ Enable: Read position data
     - ❌ Disable: Trading permissions
     - ❌ Disable: Withdrawal permissions
     - ❌ Disable: Transfer permissions

3. **IP Restrictions (Recommended)**
   - If possible, add your IP address for additional security
   - You can find your IP at [whatismyipaddress.com](https://whatismyipaddress.com)
   - Add your current IP to the whitelist

4. **Create the Key**
   - Click "Create" or "Generate"
   - Complete any additional verification steps

### 3. Save Your API Credentials

⚠️ **IMPORTANT**: You will only see the API key once. Make sure to copy it immediately.

1. **Copy API Key**
   - Copy the generated API key
   - Store it securely (password manager recommended)
   - Do NOT share this key with anyone

2. **Note Additional Information**
   - Some exchanges also provide an API Secret
   - Copy any additional credentials provided
   - Note the API endpoint URL if provided

### 4. Configure in Trading Journal

1. **Open Trading Journal**
   - Navigate to `http://localhost:8501`
   - Go to the "Config" page

2. **Add Bitunix Configuration**
   - Find the "Exchange Configuration" section
   - Look for Bitunix in the list of supported exchanges
   - Click "Add" or "Configure" for Bitunix

3. **Enter API Credentials**
   - **API Key**: Paste your copied API key
   - **API Secret**: Enter if required (some exchanges don't use secrets)
   - **Passphrase**: Enter if required
   - Use the "Show/Hide" toggle to verify you entered correctly

4. **Test Connection**
   - Click "Test Connection" button
   - Wait for the test to complete
   - You should see a "Connection Successful" message

5. **Save Configuration**
   - Click "Save" to store your configuration
   - The API key will be encrypted and stored securely

### 5. Verify Setup

1. **Check Connection Status**
   - The exchange should show as "Connected" or "Active"
   - Note the last connection test timestamp

2. **Test Data Sync**
   - Click the "Refresh Data" button
   - Wait for the sync to complete
   - Check if your recent trades appear in the Trade History page

## Security Best Practices

### API Key Security

1. **Read-Only Permissions**
   - Never grant trading or withdrawal permissions
   - Only enable read permissions for account and trading data

2. **IP Restrictions**
   - Always use IP restrictions when available
   - Update IP restrictions if your IP changes

3. **Regular Rotation**
   - Rotate API keys every 3-6 months
   - Delete old keys after creating new ones

4. **Secure Storage**
   - Never store API keys in plain text files
   - Use password managers or secure note applications
   - Don't share keys via email or messaging apps

### Account Security

1. **Enable 2FA**
   - Use Google Authenticator or similar app
   - Enable 2FA for both login and API management

2. **Monitor Activity**
   - Regularly check API usage logs on Bitunix
   - Monitor for any unauthorized access attempts

3. **Account Alerts**
   - Enable email/SMS alerts for API key creation/deletion
   - Set up alerts for unusual account activity

## Troubleshooting

### Common Issues

#### "Invalid API Key" Error

**Possible Causes**:
- API key was copied incorrectly
- API key has been disabled or deleted
- API key doesn't have required permissions

**Solutions**:
1. Double-check the API key for typos
2. Verify the key is still active in Bitunix
3. Ensure read permissions are enabled
4. Try creating a new API key

#### "Connection Timeout" Error

**Possible Causes**:
- Network connectivity issues
- Bitunix API is temporarily unavailable
- IP restrictions blocking access

**Solutions**:
1. Check your internet connection
2. Verify your IP hasn't changed (if using IP restrictions)
3. Check Bitunix API status
4. Try again after a few minutes

#### "Insufficient Permissions" Error

**Possible Causes**:
- API key doesn't have read permissions
- Account doesn't have trading history
- KYC verification incomplete

**Solutions**:
1. Verify API key has read permissions enabled
2. Check if you have any trading history on Bitunix
3. Complete KYC verification if required

#### "Rate Limit Exceeded" Error

**Possible Causes**:
- Too many API requests in short time
- Multiple applications using same API key

**Solutions**:
1. Wait a few minutes before trying again
2. Ensure only one application is using the API key
3. Check if you have other trading bots or tools connected

### Getting Help

If you continue to experience issues:

1. **Check Bitunix Documentation**
   - Review Bitunix API documentation
   - Check for any recent API changes

2. **Contact Bitunix Support**
   - Use Bitunix customer support for API-related issues
   - Provide specific error messages

3. **Application Logs**
   - Check Trading Journal logs for detailed error information:
   ```bash
   docker-compose -f docker-compose.prod.yml logs --tail=50
   ```

## API Limitations

### Rate Limits

Bitunix typically implements rate limits:
- **Requests per minute**: Usually 60-120 requests
- **Requests per day**: Usually 10,000+ requests
- **Burst limits**: Short-term higher limits

The Trading Journal respects these limits automatically.

### Data Availability

- **Historical Data**: Usually available for 1-3 months
- **Real-time Data**: Position updates may have slight delays
- **Partial Positions**: Open positions are tracked and updated

### Supported Data Types

The application can import:
- ✅ Completed trades/positions
- ✅ Partially closed positions
- ✅ Position history
- ✅ PnL data
- ✅ Trade timestamps
- ❌ Order book data
- ❌ Real-time price feeds

## Maintenance

### Regular Tasks

1. **Monitor API Usage**
   - Check API usage in Bitunix dashboard
   - Ensure you're within rate limits

2. **Update IP Restrictions**
   - Update if your IP address changes
   - Remove old IPs from whitelist

3. **Key Rotation**
   - Create new API key every 3-6 months
   - Update in Trading Journal configuration
   - Delete old key from Bitunix

### Backup Configuration

After successful setup, consider backing up your configuration:

```bash
# Backup encrypted configuration
cp data/config.json config-backup.json
cp data/credentials.enc credentials-backup.enc
```

---

**Security Reminder**: Never share your API keys or store them in unsecured locations. The Trading Journal encrypts and stores them securely, but you should also keep a secure backup.