"""Safe, actionable external-source failures; never carry raw response bodies or URLs."""


class SourceError(ValueError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


def from_http(status: int) -> SourceError:
    if status == 401:
        return SourceError("credentials_rejected", "Your API credentials were rejected. Open Source Manager to check your connection.")
    if status == 403:
        return SourceError("access_denied", "The source denied access. Check your API key, account approval and quota in Source Manager.")
    if status == 429:
        return SourceError("rate_limited", "This source has reached its request limit. Wait before running research again.")
    return SourceError("source_unavailable", "The source could not complete the request. Try later or check Source Manager.")
