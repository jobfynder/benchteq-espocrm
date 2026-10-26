#!/usr/bin/env python3
"""One-off jobs for the live CRM, both safe to run again:

  --show-record   Read only. Show the phone data of one record, like Lead/6ad022706b0544e92.
  --demo          Create one complete demo story (Job Support, Interview Support, BGC,
                  payments, payouts). Every record is named or described "DEMO ...".
  --migrate-technologies  Move the old Technologies choices into the shared Technology list.
  --link-timesheets  Fill Timesheet.project from the Payment Block (so Projects list them).
  --fix-dashboards  Remove dashboard widgets (every user, plus the default) whose saved filter
                  no longer exists, which causes "No primary filter ... for ...".
  --remove-demo   Delete every record whose description starts with "DEMO".

Start with --dry-run: it reads the CRM and prints what it would do, and changes nothing.

  export ESPO_URL=https://crm.example.com ESPO_USER=admin ESPO_PASSWORD=...
  python3 scripts/demo-data-and-whatsapp.py --demo --dry-run

Only Python 3.8+ is needed, no extra packages.
"""
import argparse
import base64
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

# entity -> field that holds its phone number (EspoCRM's native phone field)
PHONE_FIELD = {'Contact': 'phoneNumber', 'Lead': 'phoneNumber', 'CDeliveryResource': 'phoneNumber',
               'CProvider': 'phoneNumber', 'CReferrer': 'phoneNumber'}
TAG = 'DEMO'
NOTE = 'DEMO data for team training. Safe to delete.'
NEW = '(new)'
OLD_TECHNOLOGIES = ['Java', '.NET', 'Python', 'JavaScript', 'React', 'Angular', 'Node.js', 'SQL', 'AWS',
                    'Azure', 'DevOps', 'Data Engineering', 'Salesforce', 'SAP', 'QA Testing', 'Other']


class Api:
    def __init__(self, base, user, password, api_key, dry_run):
        self.base = base.rstrip('/') + '/api/v1/'
        self.dry = dry_run
        self.headers = {'Content-Type': 'application/json'}
        if api_key:
            self.headers['X-Api-Key'] = api_key
        else:
            self.headers['Authorization'] = 'Basic ' + base64.b64encode(
                f'{user}:{password}'.encode()).decode()

    def call(self, method, path, body=None, params=None, write=False):
        if write and self.dry:
            print(f'  [dry-run] {method} {path}')
            return {'id': NEW}
        if params:
            path += '?' + urllib.parse.urlencode(params, doseq=True)
        req = urllib.request.Request(
            self.base + path, method=method,
            data=json.dumps(body).encode() if body is not None else None, headers=self.headers)
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                text = r.read().decode()
        except urllib.error.HTTPError as e:
            sys.exit(f'{method} {path} failed: HTTP {e.code} {e.headers.get("X-Status-Reason", "")}')
        except urllib.error.URLError as e:
            sys.exit(f'Cannot reach {self.base}: {e.reason}')
        return json.loads(text) if text else {}

    def find(self, entity, where, select='id,name', size=200):
        params = {'select': select, 'maxSize': size}
        for i, (attr, value, kind) in enumerate(where):
            params[f'where[{i}][type]'] = kind
            params[f'where[{i}][attribute]'] = attr
            params[f'where[{i}][value]'] = value
        return self.call('GET', entity, params=params).get('list', [])

    def create(self, entity, body):
        out = self.call('POST', entity, body, write=True)
        print(f'  created {entity}: {body.get("name") or body.get("lastName") or ""}')
        return out

    def update(self, entity, id_, body):
        if id_ == NEW:
            return {}
        return self.call('PUT', f'{entity}/{id_}', body, write=True)


def ts(days, hour, minutes=0):
    d = datetime.now(timezone.utc).replace(hour=hour, minute=minutes, second=0, microsecond=0)
    return (d + timedelta(days=days)).strftime('%Y-%m-%d %H:%M:%S')


# ---------------------------------------------------------------------- demo

def ensure(api, entity, where, body):
    """Return the id of the record matching `where`, creating it from `body` if missing."""
    found = api.find(entity, where)
    if found:
        print(f'  exists  {entity}: {body.get("name") or body.get("lastName")}')
        return found[0]['id']
    return api.create(entity, {**body, 'description': body.get('description', NOTE)})['id']


def convert(api, lead_id, records):
    lead = api.call('GET', f'Lead/{lead_id}') if lead_id != NEW else {}
    if lead.get('status') == 'Converted':
        print('  exists  converted lead')
        return lead.get('createdContactId'), lead.get('createdAccountId')
    api.call('POST', 'Lead/action/convert', {'id': lead_id, 'records': records}, write=True)
    print('  converted lead into contact' + (' and account' if 'Account' in records else ''))
    if lead_id == NEW:
        return NEW, NEW
    lead = api.call('GET', f'Lead/{lead_id}')
    return lead.get('createdContactId') or NEW, lead.get('createdAccountId') or NEW


def demo_data(api):
    print('\n== Demo data ==')
    me = api.call('GET', 'App/user')['user']['id']

    def eq(attr, value):
        return (attr, value, 'equals')

    # People and companies that supply the work
    referrer = ensure(api, 'CReferrer', [eq('name', 'DEMO Referrer - Anil')], {
        'name': 'DEMO Referrer - Anil', 'referrerType': 'Existing Consultant', 'referralFee': 2000,
        'status': 'Active', 'phoneNumber': '+919800000001'})
    provider = ensure(api, 'CProvider', [eq('name', 'DEMO BGC Provider')], {
        'name': 'DEMO BGC Provider', 'providerType': 'Company', 'servicesSupplied': ['BGC Verification'],
        'phoneNumber': '+919800000002', 'email': 'demo-provider@example.com'})
    java = ensure(api, 'CTechnology', [eq('name', 'Java')], {'name': 'Java', 'description': 'Shared technology list'})
    trainer = ensure(api, 'CDeliveryResource', [eq('name', 'DEMO Trainer - Meena')], {
        'name': 'DEMO Trainer - Meena', 'roleType': 'Trainer', 'techListIds': [java], 'experienceYears': 8,
        'screeningResult': 'Passed', 'rating': 5, 'workStatus': 'On Project',
        'phoneNumber': '+919800000003', 'email': 'demo-meena@example.com',
        'providerId': provider})
    supporter = ensure(api, 'CDeliveryResource', [eq('name', 'DEMO Supporter - Kiran')], {
        'name': 'DEMO Supporter - Kiran', 'roleType': 'Interview Supporter', 'techListIds': [java], 'experienceYears': 8,
        'screeningResult': 'Passed', 'rating': 4, 'workStatus': 'Available',
        'phoneNumber': '+919800000004', 'email': 'demo-kiran@example.com'})

    # 1. Job Support: lead -> contact + account -> project -> payment block -> timesheets
    print('\n-- Job Support')
    lead = ensure(api, 'Lead', [eq('lastName', 'Kumar'), eq('firstName', 'DEMO Ravi')], {
        'firstName': 'DEMO Ravi', 'lastName': 'Kumar', 'serviceType': 'Job Support', 'status': 'New',
        'accountName': 'DEMO Acme Technologies', 'phoneNumber': '+919800000011',
        'emailAddress': 'demo-ravi@example.com', 'source': 'Web Site'})
    ravi, acme = convert(api, lead, {
        'Contact': {'firstName': 'DEMO Ravi', 'lastName': 'Kumar', 'phoneNumber': '+919800000011', 'emailAddress': 'demo-ravi@example.com', 'description': NOTE},
        'Account': {'name': 'DEMO Acme Technologies', 'description': NOTE}})
    project = ensure(api, 'CProject', [eq('consultantId', ravi), eq('technologyRefId', java)], {
        'assignedUserId': me, 'technologyRefId': java, 'consultantId': ravi, 'accountId': acme,
        'freelancerId': trainer, 'freelancerPayType': 'Hourly', 'freelancerRate': 500,
        'customerRate': 900, 'startDate': ts(-7, 0)[:10], 'status': 'Active',
        'scheduleNotes': 'Mon, Wed, Fri 8 pm IST'})
    block1 = ensure(api, 'CPaymentBlock', [eq('projectId', project), eq('totalHrs', '5')], {
        'projectId': project, 'totalHrs': 5, 'amount': 4500, 'paymentStatus': 'Paid',
        'startDate': ts(-7, 0)[:10]})
    ensure(api, 'CPaymentBlock', [eq('projectId', project), eq('totalHrs', '10')], {
        'projectId': project, 'totalHrs': 10, 'amount': 9000, 'paymentStatus': 'Pending'})
    sheets = []
    for day in (-6, -4, -2, -1, 1, 3):
        sheets.append(ensure(api, 'CTimesheet', [eq('paymentBlockId', block1),
                                                 eq('dateStart', ts(day, 15, 30))], {
            'paymentBlockId': block1, 'dateStart': ts(day, 15, 30), 'dateEnd': ts(day, 16, 30),
            'assignedUserId': me}))
    for sheet in sheets[:4]:
        api.update('CTimesheet', sheet, {'status': 'Held'})

    # 2. Interview Support
    print('\n-- Interview Support')
    lead = ensure(api, 'Lead', [eq('lastName', 'Rao'), eq('firstName', 'DEMO Sita')], {
        'firstName': 'DEMO Sita', 'lastName': 'Rao', 'serviceType': 'Interview Support',
        'status': 'New', 'phoneNumber': '+919800000012',
        'emailAddress': 'demo-sita@example.com'})
    sita, _ = convert(api, lead, {
        'Contact': {'firstName': 'DEMO Sita', 'lastName': 'Rao', 'phoneNumber': '+919800000012', 'emailAddress': 'demo-sita@example.com',
                    'description': NOTE}})
    held = ensure(api, 'CInterviewSession', [eq('contactId', sita), eq('dateStart', ts(-3, 10))], {
        'assignedUserId': me, 'contactId': sita, 'freelancerId': supporter, 'interviewType': 'Interview',
        'dateStart': ts(-3, 10), 'dateEnd': ts(-3, 10, 45), 'customerFee': 3000,
        'supporterFee': 1500, 'paymentStatus': 'Paid'})
    api.update('CInterviewSession', held, {'status': 'Held',
                                           'feedback': 'DEMO feedback: strong Java basics, practise system design.'})
    ensure(api, 'CInterviewSession', [eq('contactId', sita), eq('dateStart', ts(2, 10))], {
        'assignedUserId': me, 'contactId': sita, 'freelancerId': supporter, 'interviewType': 'Assessment',
        'dateStart': ts(2, 10), 'dateEnd': ts(2, 11, 30), 'customerFee': 4500, 'supporterFee': 2000,
        'paymentStatus': 'Pending'})

    # 3. BGC with referral
    print('\n-- BGC')
    lead = ensure(api, 'Lead', [eq('lastName', 'Patel'), eq('firstName', 'DEMO Dev')], {
        'firstName': 'DEMO Dev', 'lastName': 'Patel', 'serviceType': 'BGC', 'status': 'New',
        'phoneNumber': '+919800000013', 'emailAddress': 'demo-dev@example.com',
        'referrerId': referrer, 'bgcType': 'US', 'bgcProviderId': provider})
    api.update('Lead', lead, {'bgcStatus': 'In Verification', 'bgcAmountReceived': 55000})
    api.update('Lead', lead, {'bgcStatus': 'Cleared', 'bgcProviderCost': 20000})
    convert(api, lead, {
        'Contact': {'firstName': 'DEMO Dev', 'lastName': 'Patel', 'phoneNumber': '+919800000013', 'emailAddress': 'demo-dev@example.com', 'description': NOTE}})

    # 4. Money out
    print('\n-- Payouts')
    hourly = ensure(api, 'CPayout', [eq('projectId', project), eq('payoutType', 'Hourly')], {
        'payeeType': 'Delivery Resource', 'deliveryResourceId': trainer, 'projectId': project,
        'payoutType': 'Hourly', 'amount': 1000})
    for sheet in sheets[:2]:
        api.update('CTimesheet', sheet, {'payoutId': hourly})
    api.update('CPayout', hourly, {'status': 'Paid'})
    ensure(api, 'CPayout', [eq('deliveryResourceId', supporter), eq('payoutType', 'Per Interview')], {
        'payeeType': 'Delivery Resource', 'deliveryResourceId': supporter,
        'payoutType': 'Per Interview', 'amount': 1500})
    prov_pay = ensure(api, 'CPayout', [eq('providerId', provider), eq('payoutType', 'BGC Verification Fee')], {
        'payeeType': 'Provider', 'providerId': provider, 'leadId': lead,
        'payoutType': 'BGC Verification Fee', 'amount': 20000})
    api.update('CPayout', prov_pay, {'status': 'Paid'})
    ensure(api, 'CPayout', [eq('referrerId', referrer), eq('payoutType', 'Referral Fee')], {
        'payeeType': 'Referrer', 'referrerId': referrer, 'leadId': lead,
        'payoutType': 'Referral Fee', 'amount': 2000})
    # The Per Interview and Referral payouts stay Due on purpose: the Money tab on the
    # dashboard then has something to show, and the team can attach and pay them live.


def mask(v):
    v = str(v)
    return '*' * max(len(v) - 2, 0) + v[-2:]


def diagnose_phones(api):
    """Read-only. Shows how phone data looks for Contact and Freelancer records."""
    print('\n== Phone diagnosis (read only, numbers masked) ==')
    for entity in ('CDeliveryResource', 'CProvider', 'CReferrer', 'Contact'):
        field = PHONE_FIELD.get(entity, 'phoneNumber')
        meta = api.call('GET', 'Metadata', params={'key': f'entityDefs.{entity}.fields.{field}'})
        print(f'{entity}: field definition at runtime: {json.dumps(meta)[:300]}')
        page = api.call('GET', entity, params={'maxSize': 200, 'orderBy': 'createdAt', 'order': 'asc'})
        rows = page.get('list', [])
        with_value = sum(1 for r in rows if r.get(field))
        with_data = sum(1 for r in rows if r.get(field + 'Data'))
        print(f'{entity}: {len(rows)} read, {with_value} with {field}, {with_data} with {field}Data')
        for r in rows[:3]:
            keys = {k: (mask(v) if k == field and v else v) for k, v in r.items()
                    if 'phone' in k.lower() and k != field + 'Data'}
            data = [{**d, 'phoneNumber': mask(d.get('phoneNumber', ''))} for d in (r.get(field + 'Data') or [])]
            print(f'  {r.get("id")}: {json.dumps(keys)} data={json.dumps(data)}')


def show_record(api, spec):
    """Read-only. spec is Entity/id. Prints the phone data of one record, numbers masked."""
    entity, rid = spec.split('/', 1)
    r = api.call('GET', f'{entity}/{rid}')
    print(f'\n== {entity} {rid}: {r.get("name") or r.get("lastName")} ==')
    for k, v in r.items():
        if k == 'phoneNumberData':
            v = [{**d, 'phoneNumber': mask(d.get('phoneNumber', ''))} for d in (v or [])]
        elif 'phone' in k.lower() or 'whatsapp' in k.lower():
            v = mask(v) if v else v
        else:
            continue
        print(f'  {k}: {json.dumps(v)}')


def inspect(api, spec):
    """Read only. For each entity, count records and how often each link field is filled."""
    for entity in [e.strip() for e in spec.split(',') if e.strip()]:
        print(f'\n== {entity} ==')
        rows, offset = [], 0
        while True:
            page = api.call('GET', entity, params={'maxSize': 200, 'offset': offset,
                                                   'orderBy': 'createdAt', 'order': 'asc'})
            part = page.get('list', [])
            rows += part
            offset += len(part)
            if not part or offset >= page.get('total', 0):
                break
        print(f'{len(rows)} record(s)')
        links = sorted({k for r in rows for k in r if k.endswith('Id') and k != 'id'})
        for k in links:
            print(f'  {k}: filled on {sum(1 for r in rows if r.get(k))} of {len(rows)}')
        for key in ('serviceType', 'status', 'paymentStatus'):
            if any(key in r for r in rows):
                counts = {}
                for r in rows:
                    counts[r.get(key)] = counts.get(r.get(key), 0) + 1
                print(f'  {key}: {json.dumps(counts)}')
        if rows and 'serviceType' in rows[0]:
            combo = {}
            for r in rows:
                k = (f'{r.get("serviceType")} | status {r.get("status")} | '
                     f'freelancer {"yes" if r.get("primaryDeliveryResourceId") else "no"} | '
                     f'provider {"yes" if r.get("fulfillingProviderId") else "no"}')
                combo[k] = combo.get(k, 0) + 1
            for k, v in sorted(combo.items()):
                print(f'    {v:4d}  {k}')
        for r in rows[:5]:
            shown = {k[:-2] + 'Name': r.get(k[:-2] + 'Name') for k in links if r.get(k)}
            print(f'  - {r.get("name")} | {r.get("status")} | {json.dumps(shown)}')


MIGRATED = 'Migrated from Service Package '


def migrate_interviews(api):
    """Copy each old Interview Support Service Package into one Interview Session.
    Nothing is changed or deleted on the old package. Safe to run again."""
    print('\n== Move Interview Support packages into Interview Sessions ==')
    select = ('id,name,contactId,contactName,primaryDeliveryResourceId,status,paymentStatus,'
              'packagePrice,packagePriceCurrency,amountPaid,amountPaidCurrency,sessionsTotal,'
              'sessionsRemaining,startDate,createdAt,assignedUserId')
    packages, offset = [], 0
    while True:
        page = api.call('GET', 'CServicePackage', params={
            'select': select, 'maxSize': 200, 'offset': offset, 'orderBy': 'createdAt',
            'order': 'asc', 'where[0][type]': 'equals', 'where[0][attribute]': 'serviceType',
            'where[0][value]': 'Interview Support'})
        rows = page.get('list', [])
        packages += rows
        offset += len(rows)
        if not rows or offset >= page.get('total', 0):
            break
    done, offset = set(), 0
    while True:
        page = api.call('GET', 'CInterviewSession', params={
            'select': 'id,description', 'maxSize': 200, 'offset': offset})
        rows = page.get('list', [])
        for r in rows:
            d = r.get('description') or ''
            if d.startswith(MIGRATED):
                done.add(d[len(MIGRATED):].split()[0].rstrip('.'))
        offset += len(rows)
        if not rows or offset >= page.get('total', 0):
            break
    made = skipped = no_contact = no_freelancer = 0
    status_map = {'Completed': 'Held', 'Active': 'Planned', 'Expired': 'Cancelled'}
    for p in packages:
        if p['id'] in done:
            skipped += 1
            continue
        if not p.get('contactId'):
            no_contact += 1
            print(f'  skipped (no customer): {p.get("name")}')
            continue
        day = (p.get('startDate') or (p.get('createdAt') or '')[:10] or '2026-01-01')
        start = f'{day} 09:00:00'
        end = f'{day} 09:30:00'
        notes = (f'{MIGRATED}{p["id"]}. Sessions in the old package: {p.get("sessionsTotal")}, '
                 f'remaining: {p.get("sessionsRemaining")}. Old payment status: '
                 f'{p.get("paymentStatus")}. Amount paid so far: {p.get("amountPaid")} '
                 f'{p.get("amountPaidCurrency") or ""}.')
        body = {
            'name': f'Interview - {p.get("contactName")}',
            'interviewType': 'Interview', 'status': status_map.get(p.get('status'), 'Planned'),
            'dateStart': start, 'dateEnd': end, 'contactId': p['contactId'],
            'freelancerId': p.get('primaryDeliveryResourceId'),
            'paymentStatus': 'Paid' if p.get('paymentStatus') == 'Paid' else 'Pending',
            'assignedUserId': p.get('assignedUserId'), 'description': notes}
        if p.get('packagePrice') is not None:
            body['customerFee'] = p['packagePrice']
            body['customerFeeCurrency'] = p.get('packagePriceCurrency') or 'INR'
        if not body['freelancerId']:
            no_freelancer += 1
        api.create('CInterviewSession', body)
        made += 1
    print(f'{len(packages)} Interview Support package(s): {made} to create, {skipped} already moved, '
          f'{no_contact} skipped without a customer; {no_freelancer} of the new ones have no Freelancer')


def migrate_technologies(api):
    """Move the old fixed Technologies lists into the shared Technology list.
    Adds every old option as a Technology (if missing), then links each Freelancer
    and Project to the matching Technology. The old values stay in place. Safe to run again."""
    print('\n== Move technologies to the shared list ==')
    existing = {t['name'].strip().lower(): t['id']
                for t in api.call('GET', 'CTechnology', params={'maxSize': 200, 'select': 'id,name'}).get('list', [])}

    def tech_id(name):
        key = name.strip().lower()
        if key not in existing:
            existing[key] = api.create('CTechnology', {'name': name.strip()})['id']
        return existing[key]

    for name in OLD_TECHNOLOGIES:
        tech_id(name)

    def pages(entity, select):
        offset = 0
        while True:
            page = api.call('GET', entity, params={'select': select, 'maxSize': 100, 'offset': offset})
            rows = page.get('list', [])
            yield from rows
            offset += len(rows)
            if not rows or offset >= page.get('total', 0):
                break

    done = skipped = 0
    for r in pages('CDeliveryResource', 'id,name,technologies,techListIds'):
        old = r.get('technologies') or []
        if not old or r.get('techListIds'):
            skipped += 1
            continue
        api.update('CDeliveryResource', r['id'], {'techListIds': [tech_id(n) for n in old]})
        done += 1
    for r in pages('CProject', 'id,name,technology,technologyRefId'):
        old = r.get('technology')
        if not old or r.get('technologyRefId'):
            skipped += 1
            continue
        api.update('CProject', r['id'], {'technologyRefId': tech_id(old)})
        done += 1
    print(f'Linked {done} record(s), left {skipped} as they were.')


def refresh_customers(api):
    """Set the customer status on every Contact and Account from their Projects, Interviews
    and BGC Checks. The CRM keeps it up to date afterwards. Safe to run again."""
    print('\n== Set customer status ==')

    def all_rows(entity, select, extra=None):
        rows, offset = [], 0
        while True:
            params = {'select': select, 'maxSize': 200, 'offset': offset}
            params.update(extra or {})
            page = api.call('GET', entity, params=params)
            got = page.get('list', [])
            rows += got
            offset += len(got)
            if not got or offset >= page.get('total', 0):
                return rows

    counts, project_accounts = {}, set()
    for r in all_rows('CProject', 'id,consultantId,accountId'):
        if r.get('consultantId'):
            counts[r['consultantId']] = counts.get(r['consultantId'], 0) + 1
        if r.get('accountId'):
            project_accounts.add(r['accountId'])
    for r in all_rows('CInterviewSession', 'id,contactId,status'):
        if r.get('contactId') and r.get('status') != 'Cancelled':
            counts[r['contactId']] = counts.get(r['contactId'], 0) + 1
    for r in all_rows('CBgcCheck', 'id,contactId'):
        if r.get('contactId'):
            counts[r['contactId']] = counts.get(r['contactId'], 0) + 1

    customer_accounts, changed = set(project_accounts), 0
    for c in all_rows('Contact', 'id,customerStatus,accountId'):
        n = counts.get(c['id'], 0)
        status = 'Prospect' if n == 0 else 'Customer' if n == 1 else 'Repeat customer'
        if n and c.get('accountId'):
            customer_accounts.add(c['accountId'])
        if c.get('customerStatus') != status:
            api.update('Contact', c['id'], {'customerStatus': status})
            changed += 1
    for a in all_rows('Account', 'id,customerStatus'):
        status = 'Customer' if a['id'] in customer_accounts else 'Prospect'
        if a.get('customerStatus') != status:
            api.update('Account', a['id'], {'customerStatus': status})
            changed += 1
    print(f'Updated {changed} record(s). Customers: {sum(1 for v in counts.values() if v)} contact(s).')


def refresh_margins(api):
    """Re-save every Interview, BGC Check and Project with no change, so the CRM works out
    the margin for records made before margin existed. A record that cannot be saved is
    listed and skipped. Safe to run again."""
    print('\n== Calculate margins ==')
    done = failed = 0
    for entity in ('CInterviewSession', 'CBgcCheck', 'CProject'):
        offset = 0
        while True:
            page = api.call('GET', entity, params={'select': 'id,name', 'maxSize': 100,
                                                   'offset': offset})
            rows = page.get('list', [])
            for r in rows:
                try:
                    api.update(entity, r['id'], {'name': r['name']})
                    done += 1
                except SystemExit as e:
                    failed += 1
                    print(f'  skipped {entity} {r.get("name")}: {e}')
            offset += len(rows)
            if not rows or offset >= page.get('total', 0):
                break
    print(f'Re-saved {done} record(s), skipped {failed}.')


def link_timesheets(api):
    """Fill Timesheet.project from its Payment Block, so a Project lists its timesheets."""
    print('\n== Link timesheets to projects ==')
    blocks = {}
    offset = 0
    while True:
        page = api.call('GET', 'CPaymentBlock', params={
            'select': 'id,projectId', 'maxSize': 200, 'offset': offset})
        rows = page.get('list', [])
        blocks.update({r['id']: r.get('projectId') for r in rows})
        offset += len(rows)
        if not rows or offset >= page.get('total', 0):
            break
    changed = skipped = offset = 0
    while True:
        page = api.call('GET', 'CTimesheet', params={
            'select': 'id,paymentBlockId,projectId', 'maxSize': 200, 'offset': offset,
            'orderBy': 'createdAt', 'order': 'asc'})
        rows = page.get('list', [])
        for r in rows:
            project = blocks.get(r.get('paymentBlockId'))
            if project and r.get('projectId') != project:
                api.update('CTimesheet', r['id'], {'projectId': project})
                changed += 1
            else:
                skipped += 1
        offset += len(rows)
        if not rows or offset >= page.get('total', 0):
            break
    print(f'CTimesheet: {changed} to link, {skipped} already linked or without a project')


def filter_exists(api, entity, name, cache):
    key = (entity, name)
    if key not in cache:
        req = urllib.request.Request(
            api.base + entity + '?' + urllib.parse.urlencode(
                {'maxSize': 1, 'primaryFilter': name}), headers=api.headers)
        try:
            urllib.request.urlopen(req, timeout=60).read()
            cache[key] = True
        except urllib.error.HTTPError as e:
            reason = e.headers.get('X-Status-Reason', '')
            cache[key] = not (e.code == 400 and 'primary filter' in reason.lower())
    return cache[key]


def clean_layout(api, layout, options, cache, label):
    """Returns (new layout, new options, number removed). Handles tabs and flat lists."""
    removed = 0
    options = dict(options or {})

    def keep(item):
        nonlocal removed
        opts = options.get(item.get('id')) or {}
        entity, flt = opts.get('entityType'), opts.get('primaryFilter')
        if item.get('name') == 'Records' and entity and flt and \
                not filter_exists(api, entity, flt, cache):
            print(f'  {label}: remove "{opts.get("title") or item.get("id")}" '
                  f'({entity}, filter {flt} is gone)')
            options.pop(item.get('id'), None)
            removed += 1
            return False
        return True

    out = []
    for tab in layout or []:
        if isinstance(tab, dict) and 'layout' in tab:
            out.append(dict(tab, layout=[i for i in tab['layout'] if keep(i)]))
        elif keep(tab):
            out.append(tab)
    return out, options, removed


def fix_dashboards(api):
    print('\n== Remove dashboard widgets with a missing filter ==')
    cache = {}
    users = api.call('GET', 'User', params={'maxSize': 200, 'select': 'id,userName'}).get('list', [])
    for u in users:
        pref = api.call('GET', f'Preferences/{u["id"]}')
        layout, options, n = clean_layout(
            api, pref.get('dashboardLayout'), pref.get('dashletsOptions'), cache, u['userName'])
        if n:
            api.call('PUT', f'Preferences/{u["id"]}',
                     {'dashboardLayout': layout, 'dashletsOptions': options}, write=True)
    st = api.call('GET', 'Settings')
    layout, options, n = clean_layout(
        api, st.get('dashboardLayout'), st.get('dashletsOptions'), cache, 'default dashboard')
    if n:
        api.call('PUT', 'Settings', {'dashboardLayout': layout, 'dashletsOptions': options},
                 write=True)
    print(f'Checked {len(users)} user(s) and the default dashboard.')


def probe_project(api):
    print('\n== Open a Project: which request answers Not found ==')
    rows = api.call('GET', 'CProject', params={'maxSize': 3, 'select': 'id,name'}).get('list', [])
    print(f'{len(rows)} project(s) found')
    for r in rows:
        print(f'Project {r["name"]}')
        paths = [f'CProject/{r["id"]}', f'CProject/{r["id"]}/timesheets',
                 f'CProject/{r["id"]}/paymentBlocks', f'CProject/{r["id"]}/payouts',
                 f'Activities/CProject/{r["id"]}/activities',
                 f'Activities/CProject/{r["id"]}/history',
                 f'CProject/{r["id"]}/tasks', f'Stream/CProject/{r["id"]}']
        for path in paths:
            req = urllib.request.Request(api.base + path + '?maxSize=1', headers=api.headers)
            try:
                urllib.request.urlopen(req, timeout=60).read()
                print(f'  OK   {path}')
            except urllib.error.HTTPError as e:
                print(f'  {e.code}  {path}  {e.headers.get("X-Status-Reason", "")}')


def remove_demo(api):
    print('\n== Remove demo data ==')
    order = ['CPayout', 'CTimesheet', 'CInterviewSession', 'CPaymentBlock', 'CProject',
             'CDeliveryResource', 'CProvider', 'CReferrer', 'Contact', 'Lead', 'Account']
    for entity in order:
        rows = api.find(entity, [('description', NOTE[:20], 'startsWith')])
        for r in rows:
            api.call('DELETE', f'{entity}/{r["id"]}', write=True)
        print(f'{entity}: {len(rows)} demo record(s) removed')


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    p.add_argument('--url', default=os.environ.get('ESPO_URL'))
    p.add_argument('--user', default=os.environ.get('ESPO_USER'))
    p.add_argument('--password', default=os.environ.get('ESPO_PASSWORD'))
    p.add_argument('--api-key', default=os.environ.get('ESPO_API_KEY'))
    p.add_argument('--demo', action='store_true')
    p.add_argument('--remove-demo', action='store_true')
    p.add_argument('--diagnose-phones', action='store_true')
    p.add_argument('--link-timesheets', action='store_true')
    p.add_argument('--fix-dashboards', action='store_true')
    p.add_argument('--probe-project', action='store_true')
    p.add_argument('--show-record', help='read only, Entity/id')
    p.add_argument('--inspect', help='read only, comma separated entities, like CSessionLog,CInterviewSession')
    p.add_argument('--migrate-interviews', action='store_true')
    p.add_argument('--migrate-technologies', action='store_true')
    p.add_argument('--refresh-customers', action='store_true')
    p.add_argument('--refresh-margins', action='store_true')
    p.add_argument('--dry-run', action='store_true')
    a = p.parse_args()
    if not (a.demo or a.remove_demo or a.diagnose_phones or a.link_timesheets
            or a.fix_dashboards or a.probe_project or a.show_record or a.inspect or a.migrate_interviews
            or a.refresh_customers or a.refresh_margins or a.migrate_technologies):
        p.error('choose --fix-dashboards, --demo, --remove-demo, --diagnose-phones or --link-timesheets')
    if not a.url or not (a.api_key or (a.user and a.password)):
        p.error('set ESPO_URL and ESPO_USER/ESPO_PASSWORD (or ESPO_API_KEY)')
    api = Api(a.url, a.user, a.password, a.api_key, a.dry_run)
    api.call('GET', 'App/user')
    if a.diagnose_phones:
        diagnose_phones(api)
    if a.show_record:
        show_record(api, a.show_record)
    if a.inspect:
        inspect(api, a.inspect)
    if a.migrate_interviews:
        migrate_interviews(api)
    if a.migrate_technologies:
        migrate_technologies(api)
    if a.refresh_customers:
        refresh_customers(api)
    if a.refresh_margins:
        refresh_margins(api)
    if a.probe_project:
        probe_project(api)
    if a.fix_dashboards:
        fix_dashboards(api)
    if a.link_timesheets:
        link_timesheets(api)
    if a.demo:
        demo_data(api)
    if a.remove_demo:
        remove_demo(api)
    print('\nDone.' + (' (dry run, nothing was changed)' if a.dry_run else ''))


if __name__ == '__main__':
    main()
