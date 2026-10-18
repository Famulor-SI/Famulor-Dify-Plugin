# Privacy Policy – Famulor plugin for Dify

Last updated: 18 October 2026

This plugin is published by BEK Service GmbH, Westendstr. 2A, 87439 Kempten (Allgäu), Germany
("Famulor", contact: sales@famulor.io).

## What the plugin does with data

The plugin connects your Dify workspace to **your own Famulor workspace** through the Famulor REST API.
It does **not collect, store, log or sell any user data itself**. It has no database and no analytics or
telemetry, and it only sends data to the Famulor API host you configure.

## Data sent to Famulor (third-party service)

Every request goes to `https://app.famulor.io/api/v1` (or to the white-label domain you set as Base URL),
and only when a tool runs:

- **Credentials:** your Famulor API key is sent as a Bearer token. Dify stores it encrypted as a plugin
  credential. The plugin never writes it to logs or tool output.
- **Tool inputs:** the parameters you or your Dify app pass in, for example assistant id, destination phone
  number, custom call variables, contact name, phone, email and tags, or campaign id.
- **Personal data:** phone numbers, names and emails of the people you call or create as contacts are
  personal data. Starting a call or campaign makes Famulor contact these people by phone.

## Data returned to Dify

Tool results can contain call metadata, summaries, post-call analysis, transcripts and recording links
from your Famulor workspace. Dify then processes and keeps these results according to your Dify
configuration (for example, conversation logs).

## Storage and retention

The plugin itself keeps nothing between invocations. Data in Famulor is processed under Famulor's own
privacy policy and the data retention settings of your workspace. Data in Dify is governed by your Dify
deployment.

- Famulor privacy policy: https://www.famulor.io/privacy
- Famulor Trust Center: https://docs.famulor.io/support/trust-center

## Your responsibilities

You are responsible for having a lawful basis (for example consent) for calling or storing the contacts
you process with this plugin.

## Contact

For privacy questions, contact BEK Service GmbH at sales@famulor.io.
