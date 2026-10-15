#!/usr/bin/env python3
"""Two one-off jobs for the live CRM, both safe to run again:

  --whatsapp      Copy Phone into WhatsApp for Contact, Lead, Freelancer, Provider and
                  Referrer. Only records where WhatsApp is empty and Phone is filled.
  --demo          Create one complete demo story (Job Support, Interview Support, BGC,
                  payments, payouts). Every record is named or described "DEMO ...".
  --link-timesheets  Fill Timesheet.project from the Payment Block (so Projects list them).
  --fix-dashboards  Remove dashboard widgets (every user, plus the default) whose saved filter
                  no longer exists, which causes "No primary filter ... for ...".
  --remove-demo   Delete every record whose description starts with "DEMO".

Run the WhatsApp job after the code with the new field is deployed and EspoCRM is rebuilt.
Start with --dry-run: it reads the CRM and prints what it would do, and changes nothing.

  export ESPO_URL=https://crm.example.com ESPO_USER=admin ESPO_PASSWORD=...
  python3 scripts/demo-data-and-whatsapp.py --whatsapp --demo --dry-run

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

WA = 'whatsAppNumber'
# entity -> field that holds its phone number
PHONE_FIELD = {'Contact': 'phoneNumber', 'Lead': 'phoneNumber', 'CDeliveryResource': 'phone',
               'CProvider': 'phone', 'CReferrer': 'phone'}
# entities where Phone and WhatsApp each have a country code picker
COUNTRY = ('phoneCountry', 'whatsAppCountry')
HAS_COUNTRY = ('CDeliveryResource', 'CProvider', 'CReferrer')
TAG = 'DEMO'
NOTE = 'DEMO data for team training. Safe to delete.'
NEW = '(new)'


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


# ------------------------------------------------------------------ WhatsApp

def copy_whatsapp(api):
    print('\n== Copy Phone to WhatsApp ==')
    for entity, phone in PHONE_FIELD.items():
        changed = skipped = 0
        offset = 0
        while True:
            page = api.call('GET', entity, params={
                'select': f'id,name,{phone},{WA}' + (',' + ','.join(COUNTRY) if entity in HAS_COUNTRY else ''),
                'maxSize': 200, 'offset': offset,
                'orderBy': 'createdAt', 'order': 'asc'})
            rows = page.get('list', [])
            if WA not in (rows[0] if rows else {WA: ''}):
                sys.exit(f'{entity} has no WhatsApp field yet. Deploy the new code and rebuild '
                         'EspoCRM first.')
            for r in rows:
                if r.get(phone) and not r.get(WA):
                    body = {WA: r[phone]}
                    if entity in HAS_COUNTRY and r.get(COUNTRY[0]):
                        body[COUNTRY[1]] = r[COUNTRY[0]]
                    api.update(entity, r['id'], body)
                    changed += 1
                else:
                    skipped += 1
            offset += len(rows)
            if not rows or offset >= page.get('total', 0):
                break
        print(f'{entity}: {changed} to copy, {skipped} left as they are '
              '(no phone, or WhatsApp already filled)')


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
        'status': 'Active', 'phone': '+919800000001', WA: '+919800000001'})
    provider = ensure(api, 'CProvider', [eq('name', 'DEMO BGC Provider')], {
        'name': 'DEMO BGC Provider', 'providerType': 'Company', 'servicesSupplied': ['BGC Verification'],
        'phone': '+919800000002', WA: '+919800000002', 'email': 'demo-provider@example.com'})
    trainer = ensure(api, 'CDeliveryResource', [eq('name', 'DEMO Trainer - Meena')], {
        'name': 'DEMO Trainer - Meena', 'roleType': 'Trainer', 'technologies': ['Java'],
        'screeningResult': 'Passed', 'rating': 5, 'workStatus': 'On Project',
        'phone': '+919800000003', WA: '+919800000003', 'email': 'demo-meena@example.com',
        'providerId': provider})
    supporter = ensure(api, 'CDeliveryResource', [eq('name', 'DEMO Supporter - Kiran')], {
        'name': 'DEMO Supporter - Kiran', 'roleType': 'Interview Supporter', 'technologies': ['Java'],
        'screeningResult': 'Passed', 'rating': 4, 'workStatus': 'Available',
        'phone': '+919800000004', WA: '+919800000004', 'email': 'demo-kiran@example.com'})

    # 1. Job Support: lead -> contact + account -> project -> payment block -> timesheets
    print('\n-- Job Support')
    lead = ensure(api, 'Lead', [eq('lastName', 'Kumar'), eq('firstName', 'DEMO Ravi')], {
        'firstName': 'DEMO Ravi', 'lastName': 'Kumar', 'serviceType': 'Job Support', 'status': 'New',
        'accountName': 'DEMO Acme Technologies', 'phoneNumber': '+919800000011', WA: '+919800000011',
        'emailAddress': 'demo-ravi@example.com', 'source': 'Web Site'})
    ravi, acme = convert(api, lead, {
        'Contact': {'firstName': 'DEMO Ravi', 'lastName': 'Kumar', 'phoneNumber': '+919800000011',
                    WA: '+919800000011', 'emailAddress': 'demo-ravi@example.com', 'description': NOTE},
        'Account': {'name': 'DEMO Acme Technologies', 'description': NOTE}})
    project = ensure(api, 'CProject', [eq('consultantId', ravi), eq('technology', 'Java')], {
        'assignedUserId': me, 'technology': 'Java', 'consultantId': ravi, 'accountId': acme,
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
        'status': 'New', 'phoneNumber': '+919800000012', WA: '+919800000012',
        'emailAddress': 'demo-sita@example.com'})
    sita, _ = convert(api, lead, {
        'Contact': {'firstName': 'DEMO Sita', 'lastName': 'Rao', 'phoneNumber': '+919800000012',
                    WA: '+919800000012', 'emailAddress': 'demo-sita@example.com',
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
        'phoneNumber': '+919800000013', WA: '+919800000013', 'emailAddress': 'demo-dev@example.com',
        'referrerId': referrer, 'bgcType': 'US', 'bgcProviderId': provider})
    api.update('Lead', lead, {'bgcStatus': 'In Verification', 'bgcAmountReceived': 55000})
    api.update('Lead', lead, {'bgcStatus': 'Cleared', 'bgcProviderCost': 20000})
    convert(api, lead, {
        'Contact': {'firstName': 'DEMO Dev', 'lastName': 'Patel', 'phoneNumber': '+919800000013',
                    WA: '+919800000013', 'emailAddress': 'demo-dev@example.com', 'description': NOTE}})

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
        field = PHONE_FIELD.get(entity, 'phone')
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


# ------------------------------------------------- native phone with WhatsApp type

NATIVE_ENTITIES = ('Contact', 'Lead', 'Account', 'CDeliveryResource', 'CProvider', 'CReferrer')
LEGACY_PHONE = ('CDeliveryResource', 'CProvider', 'CReferrer')   # old text Phone + country picker


def digits(v):
    return ''.join(ch for ch in (v or '') if ch.isdigit())


def with_code(number, country):
    n = (number or '').strip()
    if not n or n.startswith('+') or not (country or '').startswith('+'):
        return n
    return country + digits(n).lstrip('0')


def native_phones(api):
    """Move old Phone and WhatsApp text into EspoCRM's native phone field.
    A number that is both Phone and WhatsApp becomes one entry typed "Mobile and WhatsApp";
    a different WhatsApp number becomes an extra entry typed "WhatsApp". Old values are kept."""
    print('\n== Move Phone and WhatsApp into the native phone field ==')
    for entity in NATIVE_ENTITIES:
        legacy = entity in LEGACY_PHONE
        select = 'id,name,phoneNumber,phoneNumberData'
        if entity != 'Account':
            select += ',whatsAppNumber'
        if legacy:
            select += ',phone,phoneCountry,whatsAppCountry'
        changed = same = 0
        offset = 0
        shown = 0
        while True:
            page = api.call('GET', entity, params={'select': select, 'maxSize': 200, 'offset': offset,
                                                   'orderBy': 'createdAt', 'order': 'asc'})
            rows = page.get('list', [])
            for r in rows:
                entries = [dict(e) for e in (r.get('phoneNumberData') or [])]
                if not entries and r.get('phoneNumber'):
                    entries = [{'phoneNumber': r['phoneNumber'], 'type': 'Mobile', 'primary': True,
                                'optOut': False, 'invalid': False}]
                before = json.dumps(entries, sort_keys=True)

                def find(num):
                    d = digits(num)
                    return next((e for e in entries if d and digits(e['phoneNumber']) == d), None)

                def add(num, kind):
                    entries.append({'phoneNumber': num, 'type': kind, 'primary': not entries,
                                    'optOut': False, 'invalid': False})

                if legacy:
                    ph = with_code(r.get('phone'), r.get('phoneCountry'))
                    if ph and not find(ph):
                        add(ph, 'Mobile')
                wa = with_code(r.get('whatsAppNumber'), r.get('whatsAppCountry')) if entity != 'Account' else ''
                if wa:
                    hit = find(wa)
                    if hit is None:
                        add(wa, 'WhatsApp')
                    elif hit.get('type') == 'Mobile':
                        hit['type'] = 'Mobile and WhatsApp'
                if json.dumps(entries, sort_keys=True) != before:
                    primary = next((e for e in entries if e.get('primary')), entries[0])
                    if shown < 3:
                        print(f'  {entity} {r.get("name")}: ' + ', '.join(
                            f'{e["type"]} {mask(e["phoneNumber"])}' for e in entries))
                        shown += 1
                    api.update(entity, r['id'], {'phoneNumber': primary['phoneNumber'],
                                                 'phoneNumberData': entries})
                    changed += 1
                else:
                    same += 1
            offset += len(rows)
            if not rows or offset >= page.get('total', 0):
                break
        print(f'{entity}: {changed} to update, {same} already fine')


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
    p.add_argument('--whatsapp', action='store_true')
    p.add_argument('--demo', action='store_true')
    p.add_argument('--remove-demo', action='store_true')
    p.add_argument('--diagnose-phones', action='store_true')
    p.add_argument('--link-timesheets', action='store_true')
    p.add_argument('--fix-dashboards', action='store_true')
    p.add_argument('--probe-project', action='store_true')
    p.add_argument('--native-phones', action='store_true')
    p.add_argument('--dry-run', action='store_true')
    a = p.parse_args()
    if not (a.whatsapp or a.demo or a.remove_demo or a.diagnose_phones or a.link_timesheets
            or a.fix_dashboards or a.probe_project or a.native_phones):
        p.error('choose --fix-dashboards, --whatsapp, --demo, --remove-demo, --diagnose-phones or --link-timesheets')
    if not a.url or not (a.api_key or (a.user and a.password)):
        p.error('set ESPO_URL and ESPO_USER/ESPO_PASSWORD (or ESPO_API_KEY)')
    api = Api(a.url, a.user, a.password, a.api_key, a.dry_run)
    api.call('GET', 'App/user')
    if a.diagnose_phones:
        diagnose_phones(api)
    if a.native_phones:
        native_phones(api)
    if a.probe_project:
        probe_project(api)
    if a.fix_dashboards:
        fix_dashboards(api)
    if a.link_timesheets:
        link_timesheets(api)
    if a.whatsapp:
        copy_whatsapp(api)
    if a.demo:
        demo_data(api)
    if a.remove_demo:
        remove_demo(api)
    print('\nDone.' + (' (dry run, nothing was changed)' if a.dry_run else ''))


if __name__ == '__main__':
    main()
