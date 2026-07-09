"""Telemetry and structured logging for AI gateway."""
from __future__ import annotations

import logging
import json
import uuid
from datetime import datetime
from typing import Any, Dict

logger = logging.getLogger("ai.gateway")
if not logger.handlers:
	handler = logging.StreamHandler()
	logger.addHandler(handler)
	logger.setLevel(logging.INFO)


def make_request_id() -> str:
	return str(uuid.uuid4())


def emit_log(record: Dict[str, Any]) -> None:
	# Ensure no secrets included
	safe = {k: v for k, v in record.items() if "key" not in k.lower() and "secret" not in k.lower()}
	safe["timestamp"] = datetime.utcnow().isoformat() + "Z"
	logger.info(json.dumps(safe))


def build_log(**kwargs: Any) -> Dict[str, Any]:
	base = {"request_id": make_request_id()}
	base.update(kwargs)
	return base
