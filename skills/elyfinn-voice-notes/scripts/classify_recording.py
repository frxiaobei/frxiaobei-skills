#!/usr/bin/env python3
"""
录音分类脚本

根据转录文本判断录音类型，返回分类结果。
"""

import json
import sys
from pathlib import Path

# 分类 prompt 模板
CLASSIFICATION_PROMPT = """请分析这段录音转录的类型。

<transcript>
{transcript_preview}
</transcript>

## 类型定义

| 类型 | 典型特征 |
|-----|---------|
| `meeting` | 内部会议/项目会/周会。多人讨论，有来回对话，讨论议题，产出决策和待办 |
| `keynote` | 发布会/讲座/演讲/播客。单人或少数人单向输出，有观点、有论据、有金句 |
| `interview` | 招聘面试。一问一答模式，面试官提问，候选人回答，评估候选人能力 |
| `customer` | 客户电话/BD沟通/销售跟进。商务场景，讨论需求、报价、合作 |
| `brainstorm` | 头脑风暴/创意讨论。发散思维，多人抛出想法，不急于下结论 |
| `consult` | 专家咨询/1对1请教。请教专家，获取建议和洞察 |
| `note` | 个人语音笔记/随手记。自言自语，记录想法或备忘 |

## 判断要点

1. 看参与者数量和角色：单人→note/keynote，多人对话→meeting/brainstorm/customer
2. 看对话模式：单向输出→keynote，一问一答→interview，来回讨论→meeting
3. 看内容性质：有观点论据→keynote，有任务分配→meeting，有商务谈判→customer
4. 看语境线索：提到「面试」「候选人」→interview，提到「客户」「报价」→customer

## 输出格式（JSON）

```json
{{
  "type": "meeting|keynote|interview|customer|brainstorm|consult|note",
  "confidence": 0.0-1.0,
  "reason": "一句话判断依据",
  "participants": ["识别到的参与者/角色"],
  "topic": "主题关键词"
}}
```

只输出 JSON，不要其他内容。"""

# 类型对应的中文前缀
TYPE_PREFIX = {
    "meeting": "会议",
    "keynote": "讲座",
    "interview": "面试",
    "customer": "客户",
    "brainstorm": "头脑风暴",
    "consult": "咨询",
    "note": "笔记"
}


def classify_transcript(transcript: str, preview_chars: int = 3000) -> dict:
    """
    分类转录文本
    
    Args:
        transcript: 完整转录文本
        preview_chars: 用于分类的预览字符数
    
    Returns:
        分类结果 dict
    """
    # 截取预览部分
    preview = transcript[:preview_chars]
    if len(transcript) > preview_chars:
        preview += "\n\n[... 后续内容省略 ...]"
    
    # 构建 prompt
    prompt = CLASSIFICATION_PROMPT.format(transcript_preview=preview)
    
    return {
        "prompt": prompt,
        "preview_length": len(preview)
    }


def parse_classification_result(response: str) -> dict:
    """
    解析分类结果
    
    Args:
        response: AI 返回的 JSON 字符串
    
    Returns:
        解析后的分类结果
    """
    # 尝试提取 JSON
    try:
        # 处理 markdown code block
        if "```json" in response:
            start = response.find("```json") + 7
            end = response.find("```", start)
            response = response[start:end].strip()
        elif "```" in response:
            start = response.find("```") + 3
            end = response.find("```", start)
            response = response[start:end].strip()
        
        result = json.loads(response)
        
        # 验证必要字段
        if "type" not in result:
            result["type"] = "note"  # 默认为笔记
        if "confidence" not in result:
            result["confidence"] = 0.5
        
        # 添加中文前缀
        result["type_prefix"] = TYPE_PREFIX.get(result["type"], "笔记")
        
        return result
    
    except json.JSONDecodeError as e:
        return {
            "type": "note",
            "confidence": 0.3,
            "reason": f"JSON 解析失败: {e}",
            "participants": [],
            "topic": "未知",
            "type_prefix": "笔记"
        }


def get_template_path(recording_type: str) -> Path:
    """获取对应类型的模板路径"""
    templates_dir = Path(__file__).parent.parent / "templates"
    template_file = templates_dir / f"{recording_type}.md"
    
    if template_file.exists():
        return template_file
    
    # 默认使用 note 模板
    return templates_dir / "note.md"


if __name__ == "__main__":
    # 测试用例
    test_cases = [
        {
            "name": "keynote",
            "text": "每天在千千万万的科技信息里穿梭...我做了张科技地图...横轴是空间尺度，从最小的夸克到宇宙边缘..."
        },
        {
            "name": "meeting", 
            "text": "好，我们开始今天的项目评审会。参加的有张三、李四、王五。第一个议题是上周的进度..."
        },
        {
            "name": "interview",
            "text": "好的，我们开始面试。我是技术面试官小北，今天面试的是前端开发岗位..."
        }
    ]
    
    for case in test_cases:
        result = classify_transcript(case["text"])
        print(f"\n=== {case['name']} ===")
        print(f"Preview length: {result['preview_length']}")
        print(f"Prompt (first 200 chars): {result['prompt'][:200]}...")
