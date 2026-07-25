# Benchteq CRM blueprint

This is the initial business design. Confirm it with process owners before adding fields or automation.

## Core record model

| Business concept | EspoCRM entity | Initial use |
|---|---|---|
| Customer or prospect company | Account | Firmographics, owner, segment, lifecycle |
| Buyer or stakeholder | Contact | Role, consent, communication history |
| Unqualified inquiry | Lead | Capture, qualification and conversion |
| Sales pursuit | Opportunity | Value, stage, probability, next step |
| Work request or issue | Case | Support queue, priority, SLA and resolution |
| Outreach initiative | Campaign | Source and response tracking |
| Delivery engagement | Custom entity: Project/Engagement | Scope, dates, owner, status and commercial link |
| Partner or vendor | Account with type | Relationship and referral tracking |

## Recommended pipelines

Sales: New inquiry → Contacted → Qualified → Discovery → Proposal → Negotiation → Closed won/lost.

Delivery: Handover → Planning → Active → Client review → Completed → On hold/cancelled.

Support: New → Triaged → In progress → Waiting on customer → Resolved → Closed.

## Roles and teams

- CRM Administrators: configuration only; use named accounts and MFA/SSO where available.
- Sales: own leads, accounts, contacts and opportunities.
- Delivery/Operations: access won opportunities and engagements.
- Support: access customer context and cases.
- Management: dashboards and reports; limited exports.
- Marketing: campaigns and consented contacts; no unrestricted administrative access.

## Integration register

| Integration | Purpose | Inputs required from Benchteq | Status |
|---|---|---|---|
| Microsoft 365 or Google Workspace email | Shared inboxes, outbound SMTP, email capture | Provider, tenant/domain, mailbox list | Decision needed |
| Microsoft 365 or Google Calendar | Meeting synchronization | Provider and users/groups | Decision needed |
| Website forms | Lead capture and attribution | Website/CMS, form fields, consent text | Decision needed |
| Telephony/SMS/WhatsApp | Calls and customer messaging | Current provider, countries, numbers | Decision needed |
| Accounting/ERP | Customers, invoices and payment context | Product name, system owner, API access | Decision needed |
| Identity/SSO | Central login and offboarding | Identity provider and security policy | Decision needed |
| BI/reporting | Executive metrics | Tool, refresh needs, data owner | Decision needed |
| File storage/e-signature | Documents and signed proposals | Provider and retention rules | Decision needed |

## Data and automation guardrails

- Define a system of record for every synchronized field.
- Use service accounts with least privilege; never personal administrator credentials.
- Separate production and test API credentials.
- Require deduplication rules for account domain, contact email and lead email.
- Record lawful basis/consent, source and opt-out timestamps for marketing contacts.
- Back up before upgrades or extension installs; test restore quarterly.
- Build customizations in `custom` and `client/custom`, not the application image.

## Decisions needed before production

1. Hosting location and CRM domain.
2. Primary timezone, currencies, fiscal year and languages.
3. Number of users by team and named process owners.
4. Email/calendar platform and shared mailboxes.
5. Existing data sources, approximate record counts and data quality.
6. Required sales, delivery and support stages plus approval rules.
7. Current accounting, telephony, website, BI, document and identity systems.
8. Regulatory, retention, residency, backup RPO/RTO and audit requirements.

