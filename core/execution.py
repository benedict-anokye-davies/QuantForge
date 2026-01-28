"""
Execution Handler - Simulates order execution with slippage and latency
"""



from abc import ABC, abstractmethod

from typing import Optional, Dict, Any

from dataclasses import dataclass

from datetime import datetime

import numpy as np



from .events import OrderEvent, FillEvent, MarketEvent





@dataclass

class SlippageModel:

    """Slippage model configuration"""

    model_type: str = "fixed"

    fixed_slippage: float = 0.0

    percentage: float = 0.0001

    volatility_factor: float = 0.1

    volume_factor: float = 0.1



    def calculate_slippage(

        self,

        order: OrderEvent,

        market: MarketEvent,

        direction_multiplier: float = 1.0

    ) -> float:

        """
        Calculate slippage for an order
        direction_multiplier: 1 for buy (higher fill), -1 for sell (lower fill)
        """

        if self.model_type == "fixed":

            return self.fixed_slippage * direction_multiplier



        elif self.model_type == "percentage":

            slippage = order.price * self.percentage

            return slippage * direction_multiplier



        elif self.model_type == "volatility_based":



            volatility = (market.high - market.low) / market.close

            slippage = order.price * volatility * self.volatility_factor

            return slippage * direction_multiplier



        elif self.model_type == "volume_based":



            if market.volume > 0:

                volume_impact = 1.0 / np.log1p(market.volume)

                slippage = order.price * volume_impact * self.volume_factor

                return slippage * direction_multiplier



        return 0.0





class ExecutionHandler(ABC):

    """Abstract base class for execution handling"""



    @abstractmethod

    def execute_order(

        self,

        order: OrderEvent,

        market: MarketEvent

    ) -> Optional[FillEvent]:

        """Execute order and return fill event"""

        pass



    @abstractmethod

    def set_slippage_model(self, model: SlippageModel):

        """Set slippage model"""

        pass





class SimulatedExecution(ExecutionHandler):

    """
    Simulated execution handler with realistic fill simulation
    """



    def __init__(

        self,

        slippage_model: Optional[SlippageModel] = None,

        fill_probability: float = 1.0,

        partial_fill_probability: float = 0.0,

        latency_ms: float = 0.0,

    ):

        self.slippage_model = slippage_model or SlippageModel()

        self.fill_probability = fill_probability

        self.partial_fill_probability = partial_fill_probability

        self.latency_ms = latency_ms

        self.fills: list = []



    def set_slippage_model(self, model: SlippageModel):

        self.slippage_model = model



    def execute_order(

        self,

        order: OrderEvent,

        market: MarketEvent

    ) -> Optional[FillEvent]:

        """
        Simulate order execution
        """



        if np.random.random() > self.fill_probability:

            return None





        fill_price = self._calculate_fill_price(order, market)





        fill_quantity = self._calculate_fill_quantity(order)



        if fill_quantity <= 0:

            return None





        commission = 0.0





        slippage = abs(fill_price - order.price) if order.price > 0 else 0.0



        fill = FillEvent(

            symbol=order.symbol,

            direction=order.direction,

            quantity=fill_quantity,

            fill_price=fill_price,

            commission=commission,

            timestamp=order.timestamp,

            order_id=order.order_id,

            exchange="SIMULATED",

            slippage=slippage

        )



        self.fills.append(fill)

        return fill



    def _calculate_fill_price(self, order: OrderEvent, market: MarketEvent) -> float:

        """Calculate realistic fill price with slippage"""

        base_price = order.price if order.price > 0 else market.close



        if order.order_type == "MARKET":



            direction_mult = 1.0 if order.direction == "BUY" else -1.0

            slippage = self.slippage_model.calculate_slippage(

                order, market, direction_mult

            )

            return base_price + slippage



        elif order.order_type == "LIMIT":



            if order.direction == "BUY":



                return min(order.price, market.close)

            else:



                return max(order.price, market.close)



        elif order.order_type == "STOP":



            if order.direction == "BUY":

                if market.high >= order.stop_price:



                    direction_mult = 1.0

                    slippage = self.slippage_model.calculate_slippage(

                        order, market, direction_mult

                    )

                    return max(order.stop_price, market.close) + slippage

            else:

                if market.low <= order.stop_price:



                    direction_mult = -1.0

                    slippage = self.slippage_model.calculate_slippage(

                        order, market, direction_mult

                    )

                    return min(order.stop_price, market.close) - slippage

            return base_price



        return base_price



    def _calculate_fill_quantity(self, order: OrderEvent) -> float:

        """Calculate fill quantity (handle partial fills)"""

        if np.random.random() < self.partial_fill_probability:



            fill_pct = np.random.uniform(0.1, 0.9)

            return order.quantity * fill_pct

        return order.quantity



    def get_fill_statistics(self) -> Dict[str, Any]:

        """Get statistics about fills"""

        if not self.fills:

            return {}



        total_slippage = sum(f.slippage * f.quantity for f in self.fills)

        total_quantity = sum(f.quantity for f in self.fills)



        return {

            'total_fills': len(self.fills),

            'total_quantity': total_quantity,

            'avg_slippage': total_slippage / total_quantity if total_quantity > 0 else 0,

            'total_slippage_cost': total_slippage,

        }





class MarketImpactExecution(SimulatedExecution):

    """
    Advanced execution with market impact modeling
    For large orders that move the market
    """



    def __init__(

        self,

        impact_model: str = "linear",

        impact_coefficient: float = 1.0,

        **kwargs

    ):

        super().__init__(**kwargs)

        self.impact_model = impact_model

        self.impact_coefficient = impact_coefficient



    def _calculate_market_impact(

        self,

        order: OrderEvent,

        market: MarketEvent

    ) -> float:

        """Calculate price impact of order"""

        if market.volume <= 0:

            return 0.0





        participation_rate = order.quantity / market.volume



        if self.impact_model == "linear":

            impact = participation_rate * self.impact_coefficient

        elif self.impact_model == "square_root":

            impact = np.sqrt(participation_rate) * self.impact_coefficient

        else:

            impact = 0.0



        return impact * market.close



    def execute_order(

        self,

        order: OrderEvent,

        market: MarketEvent

    ) -> Optional[FillEvent]:

        """Execute with market impact"""



        impact = self._calculate_market_impact(order, market)





        original_slippage = self.slippage_model.fixed_slippage



        if order.direction == "BUY":

            self.slippage_model.fixed_slippage += impact

        else:

            self.slippage_model.fixed_slippage -= impact



        fill = super().execute_order(order, market)





        self.slippage_model.fixed_slippage = original_slippage



        return fill
