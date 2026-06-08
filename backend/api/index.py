"""
Vercel serverless entrypoint.

Vercel's Python runtime detects the ASGI `app` object and routes all HTTP
traffic to it (see backend/vercel.json).
"""

from main import app  # noqa: F401
