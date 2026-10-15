#!/usr/bin/env python3
"""Two one-off jobs for the live CRM, both safe to run again:

  --whatsapp      Copy Phone into WhatsApp for Contact, Lead, Freelancer, Provider and
                  Referrer. Only records where WhatsApp is empty and Phone is filled.
  --demo          Create one complete demo story (Job Support, Interview Support, BGC,
                  payments, payouts). Every record is named or described "DEMO ...".
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
                'select': f'id,name,{phone},{WA}', 'maxSize': 200, 'offset': offset,
                'orderBy': 'createdAt', 'order': 'asc'})
            rows = page.get('list', [])
            if WA not in (rows[0] if rows else {WA: ''}):
                sys.exit(f'{entity} has no WhatsApp field yet. Deploy the new code and rebuild '
                         'EspoCRM first.')
            for r in rows:
                if r.get(phone) and not r.get(WA):
                    api.update(entity, r['id'], {WA: r[phone]})
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
    p.add_argument('--dry-run', action='store_true')
    a = p.parse_args()
    if not (a.whatsapp or a.demo or a.remove_demo):
        p.error('choose --whatsapp, --demo or --remove-demo')
    if not a.url or not (a.api_key or (a.user and a.password)):
        p.error('set ESPO_URL and ESPO_USER/ESPO_PASSWORD (or ESPO_API_KEY)')
    api = Api(a.url, a.user, a.password, a.api_key, a.dry_run)
    api.call('GET', 'App/user')
    if a.whatsapp:
        copy_whatsapp(api)
    if a.demo:
        demo_data(api)
    if a.remove_demo:
        remove_demo(api)
    print('\nDone.' + (' (dry run, nothing was changed)' if a.dry_run else ''))


if __name__ == '__main__':
    main()
