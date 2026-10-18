# Famulor for Dify

**Author:** famulor (published by BEK Service GmbH, maker of Famulor)
**Version:** 0.1.0
**Type:** tool
**Source repository:** https://github.com/bekservice/famulor-dify-plugin
**Contact:** sales@famulor.io

## Description

[Famulor](https://www.famulor.io) is an AI voice agent platform. Its assistants answer and place phone calls,
run outbound campaigns and analyse every conversation. With this plugin, your Dify agents, chatflows and
workflows can:

| Tool | What it does | Famulor API |
|---|---|---|
| List Assistants | List the voice assistants in your workspace (id, name, status) | `GET /assistants` |
| Start Outbound Call | Place a **real** outbound phone call with an assistant | `POST /calls` |
| Get Call | Read a call's status, summary, post-call analysis and transcript | `GET /calls/{id}` |
| List Calls | List recent calls, filtered by assistant, campaign or status | `GET /calls` |
| Create Contact | Create or merge an Audience contact (lead) by phone or email | `POST /leads` |
| List Campaigns | List outbound campaigns and their status | `GET /campaigns` |
| Start Campaign | Start a campaign. This begins **real** outreach to its leads | `POST /campaigns/{id}/start` |

## Setup

1. You need a Famulor workspace whose plan or add-on includes **API Access**.
2. In Famulor, open **Settings → API & MCP** and create an API key. Copy it (it starts with `fam_` and is
   shown only once).
3. In Dify, install the plugin, open **Tools → Famulor → Authorize** and paste the API key.
4. Leave **Base URL** at `https://app.famulor.io`. Only change it if you use Famulor under a white-label
   domain, for example `https://app.example.com`. Only HTTPS is accepted.

The credentials are checked with `GET /api/v1/me`, a read-only endpoint, when you save them.

## Required APIs and credentials

- Famulor REST API v1 at `https://app.famulor.io/api/v1` (or your white-label domain) with a
  workspace API key (`fam_...`), sent as a Bearer token.
- Dashboard keys have full workspace scope. You can create a narrower key with `POST /api/v1/api-keys`
  instead. Needed scopes: `assistants:read`, `calls:read`, `calls:write` (start call), `leads:write`
  (create contact), `campaigns:read` and `campaigns:write` (start campaign).

## Connection requirements

The plugin makes outbound HTTPS requests to one host: `app.famulor.io`, or the white-label domain you
configured. It has no inbound endpoint. Famulor rate limits apply (120 requests per minute per key).
Read requests are retried on 429/5xx. Write requests (start call, create contact, start campaign) are
never retried automatically.

## Usage

- **Agent:** add the Famulor tools to an Agent app and ask, for example: *"Which assistants do I have?"*,
  *"Summarise my last 5 completed calls"* or *"Show the transcript of call 7c1e…"*.
- **Workflow:** after a form or CRM trigger, use **Create Contact** and then **Start Outbound Call** with
  `assistant_id` and the lead's `to_number` (E.164, e.g. `+4930123456`). Pass context to the assistant as
  JSON in **Variables**, e.g. `{"customer_name": "Ada", "order_id": "A-1001"}`. Later, a **Get Call** step
  reads the summary, analysis and transcript.
- **Campaigns:** use **List Campaigns** to find a campaign id, then **Start Campaign**.

> ⚠️ **Start Outbound Call** and **Start Campaign** contact real people and use Famulor credits. In agent
> apps, only enable them when your users should be able to trigger calls. Make sure you have a lawful
> basis and any required consent for outbound calls in your country.

## Example output

`Get Call` returns JSON like:

```json
{
  "call": {"id": "…", "status": "completed", "duration_sec": 74, "summary": "Customer confirmed the appointment."},
  "analysis": {"sentiment": "positive", "success": true},
  "transcript": [{"role": "assistant", "text": "Hello, this is Famulor…"}, {"role": "user", "text": "Hi!"}]
}
```

## Links

- Famulor API reference: https://docs.famulor.io/api-reference/introduction
- Famulor docs: https://docs.famulor.io
- Privacy policy of this plugin: [PRIVACY.md](PRIVACY.md)

## Support

Questions or problems: sales@famulor.io, or open an issue in the source repository.
