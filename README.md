# JSSP Backend - Job Shop Scheduling Problem Solver

A FastAPI-based backend service for solving Job Shop Scheduling Problems (JSSP) using MiniZinc constraint programming.

## Features

- ✅ **Two Problem Types**:
  - Weighted Tardiness Minimization (`tardanza_ponderada`)
  - Makespan Minimization with Maintenance Windows (`jssp_maint`)

- ✅ **Multiple Solvers**: Support for Chuffed, Gecode, and OR-Tools

- ✅ **Configurable Search Strategies**: 7 search heuristics and 6 value choice strategies

- ✅ **Flexible Input**: Accept JSON or multipart/form-data with file uploads

- ✅ **Instance Management**: Load pre-stored instances or upload new ones

- ✅ **Docker Ready**: Fully containerized with MiniZinc pre-installed

- ✅ **Render.com Compatible**: Ready for one-click deployment

## Quick Start

### Using Docker (Recommended)

```bash
# Build the image
docker build -t jssp-backend .

# Run the container
docker run -p 8000:8000 jssp-backend

# Test the API
curl http://localhost:8000/
```

### Local Development

```bash
# Install MiniZinc (https://www.minizinc.org/software.html)
minizinc --version

# Install Python dependencies
pip install -r requirements.txt

# Run the server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## API Usage

### Health Check

```bash
curl http://localhost:8000/
```

### Solve with JSON

```bash
curl -X POST http://localhost:8000/api/solve-once \
  -H "Content-Type: application/json" \
  -d '{
    "instanceId": "sample-tardanza",
    "solverConfig": {
      "problemType": "tardanza_ponderada",
      "solver": "chuffed",
      "searchHeuristic": "first_fail",
      "valueChoice": "indomain_min",
      "timeLimitSec": 30,
      "maxSolutions": 1
    }
  }'
```

### Solve with File Upload

```bash
curl -X POST http://localhost:8000/api/solve-once \
  -F "file=@./instances/sample.dzn" \
  -F "instanceId=sample-instance" \
  -F 'solverConfig={"problemType":"tardanza_ponderada","solver":"chuffed","searchHeuristic":"first_fail","valueChoice":"indomain_min","timeLimitSec":30,"maxSolutions":1}'
```

## Configuration

### Solver Configuration

```typescript
{
  problemType: 'jssp_maint' | 'tardanza_ponderada'
  solver: 'chuffed' | 'gecode' | 'or-tools'
  searchHeuristic: 'input_order' | 'first_fail' | 'smallest' | 'largest' | 'dom_w_deg' | 'impact' | 'activity'
  valueChoice: 'indomain_min' | 'indomain_max' | 'indomain_middle' | 'indomain_median' | 'indomain_random' | 'indomain_split'
  timeLimitSec: number  // ≥ 0
  maxSolutions: number  // ≥ 1
}
```

### Problem Types

#### Tardanza Ponderada (Weighted Tardiness)
Minimizes weighted tardiness across all jobs.

**Required Data:**
- `jobs`: Number of jobs
- `tasks`: Number of tasks per job
- `d`: Duration matrix [jobs][tasks]
- `weights`: Weight per job [jobs]
- `due_dates`: Due date per job [jobs]

#### JSSP with Maintenance
Minimizes makespan while respecting maintenance windows.

**Required Data:**
- `JOBS`: Number of jobs
- `TASKS`: Number of tasks per job
- `PROC_TIME`: Processing time matrix [JOBS][TASKS]
- `MAX_MAINT_WINDOWS`: Maximum maintenance windows
- `MAINT_START`: Maintenance start times [TASKS][MAX_MAINT_WINDOWS]
- `MAINT_END`: Maintenance end times [TASKS][MAX_MAINT_WINDOWS]
- `MAINT_ACTIVE`: Active maintenance flags [TASKS][MAX_MAINT_WINDOWS]

## Response Format

```json
{
  "status": "COMPLETED",
  "solution": {
    "makespan": 15.0,
    "machines": [
      {"id": "M1", "name": "M1"},
      {"id": "M2", "name": "M2"}
    ],
    "operations": [
      {
        "jobId": "J1",
        "machineId": "M1",
        "opId": "J1-1",
        "start": 0.0,
        "end": 3.0,
        "duration": 3.0
      }
    ],
    "stats": {
      "w": 5.0,
      "tardanza": 5.0
    }
  },
  "logs": [
    "solver:chuffed",
    "problemType:tardanza_ponderada",
    "searchHeuristic:first_fail",
    "valueChoice:indomain_min"
  ]
}
```

## Deployment

### Render.com (Recommended)

1. Push code to GitHub
2. Create new Web Service on Render
3. Connect your repository
4. Select "Docker" runtime
5. Deploy!

See [DEPLOYMENT.md](DEPLOYMENT.md) for detailed instructions.

### Other Platforms

The Docker image works on any platform supporting Docker:
- AWS ECS/Fargate
- Google Cloud Run
- Azure Container Instances
- Heroku
- DigitalOcean App Platform

## Project Structure

```
jssp-backend/
├── app/
│   ├── __init__.py
│   ├── main.py           # FastAPI application and endpoints
│   ├── models.py         # Pydantic models and schemas
│   ├── solver.py         # MiniZinc solver integration
│   ├── validation.py     # Input/output validation
│   └── modelos/
│       ├── JOBSHOP_MANTENIMIENTO.MZN
│       └── JOBSHOP_TARDANZA.MZN
├── storage/
│   └── instances/        # Pre-stored instance files
│       ├── sample-tardanza.json
│       └── sample-maint.json
├── Dockerfile            # Docker configuration
├── requirements.txt      # Python dependencies
├── README.md            # This file
└── DEPLOYMENT.md        # Deployment guide
```

## Development

### Running Tests

```bash
# Install dev dependencies
pip install pytest pytest-asyncio httpx

# Run tests (when implemented)
pytest
```

### Code Style

```bash
# Format code
black app/

# Type checking
mypy app/

# Linting
ruff check app/
```

## Technologies

- **FastAPI**: Modern Python web framework
- **MiniZinc**: Constraint programming platform
- **Pydantic**: Data validation
- **Uvicorn**: ASGI server
- **Docker**: Containerization

## Requirements

- Python 3.11+
- MiniZinc 2.8.5+
- Docker (for containerized deployment)

## License

[Your License Here]

## Contributing

Contributions are welcome! Please:
1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

## Support

For issues or questions:
- Check [DEPLOYMENT.md](DEPLOYMENT.md) for deployment help
- Review API documentation at `/docs` (when server is running)
- Open an issue on GitHub

## Acknowledgments

- MiniZinc team for the constraint programming platform
- FastAPI team for the excellent web framework