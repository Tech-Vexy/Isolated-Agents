"""Policy validation and normalisation for the Isolated Agents SDK."""

from __future__ import annotations

from isolated_agents_sdk.models import Policy


class PolicyValidator:
    """Validate and normalise a Policy object, applying defaults where values are absent.

    Defaults applied when ``None`` is passed:
    - ``cpu_cores``: 1.0
    - ``memory_mb``: 512
    - ``network.disabled``: True (no network access)
    - ``readonly_mounts``: [] (no extra mounts)
    - ``allowed_env_vars``: []
    - ``output_path_in_container``: "/output"
    - ``max_output_bytes``: None (unlimited)
    - ``timeout_seconds``: None (no timeout)
    - ``log_output_path``: None (stderr)

    Raises:
        PolicyValidationError: if the policy contains unknown fields or fields
            with incorrect value types (delegated to ``Policy.from_json()``).
    """

    def validate(self, policy: Policy | None) -> Policy:
        """Return a validated, normalised ``Policy``.

        If *policy* is ``None`` a default ``Policy`` is returned.
        If *policy* is already a ``Policy`` instance it is returned as-is
        (field-level validation is enforced at deserialisation time via
        ``Policy.from_json()``).
        """
        if policy is None:
            return Policy()
        if not isinstance(policy, Policy):
            raise TypeError(
                f"Expected a Policy instance or None, got {type(policy).__name__}"
            )
        return policy
