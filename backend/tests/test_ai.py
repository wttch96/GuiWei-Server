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


def test_ai_status(client, auth):
    data = client.get("/api/ai/status", headers=auth).get_json()["data"]
    assert "chat_configured" in data
    assert data["vision"]["configured"] is False
