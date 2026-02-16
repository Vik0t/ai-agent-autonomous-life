"""
BDI (Belief-Desire-Intention) Architecture Module

Этот модуль реализует BDI архитектуру для интеллектуальных агентов.
"""

from .beliefs import Belief, BeliefType, BeliefBase, create_self_belief
from .desires import Desire, DesireStatus, MotivationType, DesireGenerator
from .intentions import Intention, IntentionStatus, IntentionSelector
from .plans import Plan, PlanStep, Planner, ActionType
from .deliberation import DeliberationCycle, create_perception

__all__ = [
    # Beliefs
    'Belief',
    'BeliefType',
    'BeliefBase',
    'create_self_belief',
    
    # Desires
    'Desire',
    'DesireStatus',
    'MotivationType',
    'DesireGenerator',
    
    # Intentions
    'Intention',
    'IntentionStatus',
    'IntentionSelector',
    
    # Plans
    'Plan',
    'PlanStep',
    'Planner',
    'ActionType'
    
    # Deliberation
    'DeliberationCycle',
    'create_perception'
]

__version__ = '1.0.0'
