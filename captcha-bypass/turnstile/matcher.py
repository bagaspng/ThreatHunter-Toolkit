"""
matcher.py v2
Adaptive visual engine with token extraction fallback.
Strategy priority:
1. Template matching (for embedded interactive mode)
2. Direct token extraction via window.turnstile.getResponse() (for invisible/managed)
3. Input field polling (last resort)
"""
import base64
import os
from typing import Literal, Optional, Tuple
import cv2
import numpy as np

def get_cdp_screenshot(driver) -> np.ndarray:
    """Capture screenshot via CDP, return as NumPy BGR array."""
    result = driver.execute_cdp_cmd("Page.captureScreenshot", {
        "format": "png",
        "fromSurface": True
    })
    img_bytes = base64.b64decode(result["data"])
    return np.frombuffer(img_bytes, dtype=np.uint8)

class TurnstileMatcher:
    """
    Adaptive matcher with multi-strategy fallback chain.
    """
    def __init__(
        self,
        driver,
        theme: Literal["light", "dark", "auto"] = "auto",
        grayscale: bool = False,
        thresh: float = 0.75  # Lowered from 0.8 for production variance
    ):
        self.driver = driver
        self.theme = theme
        self.grayscale = grayscale
        self.thresh = thresh
        
        base_dir = os.path.dirname(__file__)
        self.images = {
            "light": os.path.join(base_dir, "assets", "light_turnstile.png"),
            "dark": os.path.join(base_dir, "assets", "dark_turnstile.png"),
        }
        self.templates = self._load_templates()

    def _load_templates(self) -> list[np.ndarray]:
        flag = cv2.IMREAD_GRAYSCALE if self.grayscale else cv2.IMREAD_COLOR
        paths = list(self.images.values()) if self.theme == "auto" else [self.images[self.theme]]
        templates = []
        for path in paths:
            img = cv2.imread(str(path), flag)
            if img is None:
                raise FileNotFoundError(f"Template not found: {path}")
            templates.append(img)
        return templates

    def match(self) -> Optional[Tuple[int, int]]:
        """
        Multi-strategy match. Returns (x, y) coordinates or None.
        Priority: template → token extraction → input field
        """
        # Strategy 1: Visual template matching
        coords = self._template_match()
        if coords:
            return coords
        
        # Strategy 2: Direct token extraction (invisible mode)
        if self._try_extract_token():
            return (0, 0)  # Signal: token already extracted, no click needed
        
        # Strategy 3: Locate input field via DOM
        return self._locate_input_field()

    def _template_match(self) -> Optional[Tuple[int, int]]:
        """OpenCV template matching on CDP screenshot."""
        flag = cv2.IMREAD_GRAYSCALE if self.grayscale else cv2.IMREAD_COLOR
        screenshot = get_cdp_screenshot(self.driver)
        canvas = cv2.imdecode(screenshot, flag)
        
        best_val = 0.0
        best_loc = None
        for template in self.templates:
            if canvas.shape[0] < template.shape[0] or canvas.shape[1] < template.shape[1]:
                continue
            result = cv2.matchTemplate(canvas, template, cv2.TM_CCOEFF_NORMED)
            _, max_val, _, max_loc = cv2.minMaxLoc(result)
            if max_val > best_val and max_val >= self.thresh:
                best_val = max_val
                best_loc = max_loc
        return best_loc

    def _try_extract_token(self) -> bool:
        """
        Attempt direct token extraction via window.turnstile API.
        Works for invisible/managed mode where no UI interaction is needed.
        """
        result = self.driver.execute_cdp_cmd("Runtime.evaluate", {
            "expression": """
                (function() {
                    // Try turnstile.getResponse()
                    if (typeof window.turnstile !== 'undefined') {
                        const containers = document.querySelectorAll('.cf-turnstile, [data-sitekey]');
                        for (const container of containers) {
                            try {
                                const widgetId = container.getAttribute('data-widget-id') || 
                                               container.dataset.widgetId;
                                if (widgetId) {
                                    const token = window.turnstile.getResponse(widgetId);
                                    if (token && token.length > 50) {
                                        sessionStorage.setItem('turnstile_token', token);
                                        return true;
                                    }
                                }
                            } catch(e) {}
                        }
                    }
                    return false;
                })()
            """,
            "returnByValue": True
        })["result"].get("value", False)
        return result

    def _locate_input_field(self) -> Optional[Tuple[int, int]]:
        """
        Locate Turnstile input field via DOM and return its center coordinates.
        Fallback for when visual matching fails.
        """
        result = self.driver.execute_cdp_cmd("Runtime.evaluate", {
            "expression": """
                (function() {
                    const widget = document.querySelector('.cf-turnstile');
                    if (!widget) return null;
                    const input = widget.querySelector('input[name*="cf-turnstile"]');
                    if (!input) return null;
                    const rect = widget.getBoundingClientRect();
                    return {
                        x: Math.round(rect.left + rect.width / 2),
                        y: Math.round(rect.top + rect.height / 2)
                    };
                })()
            """,
            "returnByValue": True
        })["result"].get("value")
        
        if result:
            return (result["x"], result["y"])
        return None