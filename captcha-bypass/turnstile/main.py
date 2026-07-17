import sys
import time
import logging
import threading
import asyncio
from typing import Dict
from queue import Queue
from sync_solver import get_turnstile_token as sync_solve


class CustomLogger(logging.Logger):
    COLORS = {
        'DEBUG': '\033[35m',    # Magenta
        'INFO': '\033[34m',     # Blue
        'SUCCESS': '\033[32m',  # Green
        'WARNING': '\033[33m',  # Yellow
        'ERROR': '\033[31m',    # Red
    }
    RESET = '\033[0m'  # Reset color

    def format_message(self, level, message):
        timestamp = time.strftime('%H:%M:%S')
        return f"[{timestamp}] [{self.COLORS.get(level, '')}{level}{self.RESET}] -> {message}"

    def debug(self, message, *args, **kwargs):
        super().debug(self.format_message('DEBUG', message), *args, **kwargs)

    def info(self, message, *args, **kwargs):
        super().info(self.format_message('INFO', message), *args, **kwargs)

    def success(self, message, *args, **kwargs):
        super().info(self.format_message('SUCCESS', message), *args, **kwargs)

    def warning(self, message, *args, **kwargs):
        super().warning(self.format_message('WARNING', message), *args, **kwargs)

    def error(self, message, *args, **kwargs):
        super().error(self.format_message('ERROR', message), *args, **kwargs)


logging.setLoggerClass(CustomLogger)
logger = logging.getLogger("TurnstileTester")
logger.setLevel(logging.DEBUG)
if not logger.handlers:
    handler = logging.StreamHandler(sys.stdout)
    logger.addHandler(handler)


class TurnstileTester:
    def _get_user_input(self) -> tuple[str, str, str]:
        """Get user input for solver configuration."""
        logger.info("Select solver mode:")
        logger.info("1. Sync Solver (Demo approach - navigate to real page)")
        logger.info("2. API Server")

        mode = input("Enter mode (1-2): ")
        while mode not in ['1', '2']:
            logger.warning("Invalid mode. Please enter 1 or 2.")
            mode = input("Enter mode (1-2): ")

        if mode == '2':
            return 'api', '', ''

        logger.info("\nEnter Turnstile details:")
        url = input("URL: ")
        sitekey = input("Sitekey: ")

        return 'sync', url, sitekey


    def run_sync_solver(self, url: str, sitekey: str, result_queue: Queue) -> None:
        """Run the synchronous solver with logging in a separate thread."""
        logger.debug(f"Starting sync solver for {url}")

        def sync_task():
            try:
                result = sync_solve(
                    url=url,
                    sitekey=sitekey,
                    debug=True,
                    headless=False,
                )
                if result.get('status') == 'success':
                    logger.success("Sync solver completed successfully")
                else:
                    logger.error("Sync solver failed")
                result_queue.put(result)
            except Exception as e:
                logger.error(f"Sync solver encountered an error: {e}")
                result_queue.put({})

        thread = threading.Thread(target=sync_task)
        thread.start()
        thread.join()


    async def run_api_server(self, debug=False, headless=False,
                              useragent=None, browser_type="chromium",
                              thread=1) -> None:
        """Run the API server with logging."""
        logger.info("Starting API server on http://localhost:5000")
        logger.info("API documentation available at http://localhost:5000/")

        try:
            from api_solver import create_app
            app = create_app(
                debug=debug, headless=headless, useragent=useragent,
                browser_type=browser_type, thread=thread,
                proxy_support=False,
            )
            import hypercorn.asyncio
            config = hypercorn.Config()
            config.bind = ["127.0.0.1:5000"]
            await hypercorn.asyncio.serve(app, config)
        except Exception as e:
            logger.error(f"API server failed to start: {str(e)}")

    async def main(self):
        """Main execution flow with proper logging."""
        logger.info("Turnstile: Welcome to Turnstile Solver")
        logger.info("Using DrissionPage demo approach (navigate to real page)")

        try:
            mode, url, sitekey = self._get_user_input()

            if mode == 'api':
                await self.run_api_server()
            else:
                if not url or not sitekey:
                    logger.error("URL and sitekey are required")
                    return

                result_queue = Queue()
                self.run_sync_solver(url, sitekey, result_queue)
                result = result_queue.get()

                if result:
                    logger.debug("Result details:")
                    for key, value in result.items():
                        logger.debug(f"  {key}: {value}")

        except KeyboardInterrupt:
            logger.warning("\nOperation cancelled by user")
        except Exception as e:
            logger.error(f"An error occurred: {str(e)}")
        finally:
            logger.info("Turnstile: Testing completed")


if __name__ == "__main__":
    tester = TurnstileTester()
    asyncio.run(tester.main())
