#!/usr/bin/env python3
"""CallShield AI - Real-time Scam Call Intelligence System.

Usage:
    python3 main.py --help          Show help
    python3 main.py server           Start the FastAPI server
    python3 main.py sdk            Run SDK demo
    python3 main.py test             Run test suite
    python3 main.py demo             Open dashboard
"""

import sys
import os
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))


def run_server():
    """Start the CallShield API server."""
    import os
    import socket
    import uvicorn

    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8000"))
    lan_urls = []
    try:
        hostname = socket.gethostname()
        for _, _, _, _, sockaddr in socket.getaddrinfo(hostname, None, socket.AF_INET):
            ip = sockaddr[0]
            if not ip.startswith("127.") and ip not in lan_urls:
                lan_urls.append(ip)
    except OSError:
        lan_urls = []

    print(f"\n{'='*60}")
    print(f"  CallShield AI v2.3.5 - Server")
    print(f"  API: http://{host}:{port}")
    print(f"  Dashboard: http://{host}:{port}/demo")
    if lan_urls:
        print("  Phone URLs:")
        for ip in lan_urls:
            print(f"    http://{ip}:{port}")
    print(f"{'='*60}\n")

    uvicorn.run(
        "callshield.api.server:app",
        host=host,
        port=port,
        reload=os.getenv("CALLSHIELD_RELOAD", "false").lower() == "true",
        log_level="info"
    )


def run_demo():
    """Print the dashboard URL and optionally open it in a browser."""
    host = os.getenv("HOST", "127.0.0.1")
    port = int(os.getenv("PORT", "8000"))
    url = f"http://{host}:{port}/demo"
    print(f"\nDashboard: {url}")
    print("Start the API first with: python main.py server")
    if os.getenv("CALLSHIELD_OPEN_BROWSER", "false").lower() == "true":
        import webbrowser
        webbrowser.open(url)


def run_sdk_demo():
    """Run the SDK demo."""
    print(f"\n{'='*60}")
    print(f"  CallShield SDK Demo")
    print(f"{'='*60}\n")

    from callshield.sdk import CallShieldSDK

    sdk = CallShieldSDK()

    # Demo scenarios
    demos = [
        ("Normal call", "Hello beta, how are you? I made your favorite food."),
        ("Family emergency scam", "Beta, I'm in trouble. My phone is dead. Send ₹25,000 now, don't tell anyone."),
        ("Bank fraud", "Your KYC has been suspended. Confirm your card number, CVV, and OTP immediately!"),
        ("UPI payment scam", "Mera phone dead hai. Main doosra number se bol raha hoon. ₹25,000 bhejo urgently via UPI."),
    ]

    for name, text in demos:
        result = sdk.analyze_transcript(text)
        print(f"\n📞 {name}")
        print(f"   📝 {text[:80]}...")
        print(f"   🎯 Risk: {result.risk_score}/100 ({result.risk_band})")
        print(f"   🔍 Type: {result.scam_type} (confidence: {result.scam_type_confidence})")
        print(f"   💡 Cues: {', '.join(result.detected_cues[:3]) if result.detected_cues else 'None'}")
        print(f"   📋 Action: {result.recommended_action}")


def run_tests():
    """Run the test suite."""
    print(f"\n{'='*60}")
    print(f"  CallShield Test Suite")
    print(f"{'='*60}\n")
    from callshield.tests.test_evaluation import evaluate_scenarios
    evaluate_scenarios(verbose=True)


def show_help():
    print(__doc__)
    print("\nCommands:")
    print("  server    Start the FastAPI server")
    print("  sdk       Run SDK demo")
    print("  test      Run test suite (50 normal + 50 scam)")
    print("  demo      Open dashboard in browser")
    print("  help      Show this help")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        show_help()
    else:
        cmd = sys.argv[1].lower()
        if cmd == "server":
            run_server()
        elif cmd == "sdk":
            run_sdk_demo()
        elif cmd == "test":
            run_tests()
        elif cmd == "demo":
            run_demo()
        elif cmd == "help":
            show_help()
        else:
            print(f"Unknown command: {cmd}")
            show_help()
