"""The email-generation prompt.

Advanced prompting technique = three techniques combined and documented:

  1. ROLE-PLAYING   - the system prompt casts the model as a specific expert persona,
                      which reliably raises register, structure, and professionalism.
  2. FEW-SHOT       - two compact input->email exemplars (different tones) teach the
                      output format and the "include every fact, match the tone" contract
                      by demonstration rather than description.
  3. CHAIN-OF-THOUGHT - the model is told to PLAN silently (recipient, must-include facts,
                      tone calibration, structure) and then output ONLY the final email.
                      Hidden planning improves fact coverage and structure; suppressing the
                      visible reasoning keeps the output clean for both a reasoning model
                      (gpt-oss) and a non-reasoning one (llama).

The exact same template is sent to both candidate models so the comparison isolates the model.
Exemplars are kept short on purpose to limit token usage under the free-tier TPM ceiling.
"""

SYSTEM_PROMPT = (
    "You are an expert executive communications assistant who ghost-writes professional "
    "emails for busy leaders. You are known for emails that are clear, warm, on-brand, and "
    "perfectly calibrated to their audience and purpose. You never invent facts, you weave "
    "in every fact you are given naturally, and you write tight, skimmable prose with a clear "
    "call to action."
)

# Each exemplar shows: the structured input, then the ideal email. Two contrasting tones.
_FEWSHOT = [
    {
        "intent": "Schedule a kickoff call for a new project",
        "key_facts": [
            "Project name: Beacon redesign",
            "Proposed time: Wednesday 10:00am",
            "Attendees: design and engineering leads",
        ],
        "tone": "friendly and professional",
        "email": (
            "Subject: Kicking off the Beacon redesign\n\n"
            "Hi team,\n\n"
            "I'm excited to get the Beacon redesign moving. Could we hold a kickoff for "
            "Wednesday at 10:00am? I'd love to have the design and engineering leads there "
            "so we can align on goals and next steps from the start.\n\n"
            "If that time doesn't work, just send me a couple of alternatives and I'll "
            "make it happen.\n\n"
            "Best,\n[Your Name]"
        ),
    },
    {
        "intent": "Apologize for a late delivery and offer a goodwill gesture",
        "key_facts": [
            "Order #5567 shipped two days late",
            "10% refund applied",
            "Tracking link now active",
        ],
        "tone": "empathetic and sincere",
        "email": (
            "Subject: An apology for your delayed order\n\n"
            "Hi Jordan,\n\n"
            "I'm sorry your order #5567 shipped two days later than promised - that's not "
            "the experience we want you to have, and I understand the frustration.\n\n"
            "Your package is on its way and the tracking link is now active. To make it "
            "right, I've applied a 10% refund to your order, which you'll see within a few "
            "business days.\n\n"
            "Thank you for your patience, and please reach out if there's anything else I "
            "can do.\n\nWarm regards,\n[Your Name]"
        ),
    },
]


def _format_input(intent, key_facts, tone) -> str:
    facts = "\n".join(f"- {f}" for f in key_facts)
    return (
        f"Intent: {intent}\n"
        f"Tone: {tone}\n"
        f"Key facts (every one MUST appear naturally in the email):\n{facts}"
    )


_COT_INSTRUCTION = (
    "\n\nBefore writing, plan silently (do NOT show this):\n"
    "  1. Who is the recipient and what is the single goal of this email?\n"
    "  2. Check off each key fact and decide where it fits naturally.\n"
    "  3. Calibrate vocabulary, warmth, and urgency to the requested tone.\n"
    "  4. Structure it: subject line, greeting, a tight body, a clear call to action, sign-off.\n"
    "Then output ONLY the final email (subject line + body). No preamble, no notes, no "
    "explanation of your reasoning. Use [Your Name] as the sign-off placeholder."
)


def build_messages(intent, key_facts, tone):
    """Assemble the system + few-shot + task messages for one generation."""
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    for ex in _FEWSHOT:
        messages.append({
            "role": "user",
            "content": _format_input(ex["intent"], ex["key_facts"], ex["tone"]),
        })
        messages.append({"role": "assistant", "content": ex["email"]})
    messages.append({
        "role": "user",
        "content": _format_input(intent, key_facts, tone) + _COT_INSTRUCTION,
    })
    return messages


def render_template_for_docs(intent="<INTENT>", key_facts=("<FACT 1>", "<FACT 2>"),
                             tone="<TONE>") -> str:
    """Human-readable dump of the full prompt, used by the README/report."""
    lines = [f"[SYSTEM]\n{SYSTEM_PROMPT}\n"]
    for i, ex in enumerate(_FEWSHOT, 1):
        lines.append(f"[FEW-SHOT {i} - USER]\n{_format_input(ex['intent'], ex['key_facts'], ex['tone'])}\n")
        lines.append(f"[FEW-SHOT {i} - ASSISTANT]\n{ex['email']}\n")
    lines.append(f"[USER - actual request]\n{_format_input(intent, list(key_facts), tone)}{_COT_INSTRUCTION}")
    return "\n".join(lines)
