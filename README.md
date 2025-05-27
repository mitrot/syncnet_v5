# SyncNet v5

A distributed chat system with high availability and fault tolerance.

## Features

- Distributed architecture with leader election
- Real-time messaging with WebSocket support
- Room-based chat with private and public rooms
- User authentication and authorization
- Message persistence and history
- Fault tolerance and automatic failover
- Monitoring and metrics
- Security features (TLS, rate limiting)

## Project Structure

```
syncnet_v5/
├── server/                 # Server components
│   ├── core/              # Core server functionality
│   │   ├── __init__.py
│   │   ├── server.py      # Main server class
│   │   ├── room.py        # Room management
│   │   └── user.py        # User management
│   ├── network/           # Network handling
│   │   ├── __init__.py
│   │   ├── connection.py  # Connection management
│   │   └── protocol.py    # Protocol implementation
│   ├── consensus/         # Consensus algorithms
│   │   ├── __init__.py
│   │   ├── election.py    # Leader election
│   │   └── replication.py # State replication
│   ├── security/          # Security features
│   │   ├── __init__.py
│   │   ├── auth.py        # Authentication
│   │   └── crypto.py      # Cryptography
│   └── monitoring/        # Monitoring and metrics
│       ├── __init__.py
│       ├── metrics.py     # Metrics collection
│       └── health.py      # Health checks
├── client/                # Client components
│   ├── core/             # Core client functionality
│   │   ├── __init__.py
│   │   └── client.py     # Main client class
│   ├── network/          # Network handling
│   │   ├── __init__.py
│   │   └── connection.py # Connection management
│   ├── ui/               # User interface
│   │   ├── __init__.py
│   │   ├── cli.py        # Command-line interface
│   │   └── gui.py        # Graphical interface
│   └── security/         # Security features
│       ├── __init__.py
│       └── auth.py       # Authentication
├── common/               # Shared components
│   ├── protocol/         # Protocol definitions
│   │   ├── __init__.py
│   │   └── messages.py   # Message types
│   ├── utils/            # Utility functions
│   │   ├── __init__.py
│   │   ├── async_utils.py # Async utilities
│   │   └── error_handling.py # Error handling
│   └── config/           # Configuration
│       ├── __init__.py
│       ├── settings.py   # Settings
│       ├── constants.py  # Constants
│       └── logging_config.py # Logging
├── tests/                # Test suite
│   ├── __init__.py
│   ├── conftest.py      # Test configuration
│   ├── test_server/     # Server tests
│   └── test_client/     # Client tests
├── docs/                 # Documentation
│   ├── api/             # API documentation
│   └── guides/          # User guides
├── scripts/             # Utility scripts
├── config.json          # Configuration file
├── requirements.txt     # Python dependencies
├── setup.py            # Package setup
├── README.md           # This file
└── LICENSE             # License file
```

## Requirements

- Python 3.8 or higher
- Dependencies listed in `requirements.txt`

## Installation

1. Clone the repository:
```bash
git clone https://github.com/yourusername/syncnet_v5.git
cd syncnet_v5
```

2. Create a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Copy the example configuration:
```bash
cp config.json.example config.json
```

5. Edit `config.json` to match your environment.

## Running the Server

1. Start the server:
```bash
python -m server.core.server
```

2. For development with auto-reload:
```bash
python -m server.core.server --dev
```

## Running the Client

1. Start the CLI client:
```bash
python -m client.ui.cli
```

2. Start the GUI client:
```bash
python -m client.ui.gui
```

## Development

### Code Style

This project uses:
- Black for code formatting
- isort for import sorting
- flake8 for linting
- mypy for type checking
- pylint for additional checks

Run the style checks:
```bash
# Format code
black .

# Sort imports
isort .

# Run linters
flake8
mypy .
pylint server client common
```

### Testing

Run the test suite:
```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=server --cov=client --cov=common

# Run specific test file
pytest tests/test_server/test_server.py
```

### Documentation

Build the documentation:
```bash
cd docs
make html
```

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Contributing

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

## Acknowledgments

- [Raft Consensus Algorithm](https://raft.github.io/)
- [WebSocket Protocol](https://websockets.spec.whatwg.org/)
- [Python asyncio](https://docs.python.org/3/library/asyncio.html) 