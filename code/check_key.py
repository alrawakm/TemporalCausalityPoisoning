"""One minimal call, to say exactly why the arm did not start.

Costs a few tokens. Reports the failure by class rather than dumping a
traceback, because the fix differs completely between an unset key, a rejected
key, no credit, and a model the account cannot reach.

    python check_key.py
"""

import os
import sys


def main():
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        print("ANTHROPIC_API_KEY is not set in THIS shell.")
        print()
        print("If it was set in another terminal window, that does not carry over.")
        print("Set it in the same window you run the experiment from:")
        print('    $env:ANTHROPIC_API_KEY = "sk-ant-..."')
        return 1
    print("key present: %d chars, starts %s" % (len(key), key[:7]))

    try:
        import anthropic
    except ImportError:
        print("the anthropic package is not installed: pip install anthropic")
        return 1

    c = anthropic.Anthropic()
    model = sys.argv[1] if len(sys.argv) > 1 else "claude-opus-5"
    print("calling %s ..." % model)

    try:
        r = c.messages.create(
            model=model,
            max_tokens=16,
            output_config={"effort": "low"},
            messages=[{"role": "user", "content": "Reply with the word: ready"}],
        )
    except anthropic.AuthenticationError:
        print("\nFAILED: the key was rejected. Check it was copied whole, and that")
        print("it is an API key from console.anthropic.com rather than anything else.")
        return 1
    except anthropic.PermissionDeniedError as e:
        print("\nFAILED: authenticated, but not permitted. Often the model is not")
        print("enabled for the account. Try:  python check_key.py claude-sonnet-5")
        print("detail: %s" % e)
        return 1
    except anthropic.NotFoundError:
        print("\nFAILED: model %r not found for this account." % model)
        print("Try:  python check_key.py claude-sonnet-5")
        return 1
    except anthropic.BadRequestError as e:
        print("\nFAILED: the request was rejected: %s" % e)
        print("If this names output_config or effort, tell me and I will drop it.")
        return 1
    except anthropic.RateLimitError:
        print("\nFAILED: rate limited, or the balance is exhausted. Check the")
        print("credit balance in the console.")
        return 1
    except anthropic.APIConnectionError as e:
        print("\nFAILED: could not reach the API. Network or proxy. detail: %s" % e)
        return 1
    except Exception as e:                                    # noqa: BLE001
        print("\nFAILED: %s: %s" % (type(e).__name__, e))
        return 1

    text = "".join(b.text for b in r.content if getattr(b, "type", "") == "text")
    print("\nOK. model replied: %r" % text.strip())
    print("stop_reason: %s | in %d tok, out %d tok"
          % (r.stop_reason, r.usage.input_tokens, r.usage.output_tokens))
    print("\nthe arm will run. rerun the sweep command.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
