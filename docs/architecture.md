# Virtual World Simulator - Architecture

## Overview
The Virtual World Simulator is a web application that creates a virtual world populated with autonomous AI agents. Each agent has a personality, emotions, memories, and relationships with other agents.

## System Architecture

### Backend (Python/FastAPI)
- **Main Server**: FastAPI application that handles HTTP requests and WebSocket connections
- **Agent Engine**: Core simulation logic for agent behavior and interactions
- **LLM Interface**: Integration with OpenAI GPT for natural language processing
- **Memory System**: Vector database for storing and retrieving agent memories
- **Communication Hub**: Message passing system between agents

### Frontend (React/JavaScript)
- **Dashboard**: Main user interface with panels for agents, events, and controls
- **Agent Inspector**: Detailed view of individual agent characteristics
- **Relationship Graph**: D3.js visualization of agent relationships
- **Control Panel**: Interface for user interventions in the simulation

## Data Flow

1. **Agent Initialization**: Agents are created with default personalities and emotions
2. **Simulation Loop**: The world simulator runs continuously, processing agent actions
3. **Agent Actions**: Agents generate plans and communicate with other agents
4. **LLM Processing**: Natural language interactions are processed through LLM
5. **Memory Storage**: Important events are stored in the vector database
6. **Relationship Updates**: Agent interactions affect their relationships
7. **User Interface**: Real-time updates are sent to the frontend via WebSocket
8. **User Interaction**: Users can add events, send messages, and control simulation speed

## API Endpoints

### Agent Management
- `GET /agents` - List all agents
- `GET /agents/{id}` - Get detailed information about a specific agent
- `POST /agents` - Create a new agent

### Event Management
- `POST /events` - Add a global event affecting all agents
- `POST /messages` - Send a direct message between agents

### Control
- `POST /control/speed` - Set simulation speed multiplier

## WebSocket Interface
- `/ws` - Real-time updates of world state, events, and messages

## Data Models

### Agent
- ID (string)
- Name (string)
- Personality (OCEAN model)
- Emotions (happiness, sadness, anger, fear, surprise, disgust)
- Memories (list of events)
- Relationships (affinity and familiarity with other agents)
- Current Plan (short-term goals)

### Memory
- ID (string)
- Content (text description)
- Timestamp (when the memory was created)
- Importance (float 0-1)

### Relationship
- Agent ID (string)
- Affinity (float -1 to 1)
- Familiarity (float 0-1)
- Last Interaction (timestamp)

## Technologies Used

### Backend
- Python 3.8+
- FastAPI (web framework)
- OpenAI API (LLM integration)
- Scikit-learn (vector memory)
- NumPy (numerical computations)

### Frontend
- React (component-based UI)
- D3.js (data visualization)
- WebSocket (real-time communication)

## Deployment
The application can be deployed using Docker containers for both frontend and backend services, with appropriate environment variables for API keys and configuration.