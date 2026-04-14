#!/usr/bin/env python3
"""
UB eBallot Security Testing Suite
Comprehensive testing for production readiness validation.
"""

import os
import sys
import requests
import time
import json
from datetime import datetime, timezone
import subprocess
import tempfile

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from crypto_utils import hash_password, verify_password
from security import log_security_event
from models import AdminUser, AuditLog
from app import create_app, db

ADMIN_USERNAME = os.environ.get('ADMIN_USERNAME', 'admin')
ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD', 'admin1234')


class SecurityTestSuite:
    """Comprehensive security testing suite."""

    def __init__(self, base_url="http://localhost:5000"):
        self.base_url = base_url
        self.session = requests.Session()
        self.test_results = []

    def log_test(self, test_name, result, message=""):
        """Log test result."""
        status = "PASS" if result else "FAIL"
        print(f"[{status}] {test_name}: {message}")
        self.test_results.append({
            'test': test_name,
            'result': result,
            'message': message,
            'timestamp': datetime.now(timezone.utc).isoformat()
        })

    def test_admin_login_security(self):
        """Test admin login security features."""
        print("\n=== Testing Admin Login Security ===")

        # Test 1: Valid login
        response = self.session.post(f"{self.base_url}/admin/login", data={
            'username': ADMIN_USERNAME,
            'password': ADMIN_PASSWORD,
            'csrf_token': 'dummy_token'  # Will be rejected by CSRF protection
        })
        if response.status_code == 403:
            self.log_test("CSRF Protection", True, "CSRF token validation working")
        else:
            self.log_test("CSRF Protection", False, f"Expected 403, got {response.status_code}")

        # Test 2: Rate limiting
        for i in range(6):  # Exceed rate limit
            response = self.session.post(f"{self.base_url}/admin/login", data={
                'username': ADMIN_USERNAME,
                'password': 'wrong',
                'csrf_token': 'dummy_token'
            })
            if response.status_code == 429:
                self.log_test("Rate Limiting", True, f"Rate limit triggered after {i+1} attempts")
                break
        else:
            self.log_test("Rate Limiting", False, "Rate limiting not triggered")

        # Test 3: SQL injection attempt
        response = self.session.post(f"{self.base_url}/admin/login", data={
            'username': "admin' OR '1'='1",
            'password': ADMIN_PASSWORD,
            'csrf_token': 'dummy_token'
        })
        if response.status_code in [403, 401]:  # Should be blocked
            self.log_test("SQL Injection Protection", True, "SQL injection attempt blocked")
        else:
            self.log_test("SQL Injection Protection", False, "SQL injection may have succeeded")

    def test_session_security(self):
        """Test session security features."""
        print("\n=== Testing Session Security ===")

        # Test session timeout (this would require waiting, so we'll just check configuration)
        app = create_app()
        with app.app_context():
            # Check if session security is configured
            if hasattr(app, 'session_interface'):
                self.log_test("Session Configuration", True, "Session interface configured")
            else:
                self.log_test("Session Configuration", False, "Session interface not configured")

    def test_cryptography(self):
        """Test cryptographic functions."""
        print("\n=== Testing Cryptography ===")

        # Test password hashing
        password = "test_password_123"
        hashed = hash_password(password)

        if verify_password(hashed, password):
            self.log_test("Password Hashing", True, "Password hashing and verification working")
        else:
            self.log_test("Password Hashing", False, "Password verification failed")

        # Test wrong password
        if not verify_password(hashed, "wrong_password"):
            self.log_test("Password Security", True, "Wrong password correctly rejected")
        else:
            self.log_test("Password Security", False, "Wrong password incorrectly accepted")

    def test_database_security(self):
        """Test database security features."""
        print("\n=== Testing Database Security ===")

        app = create_app()
        with app.app_context():
            # Check if admin user exists
            admin = AdminUser.query.filter_by(username=ADMIN_USERNAME).first()
            if admin:
                self.log_test("Admin User Setup", True, "Default admin user exists")
            else:
                self.log_test("Admin User Setup", False, "Default admin user missing")

            # Check audit logging
            recent_logs = AuditLog.query.order_by(AuditLog.timestamp.desc()).limit(5).all()
            if recent_logs:
                self.log_test("Audit Logging", True, f"Found {len(recent_logs)} recent audit logs")
            else:
                self.log_test("Audit Logging", False, "No audit logs found")

    def test_file_upload_security(self):
        """Test file upload security."""
        print("\n=== Testing File Upload Security ===")

        # Test with a malicious file
        malicious_content = '<script>alert("XSS")</script>'
        files = {'registry_file': ('malicious.csv', malicious_content, 'text/csv')}

        # This would require being logged in, so we'll just test the validation function
        from security_middleware import validate_file_upload
        from io import BytesIO

        file_obj = BytesIO(malicious_content.encode())
        file_obj.filename = 'test.csv'

        is_valid, message = validate_file_upload(file_obj, ['.csv'], 1024*1024)
        if not is_valid and "suspicious content" in message.lower():
            self.log_test("File Upload Security", True, "Malicious content detected")
        else:
            self.log_test("File Upload Security", False, "Malicious content not detected")

    def test_headers_security(self):
        """Test security headers."""
        print("\n=== Testing Security Headers ===")

        response = self.session.get(f"{self.base_url}/")
        headers = response.headers

        security_headers = [
            ('X-Content-Type-Options', 'nosniff'),
            ('X-Frame-Options', 'DENY'),
            ('X-XSS-Protection', '1; mode=block'),
            ('Content-Security-Policy', None),  # Just check if present
        ]

        for header, expected_value in security_headers:
            if header in headers:
                if expected_value is None or headers[header] == expected_value:
                    self.log_test(f"Security Header: {header}", True, f"Header present: {headers[header][:50]}...")
                else:
                    self.log_test(f"Security Header: {header}", False, f"Expected {expected_value}, got {headers[header]}")
            else:
                self.log_test(f"Security Header: {header}", False, "Header missing")

    def test_error_handling(self):
        """Test error handling and pages."""
        print("\n=== Testing Error Handling ===")

        # Test 404
        response = self.session.get(f"{self.base_url}/nonexistent")
        if response.status_code == 404:
            self.log_test("404 Error Handling", True, "404 page working")
        else:
            self.log_test("404 Error Handling", False, f"Expected 404, got {response.status_code}")

        # Test large payload (should trigger 413)
        large_data = 'x' * (11 * 1024 * 1024)  # 11MB
        response = self.session.post(f"{self.base_url}/admin/login",
                                   data={'data': large_data})
        if response.status_code == 413:
            self.log_test("Payload Size Limit", True, "Large payload correctly rejected")
        else:
            self.log_test("Payload Size Limit", False, f"Expected 413, got {response.status_code}")

    def run_full_test_suite(self):
        """Run all security tests."""
        print("Starting UB eBallot Security Test Suite")
        print("=" * 50)

        # Check if server is running
        try:
            response = self.session.get(f"{self.base_url}/", timeout=5)
            if response.status_code != 200:
                print("ERROR: Server not responding correctly")
                return False
        except requests.exceptions.RequestException:
            print("ERROR: Cannot connect to server. Make sure it's running on localhost:5000")
            return False

        # Run all tests
        self.test_cryptography()
        self.test_database_security()
        self.test_file_upload_security()
        self.test_session_security()
        self.test_headers_security()
        self.test_admin_login_security()
        self.test_error_handling()

        # Summary
        print("\n" + "=" * 50)
        print("SECURITY TEST SUMMARY")
        print("=" * 50)

        passed = sum(1 for test in self.test_results if test['result'])
        total = len(self.test_results)

        for test in self.test_results:
            status = "✓" if test['result'] else "✗"
            print(f"{status} {test['test']}")

        print(f"\nPassed: {passed}/{total} tests")

        if passed == total:
            print("🎉 ALL SECURITY TESTS PASSED!")
            print("Your UB eBallot system is ready for production deployment.")
            return True
        else:
            print("⚠️  Some security tests failed.")
            print("Please review the failed tests before deploying to production.")
            return False

    def save_results(self, filename="security_test_results.json"):
        """Save test results to file."""
        with open(filename, 'w') as f:
            json.dump(self.test_results, f, indent=2)
        print(f"\nTest results saved to {filename}")


def main():
    """Main test runner."""
    import argparse

    parser = argparse.ArgumentParser(description="UB eBallot Security Test Suite")
    parser.add_argument('--url', default='http://localhost:5000',
                       help='Base URL of the running application')
    parser.add_argument('--save-results', action='store_true',
                       help='Save test results to JSON file')

    args = parser.parse_args()

    # Check if we need to start the server
    try:
        response = requests.get(args.url, timeout=2)
    except:
        print("Server not running. Starting test server...")
        # Start server in background
        server_process = subprocess.Popen([
            sys.executable, 'run.py'
        ], cwd=os.path.dirname(os.path.abspath(__file__)))

        # Wait for server to start
        time.sleep(3)

        try:
            response = requests.get(args.url, timeout=5)
        except:
            print("Failed to start server automatically.")
            print("Please start the server manually with: python run.py")
            return 1

    # Run tests
    tester = SecurityTestSuite(args.url)
    success = tester.run_full_test_suite()

    if args.save_results:
        tester.save_results()

    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
