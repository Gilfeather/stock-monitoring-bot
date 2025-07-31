#!/usr/bin/env python3
"""
Comprehensive Discord Signature Verification Debugging Script
"""
import json
import os
import boto3
import logging
from typing import Optional, Dict, Any
from nacl.signing import VerifyKey
from nacl.exceptions import BadSignatureError

# Setup logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

class SignatureVerificationDebugger:
    """Debug Discord signature verification issues"""

    def __init__(self):
        self.environment = os.getenv('ENVIRONMENT', 'dev')
        self.project_name = 'stock-monitoring-bot'
        self.ssm_client = boto3.client('ssm', region_name='ap-northeast-1')

    def debug_parameter_retrieval(self) -> Dict[str, Any]:
        """Debug Discord public key parameter retrieval"""
        results = {}
        
        # Test parameter name variations
        parameter_variations = [
            f"/{self.project_name}/{self.environment}/discord-public-key",
            f"/stock-monitoring-bot/dev/discord-public-key",
            "/discord-public-key",
            "discord-public-key"
        ]
        
        for param_name in parameter_variations:
            try:
                response = self.ssm_client.get_parameter(
                    Name=param_name,
                    WithDecryption=True
                )
                value = response['Parameter']['Value']
                results[param_name] = {
                    'success': True,
                    'value_length': len(value),
                    'is_hex': self._is_valid_hex(value),
                    'correct_length': len(value) == 64,
                    'value_preview': value[:8] + '...' + value[-8:] if len(value) > 16 else value
                }
                logger.info(f"✅ Found parameter: {param_name}")
            except Exception as e:
                results[param_name] = {
                    'success': False,
                    'error': str(e),
                    'error_type': type(e).__name__
                }
                logger.error(f"❌ Failed to get parameter {param_name}: {e}")
        
        return results

    def debug_signature_verification_logic(self, public_key: str) -> Dict[str, Any]:
        """Debug the signature verification logic itself"""
        results = {}
        
        # Test public key format
        results['public_key_analysis'] = {
            'length': len(public_key),
            'is_hex': self._is_valid_hex(public_key),
            'correct_length': len(public_key) == 64,
            'can_create_verify_key': False,
            'verify_key_error': None
        }
        
        try:
            verify_key = VerifyKey(bytes.fromhex(public_key))
            results['public_key_analysis']['can_create_verify_key'] = True
            logger.info("✅ Successfully created VerifyKey from public key")
        except Exception as e:
            results['public_key_analysis']['verify_key_error'] = str(e)
            logger.error(f"❌ Failed to create VerifyKey: {e}")
        
        # Test signature verification with dummy data
        test_cases = [
            {
                'name': 'valid_format_invalid_signature',
                'signature': 'a' * 128,  # Valid hex length, invalid signature
                'timestamp': '1234567890',
                'body': '{"type":1,"id":"test","application_id":"123"}'
            },
            {
                'name': 'short_signature',
                'signature': 'a' * 64,  # Too short
                'timestamp': '1234567890',
                'body': '{"type":1}'
            },
            {
                'name': 'non_hex_signature',
                'signature': 'g' * 128,  # Invalid hex
                'timestamp': '1234567890',
                'body': '{"type":1}'
            }
        ]
        
        results['signature_tests'] = {}
        for test_case in test_cases:
            try:
                result = self._test_signature_verification(
                    public_key,
                    test_case['signature'],
                    test_case['timestamp'],
                    test_case['body']
                )
                results['signature_tests'][test_case['name']] = result
            except Exception as e:
                results['signature_tests'][test_case['name']] = {
                    'error': str(e),
                    'error_type': type(e).__name__
                }
        
        return results
    
    def debug_header_processing(self) -> Dict[str, Any]:
        """Debug header processing for common API Gateway issues"""
        results = {}
        
        # Test header name variations (API Gateway may normalize)
        test_headers = {
            'original_case': {
                'X-Signature-Ed25519': 'a' * 128,
                'X-Signature-Timestamp': '1234567890'
            },
            'lowercase': {
                'x-signature-ed25519': 'a' * 128,
                'x-signature-timestamp': '1234567890'
            },
            'mixed_case': {
                'X-signature-ED25519': 'a' * 128,
                'x-Signature-Timestamp': '1234567890'
            }
        }
        
        for case_name, headers in test_headers.items():
            extracted = self._extract_signature_headers(headers)
            results[case_name] = {
                'signature_found': bool(extracted['signature']),
                'timestamp_found': bool(extracted['timestamp']),
                'signature_length': len(extracted['signature']) if extracted['signature'] else 0,
                'timestamp_value': extracted['timestamp']
            }
        
        return results
    
    def debug_environment_configuration(self) -> Dict[str, Any]:
        """Debug environment configuration"""
        results = {}
        
        # Check environment variables
        env_vars = [
            'ENVIRONMENT',
            'AWS_REGION',
            'DYNAMODB_TABLE_STOCKS',
            'DISCORD_PUBLIC_KEY_PARAMETER'
        ]
        
        results['environment_variables'] = {}
        for var in env_vars:
            value = os.getenv(var)
            results['environment_variables'][var] = {
                'set': value is not None,
                'value': value if value else None,
                'length': len(value) if value else 0
            }
        
        # Check AWS credentials
        try:
            # Test SSM access
            self.ssm_client.describe_parameters(MaxResults=1)
            results['aws_access'] = {'ssm_accessible': True}
        except Exception as e:
            results['aws_access'] = {
                'ssm_accessible': False,
                'error': str(e)
            }
        
        return results

    def run_comprehensive_debug(self) -> Dict[str, Any]:
        """Run all debugging checks"""
        logger.info("🔍 Starting comprehensive Discord signature verification debugging...")
        
        results = {
            'environment_check': self.debug_environment_configuration(),
            'parameter_retrieval': self.debug_parameter_retrieval(),
            'header_processing': self.debug_header_processing()
        }
        
        # Try to get a public key for signature testing
        public_key = None
        for param_name, param_result in results['parameter_retrieval'].items():
            if param_result.get('success') and param_result.get('correct_length'):
                # Get the actual key for testing
                try:
                    response = self.ssm_client.get_parameter(Name=param_name, WithDecryption=True)
                    public_key = response['Parameter']['Value']
                    break
                except:
                    continue
        
        if public_key:
            results['signature_verification'] = self.debug_signature_verification_logic(public_key)
        else:
            results['signature_verification'] = {'error': 'No valid public key found for testing'}
        
        return results

    def _is_valid_hex(self, value: str) -> bool:
        """Check if string is valid hexadecimal"""
        try:
            int(value, 16)
            return True
        except ValueError:
            return False

    def _extract_signature_headers(self, headers: Dict[str, str]) -> Dict[str, str]:
        """Extract signature headers (mimicking the production logic)"""
        signature = ''
        timestamp = ''
        
        for key, value in headers.items():
            key_lower = key.lower()
            if key_lower == 'x-signature-ed25519':
                signature = value
            elif key_lower == 'x-signature-timestamp':
                timestamp = value
        
        return {'signature': signature, 'timestamp': timestamp}
    
    def _test_signature_verification(self, public_key: str, signature: str, timestamp: str, body: str) -> Dict[str, Any]:
        """Test signature verification with given parameters"""
        result = {
            'signature_length_valid': len(signature) == 128,
            'signature_is_hex': self._is_valid_hex(signature),
            'verification_attempted': False,
            'verification_result': False,
            'error': None
        }
        
        try:
            if len(signature) != 128:
                result['error'] = f"Invalid signature length: {len(signature)}"
                return result
            
            if not self._is_valid_hex(signature):
                result['error'] = "Signature is not valid hex"
                return result
            
            verify_key = VerifyKey(bytes.fromhex(public_key))
            message = f'{timestamp}{body}'.encode()
            signature_bytes = bytes.fromhex(signature)
            
            result['verification_attempted'] = True
            verify_key.verify(message, signature_bytes)
            result['verification_result'] = True
            
        except BadSignatureError:
            result['verification_result'] = False
            result['error'] = "BadSignatureError (expected for dummy data)"
        except Exception as e:
            result['error'] = f"{type(e).__name__}: {str(e)}"
        
        return result

    def print_debug_report(self, results: Dict[str, Any]):
        """Print a formatted debug report"""
        print("\n" + "="*60)
        print("🔍 DISCORD SIGNATURE VERIFICATION DEBUG REPORT")
        print("="*60)
        
        # Environment Check
        print("\n📋 ENVIRONMENT CONFIGURATION:")
        env_check = results['environment_check']
        for var, details in env_check['environment_variables'].items():
            status = "✅" if details['set'] else "❌"
            print(f"  {status} {var}: {'SET' if details['set'] else 'NOT SET'}")
        
        if 'aws_access' in env_check:
            aws_status = "✅" if env_check['aws_access']['ssm_accessible'] else "❌"
            print(f"  {aws_status} AWS SSM Access: {'OK' if env_check['aws_access']['ssm_accessible'] else 'FAILED'}")
        
        # Parameter Retrieval
        print("\n🔑 PARAMETER STORE ACCESS:")
        param_results = results['parameter_retrieval']
        found_valid_key = False
        for param_name, details in param_results.items():
            if details['success']:
                status = "✅" if details['correct_length'] and details['is_hex'] else "⚠️"
                print(f"  {status} {param_name}")
                print(f"      Length: {details['value_length']} ({'OK' if details['correct_length'] else 'INVALID'})")
                print(f"      Format: {'HEX' if details['is_hex'] else 'INVALID'}")
                print(f"      Preview: {details['value_preview']}")
                if details['correct_length'] and details['is_hex']:
                    found_valid_key = True
            else:
                print(f"  ❌ {param_name}: {details['error']}")
        
        # Header Processing
        print("\n📡 HEADER PROCESSING:")
        header_results = results['header_processing']
        for case_name, details in header_results.items():
            sig_status = "✅" if details['signature_found'] else "❌"
            ts_status = "✅" if details['timestamp_found'] else "❌"
            print(f"  {case_name.upper()}:")
            print(f"    {sig_status} Signature Found: {details['signature_found']}")
            print(f"    {ts_status} Timestamp Found: {details['timestamp_found']}")
        
        # Signature Verification
        print("\n🔐 SIGNATURE VERIFICATION LOGIC:")
        sig_results = results.get('signature_verification', {})
        if 'error' in sig_results:
            print(f"  ❌ {sig_results['error']}")
        else:
            if 'public_key_analysis' in sig_results:
                key_analysis = sig_results['public_key_analysis']
                key_status = "✅" if key_analysis['can_create_verify_key'] else "❌"
                print(f"  {key_status} Public Key Validation:")
                print(f"      Length: {key_analysis['length']} ({'OK' if key_analysis['correct_length'] else 'INVALID'})")
                print(f"      Format: {'HEX' if key_analysis['is_hex'] else 'INVALID'}")
                print(f"      VerifyKey Creation: {'OK' if key_analysis['can_create_verify_key'] else 'FAILED'}")
                if key_analysis['verify_key_error']:
                    print(f"      Error: {key_analysis['verify_key_error']}")
            
            if 'signature_tests' in sig_results:
                print("  📝 Test Cases:")
                for test_name, test_result in sig_results['signature_tests'].items():
                    if 'error' in test_result:
                        print(f"    ❌ {test_name}: {test_result['error']}")
                    else:
                        print(f"    📋 {test_name}:")
                        print(f"        Verification Attempted: {test_result['verification_attempted']}")
                        print(f"        Result: {test_result['verification_result']}")
                        if test_result['error']:
                            print(f"        Error: {test_result['error']}")
        
        # Summary and Recommendations
        print("\n🎯 DIAGNOSIS & RECOMMENDATIONS:")
        
        if not found_valid_key:
            print("  ❌ CRITICAL: No valid Discord public key found in Parameter Store")
            print("     → Verify the public key is stored with correct parameter name")
            print("     → Ensure the key is 64 characters (32 bytes) of hex")
            print("     → Check IAM permissions for Parameter Store access")
        
        if not env_check.get('aws_access', {}).get('ssm_accessible', False):
            print("  ❌ CRITICAL: Cannot access AWS Parameter Store")
            print("     → Check AWS credentials and IAM permissions")
            print("     → Verify Lambda execution role has ssm:GetParameter permission")
        
        # Check if signature verification logic has issues
        if 'signature_verification' in results and 'public_key_analysis' in results['signature_verification']:
            key_analysis = results['signature_verification']['public_key_analysis']
            if not key_analysis['can_create_verify_key']:
                print("  ❌ CRITICAL: Cannot create VerifyKey from public key")
                print("     → Public key format is invalid")
                print("     → Verify key is exactly 64 hex characters")

        print("\n" + "="*60)


def main():
    """Main debugging function"""
    debugger = SignatureVerificationDebugger()
    results = debugger.run_comprehensive_debug()
    debugger.print_debug_report(results)
    
    # Save detailed results to file
    with open('signature_debug_results.json', 'w') as f:
        json.dump(results, f, indent=2, default=str)
    
    print(f"\n💾 Detailed results saved to: signature_debug_results.json")


if __name__ == "__main__":
    main()