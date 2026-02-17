// WebSocket Client for real-time communication with backend
class WebSocketClient {
    constructor() {
        this.ws = null;
        this.isConnected = false;
        this.reconnectAttempts = 0;
        this.maxReconnectAttempts = 5;
        this.reconnectDelay = 1000;
        this.messageHandlers = new Map();
        this.agentData = new Map();
    }

    connect() {
        try {
            // Use the current host for WebSocket connection
            const wsUrl = `ws://${window.location.host}/ws`;
            this.ws = new WebSocket(wsUrl);
            
            this.ws.onopen = () => {
                console.log('WebSocket connected to backend');
                this.isConnected = true;
                this.reconnectAttempts = 0;
                this.onConnected();
            };
            
            this.ws.onmessage = (event) => {
                try {
                    const data = JSON.parse(event.data);
                    this.handleMessage(data);
                } catch (error) {
                    console.error('Error parsing WebSocket message:', error);
                }
            };
            
            this.ws.onclose = () => {
                console.log('WebSocket disconnected');
                this.isConnected = false;
                this.onDisconnected();
                this.attemptReconnect();
            };
            
            this.ws.onerror = (error) => {
                console.error('WebSocket error:', error);
                this.onConnectionError(error);
            };
        } catch (error) {
            console.error('Failed to create WebSocket connection:', error);
        }
    }
    
    onConnected() {
        // Notify any listeners that we're connected
        if (this.messageHandlers.has('connected')) {
            this.messageHandlers.get('connected').forEach(callback => callback());
        }
    }
    
    onDisconnected() {
        // Notify any listeners that we're disconnected
        if (this.messageHandlers.has('disconnected')) {
            this.messageHandlers.get('disconnected').forEach(callback => callback());
        }
    }
    
    onConnectionError(error) {
        // Notify any listeners of connection errors
        if (this.messageHandlers.has('error')) {
            this.messageHandlers.get('error').forEach(callback => callback(error));
        }
    }
    
    handleMessage(data) {
        // Handle different types of messages from the backend
        if (data.type === 'event') {
            this.handleEvent(data);
        } else if (data.type === 'message') {
            this.handleAgentMessage(data);
        } else if (data.agents && data.recent_messages) {
            // This is a full world state update
            this.handleWorldState(data);
        } else {
            console.log('Received unknown message type:', data);
        }
    }
    
    handleEvent(eventData) {
        // Handle system events
        if (this.messageHandlers.has('event')) {
            this.messageHandlers.get('event').forEach(callback => callback(eventData));
        }
    }
    
    handleAgentMessage(messageData) {
        // Handle individual agent messages
        if (this.messageHandlers.has('agent_message')) {
            this.messageHandlers.get('agent_message').forEach(callback => callback(messageData));
        }
    }
    
    handleWorldState(worldState) {
        // Handle full world state updates
        // Update agent data
        if (worldState.agents) {
            worldState.agents.forEach(agent => {
                this.agentData.set(agent.id, agent);
            });
            
            // Update global agents data
            window.agentsData = worldState.agents;
        }
        
        // Handle recent messages
        if (worldState.recent_messages) {
            if (this.messageHandlers.has('recent_messages')) {
                this.messageHandlers.get('recent_messages').forEach(callback => callback(worldState.recent_messages));
            }
        }
        
        // Notify about world state update
        if (this.messageHandlers.has('world_state')) {
            this.messageHandlers.get('world_state').forEach(callback => callback(worldState));
        }
    }
    
    sendMessage(message) {
        if (this.isConnected && this.ws) {
            this.ws.send(JSON.stringify(message));
        } else {
            console.warn('WebSocket not connected. Message not sent:', message);
        }
    }
    
    attemptReconnect() {
        if (this.reconnectAttempts < this.maxReconnectAttempts) {
            this.reconnectAttempts++;
            console.log(`Attempting to reconnect (${this.reconnectAttempts}/${this.maxReconnectAttempts})...`);
            
            setTimeout(() => {
                this.connect();
            }, this.reconnectDelay * this.reconnectAttempts);
        } else {
            console.error('Max reconnection attempts reached');
        }
    }
    
    // Register message handlers
    on(eventType, callback) {
        if (!this.messageHandlers.has(eventType)) {
            this.messageHandlers.set(eventType, []);
        }
        this.messageHandlers.get(eventType).push(callback);
    }
    
    // Remove message handlers
    off(eventType, callback) {
        if (this.messageHandlers.has(eventType)) {
            const handlers = this.messageHandlers.get(eventType);
            const index = handlers.indexOf(callback);
            if (index > -1) {
                handlers.splice(index, 1);
            }
        }
    }
    
    // Get agent data by ID
    getAgentData(agentId) {
        return this.agentData.get(agentId);
    }
    
    // Get all agent data
    getAllAgents() {
        return Array.from(this.agentData.values());
    }
}

// Create a global instance
window.websocketClient = new WebSocketClient();