"""
Vercel entry point for SAFI RCA.

This file makes the app compatible with Vercel's Python runtime.
It imports the Streamlit app and serves it via Flask.
"""

import sys
import os
import subprocess

# Add the app directory to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# VerceL expects either:
# 1. A `handler` function
# 2. An `app` Flask object
# 3. An `application` WSGI object

# Since we can't easily make Streamlit a WSGI app,
# we'll create a simple Flask wrapper that redirects to the Streamlit app

try:
    import flask
    from flask import Flask, send_file, jsonify
    
    app = Flask(__name__)
    
    @app.route("/")
    def index():
        """Redirect to Streamlit app or show info."""
        return """
        <h1>SAFI Root Cause Analyzer</h1>
        <p>This app requires Streamlit to be running separately.</p>
        <p>Please use <code>streamlit run app.py</code> or deploy via Docker.</p>
        <p>Environment variables needed:</p>
        <ul>
            <li>RCA_API_KEY</li>
            <li>RCA_API_BASE_URL</li>
            <li>RCA_MODEL_NAME</li>
        </ul>
        """
    
    @app.route("/health")
    def health():
        return {"status": "ok", "service": "safi-rca-vercel"}
    
    # The Vercel Python runtime needs to export `app`
    print("Vercel Flask wrapper loaded successfully")
    
except ImportError:
    # Fallback if Flask not installed
    def handler(event, context):
        """Vercel's expected handler function."""
        return {
            "statusCode": 200,
            "body": json.dumps({
                "message": "SAFI RCA - Deploy with Docker or Streamlit Sharing",
                "instructions": "Use Docker: `docker build -t safi-rca . && docker run -d -p 8501:8501 -e RCA_API_KEY=... safi-rca`",
                "streamlit": "Or deploy via share.streamlit.io"
            })
        }
