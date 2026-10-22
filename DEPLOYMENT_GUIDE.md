# SAFI RCA - Deployment Guide

## Streamlit Sharing Deployment ✅

The error "Error installing requirements" is likely caused by incompatible packages in requirements.txt (especially `aider-chat` and `openhands-ai` which have many transitive dependencies).

### Solution: Use Clean Requirements

I've updated `requirements.txt` to only include essential packages:

```text
streamlit>=1.28.0
gitpython>=3.1.0
pytest>=7.4.0  # optional, for testing
```

### How to Deploy on Streamlit Sharing

1. **Push your code to GitHub**:
   ```bash
   git add .
   git commit -m "Prepare for Streamlit Sharing"
   git push origin main
   ```

2. **Go to [share.streamlit.io](https://share.streamlit.io/)**
   - Click "New app"
   - Select your repository: `safi-rca-tool`
   - Set the main file path: `/app.py`

2. **Configure Environment Variables** (in the Streamlit Sharing dashboard):
   - **RCA_API_KEY**: Your OpenAI API key (e.g., `sk-proj-...`)
   - **RCA_API_BASE_URL**: `https://api.openai.com/v1`
   - **RCA_MODEL_NAME**: `gpt-4o-mini` (or `gpt-4o`, `gpt-4-turbo`, `gpt-3.5-turbo`)

3. **Click "Deploy"**

Your app will be available at: `https://your-username-safi-rca-tool.streamlit.app`

### What Works on Streamlit Sharing

✅ **Sidebar configuration**: Repo path, SHA, SOW upload, evidence upload  
✅ **Run analysis**: Full RCA pipeline executes  
✅ **Report rendering**: Structured Markdown report with confidence badge, affected component, root cause, evidence, uncertainty, next action  
✅ **Download JSON report**: Available after analysis  
✅ **Follow-up questions**: Chat grounded in the RCA result  

❌ **Not supported on Streamlit Sharing**:
- Git remote URL cloning (uses local path only)
- Git SSH operations
- File protocol URLs

### Why the Original Requirements.txt Failed

The original `requirements.txt` included:
- `aider-chat` - Very large package with many transitive dependencies, often causes installation failures
- `openhands-ai` - Not a standard PyPI package
- `openhands` - Similarly problematic

Streamlit Sharing has had issues with these packages. The clean `requirements.txt` I created only includes `streamlit` and `gitpython`, which are well-supported.

### Alternative: Docker Deployment

If you need Docker deployment, use the Dockerfile I created earlier. Docker gives you full control over the environment and avoids the package installation issues of Streamlit Sharing.

```bash
docker build -t safi-rca .
docker run -d -p 8501:8501 -e RCA_API_KEY="sk-..." safi-rca
```

### Summary

**Recommended approach**: Streamlit Sharing with the clean `requirements.txt` I created.

**Deploy now**: Go to [share.streamlit.io](https://share.streamlit.io/), select your repo, and set the environment variables RCA_API_KEY, RCA_API_BASE_URL, and RCA_MODEL_NAME.
