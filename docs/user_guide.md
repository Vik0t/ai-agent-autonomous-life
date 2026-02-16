# Virtual World Simulator - User Guide

## Getting Started

### Prerequisites
- Python 3.8 or higher
- Node.js and npm (for frontend development)
- OpenAI API key (optional, for LLM features)

### Installation
1. Clone the repository
2. Install backend dependencies:
   ```
   pip install -r requirements.txt
   ```
3. Set up environment variables (optional):
   - `OPENAI_API_KEY` for LLM features

### Running the Application
1. Start the backend server:
   ```
   cd backend
   python main.py
   ```
2. Open `frontend/index.html` in a web browser

## Using the Simulator

### Dashboard Overview
The main dashboard consists of several panels:
- **Agents Panel**: Shows all agents in the simulation with their current mood
- **Control Panel**: Allows you to interact with the world
- **Event Feed**: Displays real-time events and messages
- **Relationship Graph**: Visualizes relationships between agents
- **Agent Inspector**: Detailed view of a selected agent

### Agent Interaction
Click on any agent card to open the Agent Inspector, which shows:
- Personality traits (OCEAN model)
- Current emotions
- Relationships with other agents
- Memory count

### User Controls
The Control Panel allows you to influence the simulation:

#### Add Global Events
Enter a description of an event that affects all agents, then click "Add Event". Examples:
- "A treasure has been discovered!"
- "It's raining heavily outside"
- "A festival is happening in the town square"

#### Send Direct Messages
Select an agent from the dropdown, enter a message, and click "Send Message" to communicate directly with that agent.

#### Control Simulation Speed
Use the slider to adjust how fast time passes in the simulation:
- 0.1x: 10% speed (slower)
- 1.0x: Normal speed
- 5.0x: 500% speed (faster)

Click "Set Speed" to apply the selected speed.

### Real-time Events
The Event Feed shows real-time updates including:
- Agent communications
- Global events
- System messages

### Relationship Visualization
The Relationship Graph shows:
- Agents as nodes (circles)
- Relationships as edges (lines)
- Green lines indicate positive relationships (affinity)
- Red lines indicate negative relationships (affinity)
- Line thickness represents relationship strength

You can drag nodes to rearrange the graph layout.

## Technical Details

### Agent Behavior
Agents have:
- **Personalities** based on the OCEAN model (Openness, Conscientiousness, Extraversion, Agreeableness, Neuroticism)
- **Emotions** that change based on events and interactions
- **Memories** stored in a vector database
- **Relationships** with affinity and familiarity metrics

### Communication
Agents communicate through:
- Direct messaging
- Broadcast messages for global events
- LLM-generated natural language responses

### Memory System
Agents store important events in memory:
- Memories are stored with importance ratings
- Older memories may be summarized when storage limits are reached
- Memories influence future decisions and interactions

## Troubleshooting

### Common Issues
1. **WebSocket connection failed**: Ensure the backend server is running
2. **Agents not communicating**: Check that the simulation is running
3. **LLM features not working**: Verify your OpenAI API key is set

### Getting Help
For additional support, check the project documentation or contact the development team.