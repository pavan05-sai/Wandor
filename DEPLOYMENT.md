# Wandor — Deployment Guide

This guide details the step-by-step process for deploying **Wandor**:
- **Backend**: [Render](https://render.com) (Python / FastAPI / Uvicorn)
- **Frontend**: [Vercel](https://vercel.com) (React / Vite / TypeScript)
- **Database**: [MongoDB Atlas](https://www.mongodb.com/cloud/atlas) (Managed Cloud MongoDB)

---

## Architecture Overview

```
                      ┌─────────────────────────────────┐
                      │             Vercel              │
                      │  (Frontend: React 19 + Vite)    │
                      └────────────────┬────────────────┘
                                       │ HTTPS / REST
                                       ▼
                      ┌─────────────────────────────────┐
                      │             Render              │
                      │ (Backend: FastAPI + Uvicorn)    │
                      └────────┬───────────────┬────────┘
                               │               │
                               ▼               ▼
                      ┌────────────────┐ ┌───────────────┐
                      │  MongoDB Atlas │ │ Google Gemini │
                      │   (Cluster0)   │ │  (2.0 Flash)  │
                      └────────────────┘ └───────────────┘
```

---

## Phase 1: Set Up MongoDB Atlas (Database)

1. Create a free account at [mongodb.com/cloud/atlas](https://www.mongodb.com/cloud/atlas).
2. Create a new **M0 Free Cluster** (choose the region closest to your users, e.g., `AWS / Mumbai` or `AWS / Singapore`).
3. In **Security > Database Access**:
   - Create a database user (e.g. `wandor_user`) with password authentication and `readWriteAnyDatabase` privileges.
4. In **Security > Network Access**:
   - Add an IP access entry: `0.0.0.0/0` (Allow access from anywhere, required for dynamic serverless IPs like Render).
5. In **Database > Clusters > Connect**:
   - Choose **Connect your application (Drivers)**.
   - Driver: `Python`, Version `3.11 or later`.
   - Copy the connection URI:
     ```
     mongodb+srv://wandor_user:<password>@cluster0.xxxx.mongodb.net/?retryWrites=true&w=majority
     ```
   - Replace `<password>` with the password you created.

---

## Phase 2: Deploy Backend to Render

### Option A: Using Render Blueprint (Automatic via `render.yaml`)
1. Sign up or log in at [render.com](https://render.com).
2. Click **New +** > **Blueprint**.
3. Connect your GitHub repository: `AI-Dynamic_Travel_Planning_Agent-` (or your repository fork).
4. Render will automatically detect `render.yaml`.
5. Under Environment Variables, fill in:
   - `MONGODB_URI`: Your MongoDB Atlas connection string from Phase 1.
   - `GEMINI_API_KEY`: Your Google Gemini API key from [Google AI Studio](https://aistudio.google.com).
6. Click **Apply**. Render will build and deploy the backend.

### Option B: Manual Web Service Setup
1. On Render, click **New +** > **Web Service**.
2. Connect your GitHub repository.
3. Configure settings:
   - **Name**: `wandor-backend`
   - **Root Directory**: `backend`
   - **Environment**: `Python 3`
   - **Region**: Choose the region closest to your MongoDB Atlas cluster (e.g., `Singapore` or `Oregon`).
   - **Branch**: `main`
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
   - **Plan**: `Free`
4. In **Environment Variables**, add:
   | Key | Value | Description |
   | :--- | :--- | :--- |
   | `PYTHON_VERSION` | `3.11.9` | Recommended Python version |
   | `ENVIRONMENT` | `production` | Production environment mode |
   | `DEMO_MODE` | `off` | Live database and live AI mode |
   | `MONGODB_URI` | `mongodb+srv://...` | Connection URI from Phase 1 |
   | `MONGODB_DB_NAME` | `wandor` | Database name |
   | `GEMINI_API_KEY` | `AIzaSy...` | Google Gemini API key |
   | `LLM_PROVIDER` | `gemini` | Primary LLM provider |
   | `LLM_MODEL` | `gemini-2.0-flash` | Latest high-accuracy model |
   | `JWT_SECRET` | *32+ random chars* | E.g. generate via `openssl rand -hex 32` |
   | `SECRET_KEY` | *32+ random chars* | E.g. generate via `openssl rand -hex 32` |
   | `CORS_ORIGINS` | `*` | Or specify your Vercel URL once known |
5. In **Health Check Path**: enter `/health`.
6. Click **Create Web Service**.
7. Once deployed, copy your Render service URL (e.g., `https://wandor-backend.onrender.com`).
   - Verify health: Visit `https://wandor-backend.onrender.com/health` in your browser.

---

## Phase 3: Deploy Frontend to Vercel

1. Sign up or log in at [vercel.com](https://vercel.com).
2. Click **Add New...** > **Project**.
3. Import your GitHub repository: `AI-Dynamic_Travel_Planning_Agent-`.
4. In the **Configure Project** screen:
   - **Project Name**: `wandor` (or your choice)
   - **Framework Preset**: `Vite`
   - **Root Directory**: Click **Edit** and select `frontend`.
   - **Build and Output Settings**:
     - Build Command: `npm run build`
     - Output Directory: `dist`
     - Install Command: `npm install`
5. In **Environment Variables**, add:
   | Key | Value |
   | :--- | :--- |
   | `VITE_API_URL` | `https://wandor-backend.onrender.com` (Your Render URL from Phase 2, without trailing slash) |
6. Click **Deploy**.
7. Vercel will build the frontend and provide your live URL (e.g., `https://wandor.vercel.app`).

---

## Phase 4: Final Verification & Seed Data

1. Open your Vercel frontend URL in a browser.
2. Register a new user account or log in with demo credentials.
3. Create a trip (e.g. 4 days in Goa or Jaipur).
4. Click **Generate Itinerary** — the backend will populate catalog POIs and call Gemini 2.0 Flash to synthesize a personalized schedule.
5. Test the **AI Concierge Drawer** (ask questions and test modification prompts such as *"Make Day 2 cheaper"*).
6. Test sharing and public read-only views via the **Share** button.
