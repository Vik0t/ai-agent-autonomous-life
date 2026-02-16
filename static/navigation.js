// Navigation Component
const Navigation = ({ currentPage, onNavigate }) => {
    const navItems = [
        { id: 'dashboard', label: 'Дашборд', icon: '📊' },
        { id: 'agents', label: 'Агенты', icon: '🤖' },
        { id: 'chat', label: 'Чаты', icon: '💬' },
        { id: 'analytics', label: 'Аналитика', icon: '📈' }
    ];

    return React.createElement('nav', { className: 'main-navigation' },
        React.createElement('ul', { className: 'nav-list' },
            navItems.map(item => 
                React.createElement('li', { key: item.id },
                    React.createElement('button', {
                        className: `nav-item ${currentPage === item.id ? 'active' : ''}`,
                        onClick: () => onNavigate(item.id)
                    },
                        React.createElement('span', { className: 'nav-icon' }, item.icon),
                        React.createElement('span', { className: 'nav-label' }, item.label)
                    )
                )
            )
        )
    );
};

// Add to global styles
const addNavigationStyles = () => {
    const style = document.createElement('style');
    style.textContent = `
        .main-navigation {
            margin-bottom: 24px;
        }
        
        .nav-list {
            display: flex;
            gap: 12px;
            list-style: none;
            padding: 0;
            margin: 0;
        }
        
        .nav-item {
            display: flex;
            align-items: center;
            gap: 8px;
            padding: 12px 20px;
            background: rgba(0, 0, 0, 0.3);
            border: 1px solid rgba(0, 240, 255, 0.2);
            border-radius: 8px;
            color: rgba(255, 255, 255, 0.7);
            font-family: 'JetBrains Mono', monospace;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.3s ease;
        }
        
        .nav-item:hover {
            background: rgba(0, 240, 255, 0.1);
            color: #fff;
            border-color: rgba(0, 240, 255, 0.4);
        }
        
        .nav-item.active {
            background: linear-gradient(135deg, var(--neon-cyan), var(--neon-purple));
            color: #000;
            border-color: var(--neon-cyan);
        }
        
        .nav-icon {
            font-size: 1.2rem;
        }
        
        .nav-label {
            font-size: 0.9rem;
        }
        
        @media (max-width: 768px) {
            .nav-list {
                flex-wrap: wrap;
            }
            
            .nav-item {
                flex: 1;
                justify-content: center;
            }
        }
    `;
    document.head.appendChild(style);
};

// Add styles when the file loads
addNavigationStyles();