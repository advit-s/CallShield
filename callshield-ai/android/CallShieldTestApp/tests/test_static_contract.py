from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def read(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


def test_android_test_app_contract():
    manifest = read("app/src/main/AndroidManifest.xml")
    main_activity = read("app/src/main/java/ai/callshield/testapp/MainActivity.java")
    api_client = read("app/src/main/java/ai/callshield/testapp/CallShieldTestApiClient.java")
    strings = read("app/src/main/res/values/strings.xml")

    assert 'package="ai.callshield.testapp"' not in manifest
    assert 'android.permission.RECORD_AUDIO' not in manifest
    assert 'android.permission.INTERNET' in manifest
    assert 'Testing Only' in main_activity
    assert 'http://10.0.2.2:8000' in main_activity
    assert '/health' in api_client
    assert '/model-status' in api_client
    assert '/analyze-transcript' in api_client
    assert '/score-call' in api_client
    assert 'CallShield Test App' in strings
