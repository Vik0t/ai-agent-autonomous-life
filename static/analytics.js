// Analytics Component
const Analytics = ({ onBack }) => {
    // Mock analytics data
    const [agentStats, setAgentStats] = React.useState([]);
    const [interactionStats, setInteractionStats] = React.useState({});
    const [emotionStats, setEmotionStats] = React.useState({});
    
    React.useEffect(() => {
        // Simulate loading data
        setTimeout(() => {
            // Agent activity data
            const agents = window.agentsData || [];
            const activityData = agents.map(agent => ({
                id: agent.id,
                name: agent.name,
                avatar: agent.avatar,
                messages: Math.floor(Math.random() * 100) + 20,
                interactions: Math.floor(Math.random() * 50) + 10,
                memoryCount: agent.memory_count || Math.floor(Math.random() * 100)
            }));
            
            setAgentStats(activityData);
            
            // Interaction stats
            setInteractionStats({
                totalMessages: activityData.reduce((sum, agent) => sum + agent.messages, 0),
                totalInteractions: activityData.reduce((sum, agent) => sum + agent.interactions, 0),
                activeAgents: agents.length,
                avgMessagesPerAgent: Math.round(activityData.reduce((sum, agent) => sum + agent.messages, 0) / agents.length)
            });
            
            // Emotion stats (mock data)
            setEmotionStats({
                happiness: 72,
                sadness: 12,
                anger: 5,
                fear: 3,
                surprise: 6,
                disgust: 2
            });
        }, 500);
    }, []);
    
    // Sort agents by message count
    const topActiveAgents = [...agentStats].sort((a, b) => b.messages - a.messages).slice(0, 5);
    
    return React.createElement('div', { className: 'container analytics-container' },
        // Header
        React.createElement('div', { className: 'analytics-header' },
            React.createElement('button', {
                className: 'cyber-btn secondary back-button',
                onClick: onBack
            }, '← Назад'),
            React.createElement('h1', null, 'Аналитика Системы')
        ),
        
        // Summary stats
        React.createElement('div', { className: 'stats-grid' },
            React.createElement('div', { className: 'stat-card' },
                React.createElement('div', { className: 'stat-value' }, interactionStats.totalMessages || 0),
                React.createElement('div', { className: 'stat-label' }, 'Всего Сообщений')
            ),
            React.createElement('div', { className: 'stat-card' },
                React.createElement('div', { className: 'stat-value' }, interactionStats.activeAgents || 0),
                React.createElement('div', { className: 'stat-label' }, 'Активных Агентов')
            ),
            React.createElement('div', { className: 'stat-card' },
                React.createElement('div', { className: 'stat-value' }, interactionStats.avgMessagesPerAgent || 0),
                React.createElement('div', { className: 'stat-label' }, 'Сообщений/Агент')
            ),
            React.createElement('div', { className: 'stat-card' },
                React.createElement('div', { className: 'stat-value' }, interactionStats.totalInteractions || 0),
                React.createElement('div', { className: 'stat-label' }, 'Взаимодействий')
            )
        ),
        
        // Emotion distribution
        React.createElement('div', { className: 'panel' },
            React.createElement('h2', null, 'Эмоциональное Распределение'),
            React.createElement('div', { className: 'emotion-chart' },
                Object.entries(emotionStats).map(([emotion, value]) => 
                    React.createElement('div', { key: emotion, className: 'emotion-bar' },
                        React.createElement('div', { className: 'emotion-label' }, 
                            emotion === 'happiness' ? 'Радость' :
                            emotion === 'sadness' ? 'Грусть' :
                            emotion === 'anger' ? 'Гнев' :
                            emotion === 'fear' ? 'Страх' :
                            emotion === 'surprise' ? 'Удивление' : 'Отвращение'
                        ),
                        React.createElement('div', { className: 'emotion-bar-container' },
                            React.createElement('div', {
                                className: 'emotion-bar-fill',
                                style: {
                                    width: `${value}%`,
                                    background: emotion === 'happiness' ? '#00ff88' :
                                               emotion === 'sadness' ? '#2196F3' :
                                               emotion === 'anger' ? '#ff0040' :
                                               emotion === 'fear' ? '#ffee00' :
                                               emotion === 'surprise' ? '#ff00ff' : '#9E9E9E'
                                }
                            })
                        ),
                        React.createElement('div', { className: 'emotion-value' }, `${value}%`)
                    )
                )
            )
        ),
        
        // Top active agents
        React.createElement('div', { className: 'panel' },
            React.createElement('h2', null, 'Самые Активные Агенты'),
            React.createElement('div', { className: 'agent-ranking' },
                topActiveAgents.map((agent, index) => 
                    React.createElement('div', { key: agent.id, className: 'agent-rank-item' },
                        React.createElement('div', { className: 'agent-rank-position' }, `#${index + 1}`),
                        React.createElement('div', { className: 'agent-rank-avatar' }, agent.avatar),
                        React.createElement('div', { className: 'agent-rank-info' },
                            React.createElement('div', { className: 'agent-rank-name' }, agent.name),
                            React.createElement('div', { className: 'agent-rank-stats' }, 
                                `${agent.messages} сообщений, ${agent.interactions} взаимодействий`
                            )
                        )
                    )
                )
            )
        )
    );
};

// Add to global styles
const addAnalyticsStyles = () => {
    const style = document.createElement('style');
    style.textContent = `
        .analytics-container {
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
        }
        
        .analytics-header {
            display: flex;
            align-items: center;
            gap: 20px;
            margin-bottom: 30px;
        }
        
        .stats-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }
        
        .stat-card {
            background: rgba(0, 0, 0, 0.3);
            border: 1px solid rgba(0, 240, 255, 0.2);
            border-radius: 12px;
            padding: 20px;
            text-align: center;
            transition: all 0.3s ease;
        }
        
        .stat-card:hover {
            transform: translateY(-5px);
            box-shadow: 0 10px 20px rgba(0, 240, 255, 0.1);
            border-color: rgba(0, 240, 255, 0.4);
        }
        
        .stat-value {
            font-size: 2.5rem;
            font-weight: 700;
            color: var(--neon-cyan);
            margin-bottom: 10px;
        }
        
        .stat-label {
            font-size: 1rem;
            color: rgba(255, 255, 255, 0.7);
        }
        
        .emotion-chart {
            display: flex;
            flex-direction: column;
            gap: 15px;
        }
        
        .emotion-bar {
            display: flex;
            align-items: center;
            gap: 15px;
        }
        
        .emotion-label {
            width: 120px;
            font-weight: 600;
        }
        
        .emotion-bar-container {
            flex: 1;
            height: 20px;
            background: rgba(255, 255, 255, 0.1);
            border-radius: 10px;
            overflow: hidden;
        }
        
        .emotion-bar-fill {
            height: 100%;
            border-radius: 10px;
            transition: width 1s ease;
        }
        
        .emotion-value {
            width: 50px;
            text-align: right;
            font-weight: 600;
        }
        
        .agent-ranking {
            display: flex;
            flex-direction: column;
            gap: 15px;
        }
        
        .agent-rank-item {
            display: flex;
            align-items: center;
            gap: 15px;
            padding: 15px;
            background: rgba(0, 0, 0, 0.2);
            border-radius: 8px;
            border: 1px solid rgba(0, 240, 255, 0.1);
            transition: all 0.3s ease;
        }
        
        .agent-rank-item:hover {
            background: rgba(0, 240, 255, 0.1);
            border-color: rgba(0, 240, 255, 0.3);
        }
        
        .agent-rank-position {
            font-size: 1.2rem;
            font-weight: 700;
            color: var(--neon-cyan);
            width: 40px;
        }
        
        .agent-rank-avatar {
            width: 40px;
            height: 40px;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 1.2rem;
            background: linear-gradient(135deg, var(--neon-cyan), var(--neon-purple));
        }
        
        .agent-rank-info {
            flex: 1;
        }
        
        .agent-rank-name {
            font-weight: 700;
            margin-bottom: 5px;
        }
        
        .agent-rank-stats {
            font-size: 0.9rem;
            color: rgba(255, 255, 255, 0.7);
        }
        
        @media (max-width: 768px) {
            .stats-grid {
                grid-template-columns: 1fr;
            }
            
            .emotion-bar {
                flex-direction: column;
                align-items: flex-start;
                gap: 8px;
            }
            
            .emotion-label {
                width: auto;
            }
            
            .analytics-header {
                flex-direction: column;
                align-items: flex-start;
            }
        }
    `;
    document.head.appendChild(style);
};

// Add styles when the file loads
addAnalyticsStyles();