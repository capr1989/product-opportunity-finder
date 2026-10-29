"""Per-user Windows Credential Manager storage. No plaintext fallback."""
import ctypes
from ctypes import wintypes
import json
import os

FIELDS = {
    "Best Buy": ("BESTBUY_API_KEY",),
    "Google Ads": ("GOOGLE_ADS_CLIENT_ID", "GOOGLE_ADS_CLIENT_SECRET", "GOOGLE_ADS_REFRESH_TOKEN",
                   "GOOGLE_ADS_CUSTOMER_ID", "GOOGLE_ADS_LOGIN_CUSTOMER_ID", "GOOGLE_ADS_DEVELOPER_TOKEN"),
}


class CredentialVault:
    def __init__(self, namespace="ProductOpportunityFinder"):
        self.namespace = namespace

    def _target(self, provider):
        if provider not in FIELDS:
            raise ValueError("This provider has no implemented credential integration")
        return self.namespace + "/" + provider

    def _api(self):
        if os.name != "nt" or os.environ.get("POF_DISABLE_CREDENTIAL_VAULT") == "1":
            raise ValueError("Windows Credential Manager is unavailable; no plaintext fallback is used")

        class Credential(ctypes.Structure):
            _fields_ = [("Flags", wintypes.DWORD), ("Type", wintypes.DWORD),
                        ("TargetName", wintypes.LPWSTR), ("Comment", wintypes.LPWSTR),
                        ("LastWritten", wintypes.FILETIME), ("CredentialBlobSize", wintypes.DWORD),
                        ("CredentialBlob", ctypes.POINTER(ctypes.c_ubyte)), ("Persist", wintypes.DWORD),
                        ("AttributeCount", wintypes.DWORD), ("Attributes", ctypes.c_void_p),
                        ("TargetAlias", wintypes.LPWSTR), ("UserName", wintypes.LPWSTR)]
        api = ctypes.WinDLL("Advapi32.dll", use_last_error=True)
        api.CredWriteW.argtypes = [ctypes.POINTER(Credential), wintypes.DWORD]
        api.CredWriteW.restype = wintypes.BOOL
        api.CredReadW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, ctypes.POINTER(ctypes.POINTER(Credential))]
        api.CredReadW.restype = wintypes.BOOL
        api.CredDeleteW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD]
        api.CredDeleteW.restype = wintypes.BOOL
        api.CredFree.argtypes = [ctypes.c_void_p]
        api.CredFree.restype = None
        return api, Credential

    def save(self, provider, values):
        target = self._target(provider)
        if set(values) - set(FIELDS[provider]) or any(not isinstance(v, str) or len(v) > 2000 for v in values.values()):
            raise ValueError("Unsupported credential fields or length")
        payload = json.dumps(values).encode("utf-16-le")
        if len(payload) > 2500:
            raise ValueError("Credential payload exceeds Windows storage limit")
        api, cls = self._api()
        blob = (ctypes.c_ubyte * len(payload)).from_buffer_copy(payload)
        credential = cls(Type=1, TargetName=target, CredentialBlobSize=len(payload), CredentialBlob=blob,
                         Persist=2, UserName="ProductOpportunityFinder")
        try:
            if not api.CredWriteW(ctypes.byref(credential), 0):
                raise ValueError("Windows could not save these credentials. No plaintext copy was saved")
        finally:
            ctypes.memset(blob, 0, len(payload))

    def load(self, provider):
        target = self._target(provider)
        api, cls = self._api()
        pointer = ctypes.POINTER(cls)()
        if not api.CredReadW(target, 1, 0, ctypes.byref(pointer)):
            if ctypes.get_last_error() == 1168:
                return {}
            raise ValueError("Windows could not read saved credentials")
        try:
            raw = ctypes.string_at(pointer.contents.CredentialBlob, pointer.contents.CredentialBlobSize)
            values = json.loads(raw.decode("utf-16-le"))
            return {k: v for k, v in values.items() if k in FIELDS[provider] and isinstance(v, str)}
        finally:
            api.CredFree(pointer)

    def remove(self, provider):
        target = self._target(provider)
        api, _ = self._api()
        if not api.CredDeleteW(target, 1, 0) and ctypes.get_last_error() != 1168:
            raise ValueError("Windows could not remove saved credentials")


def integration_credentials(provider):
    # Environment overrides are retained for existing setups. Never mutate process env.
    try:
        saved = CredentialVault().load(provider)
    except (ValueError, OSError):
        saved = {}
    return {key: os.environ.get(key) or saved.get(key, "") for key in FIELDS[provider]}


def masked_status(provider):
    return {key: "Configured (••••)" if value else "Not configured"
            for key, value in integration_credentials(provider).items()}
