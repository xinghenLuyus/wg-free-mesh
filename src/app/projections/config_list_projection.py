from __future__ import annotations

from collections.abc import Callable
from typing import cast

from app.domain.models import Config


class ConfigListProjection:
    def project(
        self,
        configs: list[Config],
        topology_for: Callable[[str], dict[str, object]],
    ) -> list[Config]:
        result: list[Config] = []
        for config in configs:
            topology = topology_for(config.id)
            result.append(
                config.model_copy(
                    update={
                        "topology_invalid": bool(config.enabled) and not bool(topology["valid"]),
                        "topology_error_count": cast(int, topology["error_count"]) if config.enabled else 0,
                    }
                )
            )
        return result


config_list_projection = ConfigListProjection()
