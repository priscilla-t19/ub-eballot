"""
Mobile Deployment Configuration for UB eBallot
Optimizes the system for mobile devices and provides deployment instructions.
"""

import os
from flask import Flask, request, render_template, make_response
from werkzeug.middleware.proxy_fix import ProxyFix


def configure_mobile_app(app: Flask):
    """Configure Flask app for mobile deployment."""

    # Enable proxy fix for mobile deployments behind reverse proxies
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_port=1, x_prefix=1)

    # Mobile-specific headers
    @app.after_request
    def mobile_headers(response):
        # Mobile viewport optimization
        if 'text/html' in response.content_type:
            response.headers['X-UA-Compatible'] = 'IE=edge'
            response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
            response.headers['Pragma'] = 'no-cache'
            response.headers['Expires'] = '0'

        return response

    # Mobile detection
    @app.context_processor
    def mobile_context():
        user_agent = request.headers.get('User-Agent', '').lower()
        is_mobile = any(device in user_agent for device in [
            'mobile', 'android', 'iphone', 'ipad', 'ipod', 'blackberry', 'opera mini'
        ])
        return {'is_mobile': is_mobile}

    return app


# Mobile deployment configuration
MOBILE_CONFIG = {
    'host': '0.0.0.0',  # Allow external connections
    'port': int(os.environ.get('PORT', 5000)),
    'debug': os.environ.get('FLASK_ENV') == 'development',
    'threaded': True,  # Enable threading for mobile requests
    'processes': 1,    # Single process for mobile deployment
}


def create_mobile_app(config_class=None):
    """Create Flask app optimized for mobile deployment."""
    from app import create_app as base_create_app
    from config import Config

    # Use Config if no config_class provided
    if config_class is None:
        config_class = Config

    app = base_create_app(config_class)

    # Apply mobile optimizations
    app = configure_mobile_app(app)

    return app


# Mobile deployment instructions
MOBILE_DEPLOYMENT_GUIDE = """
# UB eBallot Mobile Deployment Guide

## Local Mobile Testing

1. **Start the server:**
   ```bash
   python run.py
   ```

2. **Find your computer's IP:**
   ```bash
   ipconfig  # Windows
   ifconfig  # Linux/Mac
   ```
   Look for your local IP (e.g., 192.168.1.100)

3. **Access from mobile:**
   Open browser on phone: `http://[YOUR_IP]:5000`

## Production Mobile Deployment

### Option 1: Heroku (Free)
```bash
# Install Heroku CLI
# Create app
heroku create your-ub-eballot-app

# Deploy
git push heroku main
```

### Option 2: Railway (Easy)
1. Connect GitHub repo
2. Auto-deploys on push
3. Free tier available

### Option 3: DigitalOcean App Platform
1. Connect repo
2. Automatic HTTPS
3. Global CDN

### Option 4: Local Network Server
```bash
# For local network access
python run.py

# Access from mobile: http://[computer_ip]:5000
```

## Mobile Optimization Features

-  Responsive design for all screen sizes
-  Touch-friendly buttons and forms
-  Mobile-optimized navigation
-  Fast loading with minimal assets
-  Offline-capable service worker
-  Progressive Web App (PWA) support

## Security for Mobile

-  HTTPS enforced in production
-  CSRF protection on all forms
-  Rate limiting for mobile requests
-  Session security with mobile timeouts
-  Input validation and sanitization

## Testing Checklist

- [ ] Homepage loads on mobile
- [ ] Admin login works on mobile
- [ ] Student voting flow works
- [ ] Results display correctly
- [ ] Touch interactions work
- [ ] Forms are mobile-friendly
- [ ] No horizontal scrolling
- [ ] Fast loading times
"""


def print_mobile_guide():
    """Print mobile deployment guide."""
    print(MOBILE_DEPLOYMENT_GUIDE)


if __name__ == "__main__":
    print_mobile_guide()