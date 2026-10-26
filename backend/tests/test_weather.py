def _fake_current():
    return {
        "city": "天津",
        "weather": "晴",
        "weather_code": 0,
        "temperature": 20.4,
        "apparent_temperature": 19.0,
        "humidity": 40,
        "wind_speed": 5.0,
        "temp_max": 25.0,
        "temp_min": 12.0,
        "precipitation_probability": 10,
        "observed_at": "2026-10-26T12:00",
        "source": "open-meteo",
    }


def test_weather_refresh_and_cache(client, auth, app, monkeypatch):
    from app.services import weather_service

    calls = {"count": 0}

    def fake_fetch():
        calls["count"] += 1
        return _fake_current()

    monkeypatch.setattr(weather_service, "fetch", fake_fetch)
    with app.app_context():
        data = weather_service.refresh()
    assert data["temperature"] == 20.4
    assert data["weather"] == "晴"
    assert data["available"] is True

    payload = client.get("/api/weather", headers=auth).get_json()["data"]
    assert payload["city"] == "天津"
    assert payload["temperature"] == 20.4
    assert payload["stale"] is False
    assert calls["count"] == 1  # 命中缓存，不会重复请求

    with app.app_context():
        context = weather_service.prompt_context()
    assert "天津当前晴" in context
    assert "20°C" in context
    assert "12~25°C" in context


def test_weather_tool_rejects_other_city(app):
    from app.tools.weather_tools import get_weather

    with app.app_context():
        output = get_weather.invoke({"city": "北京"})
    assert "仅缓存了天津" in output


def test_weather_codes():
    from app.services.weather_service import describe_code

    assert describe_code(0) == "晴"
    assert describe_code(61) == "小雨"
    assert describe_code(999) == "未知"
    assert describe_code(None) == "未知"


def test_weather_is_injected_into_prompt(client, auth, app, monkeypatch):
    from langchain_core.messages import AIMessage

    from app.services import ai_service, weather_service
    from tests.test_ai import FakeModel

    app.config["DEEPSEEK_API_KEY"] = "sk-test"
    monkeypatch.setattr(
        weather_service, "prompt_context", lambda: "天津当前晴，气温 20°C。"
    )
    model = FakeModel([AIMessage(content="今天天津晴，约 20°C。")])
    monkeypatch.setattr(ai_service, "_build_llm", lambda: model)

    response = client.post(
        "/api/ai/chat", json={"message": "今天天气怎么样"}, headers=auth
    )
    assert response.status_code == 200, response.get_json()
    system_text = model.received[0][0].content
    assert "天津当前晴" in system_text
    assert "{weather}" not in system_text
