"""Latest observation persistence; no unbounded sample history."""

import json

from app.data.connection import connect


class RuntimeObservationRepositoryMixin:
    def start_observation(
        self, config_id: str, node_id: str, request_id: str, started: str
    ) -> None:
        with connect() as db:
            db.execute(
                "INSERT OR IGNORE INTO node_runtime_observations (node_id, config_id) VALUES (?, ?)",
                (node_id, config_id),
            )
            db.execute(
                "UPDATE node_runtime_observations SET request_id=?, requested_at=?, query_status='pending', error_code='' WHERE node_id=?",
                (request_id, started, node_id),
            )

    def fail_observation(self, node_id: str, request_id: str, reason: str, completed: str) -> None:
        with connect() as db:
            db.execute(
                "UPDATE node_runtime_observations SET query_status='failed', error_code=?, completed_at=? WHERE node_id=? AND request_id=?",
                (reason, completed, node_id, request_id),
            )
            db.execute(
                "UPDATE endpoint_runtime_status SET wg_runtime_state='unknown' WHERE node_id=? AND EXISTS (SELECT 1 FROM node_runtime_observations o WHERE o.node_id=? AND o.request_id=?)",
                (node_id, node_id, request_id),
            )

    def complete_observation(
        self,
        node_id: str,
        request_id: str,
        observed: str,
        session: str,
        collector: str,
        snapshot: dict | None,
    ) -> None:
        with connect() as db:
            if snapshot is None:
                db.execute(
                    "UPDATE node_runtime_observations SET query_status='ok', completed_at=? WHERE node_id=? AND request_id=?",
                    (observed, node_id, request_id),
                )
            else:
                db.execute(
                    "UPDATE node_runtime_observations SET query_status='ok', completed_at=?, observed_at=?, session_id=?, collector_id=?, snapshot_json=? WHERE node_id=? AND request_id=?",
                    (
                        observed,
                        observed,
                        session,
                        collector,
                        json.dumps(snapshot),
                        node_id,
                        request_id,
                    ),
                )

    def get_observation(self, config_id: str, node_id: str) -> dict | None:
        with connect() as db:
            return db.execute(
                "SELECT * FROM node_runtime_observations WHERE node_id=? AND config_id=?",
                (node_id, config_id),
            ).fetchone()
