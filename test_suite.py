#!/usr/bin/env python3
"""
10-Test Unit & Boto3 Runtime Verification Suite for AWS CDS Omnichannel Agent v2.0.
Author: Vigneshwara Kireeti Alugunulla (NuAIBot Technologies)
"""

import json
import unittest
from cds_omnichannel_agent import (
    AWSCDSRuntimeSDKGateway,
    AWSCDSOmnichannelAgent,
    StatelessRuleBotBaseline,
    lambda_handler,
)
from aws_cds_mcp_server import AWSCDSMCPServer


class TestAWSCDSOmnichannelAgentV2(unittest.TestCase):
    def setUp(self):
        self.gateway = AWSCDSRuntimeSDKGateway(region_name="us-east-1", live_aws_mode=False)
        self.agent = AWSCDSOmnichannelAgent(sdk_gateway=self.gateway)
        self.mcp = AWSCDSMCPServer(gateway=self.gateway)

    def test_01_boto3_clients_instantiated_at_runtime(self):
        self.assertIsNotNone(self.gateway.sms_rcs_client)
        self.assertIsNotNone(self.gateway.whatsapp_client)
        self.assertIsNotNone(self.gateway.ses_client)
        self.assertIsNotNone(self.gateway.bedrock_agent_client)
        self.assertIsNotNone(self.gateway.dynamodb_client)
        self.assertEqual(self.gateway.sms_rcs_client.meta.service_model.service_name, "pinpoint-sms-voice-v2")
        self.assertEqual(self.gateway.whatsapp_client.meta.service_model.service_name, "socialmessaging")
        self.assertEqual(self.gateway.ses_client.meta.service_model.service_name, "sesv2")

    def test_02_dispatch_sms_via_pinpoint_sms_voice_v2(self):
        res = self.gateway.dispatch_sms_or_rcs("+12065550101", "Rx Ready for Pickup", channel_mode="SMS")
        self.assertEqual(res["sdk_client"], "pinpoint-sms-voice-v2")
        self.assertEqual(res["operation"], "send_text_message")
        self.assertEqual(res["channel"], "SMS")
        self.assertTrue(res["message_id"].startswith("eum-sms-"))

    def test_03_dispatch_rcs_rich_card_via_pinpoint_sms_voice_v2(self):
        res = self.gateway.dispatch_sms_or_rcs(
            "+12065550102",
            "Select new flight seat",
            channel_mode="RCS",
            rcs_card_metadata={"title": "Seat Selection", "suggestions": ["12A Window", "14C Aisle"]},
        )
        self.assertEqual(res["sdk_client"], "pinpoint-sms-voice-v2")
        self.assertEqual(res["channel"], "RCS")
        self.assertIn("RCSCardTitle", res["request_params"]["Context"])

    def test_04_dispatch_whatsapp_via_socialmessaging(self):
        res = self.gateway.dispatch_whatsapp_interactive(
            "+12065550103",
            "Upload meter photo for outage verification",
            reply_buttons=["Upload Photo", "Share Location"],
        )
        self.assertEqual(res["sdk_client"], "socialmessaging")
        self.assertEqual(res["operation"], "send_whatsapp_message")
        self.assertEqual(res["channel"], "WhatsApp")
        self.assertTrue(res["message_id"].startswith("wamid."))

    def test_05_dispatch_sesv2_transactional_email(self):
        res = self.gateway.dispatch_ses_transactional_email(
            "ops@enterprise.com",
            "BOL Audit Confirmation",
            "<p>Confirmed</p>",
            audit_hash="abc123def456",
        )
        self.assertEqual(res["sdk_client"], "sesv2")
        self.assertEqual(res["operation"], "send_email")
        self.assertEqual(res["channel"], "Email")

    def test_06_dynamodb_context_graph_persistence(self):
        state = {
            "customer_id": "cust_501",
            "domain": "pharmacy_rx_refill",
            "entities": {"rx_id": "RX-101"},
            "completed_actions": ["initiate_outbound_trigger"],
        }
        res = self.gateway.persist_dynamodb_context_node(state, "hash999")
        self.assertEqual(res["sdk_client"], "dynamodb")
        self.assertEqual(res["operation"], "put_item")

    def test_07_rcs_to_whatsapp_carrier_failover_policy(self):
        ch_ok, _, _, fail_ok = self.agent.score_channel_utility("interactive_carousel_or_tap", rcs_supported=True)
        self.assertEqual(ch_ok, "RCS")
        self.assertFalse(fail_ok)

        ch_fb, svc_fb, _, fail_fb = self.agent.score_channel_utility("interactive_carousel_or_tap", rcs_supported=False)
        self.assertEqual(ch_fb, "WhatsApp")
        self.assertTrue(fail_fb)
        self.assertIn("Failover", svc_fb)

    def test_08_end_to_end_omnichannel_workflow_execution(self):
        resp = lambda_handler({"customer_id": "cust_test_88"})
        self.assertEqual(resp["statusCode"], 200)
        body = json.loads(resp["body"])
        self.assertTrue(body["completed"])
        self.assertTrue(body["context_preserved"])
        self.assertEqual(len(body["turns"]), 4)
        hashes = [t["state_hash"] for t in body["turns"]]
        self.assertEqual(len(set(hashes)), 4)

    def test_09_mcp_server_tools_list_and_call(self):
        list_res = self.mcp.handle_jsonrpc({"jsonrpc": "2.0", "id": 10, "method": "tools/list"})
        tools = list_res["result"]["tools"]
        self.assertEqual(len(tools), 4)
        call_res = self.mcp.handle_jsonrpc({
            "jsonrpc": "2.0",
            "id": 11,
            "method": "tools/call",
            "params": {
                "name": "cds_send_whatsapp_interactive",
                "arguments": {"destination_phone": "+12065550199", "body_text": "Confirm delivery dock"},
            },
        })
        payload = json.loads(call_res["result"]["content"][0]["text"])
        self.assertEqual(payload["sdk_client"], "socialmessaging")

    def test_10_stateless_baseline_fails_cross_channel_memory(self):
        base = StatelessRuleBotBaseline()
        res = base.run_workflow({
            "required_channels": ["SMS", "RCS", "WhatsApp", "Email"],
            "requires_cross_channel_memory": True,
        })
        self.assertFalse(res["completed"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
