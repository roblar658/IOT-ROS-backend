"""
Security Subsystem for SmartGuard ROS 2.
Implements SROS 2 / DDS-Security policies, HMAC-SHA256 message authentication,
AES-256 payload encryption simulation, and anti-replay nonce validation.
Addresses Non-Functional Requirements: [#NF2], [#NF5], [#NF8], [#NF13], [#NF16].
"""

import hmac
import hashlib
import json
import time
import base64
import os
from typing import Dict, Tuple, Any

SHARED_SECRET_KEY = b"SMARTGUARD_SROS2_SECRET_KEY_2026_MASTER"

class SecurityManager:
    """Manages cryptographic signatures, SROS 2 access control, and payload integrity."""
    def __init__(self, key: bytes = SHARED_SECRET_KEY):
        self.key = key
        self.seen_nonces: Dict[str, float] = {}

    def sign_payload(self, device_id: str, payload: Any, seq: int) -> str:
        """Generates an HMAC-SHA256 signature for sensor telemetry."""
        serialized = json.dumps({"dev": device_id, "data": payload, "seq": seq}, sort_keys=True)
        sig = hmac.new(self.key, serialized.encode('utf-8'), hashlib.sha256).hexdigest()
        return sig

    def verify_signature(self, device_id: str, payload: Any, seq: int, signature: str) -> bool:
        """Verifies HMAC-SHA256 signature on received telemetry."""
        expected_sig = self.sign_payload(device_id, payload, seq)
        return hmac.compare_digest(expected_sig, signature)

    def validate_anti_replay(self, nonce: str, max_age_sec: float = 5.0) -> bool:
        """Anti-replay mechanism using unique nonce and timestamp."""
        now = time.time()
        # Clean up stale nonces
        stale = [n for n, t in self.seen_nonces.items() if now - t > max_age_sec]
        for s in stale:
            del self.seen_nonces[s]

        if nonce in self.seen_nonces:
            return False  # Replay detected!
        self.seen_nonces[nonce] = now
        return True

    def encrypt_sensitive_data(self, plaintext: str) -> str:
        """
        Simulated AES-256-GCM encryption for sensitive personal health & emergency data.
        In SROS 2, this is handled natively at DDS transport layer with hardware AES-NI.
        """
        encoded = plaintext.encode('utf-8')
        # Simple high-entropy XOR stream with SHA-256 key expansion for portability
        stream = hashlib.sha256(self.key + b":STREAM").digest()
        cipher = bytes([b ^ stream[i % len(stream)] for i, b in enumerate(encoded)])
        return base64.b64encode(cipher).decode('ascii')

    def decrypt_sensitive_data(self, ciphertext: str) -> str:
        cipher = base64.b64decode(ciphertext.encode('ascii'))
        stream = hashlib.sha256(self.key + b":STREAM").digest()
        plain = bytes([b ^ stream[i % len(stream)] for i, b in enumerate(cipher)])
        return plain.decode('utf-8')

# SROS 2 Policy Generator Helper
def generate_sros2_governance_xml() -> str:
    """Returns compliant SROS 2 / DDS-Security XML Governance Policy."""
    return """<?xml version="1.0" encoding="UTF-8"?>
<dds xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
     xsi:noNamespaceSchemaLocation="http://www.omg.org/spec/DDS-SECURITY/20170901/omg_shared_ca_governance.xsd">
    <domain_access_rules>
        <domain_rule>
            <domains>
                <id>0</id>
            </domains>
            <allow_unauthenticated_participants>false</allow_unauthenticated_participants>
            <enable_join_access_control>true</enable_join_access_control>
            <discovery_protection_kind>ENCRYPT</discovery_protection_kind>
            <liveliness_protection_kind>ENCRYPT</liveliness_protection_kind>
            <rtps_protection_kind>ENCRYPT</rtps_protection_kind>
            <topic_access_rules>
                <topic_rule>
                    <topic_expression>/alerts/critical</topic_expression>
                    <enable_read_access_control>true</enable_read_access_control>
                    <enable_write_access_control>true</enable_write_access_control>
                    <metadata_protection_kind>ENCRYPT</metadata_protection_kind>
                    <data_protection_kind>ENCRYPT</data_protection_kind>
                </topic_rule>
                <topic_rule>
                    <topic_expression>/health/*</topic_expression>
                    <enable_read_access_control>true</enable_read_access_control>
                    <enable_write_access_control>true</enable_write_access_control>
                    <metadata_protection_kind>ENCRYPT</metadata_protection_kind>
                    <data_protection_kind>ENCRYPT</data_protection_kind>
                </topic_rule>
                <topic_rule>
                    <topic_expression>*</topic_expression>
                    <enable_read_access_control>true</enable_read_access_control>
                    <enable_write_access_control>true</enable_write_access_control>
                    <metadata_protection_kind>ENCRYPT</metadata_protection_kind>
                    <data_protection_kind>ENCRYPT</data_protection_kind>
                </topic_rule>
            </topic_access_rules>
        </domain_rule>
    </domain_access_rules>
</dds>"""
