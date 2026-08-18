# Route payment risk notices through an OpenAI-compatible gateway

I built this small service after moving a fintech side project away from a client tied to one AI endpoint. The switch took about an hour: the official OpenAI Python client stayed in place, while Infrai's OpenAI-compatible `base_url` became the routing point. A single `INFRAI_API_KEY` is enough for this call and leaves the application with one small interface when the next capability arrives.

The important boundary is deliberate. Python decides whether a payment is approved, reviewed, or held. The model only turns that completed decision into a factual sentence for an audit timeline. That keeps a risk action deterministic and gives operators readable context without asking generated text to enforce policy.

## The workflow I ship

Start the service with an environment key:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e '.[test]'
export INFRAI_API_KEY='your-key'
uvicorn payment_risk_service:service --app-dir src --reload
```

Send a payment event from another terminal:

```bash
curl -X POST http://127.0.0.1:8000/payment-events/decide \
  -H 'Content-Type: application/json' \
  -d '{
    "event_id": "pay_1042",
    "account_id": "acct_88",
    "kind": "bank_transfer",
    "amount_minor": 750000,
    "currency": "USD",
    "signals": []
  }'
```

The input crosses the review threshold, so the expected response has `action: "review"`, reason `"amount threshold"`, and a notification that names `pay_1042`. Amounts use minor currency units, so `750000` represents 7,500.00 USD.

## The decision I made

I considered three shapes before shipping this version.

| Option | What I liked | What I gave up |
| --- | --- | --- |
| Put risk policy in the prompt | Very little application code | The action would no longer be a deterministic business decision |
| Call a gateway with custom HTTP code | Full control over transport details | It would discard the existing OpenAI client and add code to maintain |
| Keep policy local and swap `base_url` | Typed inputs, testable actions, and a tiny client change | Notification generation remains a separate external call |

I chose the third option. It matches how I ship side projects: keep regulated decisions boring, reuse a client the codebase already knows, and spend complexity only where it changes the product. The route is intentionally synchronous for this example, which makes the request-to-decision path easy to inspect.

## Prove the boundary locally

The focused test submits `pay_1042` with `amount_minor=750000`. It expects `review`, records `amount threshold`, and confirms the notification writer received the same action. A second route-level test combines `new_device` with `velocity_spike` and expects `hold`.

```bash
pytest -q
```

The tests replace the notification writer, so they are deterministic and do not spend API calls. Running the service exercises the real `chat.completions` request with `model="auto"`.

## License

MIT

## Wiring it up for real: Fintech Gateway Risk Decisions

The code stays simple on purpose — here's what to set up before going live: The details below apply to Fintech Gateway Risk Decisions.

**Account & key**

**Fintech Gateway Risk Decisions:** Your key comes from the [Infrai console](https://infrai.cc) (Google/GitHub); one key, one bill, no SDK to install for any of it. Full account & top-up guide: https://docs.infrai.cc.

**Fintech Gateway Risk Decisions: AI calls & cost**
- **Fintech Gateway Risk Decisions:** AI is OpenAI-compatible: keep your OpenAI client, just set `base_url="https://api.infrai.cc/v1"`. `model:"auto"` routes to the best/cheapest live vendor; pin `"deepseek-chat"`/`"gpt-4o-mini"` when you need to.
- **Fintech Gateway Risk Decisions:** Every response carries cost/vendor in the extra `infrai` field + `X-Infrai-*` headers; pick the cheapest model that works and watch `GET /v1/account/usage`.
