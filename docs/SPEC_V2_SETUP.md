# Benchteq spec v2: setup, daily use and test

## Daily use (what the team does)

**Job Support.** Lead (Service = Job Support) → Convert → Project (technology, consultant,
freelancer, rates; the name fills itself) → Payment Block (hours, amount) → Timesheets.
After each call open the Timesheet and set Held. Connected and Remaining hours update by
themselves, and the block closes at zero hours. The dashboard shows blocks with 5 or fewer
hours left, so you know when to ask for the next payment.

**Interview Support.** Lead (Service = Interview Support) → Convert → Interview Session.
Pick Type (Interview or Assessment) and a slot: 30, 45, 60, 90 or 180 minutes. The default
is 30. Choosing Assessment moves a default slot to 90. After the customer pays set Payment
Status = Paid, then set Held and write the feedback. Held and No-Show are blocked until Paid.

**BGC.** Lead (Service = BGC) → pick Referrer, BGC Type (the fee fills in), Provider, BGC
Status → Cleared → Convert.

**Finance.** Dashboard tab "Money" lists everything to pay. Create a Payout, then open it
and use Select on the Timesheets or Interview Sessions panel (it only offers unpaid ones).
Mark the Payout Paid. Referral and Provider payouts: create the Payout with the Lead set;
when the Referrer payout is Paid the Lead shows Referral Fee Paid by itself.

No-Show counts as used. Cancelled (24 hours notice) does not. Create a new Planned
Timesheet for the new time (use Clone).

## Setup

### 1. Deploy the code
The deploy workflow runs `rsync --delete` on `custom/` and `client/custom/`. Anything
created on the server through Entity Manager, Layout Manager or Label Manager that is not
in this repo is deleted. Keep the repo as the only source of truth. Take an Elestio
snapshot, run the workflow in `plan` mode, then `apply`, then Administration, Rebuild.

### 2. Roles, menu, dashboard (one script, safe to rerun)

    export ESPO_URL=https://your-crm  ESPO_USER=admin  ESPO_PASSWORD=...
    python3 scripts/setup-roles-dashboards.py --dry-run
    python3 scripts/setup-roles-dashboards.py \
        --assign priya=Coordinator --assign rahul=Finance \
        --assign amit="Interview Manager" --assign meera=Manager

It creates or updates the four roles, the menu, the plus-button list, the Calendar entity
list, INR as default currency, the India time zone, India and US first in phone numbers,
and the default dashboard (tabs Today and Money). It does not create users: create them in
Administration, Users, then assign roles with `--assign` (or in the user form).
Users who already built their own dashboard keep it. Use `--reset-user-dashboards` to push
the default to everyone after the dashboard definition changes in the script.

Access (the team is small, so it is open):

| Scope | Manager | Interview Manager | Coordinator | Finance |
|---|---|---|---|---|
| Lead, Contact, Account | all | create, read, edit | create, read, edit | read |
| Freelancers | all | read | create, read, edit | read |
| Project, Payment Block | all | none | create, read, edit, delete own | read (Payment Block: edit) |
| Timesheet | all | none | create, read, edit, delete own | read, edit |
| Interview Session | all | create, read, edit, delete own | create, read, edit, delete own | read, edit |
| Referrer | all | read | create, read, edit | read |
| Provider | all | read | read | read |
| Payout | all | none | read | create, read, edit |
| Deals, Service Package, Session Log, Cases, Campaigns | none | none | none | none |

Coordinators can read everything except old modules. To close it later, change the tables
in `scripts/setup-roles-dashboards.py` and run it again.

### 3. Old data
Mass update Freelancers whose Role Type is "Freelancer" to "Trainer".

## What changed from the first spec, and why

| Spec | Built | Reason |
|---|---|---|
| `paidToFreelancer` and `referralPaid` tick boxes | A `payout` link on Timesheet and Interview Session. `Lead.referralPaid` is filled by a hook | One place to record a payment |
| `Project.amount` | Removed | Duplicated the Payment Blocks |
| Timesheet `hours` formula | PHP hook from start and end | `duration` is not stored |
| Supporter assigned only after Paid | Booking allowed. Held and No-Show need Paid | Slots are booked before money arrives |
| Interview type, slots | `Type`, slots 30/45/60/90/180, default 30, Assessment moves a default slot to 90 | Asked for by the team |
| Payout `payoutFor` | `payoutType` extended (Hourly, Referral Fee) | Keeps v1 data and Metabase reports |
| Payout payee value "Freelancer" | Stored as `Delivery Resource`, shown as Freelancer | No rewrite of old rows |
| Block status | Closes itself at zero hours, reopens if hours are freed | One less step |
| Old Freelancer `status`, `rate`, `sourcedVia`, `skillSpecialty` | Hidden from screens, data kept | No data loss |
| Lead Convert | Account and Contact only | Deals retired |
| Coordinator on Referrer | Create and edit | A referral lead needs its Referrer |

## Tests

Three tests, all on STAGING only (they create fake records):

- `scripts/tests/v2_flow.php`: business rules inside the app (35 checks).
  `php scripts/tests/v2_flow.php /var/www/html`
- `scripts/tests/v2_api_flow.py`: the full daily flow through the API, one user per role,
  including who can and cannot do what (59 checks). Needs one user per role.
- Look at the screens once with a real Coordinator and Finance login.
