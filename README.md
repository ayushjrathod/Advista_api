# Advista Python API

Backend API for Advista - Automated Research and Trigger Finder

## Getting Started

This project uses [uv](https://docs.astral.sh/uv/) as the package manager for fast and reliable dependency management.

### Prerequisites

- Python 3.12+
- [uv](https://docs.astral.sh/uv/getting-started/installation/)

### Installation

1. Clone the repository
2. Install dependencies:
   ```bash
   uv sync
   ```

### Development

- **Run the application:**

  ```bash
  uv run uvicorn main:app --host 0.0.0.0 --port 8000 --reload
  ```

- **Install development dependencies:**

  ```bash
  uv sync --dev
  ```

- **Add a new dependency:**

  ```bash
  uv add package_name
  ```

- **Add a development dependency:**

  ```bash
  uv add --dev package_name
  ```

- **Remove a dependency:**

  ```bash
  uv remove package_name
  ```

- **Update dependencies:**
  ```bash
  uv lock --upgrade
  ```

### Docker

The project includes a Dockerfile optimized for uv:

```bash
# Build the image
docker build -t advista-api .

# Run the container
docker run -p 8000:8000 --env-file .env advista-api
```

### Environment Variables

Create a `.env` file with the following variables:

```
GROQ_API_KEY=your_groq_api_key
GROQ_API_KEY2=your_second_groq_api_key
ASTRA_DB_TOKEN=your_astra_db_token
ASTRA_DB_ENDPOINT=your_astra_db_endpoint
HF_TOKEN=your_huggingface_token
YOUTUBE_API_KEY=your_youtube_api_key
```

### API Endpoints

- `GET /` - Welcome page
- `POST /chat/start` - Start a new chat session
- `POST /chat/message` - Send messages and continue conversation
- `GET /results/{session_id}` - Get search results
- `GET /analyses/{session_id}` - Get analyses
- `GET /reddit-analysis-stream/{session_id}` - Stream Reddit analysis

### Project Structure

- `main.py` - FastAPI application entry point
- `db.py` - Database operations with AstraDB
- `scripts.py` - YouTube search and chat functionality
- `video_processor.py` - Video processing and transcription
- `reddit_insights_server.py` - Reddit data processing
- `transcribe.py` - Audio transcription using Groq
- `pyproject.toml` - Project configuration and dependencies
- `uv.lock` - Locked dependency versions
