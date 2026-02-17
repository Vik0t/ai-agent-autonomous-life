// Relationship Visualizer Component
const RelationshipVisualizer = ({ agents }) => {
    // Calculate relationship metrics
    const calculateRelationshipMetrics = () => {
        if (!agents || agents.length === 0) return [];
        
        return agents.map(agent => {
            const relationships = agent.relationships || {};
            const relationshipEntries = Object.entries(relationships);
            
            if (relationshipEntries.length === 0) {
                return {
                    agent,
                    avgAffinity: 0,
                    avgFamiliarity: 0,
                    relationshipCount: 0,
                    strongestRelationship: null
                };
            }
            
            const totalAffinity = relationshipEntries.reduce((sum, [, rel]) => sum + rel.affinity, 0);
            const totalFamiliarity = relationshipEntries.reduce((sum, [, rel]) => sum + rel.familiarity, 0);
            
            const avgAffinity = totalAffinity / relationshipEntries.length;
            const avgFamiliarity = totalFamiliarity / relationshipEntries.length;
            
            // Find strongest relationship
            const strongestRelationship = relationshipEntries.reduce((strongest, [id, rel]) => {
                if (!strongest || rel.affinity > strongest.affinity) {
                    return { id, ...rel };
                }
                return strongest;
            }, null);
            
            return {
                agent,
                avgAffinity,
                avgFamiliarity,
                relationshipCount: relationshipEntries.length,
                strongestRelationship
            };
        });
    };
    
    const metrics = calculateRelationshipMetrics();
    
    // Get agent name by ID
    const getAgentName = (agentId) => {
        const agent = agents.find(a => a.id === agentId);
        return agent ? agent.name : `Агент ${agentId}`;
    };
    
    // Render relationship bar
    const renderRelationshipBar = (value, color) => {
        return React.createElement('div', { className: 'relationship-bar' },
            React.createElement('div', {
                className: 'relationship-bar-fill',
                style: {
                    width: `${Math.abs(value) * 100}%`,
                    background: color,
                    marginLeft: value < 0 ? `${(1 + value) * 100}%` : '0'
                }
            })
        );
    };
    
    return React.createElement('div', { className: 'panel relationship-visualizer-panel' },
        React.createElement('div', { className: 'panel-corner panel-corner-tl' }),
        React.createElement('div', { className: 'panel-corner panel-corner-tr' }),
        React.createElement('div', { className: 'panel-corner panel-corner-bl' }),
        React.createElement('div', { className: 'panel-corner panel-corner-br' }),
        
        React.createElement('h2', { className: 'panel-title' }, 'Анализ Отношений'),
        
        React.createElement('div', { className: 'relationship-metrics' },
            metrics.map(metric => 
                React.createElement('div', { 
                    key: metric.agent.id, 
                    className: 'agent-relationship-metric' 
                },
                    React.createElement('div', { className: 'agent-info' },
                        React.createElement('div', { className: 'agent-avatar-small' }, metric.agent.avatar),
                        React.createElement('div', { className: 'agent-name-small' }, metric.agent.name)
                    ),
                    React.createElement('div', { className: 'metric-row' },
                        React.createElement('span', { className: 'metric-label' }, 'Средняя симпатия:'),
                        React.createElement('span', { className: 'metric-value' }, 
                            metric.avgAffinity.toFixed(2)
                        )
                    ),
                    React.createElement('div', { className: 'metric-bar-container' },
                        renderRelationshipBar(metric.avgAffinity, 
                            metric.avgAffinity > 0 ? '#00ff88' : '#ff0040')
                    ),
                    React.createElement('div', { className: 'metric-row' },
                        React.createElement('span', { className: 'metric-label' }, 'Знакомство:'),
                        React.createElement('span', { className: 'metric-value' }, 
                            `${(metric.avgFamiliarity * 100).toFixed(0)}%`
                        )
                    ),
                    React.createElement('div', { className: 'metric-bar-container' },
                        renderRelationshipBar(metric.avgFamiliarity, '#00f0ff')
                    ),
                    metric.strongestRelationship && React.createElement('div', { className: 'strongest-relationship' },
                        React.createElement('span', { className: 'metric-label' }, 'Лучшие отношения с:'),
                        React.createElement('span', { className: 'metric-value' }, 
                            `${getAgentName(metric.strongestRelationship.id)} (${metric.strongestRelationship.affinity.toFixed(2)})`
                        )
                    )
                )
            )
        )
    );
};

// Add to global styles
const addRelationshipVisualizerStyles = () => {
    const style = document.createElement('style');
    style.textContent = `
        .relationship-visualizer-panel {
            grid-column: span 6;
        }
        
        .relationship-metrics {
            display: flex;
            flex-direction: column;
            gap: 20px;
        }
        
        .agent-relationship-metric {
            padding: 15px;
            background: rgba(0, 0, 0, 0.3);
            border-radius: 10px;
            border: 1px solid rgba(255, 255, 255, 0.05);
        }
        
        .agent-info {
            display: flex;
            align-items: center;
            gap: 10px;
            margin-bottom: 12px;
        }
        
        .agent-avatar-small {
            width: 30px;
            height: 30px;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 1rem;
            background: linear-gradient(135deg, var(--neon-cyan), var(--neon-purple));
        }
        
        .agent-name-small {
            font-weight: 600;
            color: #fff;
        }
        
        .metric-row {
            display: flex;
            justify-content: space-between;
            margin-bottom: 5px;
            font-size: 0.85rem;
        }
        
        .metric-label {
            color: rgba(255, 255, 255, 0.7);
        }
        
        .metric-value {
            color: var(--neon-cyan);
            font-weight: 600;
        }
        
        .metric-bar-container {
            height: 6px;
            background: rgba(255, 255, 255, 0.1);
            border-radius: 3px;
            margin-bottom: 12px;
            overflow: hidden;
            position: relative;
        }
        
        .relationship-bar {
            position: relative;
            height: 100%;
            width: 100%;
        }
        
        .relationship-bar-fill {
            position: absolute;
            height: 100%;
            border-radius: 3px;
            transition: width 0.5s ease;
        }
        
        .strongest-relationship {
            font-size: 0.8rem;
            color: rgba(255, 255, 255, 0.7);
            margin-top: 8px;
        }
        
        .strongest-relationship .metric-value {
            display: block;
            color: var(--neon-purple);
            font-size: 0.85rem;
        }
        
        @media (max-width: 1200px) {
            .relationship-visualizer-panel {
                grid-column: span 12;
            }
        }
    `;
    document.head.appendChild(style);
};

// Add styles when the file loads
addRelationshipVisualizerStyles();