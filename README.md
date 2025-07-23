# AI Vision System

A real-time AI vision processing system with camera management, object detection, and monitoring capabilities.

## Features

- **Real-time Analysis** - Process video streams with AI models (object detection, segmentation, pose estimation)
- **Camera Management** - Monitor and control multiple camera streams
- **Modern UI** - React + Vite frontend with Material-UI
- **Fast API Backend** - RESTful endpoints and real-time processing
- **PostgreSQL Database** - Reliable data storage
- **Docker Support** - Easy deployment with docker-compose

## Prerequisites

- **Node.js** (v14+ recommended)
- **Python** (v3.10+ recommended)
- **Docker** (optional - includes PostgreSQL, or install PostgreSQL separately)

## Quick Start

### 1. Initial Setup

```bash
# Copy environment variables
cp .env.example .env

# Create and activate Python virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install Python dependencies
pip install -r requirements.txt
```
Edit `.env` and update passwords and settings as needed.

### 2. Start Database (New Terminal)

**Option A: Using Docker (Recommended)**
```bash
docker-compose up
```
*Add `-d` flag to run in background: `docker-compose up -d`*

**Option B: Local PostgreSQL**
- Install PostgreSQL and ensure it's running on port 5433

*The backend will automatically create the database on first run*

### 3. Start Backend (New Terminal)

```bash
source venv/bin/activate  # On Windows: venv\Scripts\activate
uvicorn backend.main:app --reload
```

### 4. Start Frontend (New Terminal)

```bash
cd frontend
npm install
npm run dev
```

### 5. Access Application

- **Frontend**: http://localhost:5173
- **Backend API**: http://localhost:8000
- **API Docs**: http://localhost:8000/docs

## Project Structure

```
.
├── backend/          # FastAPI backend
├── frontend/         # React + Vite frontend  
├── prometheus/       # Monitoring configuration
├── docker-compose.yml
├── requirements.txt  # Python dependencies
├── .env.example     # Environment variables template
└── README.md
```

## Troubleshooting

- **Database Connection**: Check your `.env` file credentials match your PostgreSQL setup
- **Port Conflicts**: Update ports in `.env` or `docker-compose.yml` if needed
- **Dependencies**: Ensure Python 3.10+ and Node.js 14+ are installed

## License

MIT License - see [LICENSE](LICENSE) file for details.