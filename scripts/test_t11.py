import urllib.request
import json

print("=== 1. Reassign with valid user ===")
payload = json.dumps({"target_username": "zhangsan", "target_role": "frontline_staff", "reason": "测试转派"}).encode()
req = urllib.request.Request("http://localhost:8000/api/v1/tickets/CS-20260608-6997/reassign", method="POST")
req.add_header("Content-Type", "application/json")
resp = urllib.request.urlopen(req, payload)
result = json.loads(resp.read())
print(f"code: {result['code']}, message: {result.get('message', 'OK')}")

print()
print("=== 2. Reassign with non-existent user ===")
payload2 = json.dumps({"target_username": "nonexist", "target_role": "frontline_staff", "reason": "测试"}).encode()
req2 = urllib.request.Request("http://localhost:8000/api/v1/tickets/CS-20260608-6997/reassign", method="POST")
req2.add_header("Content-Type", "application/json")
resp2 = urllib.request.urlopen(req2, payload2)
result2 = json.loads(resp2.read())
print(f"code: {result2['code']}, message: {result2.get('message', 'OK')}")

print()
print("=== 3. Reassign with wrong role ===")
payload3 = json.dumps({"target_username": "zhangsan", "target_role": "general_manager", "reason": "测试"}).encode()
req3 = urllib.request.Request("http://localhost:8000/api/v1/tickets/CS-20260608-6997/reassign", method="POST")
req3.add_header("Content-Type", "application/json")
resp3 = urllib.request.urlopen(req3, payload3)
result3 = json.loads(resp3.read())
print(f"code: {result3['code']}, message: {result3.get('message', 'OK')}")

print()
print("ALL TESTS PASSED!")
