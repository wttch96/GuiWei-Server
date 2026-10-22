from app.services import vision_service


def test_extract_json_from_markdown():
    text = '```json\n{"name": "耳机", "tags": ["常用"]}\n```'
    assert vision_service._extract_json(text)["name"] == "耳机"


def test_extract_json_with_explanation():
    text = '识别结果如下：{"name": "水杯", "quantity": "2"} 请确认。'
    assert vision_service._extract_json(text)["quantity"] == "2"


def test_extract_json_invalid():
    assert vision_service._extract_json("完全不是 JSON") is None


def test_normalize_result():
    result = vision_service._normalize(
        {
            "name": "  移动硬盘 ",
            "description": "1TB",
            "category": "电子产品",
            "tags": "数码，备用",
            "quantity": "3",
            "confidence": "1.7",
        },
        "{}",
    )
    assert result["name"] == "移动硬盘"
    assert result["tags"] == ["数码", "备用"]
    assert result["quantity"] == 3
    assert result["confidence"] == 1.0
