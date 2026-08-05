import logging

try:
    from automation.contracts import PageProfile, SubmissionResult
    from automation.static import submit_static
    from automation.spa import submit_spa
except ImportError:
    from contracts import PageProfile, SubmissionResult
    from static import submit_static
    from spa import submit_spa

logger = logging.getLogger("XoS-Automation")

async def route_submission(
    profile: PageProfile,
    proxy_str: str | None = None,
    config: any = None
) -> SubmissionResult:
    """
    Phase 2: Router.
    Single responsibility: receives PageProfile, selects route (Static vs SPA),
    and returns SubmissionResult. Contains no submission logic itself.
    """
    if not profile.is_spa:
        return await submit_static(profile, proxy_str, config)
    else:
        return await submit_spa(profile, proxy_str, config)
