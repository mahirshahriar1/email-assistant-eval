"""Interactive / CLI entry point for the email assistant.

This is the "working prototype" surface: a person supplies Intent + Key Facts + Tone and
gets a finished email back. Two ways to use it:

  Interactive (prompts you for each field):
      python -m src.assistant

  One-shot via flags (facts repeatable):
      python -m src.assistant --intent "Follow up after a meeting" \
          --fact "We met on June 9" --fact "Discussed the $2,400 plan" \
          --tone "professional and friendly" --model gpt-oss-120b
"""
import argparse
import sys

from . import config, generate

# Windows consoles default to cp1252; generated emails can contain Unicode punctuation.
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass


def _interactive():
    print("Email Generation Assistant - enter the brief (Ctrl+C to quit)\n")
    intent = input("Intent (the email's purpose): ").strip()
    print("Key facts - one per line; press Enter on a blank line when done:")
    facts = []
    while True:
        line = input("  - ").strip()
        if not line:
            break
        facts.append(line)
    tone = input("Tone (e.g. formal, casual, urgent, empathetic): ").strip()
    return intent, facts, tone


def main(argv=None):
    p = argparse.ArgumentParser(description="Generate a professional email from Intent + Key Facts + Tone.")
    p.add_argument("--intent", help="The purpose of the email")
    p.add_argument("--fact", action="append", dest="facts", default=[],
                   help="A key fact to include (repeat for multiple)")
    p.add_argument("--tone", help="Desired tone, e.g. 'formal' or 'empathetic'")
    p.add_argument("--model", choices=list(config.MODELS.keys()), default="gpt-oss-120b",
                   help="Which model to use (default: gpt-oss-120b, the eval winner)")
    args = p.parse_args(argv)

    if args.intent and args.tone and args.facts:
        intent, facts, tone = args.intent, args.facts, args.tone
    else:
        try:
            intent, facts, tone = _interactive()
        except (KeyboardInterrupt, EOFError):
            print("\nCancelled.")
            return 1

    if not (intent and facts and tone):
        print("Need an intent, at least one key fact, and a tone.", file=sys.stderr)
        return 1

    scenario = {"intent": intent, "key_facts": facts, "tone": tone}
    model_id = config.MODELS[args.model]
    print(f"\nGenerating with {args.model} ...\n")
    email = generate.generate_email(scenario, model_id)
    print("-" * 60)
    print(email)
    print("-" * 60)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
