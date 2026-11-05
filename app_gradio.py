"""Gradio version of the AI Professor.  Run:  python app_gradio.py
Needs topics.json + content.json (python parse.py ..., python generate.py) and OPENAI_API_KEY.
Reuses the chat / scope-guard / video logic from server.py.
"""
import html, sys
import gradio as gr
from server import TOPICS, CONTENT, chat, ChatIn, videos

LATEX = [{"left": "$$", "right": "$$", "display": True}, {"left": "$", "right": "$", "display": False}]
CHOICES = [(("↳ " if t["level"] == 3 else "") + t["title"], t["id"]) for t in TOPICS]
BY_ID = {t["id"]: t for t in TOPICS}
esc = html.escape
fresh = lambda: {"i": 0, "score": 0, "checked": False, "picked": None}


# ---------- content views ----------
def points_md(tid):
    c = CONTENT.get(tid)
    if not c:
        return "*No key points for this topic. See the source text tab.*"
    core = [k["text"] for k in c["key_points"] if k["core"]]
    rest = [k["text"] for k in c["key_points"] if not k["core"]]
    out = "### Must know\n" + "\n".join(f"- **{t}**" for t in core)
    if rest:
        out += "\n\n### Also worth knowing\n" + "\n".join(f"- {t}" for t in rest)
    return out


def videos_html(tid):
    if tid not in CONTENT:
        return "<p>No videos for this topic.</p>"
    try:
        d = videos(tid)
    except Exception as e:
        return f"<p>Could not load videos: {esc(str(e))}</p>"
    h = ""
    for v in d["videos"]:
        h += (f'<div style="margin-bottom:18px"><iframe width="100%" height="315" frameborder="0" allowfullscreen '
              f'src="https://www.youtube-nocookie.com/embed/{esc(v["id"])}"></iframe>'
              f'<div><b>{esc(v["title"])}</b> · {esc(v["channel"])}</div></div>')
    h += "<p>YouTube searches for this topic" + (" (results may not match the text exactly)" if d["videos"] else
          " (set YOUTUBE_API_KEY to embed videos here)") + ":</p><ul>"
    h += "".join(f'<li><a href="{esc(q["url"])}" target="_blank" rel="noopener">{esc(q["q"])}</a></li>' for q in d["queries"])
    return h + "</ul>"


# ---------- quiz ----------
def quiz_view(tid, st):
    """-> (question_md, radio, check_btn, feedback_md, next_btn)"""
    qs = CONTENT.get(tid, {}).get("mcqs", [])
    hide = gr.update(visible=False)
    if not qs:
        return "*No quiz for this topic.*", gr.update(choices=[], visible=False), hide, "", hide
    if st["i"] >= len(qs):
        return (f"### Finished\n\n## Score: {st['score']} / {len(qs)}", gr.update(visible=False), hide, "",
                gr.update(visible=True, value="Try again"))
    q = qs[st["i"]]
    choices = [(o, k) for k, o in enumerate(q["options"])]
    head = f"**Question {st['i'] + 1} of {len(qs)}**\n\n{q['question']}"
    if st["checked"]:
        ok = st["picked"] == q["answer_index"]
        fb = ("✅ **Correct.** " if ok else f"❌ **Not quite.** Correct answer: {q['options'][q['answer_index']]}\n\n") + q["explanation"]
        last = st["i"] + 1 == len(qs)
        return (head, gr.update(choices=choices, value=st["picked"], interactive=False, visible=True), hide, fb,
                gr.update(visible=True, value="See score" if last else "Next question"))
    return head, gr.update(choices=choices, value=None, interactive=True, visible=True), gr.update(visible=True), "", hide


def check(tid, st, choice):
    if choice is None:
        v = list(quiz_view(tid, st)); v[3] = "Pick an answer first."
        return (st, *v)
    q = CONTENT[tid]["mcqs"][st["i"]]
    st = {**st, "checked": True, "picked": choice, "score": st["score"] + (choice == q["answer_index"])}
    return (st, *quiz_view(tid, st))


def next_q(tid, st):
    n = len(CONTENT.get(tid, {}).get("mcqs", []))
    st = fresh() if st["i"] >= n else {**st, "i": st["i"] + 1, "checked": False, "picked": None}
    return (st, *quiz_view(tid, st))


# ---------- topic selection ----------
def select_topic(tid):
    t = BY_ID[tid]
    st = fresh()
    return (f"## {t['title']}", points_md(tid), t["full_text"], videos_html(tid), st, *quiz_view(tid, st))


# ---------- chat ----------
def respond(message, history, tid):
    message = (message or "").strip()
    if not message:
        return history, ""
    hist = [{"role": h["role"], "content": h["content"]} for h in history if isinstance(h.get("content"), str)]
    try:
        answer = chat(ChatIn(message=message, topic_id=tid, history=hist))["answer"]
    except Exception as e:
        answer = f"Something went wrong: {e}"
    return history + [{"role": "user", "content": message}, {"role": "assistant", "content": answer}], ""


# ---------- UI ----------
with gr.Blocks(title="AI Professor", theme=gr.themes.Soft()) as demo:
    gr.Markdown("# AI Professor")
    st = gr.State(fresh())
    with gr.Row():
        with gr.Column(scale=2, min_width=220):
            topic = gr.Radio(CHOICES, value=TOPICS[0]["id"], label="Course topics")
        with gr.Column(scale=6):
            title = gr.Markdown()
            with gr.Tabs():
                with gr.Tab("Key points"):
                    points = gr.Markdown(latex_delimiters=LATEX)
                with gr.Tab("Source text"):
                    source = gr.Markdown(latex_delimiters=LATEX)
                with gr.Tab("Videos"):
                    vids = gr.HTML()
                with gr.Tab("Test yourself"):
                    qmd = gr.Markdown(latex_delimiters=LATEX)
                    qradio = gr.Radio([], label="Your answer")
                    qcheck = gr.Button("Check answer", variant="primary")
                    qfb = gr.Markdown(latex_delimiters=LATEX)
                    qnext = gr.Button("Next question", variant="primary", visible=False)
        with gr.Column(scale=4, min_width=300):
            chatbot = gr.Chatbot(type="messages", height=520, label="Ask the professor", latex_delimiters=LATEX,
                                 value=[{"role": "assistant", "content": "Hi! Pick a topic and ask me anything about this chapter."}])
            box = gr.Textbox(placeholder="Ask about this chapter…", show_label=False)
            with gr.Row():
                for msg in ["Explain this more simply", "Give me another example"]:
                    gr.Button(msg, size="sm").click(lambda h, t, m=msg: respond(m, h, t), [chatbot, topic], [chatbot, box])

    quiz_out = [qmd, qradio, qcheck, qfb, qnext]
    sel_out = [title, points, source, vids, st, *quiz_out]
    topic.change(select_topic, topic, sel_out)
    demo.load(select_topic, topic, sel_out)
    qcheck.click(check, [topic, st, qradio], [st, *quiz_out])
    qnext.click(next_q, [topic, st], [st, *quiz_out])
    box.submit(respond, [box, chatbot, topic], [chatbot, box])

if __name__ == "__main__":
    demo.queue().launch(share=True)   # in Colab this prints a public link
