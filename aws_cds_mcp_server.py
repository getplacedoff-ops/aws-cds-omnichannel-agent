#!/usr/bin/env python3
"""
AWS Communication Developer Services (CDS) — Model Context Protocol (MCP) Server
Author: Vigneshwara Kireeti Alugunulla (NuAIBot Technologies)

Exposes AWS End User Messaging (SMS, RCS, WhatsApp) and Amazon SESv2 as standardized
MCP tools (`tools/list`, `tools/call`) backed by `AWSCDSRuntimeSDKGateway` (`boto3`).
"""

import sys
import json
from typing import Dict, Any, List
from cds_omnichannel_agent import AWSCDSRuntimeSDKGateway


class AWSCDSMCPServer:
    """JSON-RPC 2.0 Model Context Protocol (MCP) Server for AWS CDS Omnichannel Agent."""

    def __init__(self, gateway: AWSCDSRuntimeSDKGateway | None = None):
        self.gateway = gateway or AWSCDSRuntimeSDKGateway()

    def list_tools(self) -> List[Dict[str, Any]]:
        return [
            {
                "name": "cds_send_sms_alert",
                "description": "Dispatches a proactive transactional SMS alert via AWS End User Messaging (`pinpoint-sms-voice-v2.send_text_message`).",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "destination_phone": {"type": "string"},
                        "message_body": {"type": "string"},
                    },
                    "required": ["destination_phone", "message_body"],
                },
            },
            {
                "name": "cds_send_rcs_rich_card",
                "description": "Dispatches an interactive RCS Rich Card / Carousel via AWS End User Messaging (`pinpoint-sms-voice-v2.send_text_message`).",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "destination_phone": {"type": "string"},
                        "message_body": {"type": "string"},
                        "card_title": {"type": "string"},
                        "suggestions": {"type": "array", "items": {"type": "string"}},
                    },
                    "required": ["destination_phone", "message_body", "card_title"],
                },
            },
            {
                "name": "cds_send_whatsapp_interactive",
                "description": "Dispatches a two-way interactive WhatsApp Business message via AWS End User Messaging Social (`socialmessaging.send_whatsapp_message`).",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "destination_phone": {"type": "string"},
                        "body_text": {"type": "string"},
                        "reply_buttons": {"type": "array", "items": {"type": "string"}},
                    },
                    "required": ["destination_phone", "body_text"],
                },
            },
            {
                "name": "cds_send_ses_transactional_email",
                "description": "Dispatches a formal HTML audit receipt via Amazon Simple Email Service v2 (`sesv2.send_email`).",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "to_email": {"type": "string"},
                        "subject": {"type": "string"},
                        "html_body": {"type": "string"},
                        "audit_hash": {"type": "string"},
                    },
                    "required": ["to_email", "subject", "html_body", "audit_hash"],
                },
            },
        ]

    def call_tool(self, name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        if name == "cds_send_sms_alert":
            return self.gateway.dispatch_sms_or_rcs(
                destination_phone=arguments["destination_phone"],
                message_body=arguments["message_body"],
                channel_mode="SMS",
            )
        elif name == "cds_send_rcs_rich_card":
            return self.gateway.dispatch_sms_or_rcs(
                destination_phone=arguments["destination_phone"],
                message_body=arguments["message_body"],
                channel_mode="RCS",
                rcs_card_metadata={
                    "title": arguments["card_title"],
                    "suggestions": arguments.get("suggestions", ["Confirm", "Reschedule"]),
                },
            )
        elif name == "cds_send_whatsapp_interactive":
            return self.gateway.dispatch_whatsapp_interactive(
                destination_phone=arguments["destination_phone"],
                body_text=arguments["body_text"],
                reply_buttons=arguments.get("reply_buttons", ["Approve", "Upload Photo"]),
            )
        elif name == "cds_send_ses_transactional_email":
            return self.gateway.dispatch_ses_transactional_email(
                to_email=arguments["to_email"],
                subject=arguments["subject"],
                html_body=arguments["html_body"],
                audit_hash=arguments["audit_hash"],
            )
        raise ValueError(f"Unknown MCP tool: {name}")

    def handle_jsonrpc(self, request: Dict[str, Any]) -> Dict[str, Any]:
        req_id = request.get("id", 1)
        method = request.get("method", "")
        params = request.get("params", {})

        if method == "initialize":
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "protocolVersion": "2024-11-05",
                    "serverInfo": {"name": "aws-cds-omnichannel-mcp", "version": "2.0.0"},
                    "capabilities": {"tools": {}},
                },
            }
        elif method == "tools/list":
            return {"jsonrpc": "2.0", "id": req_id, "result": {"tools": self.list_tools()}}
        elif method == "tools/call":
            tool_res = self.call_tool(params["name"], params.get("arguments", {}))
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {"content": [{"type": "text", "text": json.dumps(tool_res)}]},
            }
        return {"jsonrpc": "2.0", "id": req_id, "error": {"code": -32601, "message": f"Method not found: {method}"}}


if __name__ == "__main__":
    server = AWSCDSMCPServer()
    print(json.dumps(server.handle_jsonrpc({"jsonrpc": "2.0", "id": 1, "method": "tools/list"}), indent=2))
