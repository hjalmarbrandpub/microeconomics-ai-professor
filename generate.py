"""Step 2: one-off LLM pass. Creates content.json with, per topic:
   key points (core vs supporting), multiple-choice questions, video search queries.
Resumable: topics already in content.json are skipped (use --force to redo, or --only <id>).
"""
import argparse, json, os
from pathlib import Path
from openai import OpenAI

MODEL = os.getenv("GEN_MODEL", "gpt-4.1")
client = OpenAI()                        # reads OPENAI_API_KEY

TOPICS = json.loads(Path("topics.json").read_text(encoding="utf-8"))
OUT = Path("content.json")

SYSTEM = """You are a university professor preparing study material from the course text you are given.
Use ONLY facts, definitions and results that appear in the text. Never add outside facts.
Write math in LaTeX with single dollar signs, e.g. $x_1^*$. Be concise and precise."""


def json_schema(n_questions: int):
    """Strict JSON schema for OpenAI structured outputs (counts are enforced in valid())."""
    props = {
        "key_points": {
            "type": "array",
            "description": "4-8 key points. Mark the 2-3 that a student absolutely must remember as core=true.",
            "items": {"type": "object", "additionalProperties": False, "required": ["text", "core"],
                      "properties": {"text": {"type": "string", "description": "One or two sentences."},
                                     "core": {"type": "boolean"}}},
        },
        "video_queries": {
            "type": "array",
            "description": "2-3 self-contained YouTube search queries that would find a lecture on exactly this topic (include the economics terms).",
            "items": {"type": "string"},
        },
        "mcqs": {
            "type": "array",
            "description": f"Exactly {n_questions} multiple-choice questions." if n_questions else "Leave empty.",
            "items": {"type": "object", "additionalProperties": False,
                      "required": ["question", "options", "answer_index", "explanation"],
                      "properties": {
                          "question": {"type": "string"},
                          "options": {"type": "array", "items": {"type": "string"}, "description": "Exactly 4 options."},
                          "answer_index": {"type": "integer", "description": "0-3, index of the correct option."},
                          "explanation": {"type": "string", "description": "Why the right answer is right. 1-3 sentences."}}},
        },
    }
    return {"type": "json_schema", "json_schema": {"name": "study_material", "strict": True,
            "schema": {"type": "object", "additionalProperties": False, "required": list(props), "properties": props}}}


def n_questions_for(node) -> int:
    if node["type"] in ("chapter", "exercises") or node["title"].lower() == "summary":
        return 0
    if len(node["full_text"]) < 700:
        return 2
    return 5 if node["type"] == "subchapter" else 3


def valid(c, nq):
    if not c.get("key_points"):
        return False
    if not 2 <= len(c.get("video_queries", [])) <= 3:
        return False
    for q in c.get("mcqs", []):
        if len(q["options"]) != 4 or not 0 <= q["answer_index"] <= 3:
            return False
    return len(c.get("mcqs", [])) == nq


def generate(node):
    nq = n_questions_for(node)
    extra = ""
    if nq:
        extra = (f"\nWrite {nq} multiple-choice questions that test understanding (applying a rule, interpreting a result), "
                 "not trivia. Exactly 4 options each, one correct, plausible distractors based on common misconceptions. "
                 "Vary the position of the correct answer.")
    prompt = f"Topic: {node['title']}\n\n<text>\n{node['full_text']}\n</text>\n\nCreate the study material for this topic.{extra}"
    for attempt in range(3):
        r = client.chat.completions.create(
            model=MODEL, response_format=json_schema(nq),
            messages=[{"role": "system", "content": SYSTEM}, {"role": "user", "content": prompt}])
        c = json.loads(r.choices[0].message.content)
        if valid(c, nq):
            return c
        print("   invalid output, retrying...")
    raise RuntimeError(f"could not generate valid content for {node['id']}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--only")
    args = ap.parse_args()
    content = json.loads(OUT.read_text()) if OUT.exists() else {}
    for node in TOPICS:
        if args.only and node["id"] != args.only:
            continue
        if node["type"] == "exercises" or not node["text"] and not node["children"]:
            continue
        if node["id"] in content and not args.force:
            continue
        print(f"-> {node['title']}")
        content[node["id"]] = generate(node)
        OUT.write_text(json.dumps(content, indent=2, ensure_ascii=False), encoding="utf-8")   # save after each topic
    print("done ->", OUT)


if __name__ == "__main__":
    main()
