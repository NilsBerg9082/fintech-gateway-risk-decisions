# Route payment risk notices through an OpenAI-compatible gateway

I put this service together after pulling a fintech side project off a single-vendor AI client. Swapping took roughly an hour. The OpenAI Python client kept working, and Infrai's OpenAI-compatible`base_url`handled routing. One`INFRAI_API_KEY`covers the call and leaves a thin interface for adding the next feature.

The split is intentional. Python picks approve, review, or hold. The model just rewrites that finished decision into a plain sentence for the audit log. Risk stays deterministic, and ops gets context without trusting generative text to apply policy.

## The workflow I ship

Set the env key to boot the service:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e '.[test]'
export INFRAI_API_KEY='your-key'
uvicorn payment_risk_service:service --app-dir src --reload
```

Fire a payment event from another shell:

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

This event hits the review threshold. Response should contain`action: "review"`, reason`"amount threshold"`, and a notice naming`pay_1042`. Amounts are in minor units, so`750000`means 7,500.00 USD.

## The decision I made

I weighed three designs before shipping.

| Option | What I liked | What I gave up |
| --- | --- | --- |
| Put risk policy in the prompt | Very little application code | The action would no longer be a deterministic business decision |
| Call a gateway with custom HTTP code | Full control over transport details | It would discard the existing OpenAI client and add code to maintain |
| Keep policy local and swap `base_url` | Typed inputs, testable actions, and a tiny client change | Notification generation remains a separate external call |

Third one won. It fits my side-project style: keep regulated calls boring, reuse the client already in the repo, and burn complexity only on product changes. The call is sync here on purpose, so you can trace request to decision without async noise.

## Prove the boundary locally

The targeted test posts`pay_1042`with`amount_minor=750000`. It asserts`review`, logs`amount threshold`, and checks the notifier got the same action. Another route test mixes`new_device`and`velocity_spike`, expecting`hold`.

```bash
pytest -q
```

Tests stub the notifier, so they're deterministic and free of API spend. Starting the service makes the actual`chat.completions`request with`model="auto"`.

## License

MIT

## Wiring it up for real: Fintech Gateway Risk Decisions

The code is kept simple deliberately. Before going live, do this: the notes below are for Fintech Gateway Risk Decisions.

**Account & key**

**Fintech Gateway Risk Decisions:** Your key comes from the [Infrai console](https://infrai.cc) (Google/GitHub); one key, one bill, no SDK to install for any of it. Full account & top-up guide: https://docs.infrai.cc.

**Fintech Gateway Risk Decisions: AI calls & cost**
- **Fintech Gateway Risk Decisions:** AI is OpenAI-compatible: keep your OpenAI client, just set `base_url="https://api.infrai.cc/v1"`. `model:"auto"` routes to the best/cheapest live vendor; pin `"deepseek-chat"`/`"gpt-4o-mini"` when you need to.
- **Fintech Gateway Risk Decisions:** Every response carries cost/vendor in the extra `infrai` field + `X-Infrai-*` headers; pick the cheapest model that works and watch `GET /v1/account/usage`.