"""Page-scoped, bounded observations. Never execute caller-supplied commands."""

from __future__ import annotations

import asyncio
import json
import time
from datetime import datetime
from uuid import uuid4

from app.core.features import effective_node_type, mqtt_services_enabled
from app.data.store import store
from app.domain.models import now_utc

INTERVAL = 60
DEADLINE = 15
FRESHNESS = 150
LEASE_TTL = 90


def endpoint_state(runtime: object) -> str:
    if runtime is None or not runtime.online:
        return "offline"
    fresh = (
        runtime.wg_observed_at is not None
        and runtime.wg_observed_at >= runtime_observation_service.started_at
        and (now_utc() - runtime.wg_observed_at).total_seconds() <= FRESHNESS
    )
    return (
        "online"
        if fresh and runtime.wg_running and runtime.wg_runtime_state == "running"
        else "not_started"
    )


def mesh_health(
    a_static: bool,
    b_static: bool,
    a_online: bool,
    b_online: bool,
    a: dict | None,
    b: dict | None,
    blocked: bool = False,
) -> dict:
    if a_static and b_static:
        return {"state": None, "reason": "static", "observations": []}
    observations = [x for x in (a, b) if x is not None]
    if blocked:
        reason = "disabled_or_invalid"
    elif not a_static and not b_static and not a_online and not b_online:
        reason = "both_offline"
    elif any(x.get("interface_state") == "stopped" for x in observations):
        reason = "interface_stopped"
    elif not observations:
        reason = "no_observation"
    elif all(x.get("peer") and int(x["peer"]["latest_handshake"]) > 0 for x in observations):
        return {"state": "healthy", "reason": "handshake", "observations": observations}
    else:
        reason = "missing_handshake_or_peer"
    return {"state": "interrupted", "reason": reason, "observations": observations}


class RuntimeObservationService:
    def __init__(self) -> None:
        self.started_at = now_utc()
        self.collector_id = uuid4().hex
        self.leases: dict[str, tuple[float, str, str, str]] = {}
        self.pending: dict[str, dict] = {}
        self.last_attempt: dict[str, float] = {}
        self.capabilities: dict[tuple[str, str], bool] = {}
        self.health_cache: dict[tuple, dict] = {}
        self.scheduled: set[tuple[str, str]] = set()

    def watch(self, viewer: str, config_id: str, node_id: str = "", mesh: bool = False) -> None:
        config = store.get_config(config_id)
        if node_id and store.get_node(node_id).config_id != config.id:
            raise ValueError("Node config mismatch")
        if len(self.leases) >= 512 and viewer not in self.leases:
            raise ValueError("Too many active viewers")
        self.leases[viewer] = (
            time.monotonic() + LEASE_TTL,
            config_id,
            node_id,
            "mesh" if mesh else "node",
        )

    def targets(self) -> dict[tuple[str, str], bool]:
        now = time.monotonic()
        targets: dict[tuple[str, str], bool] = {}
        for viewer, (expiry, config_id, node_id, kind) in list(self.leases.items()):
            if expiry <= now:
                self.leases.pop(viewer, None)
                continue
            try:
                if not store.get_config(config_id).enabled:
                    continue
                ids = {node_id} if node_id else {n.id for n in store.list_nodes(config_id)}
                if kind == "mesh":
                    for link in store.list_peer_links(config_id):
                        if link.local_node_id == node_id:
                            ids.add(link.peer_node_id)
                        if link.peer_node_id == node_id:
                            ids.add(link.local_node_id)
                for nid in ids:
                    n = store.get_node(nid)
                    if (
                        n.enabled
                        and effective_node_type(n) == "dynamic"
                        and store.get_client_state(config_id, nid).get("client_initialized")
                    ):
                        key = (config_id, nid)
                        targets[key] = targets.get(key, False) or kind == "mesh"
            except Exception:
                self.leases.pop(viewer, None)
        return targets

    async def tick(self) -> None:
        if not mqtt_services_enabled():
            return
        from app.services.mqtt_ingress_service import mqtt_ingress_service as mqtt

        if not mqtt._connected:
            return
        for key, peer_needed in self.targets().items():
            if len(self.scheduled) >= 16:
                break
            if key in self.scheduled or any(p["key"] == key for p in self.pending.values()):
                continue
            if time.monotonic() - self.last_attempt.get(key[1], -INTERVAL) < INTERVAL:
                continue
            self.scheduled.add(key)
            asyncio.create_task(self._collect_target(key, peer_needed))

    async def _collect_target(self, key: tuple[str, str], peer_needed: bool) -> None:
        try:
            await self.collect(*key, peer_needed)
        except Exception:
            # A node/config may be deleted after target selection.
            import logging

            logging.getLogger(__name__).exception("Runtime observation failed for %s", key)
        finally:
            self.scheduled.discard(key)

    async def collect(self, config_id: str, node_id: str, peer_needed: bool) -> None:
        from app.services.mqtt_ingress_service import mqtt_ingress_service as mqtt
        from app.domain import awg

        if any(p["key"] == (config_id, node_id) for p in self.pending.values()):
            return
        request_id = "obs-" + uuid4().hex
        state = store.get_client_state(config_id, node_id)
        session = str(state.get("session_id") or "")
        structured = peer_needed and self.capabilities.get((node_id, session), False)
        config = store.get_config(config_id)
        p = {
            "key": (config_id, node_id),
            "session": session,
            "structured": structured,
            "peer_needed": peer_needed,
            "started": now_utc().isoformat(),
            "future": asyncio.get_running_loop().create_future(),
            "public_key": store.get_node(node_id).public_key,
            "protocol": awg.wire_protocol(config.tunnel_protocol),
            "awg_version": config.awg_version,
        }
        self.pending[request_id] = p
        self.last_attempt[node_id] = time.monotonic()
        try:
            store.start_observation(config_id, node_id, request_id, p["started"])
            await mqtt.publish_to_node(
                config_id=config_id,
                node_id=node_id,
                kind="info" if structured else "detect",
                payload={
                    "type": "info" if structured else "detect",
                    "request_id": request_id,
                    "config_id": config_id,
                    "node_id": node_id,
                    "payload": {"action": "runtime_snapshot", "tunnel_protocol": p["protocol"]},
                },
            )
            await asyncio.wait_for(p["future"], DEADLINE)
        except asyncio.TimeoutError:
            self.fail(node_id, request_id, "timeout")
            runtime = store.get_runtime(config_id, node_id)
            if not runtime.last_seen or runtime.last_seen.isoformat() <= p["started"]:
                store.mark_client_offline(config_id, node_id, reason="observation-timeout")
        except Exception:
            self.fail(node_id, request_id, "query_failed")
        finally:
            self.scheduled.discard((config_id, node_id))
            self.pending.pop(request_id, None)
            from app.services.node_runtime_service import node_runtime_service

            await node_runtime_service._publish_runtime_scope(config_id, node_id)
            from app.services.realtime_service import realtime_service

            await realtime_service.publish("mesh.observation.updated", {"config_id": config_id})

    def fail(self, node_id: str, request_id: str, reason: str) -> None:
        store.fail_observation(node_id, request_id, reason, now_utc().isoformat())

    async def receive(self, config_id: str, node_id: str, kind: str, body: dict) -> bool:
        request_id = str(body.get("request_id") or "")
        p = self.pending.get(request_id)
        payload = body.get("payload") or {}
        if not isinstance(payload, dict):
            return request_id.startswith("obs-")
        if p is None:
            return (
                request_id.startswith("obs-")
                or kind == "info/ack"
                and payload.get("action") == "runtime_snapshot"
            )
        if (
            p["key"] != (config_id, node_id)
            or body.get("config_id") != config_id
            or body.get("node_id") != node_id
        ):
            return True
        if kind != ("info/ack" if p["structured"] else "detect/ack") or p["future"].done():
            return True
        current = store.get_client_state(config_id, node_id)
        session = str(body.get("session_id") or "")
        if p["session"] and session != p["session"]:
            return True
        if current.get("session_id") and current["session_id"] != p["session"]:
            return True
        node = store.get_node(node_id)
        from app.domain import awg

        if (
            node.public_key != p["public_key"]
            or awg.wire_protocol(store.get_config(config_id).tunnel_protocol) != p["protocol"]
        ):
            self.fail(node_id, request_id, "configuration_changed")
            p["future"].set_result(None)
            return True
        if (
            not node.enabled
            or effective_node_type(node) != "dynamic"
            or not mqtt_services_enabled()
        ):
            p["future"].set_result(None)
            return True
        self.capabilities[(node_id, session)] = (
            "runtime_snapshot_v1" in payload.get("capabilities", []) or p["structured"]
        )
        store.mark_client_reachable(
            config_id,
            node_id,
            reason="observation",
            session_id=session,
            boot_id=str(body.get("boot_id") or ""),
        )
        try:
            if payload.get("status") != "applied":
                raise ValueError("query_failed")
            if not p["structured"] and not isinstance(payload.get("wg_online"), bool):
                raise ValueError("invalid wg_online")
            snapshot = (
                self.validate(payload, p)
                if p["structured"]
                else {
                    "interface_state": "running" if payload.get("wg_online") is True else "stopped",
                    "peers": [],
                }
            )
            observed = now_utc().isoformat()
            store.complete_observation(
                node_id,
                request_id,
                observed,
                session,
                self.collector_id,
                snapshot if p["structured"] else None,
            )
            store.record_detect_ack(
                config_id,
                node_id,
                session_id=session,
                wg_online=snapshot["interface_state"] == "running",
            )
        except (ValueError, TypeError, KeyError, AttributeError):
            self.fail(node_id, request_id, "invalid_or_failed_observation")
        p["future"].set_result(None)
        # Bootstrap capability discovery should not delay the first Peer query a minute.
        if p["peer_needed"] and not p["structured"] and self.capabilities.get((node_id, session)):
            self.last_attempt.pop(node_id, None)
        return True

    @staticmethod
    def validate(payload: dict, pending: dict) -> dict:
        if payload.get("interface_state") not in ("running", "stopped"):
            raise ValueError("invalid interface state")
        result = {"interface_state": payload["interface_state"], "peers": []}
        if result["interface_state"] == "stopped":
            return result
        if (
            payload.get("interface_public_key") != pending["public_key"]
            or payload.get("tunnel_protocol") != pending["protocol"]
        ):
            raise ValueError("interface identity mismatch")
        if pending["protocol"] == "amneziawg_2" and payload.get("awg_version") != pending.get(
            "awg_version"
        ):
            raise ValueError("AWG version mismatch")
        rows = payload.get("peers")
        if not isinstance(rows, list) or len(rows) > 10000:
            raise ValueError("invalid peers")
        keys = set()
        for row in rows:
            key = str(row["public_key"])
            if key in keys:
                raise ValueError("duplicate peer")
            keys.add(key)
            peer = {"public_key": key}
            for name in ("latest_handshake", "rx_bytes", "tx_bytes"):
                value = row[name]
                if (
                    not isinstance(value, str)
                    or not value.isascii()
                    or not value.isdecimal()
                    or int(value) >= 2**64
                ):
                    raise ValueError("invalid counter")
                peer[name] = value
            result["peers"].append(peer)
        result.update(
            {
                k: payload[k]
                for k in (
                    "interface_public_key",
                    "tunnel_protocol",
                    "config_sha256",
                    "interface_name",
                )
            }
        )
        result["awg_version"] = payload.get("awg_version")
        return result

    def observation(self, config_id: str, node_id: str, peer_key: str) -> dict | None:
        state = store.get_client_state(config_id, node_id)
        if state.get("client_presence_state") != "online":
            return None
        row = store.get_observation(config_id, node_id)
        if (
            not row
            or row["query_status"] not in ("ok", "pending")
            or row["collector_id"] != self.collector_id
            or row["session_id"] != state.get("session_id")
        ):
            return None
        if (
            not row["observed_at"]
            or (now_utc() - datetime.fromisoformat(row["observed_at"])).total_seconds() > FRESHNESS
        ):
            return None
        snapshot = json.loads(row["snapshot_json"])
        from app.domain import awg

        if snapshot["interface_state"] == "running" and (
            snapshot.get("interface_public_key") != store.get_node(node_id).public_key
            or snapshot.get("tunnel_protocol")
            != awg.wire_protocol(store.get_config(config_id).tunnel_protocol)
        ):
            return None
        return {
            "node_id": node_id,
            "observed_at": row["observed_at"],
            "interface_state": snapshot["interface_state"],
            "peer": next(
                (x for x in snapshot.get("peers", []) if x["public_key"] == peer_key), None
            ),
        }

    def health(
        self,
        config_id: str,
        node: object,
        peer: object,
        blocked: bool,
        *,
        all_observations: bool = False,
    ) -> dict:
        nodes = store.list_nodes(config_id)
        if (
            sum(n.public_key == node.public_key for n in nodes) > 1
            or sum(n.public_key == peer.public_key for n in nodes) > 1
        ):
            blocked = True
        a_static, b_static = (
            effective_node_type(node) == "static",
            effective_node_type(peer) == "static",
        )
        a_runtime, b_runtime = (
            store.get_runtime(config_id, node.id),
            store.get_runtime(config_id, peer.id),
        )
        a = (
            None
            if a_static or not a_runtime.online
            else self.observation(config_id, node.id, peer.public_key)
        )
        b = (
            None
            if b_static or not b_runtime.online
            else self.observation(config_id, peer.id, node.public_key)
        )
        for is_static, runtime, nid in (
            (a_static, a_runtime, node.id),
            (b_static, b_runtime, peer.id),
        ):
            if (
                not is_static
                and runtime.online
                and runtime.wg_runtime_state == "stopped"
                and runtime.wg_observed_at
                and (now_utc() - runtime.wg_observed_at).total_seconds() <= FRESHNESS
            ):
                stopped = {
                    "node_id": nid,
                    "observed_at": runtime.wg_observed_at.isoformat(),
                    "interface_state": "stopped",
                    "peer": None,
                }
                if nid == node.id:
                    a = stopped
                else:
                    b = stopped
        for static, runtime, value in ((a_static, a_runtime, a), (b_static, b_runtime, b)):
            if (
                not static
                and runtime.online
                and runtime.wg_runtime_state == "stopped"
                and value is not None
            ):
                value["interface_state"] = "stopped"
        key = (
            config_id,
            node.id,
            peer.id,
            node.public_key,
            peer.public_key,
            a_static,
            b_static,
            all_observations,
        )
        waiting = any(
            p["key"] in ((config_id, node.id), (config_id, peer.id)) for p in self.pending.values()
        )
        previous = self.health_cache.get(key)
        if (
            waiting
            and previous
            and not blocked
            and (a_runtime.online or b_runtime.online)
            and not any(x and x["interface_state"] == "stopped" for x in (a, b))
        ):
            if all(
                (now_utc() - datetime.fromisoformat(x["observed_at"])).total_seconds() <= FRESHNESS
                for x in previous["observations"]
            ):
                return previous
        result = mesh_health(a_static, b_static, a_runtime.online, b_runtime.online, a, b, blocked)
        if not all_observations and result["state"] == "healthy" and a is not None:
            result["observations"] = [a]
        if not waiting:
            if len(self.health_cache) > 10000:
                self.health_cache.clear()
            self.health_cache[key] = result
        return result

    def reset(self) -> None:
        self.started_at = now_utc()
        self.collector_id = uuid4().hex
        for pending in self.pending.values():
            pending["future"].cancel()
        self.pending.clear()
        self.leases.clear()
        self.capabilities.clear()
        self.last_attempt.clear()
        self.health_cache.clear()
        self.scheduled.clear()


runtime_observation_service = RuntimeObservationService()
