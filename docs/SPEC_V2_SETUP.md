# Benchteq spec v2: what the repo does and what you set up by hand

The code in `custom/` and `client/custom/` builds the data model, screens, rules and
filters. Some settings live in the EspoCRM database, not in files, so a deploy cannot
carry them. Do these once on staging, test, then repeat on production.

## Before you deploy

The deploy workflow runs `rsync --delete` on `custom/` and `client/custom/`. Anything
created on the server through Entity Manager, Layout Manager or Label Manager that is
not in this repo will be deleted. Treat the repo as the only source of truth. If anyone
has changed the live instance since the repo was last updated, copy those changes into
the repo first.

Take an Elestio snapshot, run the workflow in `plan` mode, then `apply`. After apply,
run Administration, Rebuild.

## What changed from the spec (and why)

| Spec | Built | Reason |
|---|---|---|
| `paidToFreelancer` tick boxes, `referralPaid` tick box | A `payout` link on Timesheet and Interview Session. `Lead.referralPaid` is filled by a hook from the Referrer Payout | One place to record a payment. No double entry |
| `Project.amount` | Removed | Duplicated the Payment Blocks and would go stale |
| Timesheet `hours = duration / 3600` formula | PHP hook from start and end time | `duration` is not stored and can be empty at save |
| Interview rule "assign supporter only after Paid" | Session can be booked while Pending. Held and No-Show need Paid | Coordinators book slots before money arrives |
| Payout `payoutFor` field | Existing `payoutType` extended with Hourly and Referral Fee | Keeps v1 data and Metabase reports |
| Payout `interviewSession` link | `Payout` has many Timesheets and Interview Sessions | One payout can cover many sessions |
| `Payout.payeeType` value "Freelancer" | Stored value stays `Delivery Resource`, label shows Freelancer | Avoids rewriting old rows |
| Freelancer `status` | New `workStatus` field. Old `status`, `rate`, `sourcedVia`, `skillSpecialty` stay in the database, hidden from screens | No data loss |
| Lead Convert | Creates Account and Contact only (Deal removed from the dialog) | Deals are retired |
| Old modules | Service Package, Session Log, Deals removed from the menu. Data kept | Per spec |

## Set up by hand (Administration)

1. **Currency.** Settings, Currency: default INR.
2. **Calendar.** Settings, Calendar: add Timesheet and Interview Session to the entity list.
3. **Menu.** Settings, User Interface, Navbar. Suggested tabs:
   - Coordinator: Leads, Contacts, Freelancers, URL tab "Freelancer Shortlist" with
     `#CDeliveryResource/list/primaryFilter=shortlist`, Projects, Timesheets,
     Interview Sessions, Calendar.
   - Interview Manager: Leads, Contacts, Interview Sessions, Calendar.
   - Finance: Payouts, Payment Blocks, Interview Sessions, Timesheets, Leads.
4. **Roles** (Administration, Roles). For every role switch each custom entity on and set
   Create, Read, Edit as below. Set Assignment Permission and User Permission to `all` for
   Manager, Interview Manager and Coordinator. Give every user a Team and a default Team.

   | Scope | Manager | Interview Manager | Coordinator | Finance |
   |---|---|---|---|---|
   | Lead, Contact, Account | all | all | create, read all, edit all | read |
   | Freelancers | all | read | create, read all, edit all | read |
   | Project, Payment Block, Timesheet | all | no | create, read all, edit all | read all, edit Payment Block and Timesheet |
   | Interview Session | all | all | all | read, edit |
   | Provider, Referrer | all | read | read | read |
   | Payout | all | no | no | all |
   | Service Package, Session Log, Deal | no | no | no | no |

   Decide whether Coordinators may see `freelancerRate`, `bgcFee` and `bgcProviderCost`. If
   not, add field-level restrictions in the role.
5. **Dashboard** for Coordinators: Calendar dashlet, a List dashlet on Timesheet with filter
   "Planned", a List dashlet on Payment Block with filter "5 or fewer hours left".
6. **Phone types.** Phone fields on Freelancers, Provider and Referrer now offer WhatsApp.
7. **Move old Freelancer role data.** Mass update Freelancers whose Role Type is
   "Freelancer" to "Trainer".

## Filters you get without any setup

Timesheet: Planned, Held, Today, Held not yet paid out.
Interview Session: Planned, Held, Today, Held not yet paid out, Planned and payment pending.
Payment Block: 5 or fewer hours left, Payment pending.
Payout: Due. Lead: BGC in verification, Referred and converted, fee not paid.
Freelancers: Shortlist (Passed).

## How Finance pays

1. Open Timesheets (or Interview Sessions) with the filter "Held not yet paid out".
2. Create a Payout (Freelancer, Hourly or Per Interview, amount, project).
3. Select the rows and mass update the Payout field.
4. When the money is sent, set the Payout to Paid. Rows with an empty Payout are the unpaid ones.

Provider and Referrer Payouts: create the Payout with the Lead set. When a Referrer Payout
is marked Paid, the Lead shows "Referral Fee Paid" by itself.

## Test

`scripts/tests/v2_flow.php` runs the whole flow with fake records (35 checks): Connected Hrs
through every status change, the Paid before Held rule, BGC fees, referral flag. Run it on
staging only:

    docker compose exec espocrm php /path/to/v2_flow.php /var/www/html

Then check the screens by hand with the Manager, Coordinator, Interview Manager and Finance
roles. Section 10 of the spec lists the manual checks.
