"""User-scoped OAuth helpers for Google Drive and Google Classroom."""

import json
import os
import secrets
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow

SCOPES = [
    "https://www.googleapis.com/auth/drive.readonly",
    "https://www.googleapis.com/auth/classroom.courses.readonly",
    "https://www.googleapis.com/auth/classroom.courseworkmaterials.readonly",
]


class GoogleOAuthStore:
    """Persist opaque OAuth state and per-browser tokens outside the web client."""

    def __init__(self, client_secret_path: Path, redirect_uri: str, state_dir: Path) -> None:
        self.client_secret_path = client_secret_path
        self.redirect_uri = redirect_uri
        self.state_dir = state_dir
        self.state_dir.mkdir(parents=True, exist_ok=True)

    @property
    def configured(self) -> bool:
        return bool(self.redirect_uri) and self.client_secret_path.is_file()

    def _flow(self, state: str | None = None, code_verifier: str | None = None) -> Flow:
        return Flow.from_client_secrets_file(
            str(self.client_secret_path),
            scopes=SCOPES,
            redirect_uri=self.redirect_uri,
            state=state,
            code_verifier=code_verifier,
        )

    def begin(self) -> tuple[str, str]:
        if not self.configured:
            raise RuntimeError("Google integration is not configured. Set GOOGLE_CLIENT_SECRET_FILE and GOOGLE_REDIRECT_URI.")
        session_id, state = secrets.token_urlsafe(24), secrets.token_urlsafe(32)
        flow = self._flow(state=state)
        url, _ = flow.authorization_url(
            access_type="offline", include_granted_scopes="true", prompt="consent"
        )
        # PKCE is enabled by google-auth-oauthlib. Its verifier must survive
        # the redirect and be supplied during the token exchange.
        (self.state_dir / f"state_{state}").write_text(
            json.dumps({"session_id": session_id, "code_verifier": flow.code_verifier}),
            encoding="utf-8",
        )
        return url, session_id

    def complete(self, state: str, code: str) -> str:
        state_path = self.state_dir / f"state_{state}"
        if not state_path.is_file():
            raise ValueError("The Google sign-in state is invalid or has expired. Please try again.")
        try:
            pending = json.loads(state_path.read_text(encoding="utf-8"))
            session_id = pending["session_id"]
            code_verifier = pending["code_verifier"]
        except (json.JSONDecodeError, KeyError, TypeError) as exc:
            raise ValueError("The Google sign-in state is invalid. Please try again.") from exc
        state_path.unlink(missing_ok=True)
        flow = self._flow(state=state, code_verifier=code_verifier)
        # Google can return already-granted Classroom scopes in addition to the
        # requested read-only scopes. OAuthlib otherwise rejects that valid
        # token response before credentials can be saved.
        os.environ.setdefault("OAUTHLIB_RELAX_TOKEN_SCOPE", "1")
        flow.fetch_token(code=code)
        (self.state_dir / f"token_{session_id}.json").write_text(flow.credentials.to_json(), encoding="utf-8")
        return session_id

    def credentials(self, session_id: str) -> Credentials:
        # Session IDs are opaque server-generated values; disallow traversal regardless.
        if not session_id or any(c not in "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_" for c in session_id):
            raise ValueError("Invalid Google session.")
        token_path = self.state_dir / f"token_{session_id}.json"
        if not token_path.is_file():
            raise ValueError("Google connection not found. Connect your account again.")
        creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)
        if creds.expired and creds.refresh_token:
            creds.refresh(Request())
            token_path.write_text(creds.to_json(), encoding="utf-8")
        if not creds.valid:
            raise ValueError("Google connection has expired. Connect your account again.")
        return creds
