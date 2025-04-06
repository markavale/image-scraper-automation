import asyncio
import random
from sim import WindscribeManager, ImageManager
from playwright.async_api import Error as PlaywrightError, TimeoutError
import subprocess
from typing import List, Dict
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class VPNSimulator:
    def __init__(self):
        self.windscribe = WindscribeManager()
        self.iteration_count = 0
        self.error_states: Dict[str, bool] = {
            "vpn_closed": False,
            "logged_out": False
        }

    async def simulate_vpn_closed(self):
        """Simulate Windscribe service being closed"""
        logger.info("Simulating VPN service closed...")
        self.error_states["vpn_closed"] = True
        # Simulate service stopped
        subprocess.run(['windscribe-cli', 'disconnect'], check=True)
        raise PlaywrightError("net::ERR_NETWORK_CHANGED")

    async def simulate_logged_out(self):
        """Simulate Windscribe being logged out"""
        logger.info("Simulating VPN logged out state...")
        self.error_states["logged_out"] = True
        # Force logout
        subprocess.run(['windscribe-cli', 'logout'], check=True)
        raise TimeoutError("Session expired")

    async def handle_iteration(self):
        """Handle VPN rotation based on iteration count"""
        self.iteration_count += 1
        
        if self.iteration_count % 3 == 0:
            logger.info(f"Iteration {self.iteration_count}: Rotating VPN...")
            await self.windscribe.reboot()

    async def simulate_error(self) -> Exception:
        """Randomly simulate different error scenarios"""
        error_scenarios = [
            (PlaywrightError("net::ERR_NETWORK_CHANGED"), 0.4),
            (TimeoutError("Connection timed out"), 0.3),
            (await self.simulate_vpn_closed(), 0.2),
            (await self.simulate_logged_out(), 0.1)
        ]

        # Choose an error based on weights
        error = random.choices(error_scenarios, weights=[w for _, w in error_scenarios])[0][0]
        return error

    async def run_simulation(self, num_iterations: int = 10):
        """Run the VPN simulation"""
        logger.info("Starting VPN simulation...")
        
        # Ensure VPN is connected at start
        try:
            await self.windscribe.connect()
        except Exception as e:
            logger.error(f"Failed to establish initial VPN connection: {e}")
            return

        for i in range(num_iterations):
            try:
                logger.info(f"\nIteration {i + 1}/{num_iterations}")
                await self.handle_iteration()

                # Randomly decide whether to simulate an error
                if random.random() < 0.3:  # 30% chance of error
                    error = await self.simulate_error()
                    if isinstance(error, Exception):
                        raise error

                # Simulate normal operation
                await asyncio.sleep(1)
                logger.info("Operation completed successfully")

            except PlaywrightError as e:
                logger.error(f"Network error: {e}")
                await self.windscribe.reboot()
            
            except TimeoutError as e:
                logger.error(f"Timeout error: {e}")
                await self.windscribe.reboot()
            
            except Exception as e:
                logger.error(f"Unexpected error: {e}")
                
                if self.error_states["vpn_closed"]:
                    logger.info("Restarting VPN service...")
                    subprocess.run(['windscribe-cli', 'start'], check=True)
                    self.error_states["vpn_closed"] = False
                
                if self.error_states["logged_out"]:
                    logger.info("Logging back into VPN...")
                    subprocess.run(['windscribe-cli', 'login'], check=True)
                    self.error_states["logged_out"] = False
                
                await self.windscribe.reboot()

            finally:
                await asyncio.sleep(random.uniform(1, 3))

async def main():
    simulator = VPNSimulator()
    await simulator.run_simulation(num_iterations=15)

if __name__ == "__main__":
    asyncio.run(main())
