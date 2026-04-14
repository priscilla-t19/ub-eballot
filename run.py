"""
UB eBallot - Run Server
Supports both local development and mobile deployment
"""

from app import create_app
from mobile_deployment import configure_mobile_app, MOBILE_CONFIG

# Create base app and apply mobile optimizations
app = create_app()
app = configure_mobile_app(app)

if __name__ == '__main__':
    print(" Starting UB eBallot Server...")
    print(f" Mobile deployment ready on: http://0.0.0.0:{MOBILE_CONFIG['port']}")
    print(" Run 'flask mobile_guide' for deployment instructions")

    app.run(
        host=MOBILE_CONFIG['host'],
        port=MOBILE_CONFIG['port'],
        debug=MOBILE_CONFIG['debug'],
        threaded=MOBILE_CONFIG['threaded']
    )
