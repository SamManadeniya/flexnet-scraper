import unittest
import json
from datetime import datetime, timezone, timedelta
from fastapi.testclient import TestClient
from api import app
from auth import (
    hash_password,
    verify_password,
    create_access_token,
    decode_access_token,
)
from scraper.engine import is_vehicle_model_match
from netlify.functions.api import handler as netlify_handler

class TestFlexnetSystem(unittest.TestCase):

    def setUp(self):
        self.client = TestClient(app)

    # -------------------------------------------------------------
    # 1. Cryptographic Security Tests
    # -------------------------------------------------------------
    def test_password_hashing_and_verification(self):
        password = "SecurePassword2025!"
        hashed = hash_password(password)
        self.assertNotEqual(password, hashed)
        self.assertTrue(hashed.startswith(("$2b$", "$pbkdf2-sha256$")))
        self.assertTrue(verify_password(password, hashed))
        self.assertFalse(verify_password("WrongPassword!", hashed))

    def test_password_length_constraints(self):
        with self.assertRaises(ValueError):
            hash_password("12345")  # Too short (< 6)
        with self.assertRaises(ValueError):
            hash_password("")  # Empty
        with self.assertRaises(ValueError):
            hash_password("a" * 129)  # Too long (> 128)

    def test_jwt_token_creation_and_validation(self):
        payload = {"sub": "qa_tester", "uid": "123-uuid", "role": "admin"}
        token = create_access_token(payload, expires_delta=timedelta(hours=1))
        self.assertIsInstance(token, str)

        decoded = decode_access_token(token)
        self.assertIsNotNone(decoded)
        self.assertEqual(decoded["sub"], "qa_tester")
        self.assertEqual(decoded["uid"], "123-uuid")
        self.assertEqual(decoded["role"], "admin")

    def test_jwt_tampering_rejected(self):
        payload = {"sub": "qa_tester", "uid": "123-uuid", "role": "admin"}
        token = create_access_token(payload)
        tampered_token = token[:-4] + "fake"
        self.assertIsNone(decode_access_token(tampered_token))

    # -------------------------------------------------------------
    # 2. Authentication API Endpoints
    # -------------------------------------------------------------
    def test_auth_login_success(self):
        res = self.client.post("/api/auth/login", json={"username": "admin", "password": "admin123"})
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertTrue(data["success"])
        self.assertIn("token", data)
        self.assertEqual(data["user"]["username"], "admin")

    def test_auth_login_invalid_credentials(self):
        res = self.client.post("/api/auth/login", json={"username": "admin", "password": "wrongpassword"})
        self.assertEqual(res.status_code, 401)

    def test_auth_me_requires_token(self):
        res = self.client.get("/api/auth/me")
        self.assertEqual(res.status_code, 401)

    def test_auth_me_with_valid_token(self):
        login_res = self.client.post("/api/auth/login", json={"username": "admin", "password": "admin123"})
        token = login_res.json()["token"]

        me_res = self.client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
        self.assertEqual(me_res.status_code, 200)
        data = me_res.json()
        self.assertTrue(data["authenticated"])
        self.assertEqual(data["user"]["username"], "admin")

    # -------------------------------------------------------------
    # 3. Dynamic Model Guard & Accuracy Tests
    # -------------------------------------------------------------
    def test_model_guard_blocks_hilux_in_prado_search(self):
        # Hilux returned due to footer recommendation text
        is_match = is_vehicle_model_match(
            search_query="Prado",
            translated_kw="プラド",
            car_model="ハイラックス",
            car_title="トヨタ ハイラックス 2.4 Z GR Sport 4WD"
        )
        self.assertFalse(is_match)

    def test_model_guard_accepts_genuine_prado(self):
        is_match = is_vehicle_model_match(
            search_query="Prado",
            translated_kw="ランドクルーザープラド",
            car_model="ランドクルーザープラド",
            car_title="トヨタ ランドクルーザープラド 3.4 TX 4WD"
        )
        self.assertTrue(is_match)

    def test_model_guard_accepts_renoca_wonder(self):
        is_match = is_vehicle_model_match(
            search_query="Wonder",
            translated_kw="Wonder",
            car_model="ランドクルーザー80",
            car_title="トヨタ ランドクルーザー80 4.5 VX 4WD",
            car_tagline="【Renoca WONDER】【NEW：アーミーグリーン】"
        )
        self.assertTrue(is_match)

    # -------------------------------------------------------------
    # 4. Netlify Serverless Function Handler Test
    # -------------------------------------------------------------
    def test_netlify_serverless_handler(self):
        event = {
            "resource": "/api/stats",
            "path": "/api/stats",
            "httpMethod": "GET",
            "headers": {"host": "localhost"},
            "multiValueHeaders": {"host": ["localhost"]},
            "queryStringParameters": None,
            "multiValueQueryStringParameters": None,
            "pathParameters": None,
            "stageVariables": None,
            "requestContext": {
                "resourcePath": "/api/stats",
                "httpMethod": "GET",
                "path": "/api/stats",
                "identity": {"sourceIp": "127.0.0.1"},
            },
            "body": None,
            "isBase64Encoded": False
        }
        context = type("Context", (), {"aws_request_id": "test-req-1"})()
        response = netlify_handler(event, context)
        self.assertEqual(response["statusCode"], 200)
        body = json.loads(response["body"])
        self.assertTrue(body.get("connected", False))

if __name__ == "__main__":
    unittest.main()
