# 🚀 Deployment Guide: AI Answer Sheet Auto-Grader

This application is built with Streamlit and Python. You can deploy it to the web using several free and cloud-hosted platforms.

---

## 🌟 Option 1: Streamlit Community Cloud (Recommended — 100% Free)

Streamlit Community Cloud is the easiest, fastest, and completely free way to host Streamlit web applications with a public `https://...streamlit.app` link.

### Step 1: Push your code to GitHub
1. Open terminal and navigate to your project directory:
   ```bash
   cd /Users/bhavinhya.rao/.gemini/antigravity/scratch/answer-sheet-grader
   ```
2. Initialize git and commit your files:
   ```bash
   git init
   git add .
   git commit -m "Initial commit of AI Answer Sheet Grader"
   ```
3. Create a new repository on [GitHub](https://github.com/new) (e.g. `answer-sheet-grader`).
4. Link and push to GitHub:
   ```bash
   git branch -M main
   git remote add origin https://github.com/<YOUR_GITHUB_USERNAME>/answer-sheet-grader.git
   git push -u origin main
   ```

### Step 2: Deploy on Streamlit Cloud
1. Go to **[share.streamlit.io](https://share.streamlit.io/)** and sign in with your GitHub account.
2. Click **"New app"**.
3. Choose your repository: `<YOUR_GITHUB_USERNAME>/answer-sheet-grader`.
4. Branch: `main`.
5. Main file path: `app.py`.
6. Click **"Deploy!"**.

### Step 3: Configure Cloud Secrets (Optional — For Pre-Configured Keys)
If you want the deployed app to have API keys pre-filled so teachers/evaluators don't need to type them:
1. In your app dashboard on Streamlit Cloud, click the three dots (`...`) in the corner and select **Settings > Secrets**.
2. Paste your keys:
   ```toml
   # Anthropic Claude API Key (sk-ant-...)
   ANTHROPIC_API_KEY = "sk-ant-api03-..."

   # Google Gemini API Key (AIzaSy...)
   GEMINI_API_KEY = "AIzaSy..."

   # Optional: Default Ollama Remote Endpoint (if you host Ollama on a GPU server)
   # OLLAMA_ENDPOINT = "https://your-ollama-gpu-instance.com"
   ```
3. Click **Save**. The app will automatically read these secrets!

> **Note on Security:** Your local `.env` and `.streamlit/secrets.toml` files are excluded by `.gitignore`, so your personal keys will NEVER be pushed publicly to GitHub. Each user on Streamlit Cloud can also enter their own key via the app sidebar.

---

## ⚡ Option 2: Render.com (Free Web Service)

Render provides free hosting for web services directly from GitHub.

1. Sign up on **[render.com](https://render.com/)**.
2. Click **"New +"** > **"Web Service"**.
3. Connect your GitHub repository.
4. Set the following settings:
   - **Environment**: `Python 3`
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `streamlit run app.py --server.port=$PORT --server.address=0.0.0.0`
5. Under **Environment Variables**, add:
   - `GEMINI_API_KEY`: `<Your Gemini API Key>`
6. Click **"Create Web Service"**.

---

## 🤗 Option 3: Hugging Face Spaces (Free)

1. Go to **[huggingface.co/spaces](https://huggingface.co/spaces)** and click **"Create new Space"**.
2. Space name: `answer-sheet-grader`.
3. Space SDK: **Streamlit**.
4. Push your repository files to the Hugging Face Git remote.
5. In **Settings > Variables and secrets**, add `GEMINI_API_KEY`.

---

## 🐳 Option 4: Docker / Self-Hosted VPS / Cloud Run

The project includes a ready-to-use production `Dockerfile`.

### Build and Run locally or on VPS:
```bash
# Build the Docker image
docker build -t answer-sheet-grader .

# Run the container (accessible at http://localhost:8501)
docker run -d -p 8501:8501 -e GEMINI_API_KEY="your-api-key" answer-sheet-grader
```

### Deploy to Google Cloud Run:
```bash
gcloud run deploy answer-sheet-grader \
  --source . \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated \
  --port 8501 \
  --set-env-vars GEMINI_API_KEY="your-api-key"
```
