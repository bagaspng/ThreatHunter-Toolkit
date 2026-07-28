"""
clicker.py v2
Hybrid trusted event simulation.
- CDP moves (smooth Bézier path)
- pyautogui click (OS-level, isTrusted: true) for GUI mode
- CDP click fallback for headless (with entropy masking)

Production Turnstile REJECTS untrusted CDP clicks.
For headless production bypass, use virtual display (Xvfb on Linux).
"""
import math
import random
import time
from typing import Literal, Tuple
import pyautogui

class TurnstileClicker:
    """
    Hybrid clicker with trusted event priority.
    """
    SCRIPT_ID = None
    
    def __init__(self, driver, method: Literal["cdp", "pyautogui", "hybrid"] = "hybrid"):
        self.driver = driver
        self.method = method
        pyautogui.PAUSE = 0.01
        
        if method in ["cdp", "hybrid"]:
            if not TurnstileClicker.SCRIPT_ID:
                self._create_mousemove_listener()

    def browser_to_screen_coords(self, element_x: int, element_y: int) -> Tuple[int, int]:
        """Convert browser-relative coords to screen coords."""
        env = self.driver.execute_cdp_cmd("Runtime.evaluate", {
            "expression": """
                (function() {
                    return {
                        screenX: window.screenX,
                        screenY: window.screenY,
                        scrollX: window.scrollX,
                        scrollY: window.scrollY,
                        outerHeight: window.outerHeight,
                        innerHeight: window.innerHeight
                    };
                })()
            """,
            "returnByValue": True
        })["result"]["value"]
        
        chrome_offset_y = env["outerHeight"] - env["innerHeight"]
        screen_x = env["screenX"] + element_x - env["scrollX"]
        screen_y = env["screenY"] + chrome_offset_y + element_y - env["scrollY"]
        return int(screen_x), int(screen_y)

    def _create_mousemove_listener(self) -> None:
        """Inject JS to track mouse position for Bézier path start point."""
        js = """
            document.addEventListener('mousemove', e => {
                window._mousePos = { x: e.clientX, y: e.clientY };
            });
        """
        res = self.driver.execute_cdp_cmd(
            "Page.addScriptToEvaluateOnNewDocument", {"source": js}
        )
        TurnstileClicker.SCRIPT_ID = res["identifier"]
        self.driver.execute_cdp_cmd("Runtime.evaluate", {"expression": js})

    def _get_mouse_pos(self) -> Tuple[int, int]:
        """Get last known mouse position or random viewport point."""
        res = self.driver.execute_cdp_cmd("Runtime.evaluate", {
            "expression": """
                (function() {
                    if (typeof window._mousePos === 'object' && window._mousePos !== null) {
                        return window._mousePos;
                    }
                    return {
                        x: Math.floor(Math.random() * window.innerWidth),
                        y: Math.floor(Math.random() * window.innerHeight)
                    };
                })()
            """,
            "returnByValue": True
        })["result"]["value"]
        return res["x"], res["y"]

    def _bezier_curve(self, p0: float, p1: float, p2: float, t: float) -> float:
        """Quadratic Bézier interpolation."""
        return (1 - t) ** 2 * p0 + 2 * (1 - t) * t * p1 + t ** 2 * p2

    def _generate_human_like_path(self, start_x: int, start_y: int, end_x: int, end_y: int) -> list:
        """
        Generate Bézier path with Gaussian noise (not uniform).
        Production Turnstile detects uniform random noise.
        """
        dx, dy = end_x - start_x, end_y - start_y
        distance = math.hypot(dx, dy)
        steps = min(60, max(15, int(distance / 4)))
        ctrl_offset = distance * 0.3
        
        # Gaussian-distributed control point offset
        ctrl_x = (start_x + end_x) / 2 + random.gauss(0, ctrl_offset / 2)
        ctrl_y = (start_y + end_y) / 2 + random.gauss(0, ctrl_offset / 2)
        
        path = []
        for i in range(steps + 1):
            t = i / steps
            # Gaussian noise (σ=0.15) instead of uniform
            x = self._bezier_curve(start_x, ctrl_x, end_x, t) + random.gauss(0, 0.15)
            y = self._bezier_curve(start_y, ctrl_y, end_y, t) + random.gauss(0, 0.15)
            path.append((int(x), int(y)))
        return path

    def click(self, end_x: int, end_y: int) -> None:
        """
        Execute hybrid click:
        - Move: CDP (smooth Bézier)
        - Click: pyautogui (trusted) OR CDP (untrusted fallback)
        """
        if self.method == "pyautogui":
            start = pyautogui.position()
            end = self.browser_to_screen_coords(end_x, end_y)
        else:  # cdp or hybrid
            start = self._get_mouse_pos()
            end = (end_x, end_y)
        
        path = self._generate_human_like_path(*start, *end)
        
        # Phase 1: Smooth movement (CDP for all modes)
        for x, y in path:
            self.driver.execute_cdp_cmd(
                "Input.dispatchMouseEvent",
                {"type": "mouseMoved", "x": x, "y": y, "buttons": 0}
            )
            # Gaussian delay between moves (not uniform)
            time.sleep(abs(random.gauss(0.008, 0.003)))
        
        # Phase 2: Click execution
        time.sleep(abs(random.gauss(0.15, 0.05)))  # Pre-click hesitation
        
        if self.method == "pyautogui":
            # Trusted OS-level click
            pyautogui.click(end[0], end[1])
        else:
            # CDP click (untrusted but masked with entropy)
            for event_type in ["mousePressed", "mouseReleased"]:
                self.driver.execute_cdp_cmd(
                    "Input.dispatchMouseEvent",
                    {
                        "type": event_type,
                        "x": end_x,
                        "y": end_y,
                        "button": "left",
                        "clickCount": 1,
                        "buttons": 1 if event_type == "mousePressed" else 0
                    }
                )
                time.sleep(abs(random.gauss(0.05, 0.02)))

    def remove_mousemove_listener(self) -> None:
        """Remove injected mousemove listener."""
        if TurnstileClicker.SCRIPT_ID:
            self.driver.execute_cdp_cmd(
                "Page.removeScriptToEvaluateOnNewDocument",
                {"identifier": TurnstileClicker.SCRIPT_ID}
            )
            TurnstileClicker.SCRIPT_ID = None