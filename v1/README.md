# App Service - Financial Markets API

A comprehensive FastAPI-based service for financial market analysis, news aggregation, and AI-powered research tools.

## Prerequisites

- Python 3.8 or higher
- Node.js and PM2 (for process management)
- PostgreSQL database
- Virtual environment support

## Installation

### 1. Clone the Repository

```bash
git clone <repository-url>
cd app_service
```

### 2. Create Virtual Environment

```bash
python3 -m venv .venv
```

### 3. Activate Virtual Environment

**On Linux/Mac:**
```bash
source .venv/bin/activate
```

**On Windows:**
```bash
.venv\Scripts\activate
```

### 4. Install Dependencies

```bash
pip install -r requirements.txt
```

**Note:** Some dependencies may require additional system libraries. If you encounter issues, you may need to install:
- `build-essential` (Linux)
- `python3-dev` (Linux)
- Other system dependencies as needed

### 5. Environment Variables Setup

Create a `.env` file in the project root directory with the following required variables:

```env
# Database Configuration
DATABASE_URL=postgresql://user:password@host:port/database
PG_IP_ADDRESS=your_postgres_ip

# OpenAI Configuration
OPENAI_API_KEY=your_openai_api_key
OPENAI_API_TYPE=openai  # or "azure" for Azure OpenAI
OPENAI_CHAT_MODEL=gpt-4o

# Azure OpenAI (if OPENAI_API_TYPE=azure)
AZURE_OPENAI_ENDPOINT=your_azure_endpoint
AZURE_OPENAI_API_KEY=your_azure_key
OPENAI_API_VERSION=2024-02-15-preview
AZURE_OPENAI_DEPLOYMENT_NAME=your_deployment_name
AZURE_OPENAI_EMBEDDING_DEPLOYMENT_NAME=your_embedding_deployment

# Vector Database
PINECONE_API_KEY=your_pinecone_api_key
PINECONE_INDEX_NAME=market-data-index

# Search APIs
BRAVE_API_KEY=your_brave_api_key
SERPER_API_KEY=your_serper_api_key

# Reddit API (for Reddit RAG)
REDDIT_CLIENT_ID=your_reddit_client_id
REDDIT_CLIENT_SECRET=your_reddit_client_secret
REDDIT_USER_AGENT=your_user_agent

# YouTube API
youtube_api_key=your_youtube_api_key
rapid_key=your_rapidapi_key

# Other Services
GROQ_API_KEY=your_groq_api_key
HUGGINGFACEHUB_API_TOKEN=your_huggingface_token
CMOTS_BEARER_TOKEN=your_cmots_token
node_key=your_node_key

# AWS S3 (for document storage)
access_key=your_aws_access_key
sect_access_key=your_aws_secret_key
content_bucket=your_s3_bucket_name

# ChromaDB
CHROMA_HOST=localhost

# API Security
AI_KEY=your_ai_key
```

### 6. PM2 Configuration

The project uses PM2 for process management. The configuration is defined in `ecosystem.config.js`.

**Install PM2 globally (if not already installed):**
```bash
npm install -g pm2
```

**Update ecosystem.config.js paths:**
Before running PM2, update the paths in `ecosystem.config.js` to match your system:
- Update the virtual environment path (`.venv/bin/uvicorn` and `.venv/bin/python`)
- Update the working directory path (`cwd`)

**Start services with PM2:**
```bash
pm2 start ecosystem.config.js
```

This will start two processes:
1. **app_service** - The main FastAPI application on port 8000
2. **chroma_db** - ChromaDB server on port 9001

**Useful PM2 commands:**
```bash
# Restart all services
pm2 restart all

# Stop all services
pm2 stop all

# View logs
pm2 logs

# View status
pm2 status

# Delete all processes
pm2 delete all
```

### 7. Verify Installation

Once the services are running, you can verify the installation by:

1. **Check if the API is running:**
   ```bash
   curl http://localhost:8000/
   ```

2. **Access API documentation:**
   - Swagger UI: http://localhost:8000/docs
   - ReDoc: http://localhost:8000/redoc

3. **Check ChromaDB:**
   ```bash
   curl http://localhost:9001/api/v1/heartbeat
   ```

## Running Without PM2

If you prefer to run the application directly without PM2:

```bash
# Activate virtual environment
source .venv/bin/activate

# Start ChromaDB (in a separate terminal)
chroma run --path ./chromadb --port 9001

# Start FastAPI application (in another terminal)
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

## API Authentication

Most endpoints require an API key. Include it in the request header:

```
X-API-Key: your_api_key_here
```

The API key is configured in `config.py` via the `VALID_API_KEY` variable.

## Project Structure

```
app_service/
├── api/                    # API endpoint modules
│   ├── chatbot.py          # Main chatbot endpoint
│   ├── tracker.py          # Contract tracking
│   ├── dashboard/          # Dashboard endpoints
│   ├── market_content/     # Market content endpoints
│   ├── doc_rag/            # Document RAG endpoints
│   ├── deep_research/      # Deep research pipeline
│   └── ...
├── streaming/              # Streaming RAG endpoints
├── main.py                 # FastAPI application entry point
├── config.py               # Configuration and environment setup
├── requirements.txt        # Python dependencies
├── ecosystem.config.js     # PM2 configuration
└── .env                    # Environment variables (create this)
```

## Troubleshooting

### Database Connection Issues
- Ensure PostgreSQL is running and accessible
- Verify `DATABASE_URL` is correctly formatted
- Check database credentials and network connectivity

### ChromaDB Issues
- Ensure ChromaDB service is running on port 9001
- Check if the `chromadb` directory has proper permissions
- Verify ChromaDB is installed: `pip show chromadb`

### PM2 Issues
- Ensure paths in `ecosystem.config.js` are correct
- Check PM2 logs: `pm2 logs app_service`
- Verify Python interpreter path is correct

### Missing Dependencies
- Reinstall dependencies: `pip install -r requirements.txt --upgrade`
- Some packages may require system libraries (e.g., `lxml` requires `libxml2-dev`)

## Additional Notes

- The application uses scheduled tasks for data aggregation (configured in `main.py`)
- Vector stores are initialized on startup
- API documentation is available at `/docs` endpoint
- CORS is enabled for all origins (configure in `main.py` if needed)

