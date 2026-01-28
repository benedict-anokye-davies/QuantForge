"""
Configuration Module

YAML-based configuration loader for QuantForge.
Supports hierarchical configs with defaults and overrides.
"""



from __future__ import annotations



from dataclasses import dataclass, field

from pathlib import Path

from typing import Any, Dict, List, Optional, Union



import yaml





@dataclass

class Config:

    """
    Configuration container for QuantForge backtests.

    Provides a typed interface to configuration settings with
    sensible defaults for all parameters.
    """





    initial_capital: float = 100000.0





    start_date: Optional[str] = None

    end_date: Optional[str] = None





    symbols: List[str] = field(default_factory=list)





    data_dir: str = "./data"





    commission_rate: float = 0.001

    slippage_model: str = "fixed"

    slippage_amount: float = 0.0





    max_position_pct: float = 0.10

    max_leverage: float = 1.0

    max_drawdown_pct: float = 0.20





    strategy_params: Dict[str, Any] = field(default_factory=dict)





    verbose: bool = True

    save_results: bool = True

    results_dir: str = "./results"





    database_path: str = "./data/quantforge.db"



    @classmethod

    def from_dict(cls, data: Dict[str, Any]) -> "Config":

        """Create Config from dictionary."""



        known_fields = {f.name for f in cls.__dataclass_fields__.values()}





        known_data = {k: v for k, v in data.items() if k in known_fields}

        unknown_data = {k: v for k, v in data.items() if k not in known_fields}





        if unknown_data:

            known_data.setdefault('strategy_params', {}).update(unknown_data)



        return cls(**known_data)



    def to_dict(self) -> Dict[str, Any]:

        """Convert Config to dictionary."""

        return {

            'initial_capital': self.initial_capital,

            'start_date': self.start_date,

            'end_date': self.end_date,

            'symbols': self.symbols,

            'data_dir': self.data_dir,

            'commission_rate': self.commission_rate,

            'slippage_model': self.slippage_model,

            'slippage_amount': self.slippage_amount,

            'max_position_pct': self.max_position_pct,

            'max_leverage': self.max_leverage,

            'max_drawdown_pct': self.max_drawdown_pct,

            'strategy_params': self.strategy_params,

            'verbose': self.verbose,

            'save_results': self.save_results,

            'results_dir': self.results_dir,

            'database_path': self.database_path,

        }



    def update(self, **kwargs: Any) -> "Config":

        """Create updated config with new values."""

        data = self.to_dict()

        data.update(kwargs)

        return Config.from_dict(data)





def load_config(

    config_path: Union[str, Path],

    overrides: Optional[Dict[str, Any]] = None

) -> Config:

    """
    Load configuration from YAML file.

    Supports configuration inheritance via 'extends' key.
    Later configs override earlier ones.

    Args:
        config_path: Path to YAML config file
        overrides: Optional dict of values to override

    Returns:
        Config object

    Raises:
        FileNotFoundError: If config file doesn't exist
        ValueError: If YAML is invalid

    Example:
        >>> config = load_config("configs/default.yaml")
        >>> config = load_config("configs/custom.yaml", overrides={"verbose": False})
    """

    config_path = Path(config_path)



    if not config_path.exists():

        raise FileNotFoundError(f"Config file not found: {config_path}")



    with open(config_path, 'r') as f:

        data = yaml.safe_load(f)



    if data is None:

        data = {}





    merged_data = {}



    if 'extends' in data:



        parent_paths = data['extends']

        if isinstance(parent_paths, str):

            parent_paths = [parent_paths]



        for parent_path in parent_paths:

            parent_full_path = config_path.parent / parent_path

            parent_config = load_config(parent_full_path)

            merged_data.update(parent_config.to_dict())





    for key, value in data.items():

        if key != 'extends':

            merged_data[key] = value





    if overrides:

        merged_data.update(overrides)



    return Config.from_dict(merged_data)





def save_config(config: Config, path: Union[str, Path]) -> None:

    """
    Save configuration to YAML file.

    Args:
        config: Config object to save
        path: Destination path
    """

    path = Path(path)

    path.parent.mkdir(parents=True, exist_ok=True)



    with open(path, 'w') as f:

        yaml.dump(config.to_dict(), f, default_flow_style=False, sort_keys=True)





def get_default_config() -> Config:

    """Get default configuration with sensible defaults."""

    return Config()
