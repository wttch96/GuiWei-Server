from langchain_core.messages import AIMessage

from app.services import ai_service


class FakeModel:
    def __init__(self, responses):
        self.responses = list(responses)
        self.received = []

    def bind_tools(self, tools):
        self.tools = tools
        return self

    def invoke(self, messages):
        self.received.append(messages)
        if not self.responses:
            return AIMessage(content="结束")
        return self.responses.pop(0)


def test_chat_requires_api_key(client, auth, app):
    app.config["DEEPSEEK_API_KEY"] = ""
    response = client.post("/api/ai/chat", json={"message": "你好"}, headers=auth)
    assert response.status_code == 503
    assert "DEEPSEEK_API_KEY" in response.get_json()["message"]


def test_chat_tool_loop(client, auth, app, monkeypatch):
    app.config["DEEPSEEK_API_KEY"] = "sk-test"
    model = FakeModel(
        [
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "create_room",
                        "args": {"name": "阳台"},
                        "id": "call_1",
                        "type": "tool_call",
                    }
                ],
            ),
            AIMessage(content="已经创建了「阳台」房间。"),
        ]
    )
    monkeypatch.setattr(ai_service, "_build_llm", lambda: model)

    response = client.post(
        "/api/ai/chat",
        json={"message": "帮我新建一个阳台房间", "session_id": "s1"},
        headers=auth,
    )
    assert response.status_code == 200, response.get_json()
    data = response.get_json()["data"]
    assert data["reply"] == "已经创建了「阳台」房间。"
    assert data["tool_calls"][0]["tool"] == "create_room"
    assert data["tool_calls"][0]["result"]["ok"] is True
    assert data["session_id"] == "s1"

    rooms = client.get("/api/rooms", headers=auth).get_json()["data"]
    assert rooms[0]["name"] == "阳台"

    history = client.get(
        "/api/ai/sessions/s1/messages", headers=auth
    ).get_json()["data"]
    assert [row["role"] for row in history] == ["user", "assistant"]
    assert history[1]["tool_trace"][0]["tool"] == "create_room"

    logs = client.get("/api/logs?source=ai", headers=auth).get_json()["data"]
    assert logs["total"] >= 1


def test_chat_returns_item_cards(client, auth, app, monkeypatch):
    app.config["DEEPSEEK_API_KEY"] = "sk-test"
    room = client.post(
        "/api/rooms", json={"name": "客厅"}, headers=auth
    ).get_json()["data"]
    item = client.post(
        "/api/items",
        json={"name": "电视遥控器", "room_id": room["id"], "description": "黑色遥控器"},
        headers=auth,
    ).get_json()["data"]

    model = FakeModel(
        [
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "get_item",
                        "args": {"item_id": item["id"]},
                        "id": "call_1",
                        "type": "tool_call",
                    }
                ],
            ),
            AIMessage(content="**电视遥控器** 在客厅。"),
        ]
    )
    monkeypatch.setattr(ai_service, "_build_llm", lambda: model)

    response = client.post(
        "/api/ai/chat",
        json={"message": "电视遥控器在哪", "session_id": "cards"},
        headers=auth,
    )
    assert response.status_code == 200, response.get_json()
    data = response.get_json()["data"]
    assert data["cards"][0]["id"] == item["id"]
    assert data["cards"][0]["name"] == "电视遥控器"
    assert data["cards"][0]["location_path"] == "客厅"
    assert data["cards"][0]["description"] == "黑色遥控器"

    history = client.get(
        "/api/ai/sessions/cards/messages", headers=auth
    ).get_json()["data"]
    assert history[1]["cards"][0]["id"] == item["id"]


def test_chat_tracks_tokens_and_manages_sessions(client, auth, app, monkeypatch):
    app.config["DEEPSEEK_API_KEY"] = "sk-test"
    model = FakeModel(
        [
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "create_room",
                        "args": {"name": "阳台"},
                        "id": "call_1",
                        "type": "tool_call",
                    }
                ],
                usage_metadata={
                    "input_tokens": 100,
                    "output_tokens": 20,
                    "total_tokens": 120,
                },
            ),
            AIMessage(
                content="已经创建了「阳台」房间。",
                usage_metadata={
                    "input_tokens": 50,
                    "output_tokens": 10,
                    "total_tokens": 60,
                },
            ),
        ]
    )
    monkeypatch.setattr(ai_service, "_build_llm", lambda: model)

    response = client.post(
        "/api/ai/chat",
        json={"message": "帮我新建一个阳台房间", "session_id": "tokens"},
        headers=auth,
    )
    assert response.status_code == 200, response.get_json()
    data = response.get_json()["data"]
    assert data["usage"]["input_tokens"] == 150
    assert data["usage"]["output_tokens"] == 30
    assert data["usage"]["total_tokens"] == 180
    assert data["usage"]["llm_calls"] == 2
    assert data["usage"]["steps"][0]["total_tokens"] == 120
    assert data["tool_calls"][0]["step"] == 1
    assert data["tool_calls"][0]["usage"]["total_tokens"] == 120
    assert data["session_usage"]["total_tokens"] == 180

    history = client.get(
        "/api/ai/sessions/tokens/messages", headers=auth
    ).get_json()["data"]
    assert history[1]["usage"]["total_tokens"] == 180
    assert history[1]["tool_trace"][0]["usage"]["total_tokens"] == 120

    sessions = client.get("/api/ai/sessions", headers=auth).get_json()["data"]
    row = next(item for item in sessions if item["session_id"] == "tokens")
    assert row["title"] == "帮我新建一个阳台房间"
    assert row["message_count"] == 2
    assert row["user_messages"] == 1
    assert row["usage"]["total_tokens"] == 180

    deleted = client.delete("/api/ai/sessions/tokens", headers=auth)
    assert deleted.status_code == 200
    assert deleted.get_json()["data"]["deleted"] == 2
    assert client.get(
        "/api/ai/sessions/tokens/messages", headers=auth
    ).get_json()["data"] == []
    assert client.get("/api/ai/sessions", headers=auth).get_json()["data"] == []
    assert client.delete("/api/ai/sessions/tokens", headers=auth).status_code == 404


def test_ai_status(client, auth):
    data = client.get("/api/ai/status", headers=auth).get_json()["data"]
    assert "chat_configured" in data
    assert data["vision"]["configured"] is False
