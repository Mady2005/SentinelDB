from __future__ import annotations

from typing import Any

import httpx

from .models import EnvStepResult, SentinelAction, SentinelObservation, StepPayload

try:
    from openenv import EnvClient  # type: ignore
except ImportError:  # pragma: no cover
    class EnvClient:  # type: ignore
        """Fallback base class used when openenv-core is not installed."""


class SentinelEnv(EnvClient):
    """Small HTTP client for SentinelDB with an OpenEnv-like sync surface.

    If `openenv.HTTPEnvClient` is available in the runtime, this class still works
    as a thin compatible wrapper. The direct `httpx` implementation keeps local
    development simple when the hackathon package is not installed yet.
    """

    def __init__(self, base_url: str, timeout: float = 30.0):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._client = httpx.Client(base_url=self.base_url, timeout=timeout)

    def reset(self) -> SentinelObservation:
        response = self._client.post("/reset")
        response.raise_for_status()
        return SentinelObservation.model_validate(response.json())

    def step(self, action: SentinelAction) -> EnvStepResult:
        response = self._client.post("/step", json=action.model_dump())
        response.raise_for_status()
        payload = StepPayload.model_validate(response.json())
        return EnvStepResult(
            observation=payload.obs,
            reward=payload.reward.value,
            done=payload.done,
            info=payload.info,
        )

    def state(self) -> dict[str, Any]:
        response = self._client.get("/state")
        response.raise_for_status()
        return response.json()

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "SentinelEnv":
        return self

    def __exit__(self, *_args: object) -> None:
        self.close()

    def sync(self) -> "SentinelEnv":
        return self
