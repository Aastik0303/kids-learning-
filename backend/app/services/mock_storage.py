"""Prototype in-memory storage only. Replace with persistent storage before production."""

mock_users: dict[str, dict] = {}
mock_sessions: dict[str, str] = {}
mock_child_profiles: dict[str, dict] = {}
mock_learning_sessions: dict[str, dict] = {}
mock_practice_sessions: dict[str, dict] = {}
mock_certificates: dict[str, dict] = {}
mock_activity_attempts: list[dict] = []
