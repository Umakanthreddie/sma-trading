"""
test_webull_login.py — Standalone diagnostic for the Webull paper-trading
connection. Prints exactly what happens at each step (login, account ID,
account fetch) so we can see the real error instead of a swallowed one.

Usage:
  python test_webull_login.py
"""

import traceback
import config

print(f"WEBULL_PAPER = {config.WEBULL_PAPER}")
print(f"WEBULL_PHONE = {config.WEBULL_PHONE!r}")
print(f"WEBULL_DEVICE_ID = {config.WEBULL_DEVICE_ID!r}")
print()

try:
    from webull import webull, paper_webull
    print("✅ webull package imported OK")
except Exception as e:
    print(f"❌ Could not import webull package: {e}")
    raise SystemExit(1)

wb = paper_webull() if config.WEBULL_PAPER else webull()
print(f"✅ Created {'paper_webull' if config.WEBULL_PAPER else 'webull'} instance")
print()

print("Attempting login...")
try:
    login_result = wb.login(
        username=config.WEBULL_PHONE,
        password=config.WEBULL_PASSWORD,
        device_name=config.WEBULL_DEVICE_ID,
    )
    print(f"login() returned: {login_result}")
except Exception:
    print("❌ login() raised an exception:")
    traceback.print_exc()
    raise SystemExit(1)

print()
print(f"wb._access_token present: {bool(getattr(wb, '_access_token', None))}")
print(f"wb._refresh_token present: {bool(getattr(wb, '_refresh_token', None))}")
print(f"wb._account_id: {getattr(wb, '_account_id', None)}")
print()

print("Attempting get_account_id()...")
try:
    acc_id = wb.get_account_id()
    print(f"get_account_id() returned: {acc_id}")
except Exception:
    print("❌ get_account_id() raised an exception:")
    traceback.print_exc()

print()
print("Attempting get_account()...")
try:
    account = wb.get_account()
    print(f"get_account() returned: {account}")
except Exception:
    print("❌ get_account() raised an exception:")
    traceback.print_exc()

print()
print("Attempting get_positions()...")
try:
    positions = wb.get_positions()
    print(f"get_positions() returned: {positions}")
except Exception:
    print("❌ get_positions() raised an exception:")
    traceback.print_exc()
