#!/usr/bin/env python3
"""
Test OpenAI endpoint configuration and dynamic selection.

This test validates that the model-to-endpoint mapping works correctly
and that the utility functions handle both chat and completion endpoints.
"""
import unittest
from unittest.mock import Mock, patch, MagicMock
import sys
from pathlib import Path

# Add scripts directory to path
sys.path.insert(0, str(Path(__file__).parent))

from global_config import get_openai_endpoint_type, OPENAI_MODEL_ENDPOINTS
from openai_utils import (
    create_openai_completion,
    extract_completion_text,
    get_finish_reason,
    _messages_to_prompt,
    _prompt_to_messages
)


class TestEndpointConfiguration(unittest.TestCase):
    """Test model-to-endpoint mapping configuration."""
    
    def test_chat_models(self):
        """Test that chat models map to 'chat' endpoint."""
        chat_models = [
            "gpt-3.5-turbo",
            "gpt-4",
            "gpt-4-turbo",
            "gpt-4o",
            "gpt-5-mini"
        ]
        
        for model in chat_models:
            with self.subTest(model=model):
                endpoint = get_openai_endpoint_type(model)
                self.assertEqual(endpoint, "chat", 
                               f"Model {model} should use chat endpoint")
    
    def test_responses_models(self):
        """Test that responses models map to 'responses' endpoint."""
        responses_models = ["gpt-5.2-pro"]
        
        for model in responses_models:
            with self.subTest(model=model):
                endpoint = get_openai_endpoint_type(model)
                self.assertEqual(endpoint, "responses",
                               f"Model {model} should use responses endpoint")
    
    def test_unknown_model_defaults_to_chat(self):
        """Test that unknown models default to chat endpoint."""
        unknown_model = "unknown-model-xyz"
        endpoint = get_openai_endpoint_type(unknown_model)
        self.assertEqual(endpoint, "chat",
                        "Unknown models should default to chat endpoint")
    
    def test_model_endpoints_dict_structure(self):
        """Test that OPENAI_MODEL_ENDPOINTS is properly structured."""
        self.assertIsInstance(OPENAI_MODEL_ENDPOINTS, dict)
        self.assertGreater(len(OPENAI_MODEL_ENDPOINTS), 0)
        
        # All values should be either "chat", "responses", or "completion"
        for model, endpoint in OPENAI_MODEL_ENDPOINTS.items():
            self.assertIn(endpoint, ["chat", "responses", "completion"],
                         f"Invalid endpoint type for {model}: {endpoint}")


class TestCompletionCreation(unittest.TestCase):
    """Test the create_openai_completion function."""
    
    @patch('openai_utils.get_openai_endpoint_type')
    def test_chat_completion_call(self, mock_get_endpoint):
        """Test that chat models use chat.completions.create."""
        mock_get_endpoint.return_value = "chat"
        
        # Create mock client
        mock_client = Mock()
        mock_response = Mock()
        mock_client.chat.completions.create.return_value = mock_response
        
        # Call function
        messages = [{"role": "user", "content": "Hello"}]
        result = create_openai_completion(
            client=mock_client,
            model="gpt-4",
            messages=messages,
            max_completion_tokens=1000
        )
        
        # Verify chat endpoint was called
        mock_client.chat.completions.create.assert_called_once()
        call_args = mock_client.chat.completions.create.call_args[1]
        self.assertEqual(call_args["model"], "gpt-4")
        self.assertEqual(call_args["messages"], messages)
        self.assertEqual(call_args["max_completion_tokens"], 1000)
        self.assertEqual(result, mock_response)
    
    @patch('openai_utils.get_openai_endpoint_type')
    def test_completion_call(self, mock_get_endpoint):
        """Test that completion models use completions.create."""
        mock_get_endpoint.return_value = "completion"
        
        # Create mock client
        mock_client = Mock()
        mock_response = Mock()
        mock_client.completions.create.return_value = mock_response
        
        # Call function with messages (should be converted to prompt)
        messages = [{"role": "user", "content": "Hello"}]
        result = create_openai_completion(
            client=mock_client,
            model="gpt-3.5-turbo-instruct",  # Legacy completion model
            messages=messages,
            max_completion_tokens=1000
        )
        
        # Verify completion endpoint was called
        mock_client.completions.create.assert_called_once()
        call_args = mock_client.completions.create.call_args[1]
        self.assertEqual(call_args["model"], "gpt-3.5-turbo-instruct")
        self.assertIn("prompt", call_args)
        self.assertEqual(call_args["max_tokens"], 1000)
        self.assertEqual(result, mock_response)
    
    @patch('openai_utils.get_openai_endpoint_type')
    def test_completion_with_direct_prompt(self, mock_get_endpoint):
        """Test completion endpoint with direct prompt string."""
        mock_get_endpoint.return_value = "completion"
        
        mock_client = Mock()
        mock_response = Mock()
        mock_client.completions.create.return_value = mock_response
        
        prompt = "Complete this sentence"
        result = create_openai_completion(
            client=mock_client,
            model="gpt-3.5-turbo-instruct",
            prompt=prompt,
            max_tokens=500
        )
        
        call_args = mock_client.completions.create.call_args[1]
        self.assertEqual(call_args["prompt"], prompt)
        self.assertEqual(call_args["max_tokens"], 500)
    
    @patch('openai_utils.get_openai_endpoint_type')
    def test_responses_api_call(self, mock_get_endpoint):
        """Test that responses models use responses.create."""
        mock_get_endpoint.return_value = "responses"
        
        # Create mock client
        mock_client = Mock()
        mock_response = Mock()
        mock_client.responses.create.return_value = mock_response
        
        # Call function with messages
        messages = [
            {"role": "system", "content": "You are helpful"},
            {"role": "user", "content": "Hello"}
        ]
        result = create_openai_completion(
            client=mock_client,
            model="gpt-5.2-pro",
            messages=messages,
            max_completion_tokens=1000,
            tools=[{"type": "web_search"}]
        )
        
        # Verify responses endpoint was called
        mock_client.responses.create.assert_called_once()
        call_args = mock_client.responses.create.call_args[1]
        self.assertEqual(call_args["model"], "gpt-5.2-pro")
        self.assertIn("input", call_args)  # Responses API uses 'input' not 'prompt'
        self.assertEqual(call_args["max_output_tokens"], 1000)
        # Reasoning controls are optional and model-dependent; the helper should
        # not force a default reasoning.effort (some models reject it).
        self.assertNotIn("reasoning", call_args)
        self.assertEqual(call_args["tools"], [{"type": "web_search"}])
        # Verify that temperature is NOT passed (not supported by Responses API)
        self.assertNotIn("temperature", call_args)
        self.assertEqual(result, mock_response)
    
    @patch('openai_utils.get_openai_endpoint_type')
    def test_responses_api_no_temperature_even_if_passed(self, mock_get_endpoint):
        """Test that temperature is not passed to Responses API even if provided."""
        mock_get_endpoint.return_value = "responses"
        
        mock_client = Mock()
        mock_response = Mock()
        mock_client.responses.create.return_value = mock_response
        
        # Call function with temperature parameter (should be ignored)
        messages = [{"role": "user", "content": "Hello"}]
        result = create_openai_completion(
            client=mock_client,
            model="gpt-5.2-pro",
            messages=messages,
            max_completion_tokens=1000,
            temperature=0.7  # This should NOT be passed to Responses API
        )
        
        # Verify that temperature was NOT passed
        call_args = mock_client.responses.create.call_args[1]
        self.assertNotIn("temperature", call_args)
    
    @patch('openai_utils.get_openai_endpoint_type')
    def test_tools_info_for_completion(self, mock_get_endpoint):
        """Test that tools parameter logs info message for completion models."""
        mock_get_endpoint.return_value = "completion"
        
        mock_client = Mock()
        mock_response = Mock()
        mock_client.completions.create.return_value = mock_response
        
        with self.assertLogs('openai_utils', level='INFO') as log:
            create_openai_completion(
                client=mock_client,
                model="gpt-3.5-turbo-instruct",  # Legacy completion model
                prompt="Test",
                tools=[{"type": "web_search"}]
            )
            
            # Check that info message was logged
            self.assertTrue(any("Tools parameter not supported" in message 
                              for message in log.output))


class TestResponseExtraction(unittest.TestCase):
    """Test response extraction functions."""
    
    @patch('openai_utils.get_openai_endpoint_type')
    def test_extract_chat_completion_text(self, mock_get_endpoint):
        """Test extracting text from chat completion response."""
        mock_get_endpoint.return_value = "chat"
        
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = "  Hello World  "
        
        text = extract_completion_text(mock_response, "gpt-4")
        self.assertEqual(text, "Hello World")
    
    @patch('openai_utils.get_openai_endpoint_type')
    def test_extract_completion_text(self, mock_get_endpoint):
        """Test extracting text from completion response."""
        mock_get_endpoint.return_value = "completion"
        
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].text = "  Response text  "
        
        text = extract_completion_text(mock_response, "gpt-3.5-turbo-instruct")
        self.assertEqual(text, "Response text")
    
    @patch('openai_utils.get_openai_endpoint_type')
    def test_extract_responses_text_with_output_text(self, mock_get_endpoint):
        """Test extracting text from Responses API response with output_text."""
        mock_get_endpoint.return_value = "responses"
        
        mock_response = Mock()
        mock_response.output_text = "  Response from Responses API  "
        
        text = extract_completion_text(mock_response, "gpt-5.2-pro")
        self.assertEqual(text, "Response from Responses API")
    
    @patch('openai_utils.get_openai_endpoint_type')
    def test_extract_responses_text_with_choices(self, mock_get_endpoint):
        """Test extracting text from Responses API response with choices format."""
        mock_get_endpoint.return_value = "responses"
        
        # Create mock without output_text attribute
        mock_response = Mock(spec=['choices'])
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = "  Response via choices  "
        
        text = extract_completion_text(mock_response, "gpt-5.2-pro")
        self.assertEqual(text, "Response via choices")
    
    @patch('openai_utils.get_openai_endpoint_type')
    def test_extract_responses_incomplete_response(self, mock_get_endpoint):
        """Test handling incomplete response from Responses API."""
        mock_get_endpoint.return_value = "responses"
        
        # Create mock for incomplete response
        mock_response = Mock()
        mock_response.status = 'incomplete'
        mock_incomplete_details = Mock()
        mock_incomplete_details.reason = 'max_output_tokens'
        mock_response.incomplete_details = mock_incomplete_details
        mock_response.output_text = None
        mock_response.output = []
        
        # Should raise ValueError with clear message about incomplete response
        with self.assertRaises(ValueError) as context:
            extract_completion_text(mock_response, "gpt-5.2-pro")
        
        self.assertIn("incomplete", str(context.exception).lower())
        self.assertIn("max_output_tokens", str(context.exception))
    
    def test_get_finish_reason(self):
        """Test extracting finish reason from response."""
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].finish_reason = "stop"
        
        reason = get_finish_reason(mock_response, "gpt-4")
        self.assertEqual(reason, "stop")
    
    @patch('openai_utils.get_openai_endpoint_type')
    def test_get_finish_reason_incomplete_status(self, mock_get_endpoint):
        """Test handling incomplete status in finish reason."""
        mock_get_endpoint.return_value = "responses"
        
        # Create mock for incomplete response
        mock_response = Mock(spec=['status', 'incomplete_details'])
        mock_response.status = 'incomplete'
        mock_incomplete_details = Mock()
        mock_incomplete_details.reason = 'max_output_tokens'
        mock_response.incomplete_details = mock_incomplete_details
        
        reason = get_finish_reason(mock_response, "gpt-5.2-pro")
        self.assertEqual(reason, "length")
    
    @patch('openai_utils.get_openai_endpoint_type')
    def test_get_finish_reason_incomplete_status_dict(self, mock_get_endpoint):
        """Test handling incomplete status with dict incomplete_details."""
        mock_get_endpoint.return_value = "responses"
        
        # Create mock for incomplete response with dict format
        mock_response = Mock(spec=['status', 'incomplete_details'])
        mock_response.status = 'incomplete'
        mock_response.incomplete_details = {'reason': 'max_output_tokens'}
        
        reason = get_finish_reason(mock_response, "gpt-5.2-pro")
        self.assertEqual(reason, "length")



class TestMessageConversion(unittest.TestCase):
    """Test message format conversion utilities."""
    
    def test_messages_to_prompt(self):
        """Test converting messages array to prompt string."""
        messages = [
            {"role": "system", "content": "You are helpful"},
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there"}
        ]
        
        prompt = _messages_to_prompt(messages)
        
        self.assertIn("System: You are helpful", prompt)
        self.assertIn("User: Hello", prompt)
        self.assertIn("Assistant: Hi there", prompt)
    
    def test_prompt_to_messages(self):
        """Test converting prompt string to messages array."""
        prompt = "This is a test prompt"
        messages = _prompt_to_messages(prompt)
        
        self.assertEqual(len(messages), 1)
        self.assertEqual(messages[0]["role"], "user")
        self.assertEqual(messages[0]["content"], prompt)


class TestErrorHandling(unittest.TestCase):
    """Test error handling in utility functions."""
    
    @patch('openai_utils.get_openai_endpoint_type')
    def test_missing_messages_for_chat(self, mock_get_endpoint):
        """Test that missing messages raises error for chat endpoint."""
        mock_get_endpoint.return_value = "chat"
        
        mock_client = Mock()
        
        with self.assertRaises(ValueError) as context:
            create_openai_completion(
                client=mock_client,
                model="gpt-4",
                messages=None  # Missing required parameter
            )
        
        self.assertIn("messages are required", str(context.exception))
    
    @patch('openai_utils.get_openai_endpoint_type')
    def test_missing_prompt_for_completion(self, mock_get_endpoint):
        """Test that missing prompt raises error for completion endpoint."""
        mock_get_endpoint.return_value = "completion"
        
        mock_client = Mock()
        
        with self.assertRaises(ValueError) as context:
            create_openai_completion(
                client=mock_client,
                model="gpt-3.5-turbo-instruct",  # Legacy completion model
                prompt=None,  # Missing required parameter
                messages=None
            )
        
        self.assertIn("prompt is required", str(context.exception))


def run_tests():
    """Run all tests."""
    unittest.main(argv=[''], verbosity=2, exit=False)


if __name__ == '__main__':
    run_tests()
