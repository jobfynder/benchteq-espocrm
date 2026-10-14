#!/usr/bin/env python3
"""End-to-end test of the Benchteq v2 flows through the REST API, one user per role.

It creates fake records, so run it on STAGING only. First run
scripts/setup-roles-dashboards.py and create one user per role.

  export ESPO_URL=https://staging.example.com
  export ESPO_MANAGER=meera:password      ESPO_COORDINATOR=priya:password
  export ESPO_INTERVIEW=amit:password     ESPO_FINANCE=rahul:password
  python3 scripts/tests/v2_api_flow.py

Exit code is 0 when every check passes.
"""
import base64
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

URL = os.environ.get('ESPO_URL', 'http://localhost:8080').rstrip('/') + '/api/v1/'
FAILED = []
RID = str(int(time.time()))[-5:]  # keeps names unique so the duplicate check stays quiet


class Forbidden(Exception):
    pass


class User:
    def __init__(self, label, env, default):
        name, _, password = os.environ.get(env, default).partition(':')
        self.label = label
        self.auth = 'Basic ' + base64.b64encode(f'{name}:{password}'.encode()).decode()

    def call(self, method, path, body=None, params=None):
        if params:
            path += '?' + urllib.parse.urlencode(params, doseq=True)
        req = urllib.request.Request(
            URL + path, method=method,
            data=json.dumps(body).encode() if body is not None else None,
            headers={'Authorization': self.auth, 'Content-Type': 'application/json'})
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                text = r.read().decode()
                return json.loads(text) if text else {}
        except urllib.error.HTTPError as e:
            reason = e.headers.get('X-Status-Reason', '')
            if e.code in (403, 404):
                raise Forbidden(f'{e.code} {reason}')
            raise RuntimeError(f'{method} {path} -> {e.code} {reason}')

    def create(self, entity, body):
        return self.call('POST', entity, body)

    def update(self, entity, id_, body):
        return self.call('PUT', f'{entity}/{id_}', body)

    def get(self, entity, id_):
        return self.call('GET', f'{entity}/{id_}')

    def delete(self, entity, id_):
        return self.call('DELETE', f'{entity}/{id_}')

    def listing(self, entity, **params):
        params.setdefault('maxSize', 100)
        return self.call('GET', entity, params=params).get('list', [])


def check(label, actual, expected):
    if isinstance(expected, float) or isinstance(actual, float):
        ok = actual is not None and abs(float(actual) - float(expected)) < 0.001
    else:
        ok = actual == expected
    print(('PASS  ' if ok else 'FAIL  ') + label + ('' if ok else f'   got {actual!r}, expected {expected!r}'))
    if not ok:
        FAILED.append(label)


def denied(label, fn):
    try:
        fn()
    except Forbidden:
        check(label, 'denied', 'denied')
    except RuntimeError as e:
        check(label, 'denied', 'denied') if ' 403' in str(e) or ' 400' in str(e) else check(label, str(e), 'denied')
    else:
        check(label, 'allowed', 'denied')


def rejected(label, fn):
    try:
        fn()
    except (RuntimeError, Forbidden):
        check(label, 'rejected', 'rejected')
    else:
        check(label, 'saved', 'rejected')


def ts(days, hour, minutes=0):
    d = datetime.now(timezone.utc).replace(hour=hour, minute=minutes, second=0, microsecond=0)
    return (d + timedelta(days=days)).strftime('%Y-%m-%d %H:%M:%S')


def main():
    mgr = User('manager', 'ESPO_MANAGER', 'meera:pw-meera-123')
    coord = User('coordinator', 'ESPO_COORDINATOR', 'priya:pw-priya-123')
    iview = User('interview manager', 'ESPO_INTERVIEW', 'amit:pw-amit-123')
    fin = User('finance', 'ESPO_FINANCE', 'rahul:pw-rahul-123')

    print('\n== Job Support (coordinator) ==')
    lead = coord.create('Lead', {'firstName': 'Ravi', 'lastName': f'Kumar{RID}', 'serviceType': 'Job Support',
                                 'phoneNumber': '+919999911111', 'status': 'New'})
    check('lead created with service type', lead['serviceType'], 'Job Support')
    coord.call('POST', 'Lead/action/convert', {
        'id': lead['id'], 'records': {'Contact': {'firstName': 'Ravi', 'lastName': f'Kumar{RID}'}}})
    contact_id = coord.get('Lead', lead['id']).get('createdContactId')
    check('lead converted to contact', bool(contact_id), True)
    check('lead status Converted', coord.get('Lead', lead['id'])['status'], 'Converted')

    f_pass = coord.create('CDeliveryResource', {'name': 'Trainer Passed', 'roleType': 'Trainer',
                                                 'technologies': ['Java'], 'screeningResult': 'Passed', 'rating': 5})
    f_fail = coord.create('CDeliveryResource', {'name': 'Trainer Pending', 'roleType': 'Trainer'})
    shortlist = [f['id'] for f in coord.listing('CDeliveryResource', primaryFilter='shortlist')]
    check('shortlist has passed freelancer', f_pass['id'] in shortlist, True)
    check('shortlist excludes pending freelancer', f_fail['id'] in shortlist, False)

    me = coord.call('GET', 'App/user')['user']['id']
    project = coord.create('CProject', {'assignedUserId': me, 'technology': 'Java', 'consultantId': contact_id,
                                        'freelancerId': f_pass['id'], 'freelancerPayType': 'Hourly',
                                        'freelancerRate': 500, 'customerRate': 900})
    check('project name', project['name'], f'Java - Ravi Kumar{RID}')
    block = coord.create('CPaymentBlock', {'projectId': project['id'], 'totalHrs': 3, 'amount': 2700,
                                           'paymentStatus': 'Paid'})
    check('block coordinator defaults from project', bool(block.get('assignedUserId')), True)
    check('block paid date auto', bool(block.get('paidDate')), True)

    t = [coord.create('CTimesheet', {'paymentBlockId': block['id'], 'dateStart': ts(1 + i, 15, 30),
                                     'dateEnd': ts(1 + i, 16, 30)}) for i in range(3)]
    check('timesheet starts Planned', t[0]['status'], 'Planned')
    check('timesheet hours', t[0]['hours'], 1.0)
    check('timesheet freelancer from project', t[0]['freelancerId'], f_pass['id'])

    cal = coord.call('GET', 'Activities', params={
        'from': ts(0, 0), 'to': ts(5, 0), 'scopeList': 'CTimesheet'})
    on_calendar = {x['id'] for x in cal}
    check('timesheets appear on coordinator calendar', {x['id'] for x in t} <= on_calendar, True)

    planned = {x['id'] for x in coord.listing('CTimesheet', primaryFilter='planned')}
    check('dashboard "planned timesheets"', {x['id'] for x in t} <= planned, True)

    for x in t[:2]:
        coord.update('CTimesheet', x['id'], {'status': 'Held'})
    b = coord.get('CPaymentBlock', block['id'])
    check('connected hrs after 2 held', b['connectedHrs'], 2.0)
    check('remaining hrs after 2 held', b['remainingHrs'], 1.0)
    low = {x['id'] for x in coord.listing('CPaymentBlock', primaryFilter='lowHours')}
    check('dashboard "5 or fewer hours left" lists block', block['id'] in low, True)
    coord.update('CTimesheet', t[2]['id'], {'status': 'No-Show'})
    b = coord.get('CPaymentBlock', block['id'])
    check('no-show uses the last hour', b['connectedHrs'], 3.0)
    check('block completes itself at zero hours', b['status'], 'Completed')
    check('completed block leaves the low-hours list',
          block['id'] in {x['id'] for x in coord.listing('CPaymentBlock', primaryFilter='lowHours')}, False)
    coord.update('CTimesheet', t[2]['id'], {'status': 'Cancelled'})
    b = coord.get('CPaymentBlock', block['id'])
    check('cancelled gives the hour back', b['connectedHrs'], 2.0)
    check('block reopens when hours are free', b['status'], 'Active')

    print('\n== Interview Support (interview manager) ==')
    lead2 = iview.create('Lead', {'firstName': 'Sita', 'lastName': f'Rao{RID}', 'serviceType': 'Interview Support'})
    iview.call('POST', 'Lead/action/convert', {
        'id': lead2['id'], 'records': {'Contact': {'firstName': 'Sita', 'lastName': f'Rao{RID}'}}})
    sita = iview.get('Lead', lead2['id']).get('createdContactId')
    iv_me = iview.call('GET', 'App/user')['user']['id']
    s = iview.create('CInterviewSession', {'assignedUserId': iv_me, 'contactId': sita, 'freelancerId': f_pass['id'],
                                           'dateStart': ts(2, 10), 'dateEnd': ts(2, 10, 30),
                                           'customerFee': 3000, 'supporterFee': 1500})
    check('interview defaults to Interview type', s['interviewType'], 'Interview')
    check('interview name', s['name'].startswith(f'Interview - Sita Rao{RID} - '), True)
    rejected('Held is blocked until the customer has paid',
             lambda: iview.update('CInterviewSession', s['id'], {'status': 'Held'}))
    iview.update('CInterviewSession', s['id'], {'paymentStatus': 'Paid'})
    iview.update('CInterviewSession', s['id'], {'status': 'Held', 'feedback': 'Strong on Java basics'})
    s = iview.get('CInterviewSession', s['id'])
    check('interview held with feedback', (s['status'], s['feedback']), ('Held', 'Strong on Java basics'))
    for minutes in (30, 45, 60, 90, 180):
        a = iview.create('CInterviewSession', {
            'assignedUserId': iv_me, 'contactId': sita, 'interviewType': 'Assessment' if minutes >= 90 else 'Interview',
            'dateStart': ts(3, 9), 'dateEnd': (datetime.strptime(ts(3, 9), '%Y-%m-%d %H:%M:%S')
                                              + timedelta(minutes=minutes)).strftime('%Y-%m-%d %H:%M:%S')})
        a = iview.get('CInterviewSession', a['id'])
        check(f'{minutes} minute slot saves', a['duration'], minutes * 60)
        iview.delete('CInterviewSession', a['id'])

    print('\n== BGC with referral (coordinator) ==')
    ref = coord.create('CReferrer', {'name': 'Anil Referrer', 'referralFee': 2000})
    prov = mgr.create('CProvider', {'name': 'BGC Provider', 'servicesSupplied': ['BGC Verification']})
    bgc = coord.create('Lead', {'firstName': 'Dev', 'lastName': f'Patel{RID}', 'serviceType': 'BGC',
                                'referrerId': ref['id'], 'bgcType': 'US', 'bgcProviderId': prov['id']})
    check('BGC US fee', bgc['bgcFee'], 55000.0)
    for kind, fee in (('India', 18000.0), ('Both', 55000.0)):
        bgc = coord.update('Lead', bgc['id'], {'bgcType': kind})
        check(f'BGC {kind} fee', bgc['bgcFee'], fee)
    coord.update('Lead', bgc['id'], {'bgcStatus': 'In Verification', 'bgcAmountReceived': 55000})
    check('dashboard "BGC in verification"',
          bgc['id'] in {x['id'] for x in coord.listing('Lead', primaryFilter='bgcInVerification')}, True)
    coord.update('Lead', bgc['id'], {'bgcStatus': 'Cleared', 'bgcProviderCost': 20000})
    coord.call('POST', 'Lead/action/convert', {
        'id': bgc['id'], 'records': {'Contact': {'firstName': 'Dev', 'lastName': f'Patel{RID}'}}})
    check('referral fee shows as due',
          bgc['id'] in {x['id'] for x in coord.listing('Lead', primaryFilter='referralDue')}, True)

    print('\n== Paying out (finance) ==')
    unpaid = {x['id'] for x in fin.listing('CTimesheet', primaryFilter='unpaid')}
    check('finance sees the 2 held timesheets to pay', {t[0]['id'], t[1]['id']} <= unpaid, True)
    iv_unpaid = {x['id'] for x in fin.listing('CInterviewSession', primaryFilter='unpaid')}
    check('finance sees the held interview to pay', s['id'] in iv_unpaid, True)

    pay = fin.create('CPayout', {'payeeType': 'Delivery Resource', 'deliveryResourceId': f_pass['id'],
                                 'projectId': project['id'], 'payoutType': 'Hourly', 'amount': 1000})
    check('payout starts Due with a name', (pay['status'], bool(pay['name'])), ('Due', True))
    for x in (t[0], t[1]):
        fin.update('CTimesheet', x['id'], {'payoutId': pay['id']})
    still = {x['id'] for x in fin.listing('CTimesheet', primaryFilter='unpaid')}
    check('paid timesheets leave the to-pay list', t[0]['id'] in still or t[1]['id'] in still, False)
    fin.update('CPayout', pay['id'], {'status': 'Paid'})
    p = fin.get('CPayout', pay['id'])
    check('payout paid date auto', bool(p['payoutDate']), True)

    iv_pay = fin.create('CPayout', {'payeeType': 'Delivery Resource', 'deliveryResourceId': f_pass['id'],
                                    'payoutType': 'Per Interview', 'amount': 1500})
    fin.update('CInterviewSession', s['id'], {'payoutId': iv_pay['id']})
    prov_pay = fin.create('CPayout', {'payeeType': 'Provider', 'providerId': prov['id'], 'leadId': bgc['id'],
                                      'payoutType': 'BGC Verification Fee', 'amount': 20000})
    ref_pay = fin.create('CPayout', {'payeeType': 'Referrer', 'referrerId': ref['id'], 'leadId': bgc['id'],
                                     'payoutType': 'Referral Fee', 'amount': 2000})
    check('referral not paid yet', fin.get('Lead', bgc['id'])['referralPaid'], False)
    fin.update('CPayout', ref_pay['id'], {'status': 'Paid'})
    fin.update('CPayout', prov_pay['id'], {'status': 'Paid'})
    check('lead shows referral fee paid by itself', fin.get('Lead', bgc['id'])['referralPaid'], True)
    check('referral leaves the "to pay" list',
          bgc['id'] in {x['id'] for x in fin.listing('Lead', primaryFilter='referralDue')}, False)
    check('freelancer page lists its payouts',
          len(fin.call('GET', f'CDeliveryResource/{f_pass["id"]}/payouts').get('list', [])) >= 2, True)
    check('provider page lists its payouts',
          len(fin.call('GET', f'CProvider/{prov["id"]}/payouts').get('list', [])) >= 1, True)
    check('referrer page lists its payouts',
          len(fin.call('GET', f'CReferrer/{ref["id"]}/payouts').get('list', [])) >= 1, True)
    check('referrer page lists its leads',
          len(fin.call('GET', f'CReferrer/{ref["id"]}/leads').get('list', [])) >= 1, True)

    print('\n== Who can do what ==')
    check('coordinator can read payouts', len(coord.listing('CPayout')) >= 3, True)
    denied('coordinator cannot create a payout',
           lambda: coord.create('CPayout', {'payeeType': 'Provider', 'amount': 1}))
    denied('coordinator cannot see old Deals', lambda: coord.listing('Opportunity'))
    denied('coordinator cannot see old Service Packages', lambda: coord.listing('CServicePackage'))
    check('coordinator can read providers', len(coord.listing('CProvider')) >= 1, True)
    denied('coordinator cannot create a provider', lambda: coord.create('CProvider', {'name': 'x'}))
    denied('interview manager cannot read projects', lambda: iview.listing('CProject'))
    denied('interview manager cannot read payouts', lambda: iview.listing('CPayout'))
    check('interview manager can read freelancers', len(iview.listing('CDeliveryResource')) >= 1, True)
    denied('finance cannot create a timesheet',
           lambda: fin.create('CTimesheet', {'paymentBlockId': block['id'], 'dateStart': ts(9, 9), 'dateEnd': ts(9, 10)}))
    denied('finance cannot create a project', lambda: fin.create('CProject', {'technology': 'Java', 'consultantId': contact_id}))
    check('manager can edit everything', mgr.update('CProject', project['id'], {'status': 'On Hold'})['status'], 'On Hold')

    print('\n' + (f'{len(FAILED)} FAILED: ' + '; '.join(FAILED) if FAILED else 'ALL PASSED'))
    sys.exit(1 if FAILED else 0)


if __name__ == '__main__':
    main()
