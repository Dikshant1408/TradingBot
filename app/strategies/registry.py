"""
Strategy registry for dynamic strategy discovery and instantiation.
"""
from typing import Dict, Type, List, Optional, Any
from app.strategies.base import BaseStrategy
from app.strategies.moving_average import MovingAverageCrossoverStrategy


class StrategyRegistry:
    def __init__(self):
        self._registry: Dict[str, Type[BaseStrategy]] = {}
        # Register default initial strategy
        self.register("MA_Crossover", MovingAverageCrossoverStrategy)

    def register(self, strategy_id: str, strategy_class: Type[BaseStrategy]) -> None:
        self._registry[strategy_id] = strategy_class

    def get(self, strategy_id: str) -> Optional[Type[BaseStrategy]]:
        return self._registry.get(strategy_id)

    def create(self, strategy_id: str, parameters: Optional[Dict[str, Any]] = None) -> BaseStrategy:
        strategy_class = self.get(strategy_id)
        if not strategy_class:
            raise KeyError(f"Strategy '{strategy_id}' not found in registry. Available: {list(self._registry.keys())}")
        return strategy_class(parameters=parameters)

    def list_strategies(self) -> List[Dict[str, Any]]:
        results = []
        for strat_id, cls_type in self._registry.items():
            sample_instance = cls_type()
            results.append({
                "id": strat_id,
                "name": sample_instance.name,
                "version": sample_instance.version,
                "description": sample_instance.description,
                "parameters": sample_instance.parameters,
                "schema": sample_instance.get_parameter_schema()
            })
        return results


strategy_registry = StrategyRegistry()
